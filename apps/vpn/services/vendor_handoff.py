"""
Build a vendor-facing handoff document for a VPN request.

The handoff is rendered as a print-friendly HTML page (the user prints or saves
to PDF from the browser) — nothing is stored. It contains only what the vendor
needs to stand up their side: tunnel/BGP peering, the IKE/IPsec parameters that
must match, and the traffic flows. Internal-only details (the pre-shared key,
our internal real service addresses) are deliberately excluded — the vendor sees
the published NAT addresses, not what they translate to.
"""

from apps.vpn.services.nat import directions_for_flow, endpoint_sites
from apps.vpn.services.panos import _remote_asn_for

TBD = "TBD — pending provisioning"


def _or_tbd(value):
    return value if value not in (None, "") else TBD


def _tunnel_rows(vpn_request):
    """Per-tunnel peering: public endpoints, the /30 interface IPs, ASNs."""
    rows = []
    tunnels = (
        vpn_request.tunnel_interfaces
        .select_related("site")
        .order_by("site__code", "tunnel_number")
    )
    for ti in tunnels:
        rows.append({
            "site_code": ti.site.code,
            "site_name": ti.site.name,
            "tunnel": f"tunnel.{ti.tunnel_number}",
            "our_public_ip": _or_tbd(ti.site.public_ip),
            "vendor_public_ip": _or_tbd(ti.vendor_endpoint_ip),
            "our_inside_ip": _or_tbd(ti.local_ip),
            "vendor_inside_ip": _or_tbd(ti.remote_ip),
            "subnet": _or_tbd(ti.subnet_cidr),
            "our_asn": _or_tbd(ti.site.bgp_asn or vpn_request.bgp_local_asn),
            "vendor_asn": _or_tbd(_remote_asn_for(vpn_request, ti)),
        })
    return rows


def _crypto(vpn_request):
    return {
        "ike_version": f"IKEv{vpn_request.ike_version}",
        "auth_method": "Pre-Shared Key" if vpn_request.auth_method == "psk" else "Certificate",
        "ike_encryption": (vpn_request.ike_encryption or TBD).upper(),
        "ike_integrity": (vpn_request.ike_integrity or TBD).upper(),
        "ike_dh_group": _or_tbd(vpn_request.ike_dh_group),
        "ike_lifetime": vpn_request.ike_lifetime,
        "dpd_enabled": vpn_request.dpd_enabled,
        "ipsec_encryption": (vpn_request.ipsec_encryption or TBD).upper(),
        "ipsec_integrity": (vpn_request.ipsec_integrity or TBD).upper(),
        "ipsec_pfs_group": _or_tbd(vpn_request.ipsec_pfs_group),
        "ipsec_lifetime": vpn_request.ipsec_lifetime,
        "tunnel_mode": (vpn_request.tunnel_mode or "tunnel").title(),
    }


def _flow_rows(vpn_request):
    """
    Vendor-facing traffic flows. Inbound (vendor-initiated) destinations use our
    published NAT address (what the vendor connects to); outbound flows are shown
    as our network reaching the vendor's host. Internal real addresses are never
    exposed.
    """
    nat_by_dest_dir = {
        (nm.real_address, nm.direction): nm.nat_address
        for nm in vpn_request.nat_mappings.all()
    }
    rows = []
    for flow in vpn_request.flows.all():
        protocols = flow.protocols_display() or "ANY"
        ports = flow.destination_ports if flow.has_port_protocol and flow.destination_ports else ""
        for direction in directions_for_flow(flow, vpn_request):
            nat_addr = nat_by_dest_dir.get((flow.destination_cidr, direction))
            if direction == "inbound":
                src = flow.source_cidr or "Vendor network"
                dst = nat_addr or flow.destination_cidr or "Our service"
                initiator = "Vendor → Us"
            else:
                src = "Our network"
                dst = flow.destination_cidr or "Vendor host"
                initiator = "Us → Vendor"
            label = f"{protocols}/{ports}" if ports else protocols
            rows.append({
                "direction": direction,
                "initiator": initiator,
                "src": src,
                "dst": dst,
                "protocols": protocols,
                "ports": ports or "any",
                "label": label,
                "description": flow.description,
            })
    return rows


