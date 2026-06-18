"""
PAN-OS set-command generation for a VPN request.

Produces, per endpoint site, the ``set`` CLI lines needed to stand up the
IPsec connection on a Palo Alto firewall: IKE/IPsec crypto profiles, tunnel
interfaces, IKE gateways, IPsec tunnels, routing (static or BGP), plus NAT
and security policy derived from the request's traffic flows and allocated
NAT mappings.

Centrally managed sites (Panorama) get template-scoped network commands
(``set template <name> config ...``) and device-group-scoped policy commands
(``set device-group <name> pre-rulebase ...``); standalone sites get plain
firewall-local commands.

The output is a starting point for a network engineer, not a finished change:
pre-shared keys are emitted as placeholders and interface/zone names are
site conventions (see ``NOTES`` constants).
"""

import netaddr

from apps.core.models import DrPeer, NatDirection

from .nat import directions_for_flow, endpoint_sites

# Site conventions assumed by the generator. Surfaced to the user as notes so
# an engineer can adjust before pushing.
UNTRUST_INTERFACE = "ethernet1/1"
INSIDE_INTERFACE = "ethernet1/2"
VPN_ZONE = "vpn-vendor"
TRUST_ZONE = "trust"
VIRTUAL_ROUTER = "default"
PSK_PLACEHOLDER = "<PRE-SHARED-KEY>"
# Secondary DR site prepends its AS this many times so the primary is preferred.
DR_PREPEND_COUNT = 2

# Free-text crypto fields normalized to PAN-OS keywords. Unknown values pass
# through lowercased so an engineer can spot and fix them.
ENCRYPTION_MAP = {
    "aes-256-cbc": "aes-256-cbc",
    "aes256": "aes-256-cbc",
    "aes-256": "aes-256-cbc",
    "aes-192-cbc": "aes-192-cbc",
    "aes-128-cbc": "aes-128-cbc",
    "aes128": "aes-128-cbc",
    "aes-128": "aes-128-cbc",
    "aes-256-gcm": "aes-256-gcm",
    "aes256-gcm": "aes-256-gcm",
    "aes-128-gcm": "aes-128-gcm",
    "3des": "3des",
    "des": "des",
}

HASH_MAP = {
    "sha1": "sha1",
    "sha-1": "sha1",
    "sha256": "sha256",
    "sha-256": "sha256",
    "sha384": "sha384",
    "sha-384": "sha384",
    "sha512": "sha512",
    "sha-512": "sha512",
    "md5": "md5",
}


def _norm_encryption(value):
    value = (value or "").strip().lower()
    return ENCRYPTION_MAP.get(value, value)


def _norm_hash(value):
    value = (value or "").strip().lower()
    return HASH_MAP.get(value, value)


