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

from apps.core.models import NatDirection

from .nat import directions_for_flow

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


def _ike_crypto_section(vpn_request, site, base):
    p = _net_prefix(site)
    name = f"{base}-ike"
    path = f"{p}network ike crypto-profiles ike-crypto-profiles {name}"
    commands = []
    enc = _norm_encryption(vpn_request.ike_encryption)
    if enc:
        commands.append(f"{path} encryption {enc}")
    hsh = _norm_hash(vpn_request.ike_integrity)
    if hsh:
        commands.append(f"{path} hash {hsh}")
    dh = _norm_dh_group(vpn_request.ike_dh_group)
    if dh:
        commands.append(f"{path} dh-group {dh}")
    if vpn_request.ike_lifetime:
        commands.append(f"{path} lifetime seconds {vpn_request.ike_lifetime}")
    return {"title": "IKE Crypto Profile", "commands": commands}


def _ipsec_crypto_section(vpn_request, site, base):
    p = _net_prefix(site)
    name = f"{base}-ipsec"
    path = f"{p}network ike crypto-profiles ipsec-crypto-profiles {name}"
    commands = []
    enc = _norm_encryption(vpn_request.ipsec_encryption)
    if enc:
        commands.append(f"{path} esp encryption {enc}")
    # GCM ciphers carry their own integrity; PAN-OS requires authentication none.
    if enc and "gcm" in enc:
        commands.append(f"{path} esp authentication none")
    else:
        hsh = _norm_hash(vpn_request.ipsec_integrity)
        if hsh:
            commands.append(f"{path} esp authentication {hsh}")
    pfs = _norm_dh_group(vpn_request.ipsec_pfs_group)
    if pfs:
        commands.append(f"{path} dh-group {pfs}")
    if vpn_request.ipsec_lifetime:
        commands.append(f"{path} lifetime seconds {vpn_request.ipsec_lifetime}")
    return {"title": "IPsec Crypto Profile", "commands": commands}


def _tunnel_interface_cmds(site, ti):
    p = _net_prefix(site)
    zp = _zone_prefix(site)
    unit = f"tunnel.{ti.tunnel_number}"
    commands = [f"{p}network interface tunnel units {unit}"]
    if ti.local_ip:
        commands.append(
            f"{p}network interface tunnel units {unit} ip {ti.local_ip}/{_subnet_prefixlen(ti)}"
        )
    commands.append(f"{zp}zone {VPN_ZONE} network layer3 {unit}")
    commands.append(f"{p}network virtual-router {VIRTUAL_ROUTER} interface {unit}")
    return commands


def _ike_gateway_cmds(vpn_request, site, ti, idx, base):
    p = _net_prefix(site)
    commands = []
    ike_ver = "ikev2" if vpn_request.ike_version == "2" else "ikev1"
    gw = f"{base}-gw{idx}"
    path = f"{p}network ike gateway {gw}"
    if vpn_request.auth_method == "psk":
        commands.append(f"{path} authentication pre-shared-key key {PSK_PLACEHOLDER}")
    else:
        commands.append(f"{path} authentication certificate certificate-profile <CERT-PROFILE>")
    commands.append(f"{path} protocol version {ike_ver}")
    commands.append(f"{path} protocol {ike_ver} ike-crypto-profile {base}-ike")
    if vpn_request.dpd_enabled:
        commands.append(f"{path} protocol {ike_ver} dpd enable yes")
    commands.append(f"{path} local-address interface {UNTRUST_INTERFACE}")
    if site.public_ip:
        commands.append(f"{path} local-address ip {site.public_ip}")
    if ti.vendor_endpoint_ip:
        commands.append(f"{path} peer-address ip {ti.vendor_endpoint_ip}")
    return commands


def _ipsec_tunnel_cmds(vpn_request, site, ti, idx, base):
    p = _net_prefix(site)
    name = f"{base}-vpn{idx}"
    path = f"{p}network tunnel ipsec {name}"
    return [
        f"{path} auto-key ike-gateway {base}-gw{idx}",
        f"{path} auto-key ipsec-crypto-profile {base}-ipsec",
        f"{path} tunnel-interface tunnel.{ti.tunnel_number}",
        f"{path} anti-replay yes",
    ]


