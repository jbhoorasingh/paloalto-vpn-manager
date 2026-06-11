"""
Segment templates: each piece of the generated configuration (crypto
profiles, tunnel interfaces, IKE gateways, NAT policy, …) is rendered from
its own Jinja template.

Python computes the VALUES (object names, IPs, normalized crypto, rule
dicts); the segment template owns the SET-COMMAND SYNTAX. Built-in defaults
reproduce the legacy generator output exactly; a ConfigTemplate row with the
segment's name overrides the default. Rendered output is split into lines
(blank lines dropped), so template whitespace is forgiving.

Every variable a segment can use is documented here (`variables`) and shown
in the editor — keep docs and context builders in panos.py in sync.
"""

from jinja2 import TemplateError, Undefined
from jinja2.sandbox import SandboxedEnvironment

_env = SandboxedEnvironment(
    undefined=Undefined,
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,
)

# Variables present in EVERY segment context.
SHARED_VARIABLES = [
    ("base", "Lowercased request reference used in object names, e.g. vpn-ab12cd34"),
    ("prefixes.net", "Command prefix for network/template config ('set ' or 'set template X config ')"),
    ("prefixes.zone", "Command prefix for zone config (adds 'vsys vsys1' under Panorama)"),
    ("prefixes.policy", "Command prefix for policy/objects ('set ' or 'set device-group X ')"),
    ("prefixes.rulebase", "'rulebase' (standalone) or 'pre-rulebase' (Panorama)"),
    ("constants.untrust_interface", "External interface convention (ethernet1/1)"),
    ("constants.inside_interface", "Inside interface convention (ethernet1/2)"),
    ("constants.vpn_zone", "Vendor VPN zone name"),
    ("constants.trust_zone", "Inside zone name"),
    ("constants.virtual_router", "Virtual router name"),
    ("constants.psk_placeholder", "Pre-shared key placeholder"),
    ("site", "Endpoint firewall: name, code, public_ip, bgp_asn, device_group, template_name, management_type"),
    ("request", "Request fields: reference_number, title, vendor, directionality, routing_type, ike_*, ipsec_*, vendor_cidrs"),
]

TUNNEL_VARIABLES = [
    ("tunnels", "Tunnel list; each has: unit ('tunnel.101'), number, idx (1-based), "
                "gw_name, vpn_name, peer_name, local_ip, ip_with_prefix ('10.255.0.1/30'), "
                "remote_ip, subnet_cidr, peer_ip (vendor IKE peer), "
                "static_routes (list of {name, destination, nexthop})"),
]

