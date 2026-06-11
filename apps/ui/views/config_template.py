from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from jinja2 import TemplateError
from jinja2.sandbox import SandboxedEnvironment

from apps.core.permissions import role_required
from apps.vpn.models import ConfigTemplate, VpnRequest
from apps.vpn.models.config_template import DEFAULT_CONFIG_TEMPLATE, GLOBAL_TEMPLATE_NAME
from apps.vpn.services.config_segments import SEGMENTS, SHARED_VARIABLES

_syntax_env = SandboxedEnvironment()

# Variables for the DOCUMENT template (assembles rendered sections into the
# final text). Keep in sync with config_render.build_template_context.
DOCUMENT_VARIABLES = [
    ("sections", "List of rendered config sections; each has .title and .commands (list of set commands)"),
    ("shared_sections", "Site-wide sections only (crypto profiles, BGP setup, policy)"),
    ("tunnels", "Per-tunnel blocks: label, number, local_ip, remote_ip, subnet_cidr, peer_ip, sections"),
    ("site", "Endpoint firewall: name, code, public_ip, bgp_asn, device_group, template_name, management_type"),
    ("request", "Request fields: reference_number, title, vendor, directionality, routing_type, ike_*, ipsec_*, vendor_cidrs"),
    ("reference", "Lowercased reference number used in object names"),
    ("flows", "Traffic flows: source_cidr, destination_cidr, direction, protocol, destination_ports"),
    ("nat_mappings", "NAT mappings: site_code, direction, nat_address, real_address"),
    ("notes", "Generator notes/assumptions for this site"),
]


def _template_specs():
    """Ordered registry of every editable template: document layout + segments."""
    specs = {
        GLOBAL_TEMPLATE_NAME: {
            "title": "Document Layout",
            "description": (
                "Assembles the rendered segments into the final config text. "
                "Per-request overrides replace this layer only."
            ),
            "default": DEFAULT_CONFIG_TEMPLATE,
            "variables": DOCUMENT_VARIABLES,
            "shared_variables": [],
        },
    }
    for name, segment in SEGMENTS.items():
        specs[name] = {
            "title": segment["title"],
            "description": segment["description"],
            "default": segment["default"],
            "variables": segment["variables"],
            "shared_variables": SHARED_VARIABLES,
        }
    return specs


def _syntax_error(content):
    try:
        _syntax_env.from_string(content)
    except TemplateError as e:
        return f"Template syntax error: {e}"
    return None


def _history(rows_by_name):
    ct = ContentType.objects.get_for_model(ConfigTemplate)
    pks = [str(row.pk) for row in rows_by_name.values()]
    entries = (
        LogEntry.objects.filter(content_type=ct, object_pk__in=pks)
        .select_related("actor")
        .order_by("-timestamp")
    )
    return entries


@role_required("network")
def config_template_view(request):
    """Library of all config templates: document layout + one per segment."""
    specs = _template_specs()
    rows = {row.name: row for row in ConfigTemplate.objects.filter(name__in=list(specs))}

    items = []
    for name, spec in specs.items():
        row = rows.get(name)
        items.append({
            "name": name,
            "title": spec["title"],
            "description": spec["description"],
            "customized": bool(row) and row.content != spec["default"],
            "updated_by": row.updated_by if row else None,
            "updated_at": row.updated_at if row else None,
        })

    return render(request, "config/template_list.html", {
        "nav_active": "config-template",
        "items": items,
        "history": _history(rows)[:12],
        "shared_variables": SHARED_VARIABLES,
    })


@role_required("network")
def config_template_edit_view(request, name):
    """Edit one template (document layout or a segment). All changes are logged."""
    specs = _template_specs()
    spec = specs.get(name)
    if spec is None:
        raise Http404

    row = ConfigTemplate.objects.filter(name=name).first()
    current = row.content if row else spec["default"]
    error = None
    saved = False

    if request.method == "POST":
        if "reset" in request.POST:
            content = spec["default"]
        else:
            content = request.POST.get("content", "")
            error = _syntax_error(content)
        if not error:
            if row is None:
                row = ConfigTemplate(name=name)
            row.content = content
            row.updated_by = request.user
            row.save()
            if "reset" in request.POST:
                return redirect("ui:config-template")
            saved = True
            current = content

    return render(request, "config/template_form.html", {
        "nav_active": "config-template",
        "template_name": name,
        "title": spec["title"],
        "description": spec["description"],
        "content": request.POST.get("content", current) if error else current,
        "error": error,
        "saved": saved,
        "is_default": current == spec["default"],
        "updated_by": row.updated_by if row else None,
        "updated_at": row.updated_at if row else None,
        "variables": spec["variables"],
        "shared_variables": spec["shared_variables"],
        "history": _history({name: row})[:10] if row else [],
    })


@role_required("network")
def request_config_template_view(request, pk):
    """Edit one request's document-template override. Logged on the request's audit trail."""
    vpn_request = get_object_or_404(VpnRequest, pk=pk)
    global_row = ConfigTemplate.objects.filter(name=GLOBAL_TEMPLATE_NAME).first()
    global_content = global_row.content if global_row else DEFAULT_CONFIG_TEMPLATE
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
        content = vpn_request.config_template_override or global_content

    return render(request, "config/request_template_form.html", {
        "nav_active": "my-requests",
        "vpn_request": vpn_request,
        "content": content,
        "has_override": bool(vpn_request.config_template_override.strip()),
        "error": error,
        "variables": DOCUMENT_VARIABLES,
    })