def _bgp_shared_cmds(vpn_request, site, base):
    """Site-level BGP setup shared by every tunnel peer."""
    p = _net_prefix(site)
    vr = f"{p}network virtual-router {VIRTUAL_ROUTER}"
    local_asn = site.bgp_asn or vpn_request.bgp_local_asn
    commands = [f"{vr} protocol bgp enable yes"]
    if local_asn:
        commands.append(f"{vr} protocol bgp local-as {local_asn}")
    if site.public_ip:
        commands.append(f"{vr} protocol bgp router-id {site.public_ip}")
    commands.append(f"{vr} protocol bgp peer-group {base}-pg type ebgp")
    return commands


def _bgp_peer_cmds(vpn_request, site, ti, idx, base):
    p = _net_prefix(site)
    vr = f"{p}network virtual-router {VIRTUAL_ROUTER}"
    peer_path = f"{vr} protocol bgp peer-group {base}-pg peer {base}-peer{idx}"
    commands = [f"{peer_path} enable yes"]
    remote_asn = _remote_asn_for(vpn_request, ti)
    if remote_asn:
        commands.append(f"{peer_path} peer-as {remote_asn}")
    if ti.local_ip:
        commands.append(
            f"{peer_path} local-address interface tunnel.{ti.tunnel_number} "
            f"ip {ti.local_ip}/{_subnet_prefixlen(ti)}"
        )
    else:
        commands.append(f"{peer_path} local-address interface tunnel.{ti.tunnel_number}")
    if ti.remote_ip:
        commands.append(f"{peer_path} peer-address ip {ti.remote_ip}")
    return commands


def _static_route_cmds(vpn_request, site, ti, base, start_idx):
    """Static routes steering each vendor CIDR into this tunnel."""
    p = _net_prefix(site)
    vr = f"{p}network virtual-router {VIRTUAL_ROUTER}"
    commands = []
    route_idx = start_idx
    for cidr in _parse_vendor_cidrs(vpn_request):
        path = f"{vr} routing-table ip static-route {base}-rt{route_idx}"
        commands.append(f"{path} destination {cidr}")
        commands.append(f"{path} interface tunnel.{ti.tunnel_number}")
        if ti.remote_ip:
            commands.append(f"{path} nexthop ip {ti.remote_ip}")
        route_idx += 1
    return commands, route_idx


def _tunnel_sections(vpn_request, site, ti, idx, base, route_start):
    """All per-tunnel sections for one TunnelInterface. Returns (sections, next_route_idx)."""
    sections = [
        {"title": "Tunnel Interface", "commands": _tunnel_interface_cmds(site, ti)},
        {"title": "IKE Gateway", "commands": _ike_gateway_cmds(vpn_request, site, ti, idx, base)},
        {"title": "IPsec Tunnel", "commands": _ipsec_tunnel_cmds(vpn_request, site, ti, idx, base)},
    ]
    next_route = route_start
    if vpn_request.routing_type == "bgp":
        sections.append({
            "title": "BGP Peering",
            "commands": _bgp_peer_cmds(vpn_request, site, ti, idx, base),
        })
    else:
        route_cmds, next_route = _static_route_cmds(vpn_request, site, ti, base, route_start)
        if route_cmds:
            sections.append({"title": "Static Routes", "commands": route_cmds})
    return sections, next_route


def _service_objects_section(vpn_request, site, flows, base):
    """One service object per flow that names TCP/UDP ports."""
    p = _policy_prefix(site)
    commands = []
    service_names = {}
    for i, flow in enumerate(flows, start=1):
        if flow.protocol in ("tcp", "udp") and flow.destination_ports:
            name = f"{base}-svc{i}"
            ports = flow.destination_ports.replace(" ", "")
            commands.append(f"{p}service {name} protocol {flow.protocol} port {ports}")
            service_names[flow.pk] = name
    return {"title": "Service Objects", "commands": commands}, service_names


