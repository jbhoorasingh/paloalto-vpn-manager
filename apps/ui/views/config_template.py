from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from apps.core.permissions import role_required
from apps.vpn.models import ConfigTemplate, VpnRequest
from apps.vpn.models.config_template import DEFAULT_CONFIG_TEMPLATE

_syntax_env = SandboxedEnvironment()

# Documented template variables, shown beside both editors. Keep in sync with
# apps/vpn/services/config_render.py build_template_context.
TEMPLATE_VARIABLES = [
    ("sections", "List of computed config sections; each has .title and .commands (list of set commands)"),
    ("shared_sections", "Site-wide sections only (crypto profiles, BGP setup, policy)"),
    ("tunnels", "Per-tunnel blocks: label, number, local_ip, remote_ip, subnet_cidr, peer_ip, sections"),
    ("site", "Endpoint firewall: name, code, public_ip, bgp_asn, device_group, template_name, management_type"),
    ("request", "Request fields: reference_number, title, vendor, directionality, routing_type, ike_*, ipsec_*, vendor_cidrs"),
    ("reference", "Lowercased reference number used in object names"),
    ("flows", "Traffic flows: source_cidr, destination_cidr, direction, protocol, destination_ports"),
    ("nat_mappings", "NAT mappings: site_code, direction, nat_address, real_address"),
    ("notes", "Generator notes/assumptions for this site"),
]


def _syntax_error(content):
    """Parse-check template content; returns an error string or None."""
    try:
        _syntax_env.from_string(content)
    except TemplateError as e:
        return f"Template syntax error: {e}"
    return None


def _template_history(template):
    ct = ContentType.objects.get_for_model(ConfigTemplate)
    return (
        LogEntry.objects.filter(content_type=ct, object_pk=str(template.pk))
        .select_related("actor")
        .order_by("-timestamp")[:10]
    )


@role_required("network")
def config_template_view(request):
    """Edit the global config-generation template (Jinja). All changes are logged."""
    template = ConfigTemplate.get_global()
    error = None
    saved = False

    if request.method == "POST":
        if "reset" in request.POST:
            template.content = DEFAULT_CONFIG_TEMPLATE
            template.updated_by = request.user
            template.save()
            return redirect("ui:config-template")
        content = request.POST.get("content", "")
        error = _syntax_error(content)
        if not error:
            template.content = content
            template.updated_by = request.user
            template.save()
            saved = True

    return render(request, "config/template_form.html", {
        "nav_active": "config-template",
        "template": template,
        "content": request.POST.get("content", template.content) if error else template.content,
        "error": error,
        "saved": saved,
        "is_default": template.is_default,
        "variables": TEMPLATE_VARIABLES,
        "history": _template_history(template),
    })


@role_required("network")
def request_config_template_view(request, pk):
    """Edit one request's config template override. Logged on the request's audit trail."""
    vpn_request = get_object_or_404(VpnRequest, pk=pk)
    global_template = ConfigTemplate.get_global()
    error = None

    if request.method == "POST":
        if "remove" in request.POST:
            vpn_request.config_template_override = ""
            vpn_request.save()
            return redirect("ui:request-detail", pk=pk)
        content = request.POST.get("content", "")
        error = _syntax_error(content)
        if not error:
            vpn_request.config_template_override = content
            vpn_request.save()
            return redirect("ui:request-detail", pk=pk)

    if request.method == "POST" and error:
        content = request.POST.get("content", "")
    else:
        content = vpn_request.config_template_override or global_template.content

    return render(request, "config/request_template_form.html", {
        "nav_active": "my-requests",
        "vpn_request": vpn_request,
        "content": content,
        "has_override": bool(vpn_request.config_template_override.strip()),
        "error": error,
        "variables": TEMPLATE_VARIABLES,
    })
