"""
Render a request's per-site configuration text through a Jinja template.

The Python generator (panos.py) stays the source of truth for the computed
commands; the template controls the final text. Resolution order:
request override (VpnRequest.config_template_override) → global template
(ConfigTemplate 'global') → built-in default, which reproduces the
generator's output verbatim.

Templates are rendered in a Jinja sandbox and receive only plain dicts —
never model instances — so a template edit can't touch the ORM.
"""

from jinja2 import TemplateError, Undefined
from jinja2.sandbox import SandboxedEnvironment

from apps.vpn.models.config_template import DEFAULT_CONFIG_TEMPLATE, ConfigTemplate
from apps.vpn.services.panos import config_as_text, generate_panos_config

_env = SandboxedEnvironment(
    undefined=Undefined,
    trim_blocks=True,
    lstrip_blocks=False,
    autoescape=False,
)


def _site_dict(site):
    return {
        "name": site.name,
        "code": site.code,
        "location": site.location,
        "public_ip": site.public_ip or "",
        "bgp_asn": site.bgp_asn,
        "device_group": site.device_group,
        "template_name": site.template_name,
        "management_type": site.management_type,
    }


def _tunnel_dict(block):
    ti = block["iface"]
    return {
        "label": block["label"],
        "number": ti.tunnel_number,
        "local_ip": ti.local_ip or "",
        "remote_ip": ti.remote_ip or "",
        "subnet_cidr": ti.subnet_cidr,
        "peer_ip": block["peer_ip"],
        "sections": block["sections"],
    }


def build_template_context(vpn_request, site_config):
    """The variables a config template can use. Keep docs in the editor in sync."""
    flows = [
        {
            "source_cidr": f.source_cidr,
            "destination_cidr": f.destination_cidr,
            "direction": f.direction,
            "protocols": f.protocol_list,
            # joined display string for templates (e.g. "tcp, udp")
            "protocol": ", ".join(f.protocol_list),
            "destination_ports": f.destination_ports,
            "description": f.description,
        }
        for f in vpn_request.flows.all()
    ]
    mappings = [
        {
            "site_code": nm.site.code,
            "direction": nm.direction,
            "nat_address": nm.nat_address,
            "real_address": nm.real_address,
        }
        for nm in vpn_request.nat_mappings.select_related("site")
    ]
    return {
        "reference": vpn_request.reference_number.lower(),
        "request": {
            "reference_number": vpn_request.reference_number,
            "title": vpn_request.title,
            "vendor": vpn_request.vendor.name if vpn_request.vendor else "",
            "directionality": vpn_request.directionality,
            "routing_type": vpn_request.routing_type,
            "ike_version": vpn_request.ike_version,
            "ike_encryption": vpn_request.ike_encryption,
            "ike_integrity": vpn_request.ike_integrity,
            "ike_dh_group": vpn_request.ike_dh_group,
            "ipsec_encryption": vpn_request.ipsec_encryption,
            "ipsec_integrity": vpn_request.ipsec_integrity,
            "ipsec_pfs_group": vpn_request.ipsec_pfs_group,
            "vendor_cidrs": vpn_request.vendor_cidrs,
        },
        "site": _site_dict(site_config["site"]),
        "sections": site_config["sections"],
        "shared_sections": site_config["shared_sections"],
        "tunnels": [_tunnel_dict(b) for b in site_config["tunnels"]],
        "flows": flows,
        "nat_mappings": mappings,
        "notes": site_config["notes"],
    }


def resolve_template(vpn_request):
    """Return (content, source) — source is 'request', 'global' or 'default'."""
    override = (vpn_request.config_template_override or "").strip()
    if override:
        return vpn_request.config_template_override, "request"
    template = ConfigTemplate.get_global()
    if template.content != DEFAULT_CONFIG_TEMPLATE:
        return template.content, "global"
    return template.content, "default"


def render_template(content, context):
    """Render template content; returns (text, error). Never raises."""
    try:
        text = _env.from_string(content).render(**context)
    except TemplateError as e:
        return "", f"Template error: {e}"
    except Exception as e:  # sandbox violations etc.
        return "", f"Template error: {e}"
    # Normalize: strip leading blank lines, ensure single trailing newline
    text = text.strip("\n")
    return (text + "\n") if text else "", None


def rendered_site_configs(vpn_request):
    """
    Per-site configs with the final text rendered through the resolved
    template. Returns the panos site dicts augmented with:
    text, render_error, template_source.
    """
    content, source = resolve_template(vpn_request)
    configs = []
    for cfg in generate_panos_config(vpn_request):
        if cfg["supported"]:
            context = build_template_context(vpn_request, cfg)
            text, error = render_template(content, context)
            if error:
                # Fall back to the generator output so downloads stay usable
                cfg["text"] = config_as_text(cfg) + ("\n" if cfg["sections"] else "")
                cfg["render_error"] = error
            else:
                cfg["text"] = text
                cfg["render_error"] = None
        else:
            cfg["text"] = ""
            cfg["render_error"] = None
        cfg["template_source"] = source
        configs.append(cfg)
    return configs
