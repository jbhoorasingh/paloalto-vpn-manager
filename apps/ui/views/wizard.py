import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.core.models import Site
from apps.vpn.models import Application, VpnRequest


def _wizard_context(vpn_request=None):
    """Build common context for the wizard page."""
    sites = list(Site.objects.filter(is_active=True).values("id", "name", "code", "public_ip", "bgp_asn"))
    applications = list(Application.objects.values("id", "name"))

    props = {
        "sites": sites,
        "applications": applications,
    }
    if vpn_request:
        props["id"] = vpn_request.pk

    return {"wizard_props_json": json.dumps(props)}


@login_required
def wizard_create_view(request):
    context = _wizard_context()
    context["nav_active"] = "wizard-create"
    return render(request, "vpn/wizard.html", context)


@login_required
def wizard_edit_view(request, pk):
    vpn_request = get_object_or_404(VpnRequest, pk=pk, requester=request.user)
    context = _wizard_context(vpn_request)
    context["nav_active"] = "wizard-create"
    return render(request, "vpn/wizard.html", context)