def _nat_section(vpn_request, site, mappings, tunnels, base):
    """
    NAT rules per mapping.

    Outbound (we → vendor): one rule per tunnel — the destination NAT to the
    real vendor host plus source NAT to that tunnel's interface address, so
    return traffic always comes back through the same tunnel (symmetry).

    Inbound (vendor → us): destination NAT to the real inside address plus
    source NAT to the firewall's inside interface, so the server's replies
    return through the translating firewall (symmetry under DR).
    """
    p = _policy_prefix(site)
    rb = _rulebase(site)
    commands = []
    counters = {NatDirection.OUTBOUND: 0, NatDirection.INBOUND: 0}
    for nm in mappings:
        counters[nm.direction] = counters.get(nm.direction, 0) + 1
        idx = counters[nm.direction]
        if nm.direction == NatDirection.OUTBOUND:
            # Internal hosts target the published NAT address; the firewall
            # DNATs it to the real vendor host and SNATs to the egress tunnel.
            if tunnels:
                for ti in tunnels:
                    name = f"{base}-out{idx}-t{ti.tunnel_number}"
                    path = f"{p}{rb} nat rules {name}"
                    commands.append(f"{path} from {TRUST_ZONE}")
                    commands.append(f"{path} to {VPN_ZONE}")
                    commands.append(f"{path} to-interface tunnel.{ti.tunnel_number}")
                    commands.append(f"{path} source any")
                    commands.append(f"{path} destination {nm.nat_address}")
                    commands.append(f"{path} service any")
                    commands.append(
                        f"{path} destination-translation translated-address {nm.real_address}"
                    )
                    commands.append(
                        f"{path} source-translation dynamic-ip-and-port "
                        f"interface-address interface tunnel.{ti.tunnel_number}"
                    )
            else:
                # No tunnels allocated yet — emit the DNAT half so the intent
                # is visible; per-tunnel SNAT rules appear once tunnels exist.
                name = f"{base}-nat-out{idx}"
                path = f"{p}{rb} nat rules {name}"
                commands.append(f"{path} from {TRUST_ZONE}")
                commands.append(f"{path} to {VPN_ZONE}")
                commands.append(f"{path} source any")
                commands.append(f"{path} destination {nm.nat_address}")
                commands.append(f"{path} service any")
                commands.append(
                    f"{path} destination-translation translated-address {nm.real_address}"
                )
        else:
            # The vendor targets the published NAT address; the firewall
            # DNATs it to the real internal service and SNATs to its inside
            # interface so replies return symmetrically.
            name = f"{base}-nat-in{idx}"
            path = f"{p}{rb} nat rules {name}"
            commands.append(f"{path} from {VPN_ZONE}")
            commands.append(f"{path} to {TRUST_ZONE}")
            commands.append(f"{path} source any")
            commands.append(f"{path} destination {nm.nat_address}")
            commands.append(f"{path} service any")
            commands.append(
                f"{path} destination-translation translated-address {nm.real_address}"
            )
            commands.append(
                f"{path} source-translation dynamic-ip-and-port "
                f"interface-address interface {INSIDE_INTERFACE}"
            )
    return {"title": "NAT Policy", "commands": commands}


def _bgp_nat_advertisement_section(vpn_request, site, mappings, base):
    """
    Advertise the inbound NAT addresses to the vendor over the tunnel BGP
    peering. On a DR pair both endpoints advertise the SAME addresses; the
    secondary (endpoint 2) prepends its AS so the primary path is preferred
    and failover to the surviving site is automatic.
    """
    inbound_addrs = []
    for nm in mappings:
        if nm.direction == NatDirection.INBOUND and nm.nat_address not in inbound_addrs:
            inbound_addrs.append(nm.nat_address)
    if not inbound_addrs:
        return {"title": "BGP NAT Advertisement", "commands": []}

    p = _net_prefix(site)
    vr = f"{p}network virtual-router {VIRTUAL_ROUTER}"
    rule = f"{vr} protocol bgp policy export rules {base}-nat-adv"
    is_secondary = (
        vpn_request.our_endpoint_2_site_id == site.pk
        and vpn_request.our_endpoint_1_site_id
        and vpn_request.our_endpoint_1_site_id != site.pk
    )

    commands = [f"{rule} enable yes", f"{rule} used-by {base}-pg"]
    for addr in inbound_addrs:
        commands.append(f"{rule} match address-prefix {addr} exact yes")
    commands.append(f"{rule} action allow")
    if is_secondary:
        commands.append(
            f"{rule} action allow update as-path prepend {DR_PREPEND_COUNT}"
        )
    return {"title": "BGP NAT Advertisement", "commands": commands}


