from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, render

from apps.vpn.models import VpnRequest
from apps.vpn.models.request import RequestStatus
from apps.vpn.services.panos import config_as_text, generate_panos_config

# Statuses shown in the filter — the deployment-relevant slice of the workflow.
DEPLOYMENT_STATUSES = [
    RequestStatus.INFOSEC_APPROVED,
    RequestStatus.NETWORK_APPROVED,
    RequestStatus.SCHEDULED,
    RequestStatus.DEPLOY_READY,
    RequestStatus.DEPLOYED,
    RequestStatus.ACTIVE,
]


def _deployable_requests():
    return (
        VpnRequest.objects
        .filter(tunnel_interfaces__isnull=False)
        .distinct()
        .select_related("vendor", "our_endpoint_1_site", "our_endpoint_2_site")
    )


@login_required
def deployment_list_view(request):
    """
    Deployment queue: every request with allocated tunnel interfaces,
    as a summary table. Configs are generated on the per-request detail page.
    """
    status = request.GET.get("status", "")

    qs = (
        _deployable_requests()
        .annotate(num_tunnels=Count("tunnel_interfaces", distinct=True))
        .order_by("-created_at")
    )
    if status:
        qs = qs.filter(status=status)

    return render(request, "deployment/list.html", {
        "nav_active": "deployment",
        "deployments": qs,
        "status_choices": [(s.value, s.label) for s in DEPLOYMENT_STATUSES],
        "selected_status": status,
    })


@login_required
def deployment_detail_view(request, pk):
    """
    Deployment workbench for a single request: PAN-OS set commands
    regenerated live per site and tunnel.
    """
    vpn_request = get_object_or_404(_deployable_requests(), pk=pk)

    site_configs = []
    for cfg in generate_panos_config(vpn_request):
        if cfg["supported"]:
            cfg["shared_text"] = config_as_text({"sections": cfg["shared_sections"]})
            for block in cfg["tunnels"]:
                block["text"] = config_as_text(block)
        site_configs.append(cfg)

    from apps.vpn.services.config_render import resolve_template

    _, config_template_source = resolve_template(vpn_request)

    return render(request, "deployment/detail.html", {
        "nav_active": "deployment",
        "vpn_request": vpn_request,
        "site_configs": site_configs,
        "tunnel_count": vpn_request.tunnel_interfaces.count(),
        "config_template_source": config_template_source,
    })