SEGMENTS = {
    "ike_crypto": {
        "title": "IKE Crypto Profile",
        "description": "Phase-1 crypto profile shared by all of the request's gateways.",
        "variables": [
            ("ike", "profile_name, encryption, hash, dh_group ('group14' or ''), lifetime, "
                    "version ('ikev2'/'ikev1'), auth_method ('psk'/'certificate'), dpd_enabled"),
        ],
        "default": """\
{% set path = prefixes.net ~ 'network ike crypto-profiles ike-crypto-profiles ' ~ ike.profile_name %}
{% if ike.encryption %}{{ path }} encryption {{ ike.encryption }}
{% endif %}
{% if ike.hash %}{{ path }} hash {{ ike.hash }}
{% endif %}
{% if ike.dh_group %}{{ path }} dh-group {{ ike.dh_group }}
{% endif %}
{% if ike.lifetime %}{{ path }} lifetime seconds {{ ike.lifetime }}
{% endif %}
""",
    },
    "ipsec_crypto": {
        "title": "IPsec Crypto Profile",
        "description": "Phase-2 crypto profile (GCM ciphers get authentication 'none').",
        "variables": [
            ("ipsec", "profile_name, encryption, authentication ('sha256', 'none' for GCM, or ''), "
                      "dh_group (PFS, 'group14' or ''), lifetime"),
        ],
        "default": """\
{% set path = prefixes.net ~ 'network ike crypto-profiles ipsec-crypto-profiles ' ~ ipsec.profile_name %}
{% if ipsec.encryption %}{{ path }} esp encryption {{ ipsec.encryption }}
{% endif %}
{% if ipsec.authentication %}{{ path }} esp authentication {{ ipsec.authentication }}
{% endif %}
{% if ipsec.dh_group %}{{ path }} dh-group {{ ipsec.dh_group }}
{% endif %}
{% if ipsec.lifetime %}{{ path }} lifetime seconds {{ ipsec.lifetime }}
{% endif %}
""",
    },
    "tunnel_interface": {
        "title": "Tunnel Interfaces",
        "description": "Logical tunnel unit, zone membership and virtual-router binding, per tunnel.",
        "variables": TUNNEL_VARIABLES,
        "default": """\
{% for t in tunnels %}
{{ prefixes.net }}network interface tunnel units {{ t.unit }}
{% if t.local_ip %}{{ prefixes.net }}network interface tunnel units {{ t.unit }} ip {{ t.ip_with_prefix }}
{% endif %}
{{ prefixes.zone }}zone {{ constants.vpn_zone }} network layer3 {{ t.unit }}
{{ prefixes.net }}network virtual-router {{ constants.virtual_router }} interface {{ t.unit }}
{% endfor %}
""",
    },
    "ike_gateway": {
        "title": "IKE Gateways",
        "description": "Phase-1 gateway to the vendor peer, per tunnel.",
        "variables": TUNNEL_VARIABLES + [
            ("ike", "Same as the IKE crypto segment: version, auth_method, dpd_enabled, profile_name"),
        ],
        "default": """\
{% for t in tunnels %}
{% set path = prefixes.net ~ 'network ike gateway ' ~ t.gw_name %}
{% if ike.auth_method == 'psk' %}{{ path }} authentication pre-shared-key key {{ constants.psk_placeholder }}
{% else %}{{ path }} authentication certificate certificate-profile <CERT-PROFILE>
{% endif %}
{{ path }} protocol version {{ ike.version }}
{{ path }} protocol {{ ike.version }} ike-crypto-profile {{ ike.profile_name }}
{% if ike.dpd_enabled %}{{ path }} protocol {{ ike.version }} dpd enable yes
{% endif %}
{{ path }} local-address interface {{ constants.untrust_interface }}
{% if site.public_ip %}{{ path }} local-address ip {{ site.public_ip }}
{% endif %}
{% if t.peer_ip %}{{ path }} peer-address ip {{ t.peer_ip }}
{% endif %}
{% endfor %}
""",
    },
    "ipsec_tunnel": {
        "title": "IPsec Tunnels",
        "description": "Phase-2 tunnel object tying gateway, crypto profile and tunnel interface.",
        "variables": TUNNEL_VARIABLES + [
            ("ipsec", "Same as the IPsec crypto segment (profile_name etc.)"),
        ],
        "default": """\
{% for t in tunnels %}
{% set path = prefixes.net ~ 'network tunnel ipsec ' ~ t.vpn_name %}
{{ path }} auto-key ike-gateway {{ t.gw_name }}
{{ path }} auto-key ipsec-crypto-profile {{ ipsec.profile_name }}
{{ path }} tunnel-interface {{ t.unit }}
{{ path }} anti-replay yes
{% endfor %}
""",
    },
    "static_routes": {
        "title": "Static Routes",
        "description": "One route per vendor CIDR steering traffic into each tunnel (static routing only).",
        "variables": TUNNEL_VARIABLES,
        "default": """\
{% for t in tunnels %}
{% for r in t.static_routes %}
{% set path = prefixes.net ~ 'network virtual-router ' ~ constants.virtual_router ~ ' routing-table ip static-route ' ~ r.name %}
{{ path }} destination {{ r.destination }}
{{ path }} interface {{ t.unit }}
{% if r.nexthop %}{{ path }} nexthop ip {{ r.nexthop }}
{% endif %}
{% endfor %}
{% endfor %}
""",
    },
    "bgp_setup": {
        "title": "BGP Setup (Shared)",
        "description": "Site-level BGP basics shared by every tunnel peer (BGP routing only).",
        "variables": [
            ("bgp", "local_asn, router_id, peer_group"),
        ],
        "default": """\
{% set vr = prefixes.net ~ 'network virtual-router ' ~ constants.virtual_router %}
{{ vr }} protocol bgp enable yes
{% if bgp.local_asn %}{{ vr }} protocol bgp local-as {{ bgp.local_asn }}
{% endif %}
{% if bgp.router_id %}{{ vr }} protocol bgp router-id {{ bgp.router_id }}
{% endif %}
{{ vr }} protocol bgp peer-group {{ bgp.peer_group }} type ebgp
""",
    },
    "bgp_peer": {
        "title": "BGP Peering",
        "description": "Per-tunnel eBGP peer to the vendor (BGP routing only).",
        "variables": TUNNEL_VARIABLES + [
            ("bgp", "local_asn, router_id, peer_group"),
            ("tunnels[].remote_asn", "Vendor ASN for the endpoint this tunnel lands on"),
        ],
        "default": """\
{% set vr = prefixes.net ~ 'network virtual-router ' ~ constants.virtual_router %}
{% for t in tunnels %}
{% set peer = vr ~ ' protocol bgp peer-group ' ~ bgp.peer_group ~ ' peer ' ~ t.peer_name %}
{{ peer }} enable yes
{% if t.remote_asn %}{{ peer }} peer-as {{ t.remote_asn }}
{% endif %}
{% if t.local_ip %}{{ peer }} local-address interface {{ t.unit }} ip {{ t.ip_with_prefix }}
{% else %}{{ peer }} local-address interface {{ t.unit }}
{% endif %}
{% if t.remote_ip %}{{ peer }} peer-address ip {{ t.remote_ip }}
{% endif %}
{% endfor %}
""",
    },
    "bgp_nat_advertisement": {
        "title": "BGP NAT Advertisement",
        "description": "Advertises inbound NAT addresses to the vendor; the DR secondary prepends its AS.",
        "variables": [
            ("bgp_nat", "rule_name, peer_group, addresses (list of CIDRs), is_secondary, prepend_count"),
        ],
        "default": """\
{% if bgp_nat.addresses %}
{% set rule = prefixes.net ~ 'network virtual-router ' ~ constants.virtual_router ~ ' protocol bgp policy export rules ' ~ bgp_nat.rule_name %}
{{ rule }} enable yes
{{ rule }} used-by {{ bgp_nat.peer_group }}
{% for addr in bgp_nat.addresses %}
{{ rule }} match address-prefix {{ addr }} exact yes
{% endfor %}
{{ rule }} action allow
{% if bgp_nat.is_secondary %}{{ rule }} action allow update as-path prepend {{ bgp_nat.prepend_count }}
{% endif %}
{% endif %}
""",
    },
    "service_objects": {
        "title": "Service Objects",
        "description": "One service object per TCP/UDP flow that names ports.",
        "variables": [
            ("services", "List of {name, protocol ('tcp'/'udp'), ports ('443,8443')}"),
        ],
        "default": """\
{% for svc in services %}
{{ prefixes.policy }}service {{ svc.name }} protocol {{ svc.protocol }} port {{ svc.ports }}
{% endfor %}
""",
    },
    "nat_policy": {
        "title": "NAT Policy",
        "description": "Destination NAT plus symmetric source NAT (outbound per tunnel; inbound to the inside interface).",
        "variables": [
            ("nat_rules", "List of {name, from_zone, to_zone, to_interface ('' if none), source, "
                          "destination, service, translated_destination, snat_interface ('' if none)}"),
        ],
        "default": """\
{% for rule in nat_rules %}
{% set path = prefixes.policy ~ prefixes.rulebase ~ ' nat rules ' ~ rule.name %}
{{ path }} from {{ rule.from_zone }}
{{ path }} to {{ rule.to_zone }}
{% if rule.to_interface %}{{ path }} to-interface {{ rule.to_interface }}
{% endif %}
{{ path }} source {{ rule.source }}
{{ path }} destination {{ rule.destination }}
{{ path }} service {{ rule.service }}
{{ path }} destination-translation translated-address {{ rule.translated_destination }}
{% if rule.snat_interface %}{{ path }} source-translation dynamic-ip-and-port interface-address interface {{ rule.snat_interface }}
{% endif %}
{% endfor %}
""",
    },
    "security_policy": {
        "title": "Security Policy",
        "description": "Allow rules per traffic flow and direction (pre-NAT addresses, post-NAT zones).",
        "variables": [
            ("security_rules", "List of {name, from_zone, to_zone, source, destination, service}"),
        ],
        "default": """\
{% for rule in security_rules %}
{% set path = prefixes.policy ~ prefixes.rulebase ~ ' security rules ' ~ rule.name %}
{{ path }} from {{ rule.from_zone }}
{{ path }} to {{ rule.to_zone }}
{{ path }} source {{ rule.source }}
{{ path }} destination {{ rule.destination }}
{{ path }} application any
{{ path }} service {{ rule.service }}
{{ path }} action allow
{% endfor %}
""",
    },
}


def get_segment_contents():
    """name → template content, DB overrides overlaid on built-in defaults."""
    from apps.vpn.models import ConfigTemplate

    contents = {name: spec["default"] for name, spec in SEGMENTS.items()}
    for row in ConfigTemplate.objects.filter(name__in=list(SEGMENTS)):
        contents[row.name] = row.content
    return contents


def render_segment_commands(name, content, context):
    """
    Render one segment into a list of command lines (blank lines dropped).

    Returns (commands, error). On error the built-in default is used so the
    output stays deployable; the error is reported for the UI.
    """
    try:
        text = _env.from_string(content).render(**context)
        return [line for line in text.splitlines() if line.strip()], None
    except TemplateError as e:
        error = f"Segment '{name}' template error: {e}"
    except Exception as e:
        error = f"Segment '{name}' template error: {e}"
    text = _env.from_string(SEGMENTS[name]["default"]).render(**context)
    return [line for line in text.splitlines() if line.strip()], error