def _security_section(vpn_request, site, flows, mappings, service_names, base):
    """
    One security rule per (flow × flow direction).

    Each flow's own direction picks the zone pair; flows without one fall back
    to the request-level directionality. Destinations use the published NAT
    address when a mapping exists for the flow (PAN-OS matches pre-NAT
    addresses with post-NAT zones), otherwise the flow's real destination.
    """
    p = _policy_prefix(site)
    rb = _rulebase(site)
    commands = []
    mapping_by_flow_dir = {
        (nm.traffic_flow_id, nm.direction): nm for nm in mappings if nm.traffic_flow_id
    }
    rule_idx = 1
    for flow in flows:
        for direction in directions_for_flow(flow, vpn_request):
            nm = mapping_by_flow_dir.get((flow.pk, direction))
            destination = nm.nat_address if nm else flow.destination_cidr
            if direction == NatDirection.OUTBOUND:
                from_zone, to_zone = TRUST_ZONE, VPN_ZONE
            else:
                from_zone, to_zone = VPN_ZONE, TRUST_ZONE
            name = f"{base}-sec{rule_idx}"
            path = f"{p}{rb} security rules {name}"
            commands.append(f"{path} from {from_zone}")
            commands.append(f"{path} to {to_zone}")
            commands.append(f"{path} source {flow.source_cidr or 'any'}")
            commands.append(f"{path} destination {destination or 'any'}")
            commands.append(f"{path} application any")
            commands.append(f"{path} service {service_names.get(flow.pk, 'any')}")
            commands.append(f"{path} action allow")
            rule_idx += 1
    return {"title": "Security Policy", "commands": commands}


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

    Returns ``sections`` (the full site config flattened by category — what the
    Config tab and download render) plus a deployment-oriented split of the
    same commands: ``shared_sections`` (crypto profiles, shared BGP setup,
    service objects, NAT and security policy — applied once per site) and
    ``tunnels`` (one block per tunnel interface with its interface, IKE
    gateway, IPsec tunnel and routing commands).
    """
    base = _name_base(vpn_request)
    notes = []

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

    crypto_sections = [
        s for s in (
            _ike_crypto_section(vpn_request, site, base),
            _ipsec_crypto_section(vpn_request, site, base),
        ) if s["commands"]
    ]
    sections = list(crypto_sections)
    shared_sections = list(crypto_sections)

    tunnel_blocks = []
    route_idx = 1
    for i, ti in enumerate(tunnels, start=1):
        tunnel_section_list, route_idx = _tunnel_sections(
            vpn_request, site, ti, i, base, route_idx
        )
        tunnel_blocks.append({
            "iface": ti,
            "label": f"tunnel.{ti.tunnel_number}",
            "peer_ip": ti.vendor_endpoint_ip or "",
            "sections": [s for s in tunnel_section_list if s["commands"]],
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
            bgp_shared = {"title": "BGP Setup (Shared)", "commands": _bgp_shared_cmds(vpn_request, site, base)}
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

    svc_section, service_names = _service_objects_section(vpn_request, site, flows, base)
    if svc_section["commands"]:
        sections.append(svc_section)
        shared_sections.append(svc_section)

    if mappings:
        nat_section = _nat_section(vpn_request, site, mappings, tunnels, base)
        sections.append(nat_section)
        shared_sections.append(nat_section)
        if vpn_request.routing_type == "bgp":
            adv_section = _bgp_nat_advertisement_section(vpn_request, site, mappings, base)
            if adv_section["commands"]:
                sections.append(adv_section)
                shared_sections.append(adv_section)
                if vpn_request.our_endpoint_2_site_id == site.pk:
                    notes.append(
                        "DR secondary: inbound NAT addresses are advertised with "
                        f"AS-path prepend ×{DR_PREPEND_COUNT} so the primary "
                        f"({vpn_request.our_endpoint_1_site}) is preferred."
                    )
    else:
        notes.append(
            "No NAT mappings allocated for this site yet — NAT IPs are assigned "
            "at Network approval."
        )

    if flows:
        security_section = _security_section(
            vpn_request, site, flows, mappings, service_names, base
        )
        sections.append(security_section)
        shared_sections.append(security_section)

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
    configs = []
    seen = set()
    for site in (vpn_request.our_endpoint_1_site, vpn_request.our_endpoint_2_site):
        if site and site.pk not in seen:
            seen.add(site.pk)
            configs.append(generate_site_config(vpn_request, site))

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