def _norm_dh_group(value):
    """'14' / 'group14' / '14, 19' → 'group14' (first group listed)."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    first = value.replace("group", "").split(",")[0].strip()
    return f"group{first}" if first else ""


def _q(name):
    """Quote a name for the CLI if it contains whitespace."""
    if name and any(c.isspace() for c in name):
        return f'"{name}"'
    return name


def _is_panorama(site):
    return site.management_type == "centralized"


def _net_prefix(site):
    """Prefix for network/template-level commands."""
    if _is_panorama(site) and site.template_name:
        return f"set template {_q(site.template_name)} config "
    return "set "


def _zone_prefix(site):
    """Zones live under vsys inside a Panorama template."""
    if _is_panorama(site) and site.template_name:
        return f"set template {_q(site.template_name)} config vsys vsys1 "
    return "set "


def _policy_prefix(site):
    """Prefix for rulebase/object commands."""
    if _is_panorama(site) and site.device_group:
        return f"set device-group {_q(site.device_group)} "
    return "set "


def _rulebase(site):
    return "pre-rulebase" if _is_panorama(site) and site.device_group else "rulebase"


def _name_base(vpn_request):
    return vpn_request.reference_number.lower()


def _parse_vendor_cidrs(vpn_request):
    raw = vpn_request.vendor_cidrs or ""
    cidrs = []
    for line in raw.replace(",", "\n").splitlines():
        line = line.strip()
        if line and line not in cidrs:
            cidrs.append(line)
    return cidrs


def _subnet_prefixlen(tunnel_iface):
    if tunnel_iface.subnet_cidr:
        try:
            return netaddr.IPNetwork(tunnel_iface.subnet_cidr).prefixlen
        except (netaddr.AddrFormatError, ValueError):
            pass
    return 30


def _remote_asn_for(vpn_request, tunnel_iface):
    """Vendor ASN for the endpoint this tunnel terminates on."""
    if (
        tunnel_iface.vendor_endpoint_ip
        and vpn_request.vendor_endpoint_2_ip
        and tunnel_iface.vendor_endpoint_ip == vpn_request.vendor_endpoint_2_ip
        and vpn_request.bgp_remote_asn_2
    ):
        return vpn_request.bgp_remote_asn_2
    return vpn_request.bgp_remote_asn


def _ike_context(vpn_request, base):
    return {
        "profile_name": f"{base}-ike",
        "encryption": _norm_encryption(vpn_request.ike_encryption),
        "hash": _norm_hash(vpn_request.ike_integrity),
        "dh_group": _norm_dh_group(vpn_request.ike_dh_group),
        "lifetime": vpn_request.ike_lifetime or "",
        "version": "ikev2" if vpn_request.ike_version == "2" else "ikev1",
        "auth_method": vpn_request.auth_method,
        "dpd_enabled": vpn_request.dpd_enabled,
    }


def _ipsec_context(vpn_request, base):
    enc = _norm_encryption(vpn_request.ipsec_encryption)
    # GCM ciphers carry their own integrity; PAN-OS requires authentication none.
    if enc and "gcm" in enc:
        authentication = "none"
    else:
        authentication = _norm_hash(vpn_request.ipsec_integrity)
    return {
        "profile_name": f"{base}-ipsec",
        "encryption": enc,
        "authentication": authentication,
        "dh_group": _norm_dh_group(vpn_request.ipsec_pfs_group),
        "lifetime": vpn_request.ipsec_lifetime or "",
    }


def _tunnel_context(vpn_request, ti, idx, base, route_start):
    """Plain-dict tunnel for segment templates. Returns (dict, next_route_idx)."""
    local_ip = ti.local_ip or ""
    static_routes = []
    route_idx = route_start
    if vpn_request.routing_type != "bgp":
        for cidr in _parse_vendor_cidrs(vpn_request):
            static_routes.append({
                "name": f"{base}-rt{route_idx}",
                "destination": cidr,
                "nexthop": ti.remote_ip or "",
            })
            route_idx += 1
    return {
        "unit": f"tunnel.{ti.tunnel_number}",
        "number": ti.tunnel_number,
        "idx": idx,
        "gw_name": f"{base}-gw{idx}",
        "vpn_name": f"{base}-vpn{idx}",
        "peer_name": f"{base}-peer{idx}",
        "local_ip": local_ip,
        "ip_with_prefix": f"{local_ip}/{_subnet_prefixlen(ti)}" if local_ip else "",
        "remote_ip": ti.remote_ip or "",
        "subnet_cidr": ti.subnet_cidr,
        "peer_ip": ti.vendor_endpoint_ip or "",
        "remote_asn": _remote_asn_for(vpn_request, ti) or "",
        "static_routes": static_routes,
    }, route_idx


def _services_context(flows, base):
    """
    Service objects + flow→service-name(s) lookup.

    A flow gets one service object per port-based protocol it carries (tcp/udp)
    when it names ports. Single-protocol flows keep the legacy ``{base}-svcN``
    name; multi-protocol flows disambiguate as ``{base}-svcN-tcp`` etc.
    ``service_names[flow.pk]`` is the list of object names for that flow.
    """
    services = []
    service_names = {}
    for i, flow in enumerate(flows, start=1):
        if not flow.destination_ports:
            continue
        protocols = flow.protocol_list
        # icmp/any widen the security rule to service 'any' — don't emit
        # service objects no rule will reference.
        if "icmp" in protocols or "any" in protocols:
            continue
        port_protocols = [p for p in protocols if p in ("tcp", "udp")]
        if not port_protocols:
            continue
        ports = flow.destination_ports.replace(" ", "")
        names = []
        for proto in port_protocols:
            name = f"{base}-svc{i}" if len(port_protocols) == 1 else f"{base}-svc{i}-{proto}"
            services.append({"name": name, "protocol": proto, "ports": ports})
            names.append(name)
        service_names[flow.pk] = names
    return services, service_names


def _nat_rules_context(mappings, tunnels, base):
    """
    NAT rule dicts mirroring the symmetric-NAT design: outbound gets one rule
    per egress tunnel (DNAT to vendor host + SNAT to the tunnel interface);
    inbound DNATs to the inside address and SNATs to the inside interface.
    """
    rules = []
    counters = {NatDirection.OUTBOUND: 0, NatDirection.INBOUND: 0}
    for nm in mappings:
        counters[nm.direction] = counters.get(nm.direction, 0) + 1
        idx = counters[nm.direction]
        if nm.direction == NatDirection.OUTBOUND:
            if tunnels:
                for ti in tunnels:
                    rules.append({
                        "name": f"{base}-out{idx}-t{ti.tunnel_number}",
                        "from_zone": TRUST_ZONE,
                        "to_zone": VPN_ZONE,
                        "to_interface": f"tunnel.{ti.tunnel_number}",
                        "source": "any",
                        "destination": nm.nat_address,
                        "service": "any",
                        "translated_destination": nm.real_address,
                        "snat_interface": f"tunnel.{ti.tunnel_number}",
                    })
            else:
                # No tunnels allocated yet — emit the DNAT half so the intent
                # is visible; per-tunnel SNAT rules appear once tunnels exist.
                rules.append({
                    "name": f"{base}-nat-out{idx}",
                    "from_zone": TRUST_ZONE,
                    "to_zone": VPN_ZONE,
                    "to_interface": "",
                    "source": "any",
                    "destination": nm.nat_address,
                    "service": "any",
                    "translated_destination": nm.real_address,
                    "snat_interface": "",
                })
        else:
            rules.append({
                "name": f"{base}-nat-in{idx}",
                "from_zone": VPN_ZONE,
                "to_zone": TRUST_ZONE,
                "to_interface": "",
                "source": "any",
                "destination": nm.nat_address,
                "service": "any",
                "translated_destination": nm.real_address,
                "snat_interface": INSIDE_INTERFACE,
            })
    return rules


def _dr_roles(vpn_request):
    """
    (primary_site, secondary_site) for a two-site request.

    The configured DR peer is authoritative regardless of which endpoint the
    requester picked first; without one, falls back to the endpoint order
    (endpoint 1 = primary).
    """
    if vpn_request.our_endpoints_count != 2:
        return None
    site1 = vpn_request.our_endpoint_1_site
    site2 = vpn_request.our_endpoint_2_site
    if not site1 or not site2 or site1.pk == site2.pk:
        return None
    peer = DrPeer.for_sites(site1, site2)
    if peer:
        return peer.primary_site, peer.secondary_site
    return site1, site2


def _bgp_nat_context(vpn_request, site, mappings, base):
    """
    Inbound NAT addresses advertised to the vendor over tunnel BGP. On a DR
    pair both endpoints advertise the SAME addresses; the secondary member
    prepends its AS so the primary path is preferred.
    """
    inbound_addrs = []
    for nm in mappings:
        if nm.direction == NatDirection.INBOUND and nm.nat_address not in inbound_addrs:
            inbound_addrs.append(nm.nat_address)
    roles = _dr_roles(vpn_request)
    return {
        "rule_name": f"{base}-nat-adv",
        "peer_group": f"{base}-pg",
        "addresses": inbound_addrs,
        "is_secondary": bool(roles) and site.pk == roles[1].pk,
        "prepend_count": DR_PREPEND_COUNT,
    }


def _flow_service(flow, service_names):
    """
    The PAN-OS ``service`` value for a flow's security rule.

    tcp/udp flows reference their service object(s) (a ``[ a b ]`` list when
    more than one). Flows that include ICMP or 'any' fall back to ``any``:
    custom service objects can't express ICMP, and the rule already permits
    ``application any``, so this keeps the traffic flowing for an engineer to
    tighten. Returns (service, widened_for_icmp).
    """
    protocols = flow.protocol_list
    names = service_names.get(flow.pk)
    # Widened (port restriction lost) when icmp is mixed with a port-based
    # protocol that named ports — those ports can't be expressed alongside ICMP.
    widened = "icmp" in protocols and flow.has_port_protocol and bool(flow.destination_ports)
    if "icmp" in protocols or "any" in protocols or not names:
        return "any", widened
    if len(names) == 1:
        return names[0], False
    return "[ " + " ".join(names) + " ]", False


def _security_rules_context(vpn_request, flows, mappings, service_names, base):
    """
    One security rule per (flow × flow direction).

    Each flow's own direction picks the zone pair; flows without one fall back
    to the request-level directionality. Destinations use the published NAT
    address when a mapping exists for the flow's destination + direction
    (multiple flows to the same host share one NAT address), otherwise the
    flow's real destination.
    """
    # Map each destination+direction to the published NAT address(es). Normally
    # one address per key (dedup); legacy requests allocated before dedup may
    # still carry several rows for one destination — emit a rule for each so the
    # security policy permits every address the NAT policy publishes.
    addrs_by_dest_dir = {}
    for nm in mappings:
        addrs_by_dest_dir.setdefault((nm.real_address, nm.direction), [])
        if nm.nat_address not in addrs_by_dest_dir[(nm.real_address, nm.direction)]:
            addrs_by_dest_dir[(nm.real_address, nm.direction)].append(nm.nat_address)

    rules = []
    rule_idx = 1
    for flow in flows:
        service, _ = _flow_service(flow, service_names)
        for direction in directions_for_flow(flow, vpn_request):
            destinations = addrs_by_dest_dir.get(
                (flow.destination_cidr, direction)
            ) or [flow.destination_cidr]
            if direction == NatDirection.OUTBOUND:
                from_zone, to_zone = TRUST_ZONE, VPN_ZONE
            else:
                from_zone, to_zone = VPN_ZONE, TRUST_ZONE
            for destination in destinations:
                rules.append({
                    "name": f"{base}-sec{rule_idx}",
                    "from_zone": from_zone,
                    "to_zone": to_zone,
                    "source": flow.source_cidr or "any",
                    "destination": destination or "any",
                    "service": service,
                })
                rule_idx += 1
    return rules


def _concat_tunnel_category(tunnel_blocks, title):
    """Flatten one per-tunnel section category across all tunnel blocks."""
    commands = []
    for block in tunnel_blocks:
        for section in block["sections"]:
            if section["title"] == title:
                commands.extend(section["commands"])
    return commands


def generate_site_config(vpn_request, site):
    """
    Generate the set-command config for one endpoint site.

    Each segment (crypto, tunnel interface, gateways, routing, NAT, security)
    is rendered from its segment template (see services/config_segments.py) —
    Python supplies the values, the templates own the command syntax.

    Returns ``sections`` (the full site config flattened by category — what the
    Config tab and download render) plus a deployment-oriented split of the
    same commands: ``shared_sections`` (crypto profiles, shared BGP setup,
    service objects, NAT and security policy — applied once per site) and
    ``tunnels`` (one block per tunnel interface with its interface, IKE
    gateway, IPsec tunnel and routing commands).
    """
    from apps.vpn.services.config_segments import (
        get_segment_contents,
        render_segment_commands,
    )

    base = _name_base(vpn_request)
    notes = []
    segment_errors = []

    if site.device_brand and site.device_brand != "palo_alto":
        return {
            "site": site,
            "supported": False,
            "reason": (
                f"Set-command generation currently supports Palo Alto only "
                f"(site device brand: {site.get_device_brand_display()})."
            ),
            "sections": [],
            "shared_sections": [],
            "tunnels": [],
            "notes": [],
        }

    tunnels = list(vpn_request.tunnel_interfaces.filter(site=site).order_by("tunnel_number"))
    flows = list(vpn_request.flows.all())
    mappings = list(
        vpn_request.nat_mappings.filter(site=site).select_related("traffic_flow")
    )

    contents = get_segment_contents()

    def render(segment, extra):
        commands, error = render_segment_commands(
            segment, contents[segment], {**ctx, **extra}
        )
        if error:
            segment_errors.append(error)
        return commands

    # Shared context for every segment
    services, service_names = _services_context(flows, base)
    ctx = {
        "base": base,
        "prefixes": {
            "net": _net_prefix(site),
            "zone": _zone_prefix(site),
            "policy": _policy_prefix(site),
            "rulebase": _rulebase(site),
        },
        "constants": {
            "untrust_interface": UNTRUST_INTERFACE,
            "inside_interface": INSIDE_INTERFACE,
            "vpn_zone": VPN_ZONE,
            "trust_zone": TRUST_ZONE,
            "virtual_router": VIRTUAL_ROUTER,
            "psk_placeholder": PSK_PLACEHOLDER,
        },
        "site": {
            "name": site.name,
            "code": site.code,
            "public_ip": site.public_ip or "",
            "bgp_asn": site.bgp_asn,
            "device_group": site.device_group,
            "template_name": site.template_name,
            "management_type": site.management_type,
        },
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
        "ike": _ike_context(vpn_request, base),
        "ipsec": _ipsec_context(vpn_request, base),
        "bgp": {
            "local_asn": site.bgp_asn or vpn_request.bgp_local_asn or "",
            "router_id": site.public_ip or "",
            "peer_group": f"{base}-pg",
        },
    }

    crypto_sections = [
        s for s in (
            {"title": "IKE Crypto Profile", "commands": render("ike_crypto", {})},
            {"title": "IPsec Crypto Profile", "commands": render("ipsec_crypto", {})},
        ) if s["commands"]
    ]
    sections = list(crypto_sections)
    shared_sections = list(crypto_sections)

    # Per-tunnel blocks: render each per-tunnel segment with a single tunnel
    tunnel_dicts = []
    tunnel_blocks = []
    route_idx = 1
    for i, ti in enumerate(tunnels, start=1):
        t, route_idx = _tunnel_context(vpn_request, ti, i, base, route_idx)
        tunnel_dicts.append(t)
        block_sections = [
            {"title": "Tunnel Interface", "commands": render("tunnel_interface", {"tunnels": [t]})},
            {"title": "IKE Gateway", "commands": render("ike_gateway", {"tunnels": [t]})},
            {"title": "IPsec Tunnel", "commands": render("ipsec_tunnel", {"tunnels": [t]})},
        ]
        if vpn_request.routing_type == "bgp":
            block_sections.append(
                {"title": "BGP Peering", "commands": render("bgp_peer", {"tunnels": [t]})}
            )
        else:
            block_sections.append(
                {"title": "Static Routes", "commands": render("static_routes", {"tunnels": [t]})}
            )
        tunnel_blocks.append({
            "iface": ti,
            "label": f"tunnel.{ti.tunnel_number}",
            "peer_ip": ti.vendor_endpoint_ip or "",
            "sections": [s for s in block_sections if s["commands"]],
        })

    if tunnels:
        sections.append({
            "title": "Tunnel Interfaces",
            "commands": _concat_tunnel_category(tunnel_blocks, "Tunnel Interface"),
        })
        sections.append({
            "title": "IKE Gateways",
            "commands": _concat_tunnel_category(tunnel_blocks, "IKE Gateway"),
        })
        sections.append({
            "title": "IPsec Tunnels",
            "commands": _concat_tunnel_category(tunnel_blocks, "IPsec Tunnel"),
        })
        if vpn_request.routing_type == "bgp":
            bgp_shared = {"title": "BGP Setup (Shared)", "commands": render("bgp_setup", {})}
            shared_sections.append(bgp_shared)
            sections.append({
                "title": "Routing (BGP)",
                "commands": bgp_shared["commands"] + _concat_tunnel_category(tunnel_blocks, "BGP Peering"),
            })
        else:
            static_cmds = _concat_tunnel_category(tunnel_blocks, "Static Routes")
            if static_cmds:
                sections.append({"title": "Routing (Static)", "commands": static_cmds})
    else:
        notes.append(
            "No tunnel interfaces allocated for this site yet — tunnel, IKE gateway, "
            "IPsec tunnel and routing commands will appear after InfoSec approval."
        )

    if services:
        svc_section = {
            "title": "Service Objects",
            "commands": render("service_objects", {"services": services}),
        }
        if svc_section["commands"]:
            sections.append(svc_section)
            shared_sections.append(svc_section)

    if mappings:
        nat_rules = _nat_rules_context(mappings, tunnels, base)
        nat_section = {
            "title": "NAT Policy",
            "commands": render("nat_policy", {"nat_rules": nat_rules}),
        }
        sections.append(nat_section)
        shared_sections.append(nat_section)
        if vpn_request.routing_type == "bgp":
            bgp_nat = _bgp_nat_context(vpn_request, site, mappings, base)
            adv_section = {
                "title": "BGP NAT Advertisement",
                "commands": render("bgp_nat_advertisement", {"bgp_nat": bgp_nat}),
            }
            if adv_section["commands"]:
                sections.append(adv_section)
                shared_sections.append(adv_section)
                roles = _dr_roles(vpn_request)
                if roles and site.pk == roles[1].pk:
                    notes.append(
                        "DR secondary: inbound NAT addresses are advertised with "
                        f"AS-path prepend ×{DR_PREPEND_COUNT} so the primary "
                        f"({roles[0]}) is preferred."
                    )
    else:
        notes.append(
            "No NAT mappings allocated for this site yet — NAT IPs are assigned "
            "at Network approval."
        )

    if flows:
        security_rules = _security_rules_context(
            vpn_request, flows, mappings, service_names, base
        )
        security_section = {
            "title": "Security Policy",
            "commands": render("security_policy", {"security_rules": security_rules}),
        }
        sections.append(security_section)
        shared_sections.append(security_section)

        if any(_flow_service(f, service_names)[1] for f in flows):
            notes.append(
                "A flow combines ICMP with TCP/UDP — its security rule uses "
                "service 'any' (custom service objects can't express ICMP), so "
                "the port restriction is relaxed. Tighten it with an "
                "application-based rule if needed."
            )

    for error in dict.fromkeys(segment_errors):
        notes.insert(0, f"{error} — using the built-in default for that segment.")

    if vpn_request.auth_method == "psk":
        notes.append(f"Replace {PSK_PLACEHOLDER} with the agreed pre-shared key before commit.")
    notes.append(
        f"Assumes external interface {UNTRUST_INTERFACE}, inside interface "
        f"{INSIDE_INTERFACE}, zones {TRUST_ZONE}/{VPN_ZONE} and virtual router "
        f"'{VIRTUAL_ROUTER}' — adjust to site conventions."
    )
    if vpn_request.routing_type == "static" and not _parse_vendor_cidrs(vpn_request):
        notes.append("Static routing selected but no vendor CIDRs entered — no routes generated.")

    return {
        "site": site,
        "supported": True,
        "reason": "",
        "sections": [s for s in sections if s["commands"]],
        "shared_sections": [s for s in shared_sections if s["commands"]],
        "tunnels": tunnel_blocks,
        "notes": notes,
    }


def generate_panos_config(vpn_request):
    """
    Generate per-site PAN-OS set commands for a VPN request.

    Returns a list of site config dicts (one per distinct endpoint site):
    {site, supported, reason, sections: [{title, commands}], notes: [str]}.
    """
    # Honor the authoritative our-side endpoint count — a single-side request
    # never emits a config for a stale Site 2 (mirrors NAT/tunnel allocation).
    configs = [
        generate_site_config(vpn_request, site)
        for site in endpoint_sites(vpn_request)
    ]

    # Object names ({ref}-gw1, {ref}-vpn1, …) restart per site. If both sites
    # push into the same Panorama template, the second paste would silently
    # overwrite the first — warn loudly.
    templates = [
        cfg["site"].template_name
        for cfg in configs
        if cfg["supported"] and _is_panorama(cfg["site"]) and cfg["site"].template_name
    ]
    if len(templates) > 1 and len(set(templates)) < len(templates):
        for cfg in configs:
            if cfg["supported"]:
                cfg["notes"].insert(0, (
                    "Both endpoint sites share Panorama template "
                    f"'{templates[0]}' — gateway/tunnel/peer/route object names "
                    "collide between the sites. Deploy only one site's commands "
                    "per template, or rename objects before pushing."
                ))
    return configs


def config_as_text(site_config):
    """Flatten one site's sections into paste-ready CLI text (no comment lines)."""
    blocks = []
    for section in site_config["sections"]:
        blocks.append("\n".join(section["commands"]))
    return "\n\n".join(blocks)