def _flow_diagram(flow_rows, width=560):
    """
    Pre-compute fully-resolved SVG geometry for a sources→destinations diagram
    (mirrors FlowDiagram.vue) so the print template only emits values — no
    arithmetic, no JavaScript, reliable when printed.
    """
    start_y, gap = 60, 14

    def collect(order, store, key, row):
        if row[key] not in store:
            store[row[key]] = set()
            order.append(row[key])
        if row["description"]:
            store[row[key]].add(row["description"])

    src_order, src_descs = [], {}
    dst_order, dst_descs = [], {}
    for r in flow_rows:
        collect(src_order, src_descs, "src", r)
        collect(dst_order, dst_descs, "dst", r)

    def layout(order, descs, box_x, text_x):
        items = {}
        y = start_y
        for key in order:
            lines = list(descs[key])[:2]
            height = 30 + len(lines) * 13
            items[key] = {
                "label": key,
                "box_x": box_x,
                "text_x": text_x,
                "y": y,
                "height": height,
                "label_y": y + 20,
                "desc_lines": [
                    {"text": line, "y": y + 34 + i * 13} for i, line in enumerate(lines)
                ],
            }
            y += height + gap
        return items

    sources = layout(src_order, src_descs, 10, 90)
    destinations = layout(dst_order, dst_descs, width - 170, width - 90)

    connections = []
    offsets = {}
    for r in flow_rows:
        s, d = sources[r["src"]], destinations[r["dst"]]
        src_y = s["y"] + s["height"] / 2
        dst_y = d["y"] + d["height"] / 2
        mid_y = (src_y + dst_y) / 2
        k = round(mid_y)
        off = offsets.get(k, 0)
        offsets[k] = off + 1
        label_y = mid_y + off * 16
        label_w = len(r["label"]) * 5.5 + 4
        connections.append({
            "x1": 170,
            "x2": width - 170,
            "src_y": src_y,
            "dst_y": dst_y,
            "label": r["label"],
            "rect_x": (width / 2) - label_w / 2 - 4,
            "rect_y": label_y - 10,
            "rect_w": label_w + 8,
            "text_x": width / 2,
            "text_y": label_y,
        })

    src_bottom = max((s["y"] + s["height"] for s in sources.values()), default=60)
    dst_bottom = max((d["y"] + d["height"] for d in destinations.values()), default=60)
    return {
        "width": width,
        "height": max(src_bottom, dst_bottom) + 30,
        "mid_x": width / 2,
        "right_label_x": width - 90,
        "sources": list(sources.values()),
        "destinations": list(destinations.values()),
        "connections": connections,
    }


def build_handoff_context(vpn_request):
    """Assemble the full vendor-handoff template context (plain values only)."""
    from django.utils import timezone

    is_bgp = vpn_request.routing_type == "bgp"
    tunnel_rows = _tunnel_rows(vpn_request)
    flow_rows = _flow_rows(vpn_request)

    # Published service addresses the vendor connects to (inbound NAT only).
    reachable = []
    seen = set()
    for nm in vpn_request.nat_mappings.filter(direction="inbound").order_by("nat_address"):
        if nm.nat_address not in seen:
            seen.add(nm.nat_address)
            reachable.append({"address": nm.nat_address, "description": nm.description})

    vendor_cidrs = [
        line.strip()
        for line in (vpn_request.vendor_cidrs or "").replace(",", "\n").splitlines()
        if line.strip()
    ]

    return {
        "vpn_request": vpn_request,
        "reference_number": vpn_request.reference_number,
        "title": vpn_request.title,
        "vendor_name": vpn_request.vendor.name if vpn_request.vendor else "Vendor",
        "generated_at": timezone.now(),
        "is_bgp": is_bgp,
        "routing_label": "BGP" if is_bgp else "Static",
        "tunnel_rows": tunnel_rows,
        "crypto": _crypto(vpn_request),
        "reachable": reachable,
        "vendor_cidrs": vendor_cidrs,
        "flow_rows": flow_rows,
        "diagram": _flow_diagram(flow_rows) if flow_rows else None,
    }
