import json

from auditlog.models import LogEntry
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.vpn.models import VpnRequest
from apps.vpn.models.flow import TrafficFlow
from apps.vpn.services.config_render import rendered_site_configs

# Human-readable labels for VpnRequest fields in audit log
FIELD_LABELS = {
    "title": "Title",
    "purpose": "Purpose",
    "vendor": "Vendor",
    "directionality": "Directionality",
    "data_description": "Data Description",
    "data_classification": "Data Classification",
    "vendor_endpoints_count": "Vendor Endpoints Count",
    "topology_type": "Topology Type",
    "vendor_endpoint_1_ip": "Vendor Endpoint 1 IP",
    "vendor_endpoint_2_ip": "Vendor Endpoint 2 IP",
    "our_endpoint_1_site": "Our Endpoint 1 Site",
    "our_endpoint_2_site": "Our Endpoint 2 Site",
    "ike_version": "IKE Version",
    "auth_method": "Auth Method",
    "ike_encryption": "IKE Encryption",
    "ike_integrity": "IKE Integrity",
    "ike_dh_group": "IKE DH Group",
    "ike_lifetime": "IKE Lifetime",
    "dpd_enabled": "DPD Enabled",
    "ipsec_encryption": "IPsec Encryption",
    "ipsec_integrity": "IPsec Integrity",
    "ipsec_pfs_group": "IPsec PFS Group",
    "ipsec_lifetime": "IPsec Lifetime",
    "tunnel_mode": "Tunnel Mode",
    "routing_type": "Routing Type",
    "vendor_cidrs": "Vendor CIDRs",
    "bgp_local_asn": "BGP Local ASN",
    "bgp_remote_asn": "BGP Remote ASN (EP1)",
    "bgp_remote_asn_2": "BGP Remote ASN (EP2)",
    "bgp_peer_ip_local": "BGP Peer IP Local",
    "bgp_peer_ip_remote": "BGP Peer IP Remote",
    "bgp_auth_enabled": "BGP Authentication",
    "tunnel_ip_assignment": "Tunnel IP Assignment",
    "nat_supported": "NAT Supported",
    "nat_exception_reason": "NAT Exception Reason",
    "config_template_override": "Config Template Override",
    "status": "Status",
    "submitted_at": "Submitted At",
    "reference_number": "Reference Number",
    "requester": "Requester",
}

# Fields to skip in the request snapshot display
SNAPSHOT_EXCLUDE = {
    "id", "created_at", "updated_at", "status", "submitted_at",
    "reference_number", "requester", "config_template_override",
}


def _build_audit_timeline(vpn_request, approval_records):
    """Build a unified, chronologically-sorted audit timeline."""
    events = []

    # 1. Created event
    events.append({
        "type": "created",
        "timestamp": vpn_request.created_at,
        "actor": vpn_request.requester,
        "summary": "created this request",
        "icon": "plus",
        "color": "slate",
    })

    # 2. Submitted event
    if vpn_request.submitted_at:
        events.append({
            "type": "submitted",
            "timestamp": vpn_request.submitted_at,
            "actor": vpn_request.requester,
            "summary": "submitted this request for approval",
            "icon": "send",
            "color": "blue",
        })

    # 3. Approval records (approved, changes_requested, rejected)
    for record in approval_records:
        if record.decision == "approved":
            summary = f"approved this request ({record.get_stage_display()} review)"
            icon = "check"
            color = "emerald"
        elif record.decision == "changes_requested":
            summary = f"requested changes ({record.get_stage_display()} review)"
            icon = "edit"
            color = "amber"
        elif record.decision == "rejected":
            summary = f"rejected this request ({record.get_stage_display()} review)"
            icon = "x"
            color = "red"
        else:
            summary = f"{record.get_decision_display()} ({record.get_stage_display()} review)"
            icon = "info"
            color = "slate"

        events.append({
            "type": "approval",
            "timestamp": record.created_at,
            "actor": record.reviewer,
            "summary": summary,
            "icon": icon,
            "color": color,
            "comments": record.comments,
        })

    # 4. Auditlog field change entries (UPDATE actions) for VpnRequest
    # Skip status/submitted_at — already covered by approval and submitted events
    SKIP_FIELDS = {"updated_at", "id", "created_at", "status", "submitted_at"}
    ct = ContentType.objects.get_for_model(VpnRequest)
    log_entries = LogEntry.objects.filter(
        content_type=ct,
        object_pk=str(vpn_request.pk),
        action=LogEntry.Action.UPDATE,
    ).select_related("actor").order_by("timestamp")

    for entry in log_entries:
        changes = entry.changes or {}
        filtered = {}
        for field, values in changes.items():
            if field in SKIP_FIELDS:
                continue
            label = FIELD_LABELS.get(field, field.replace("_", " ").title())
            old_val = values[0] if isinstance(values, list) and len(values) > 0 else ""
            new_val = values[1] if isinstance(values, list) and len(values) > 1 else ""
            filtered[field] = {
                "label": label,
                "old": old_val if old_val not in (None, "") else "(empty)",
                "new": new_val if new_val not in (None, "") else "(empty)",
            }

        if filtered:
            field_count = len(filtered)
            events.append({
                "type": "field_change",
                "timestamp": entry.timestamp,
                "actor": entry.actor,
                "summary": f"updated {field_count} field{'s' if field_count != 1 else ''} on request",
                "icon": "pencil",
                "color": "indigo",
                "changes": filtered,
            })

    # 5. Auditlog entries for TrafficFlow (create, update, delete)
    FLOW_LABELS = {
        "source_cidr": "Source CIDR",
        "destination_cidr": "Destination CIDR",
        "direction": "Direction",
        "protocol": "Protocol",
        "destination_ports": "Destination Ports",
        "description": "Description",
        "application": "Application",
        "vpn_request": "VPN Request",
    }
    FLOW_SKIP = {"id", "order", "vpn_request"}
    flow_ct = ContentType.objects.get_for_model(TrafficFlow)
    flow_pks = [str(pk) for pk in vpn_request.flows.values_list("pk", flat=True)]
    if flow_pks:
        flow_entries = LogEntry.objects.filter(
            content_type=flow_ct,
            object_pk__in=flow_pks,
        ).select_related("actor").order_by("timestamp")

        for entry in flow_entries:
            changes = entry.changes or {}
            if entry.action == LogEntry.Action.CREATE:
                events.append({
                    "type": "flow_created",
                    "timestamp": entry.timestamp,
                    "actor": entry.actor,
                    "summary": f"added traffic flow {entry.object_repr}",
                    "icon": "plus",
                    "color": "blue",
                })
            elif entry.action == LogEntry.Action.DELETE:
                events.append({
                    "type": "flow_deleted",
                    "timestamp": entry.timestamp,
                    "actor": entry.actor,
                    "summary": f"removed traffic flow {entry.object_repr}",
                    "icon": "x",
                    "color": "red",
                })
            elif entry.action == LogEntry.Action.UPDATE:
                filtered = {}
                for field, values in changes.items():
                    if field in FLOW_SKIP:
                        continue
                    label = FLOW_LABELS.get(field, field.replace("_", " ").title())
                    old_val = values[0] if isinstance(values, list) and len(values) > 0 else ""
                    new_val = values[1] if isinstance(values, list) and len(values) > 1 else ""
                    filtered[field] = {
                        "label": label,
                        "old": old_val if old_val not in (None, "") else "(empty)",
                        "new": new_val if new_val not in (None, "") else "(empty)",
                    }
                if filtered:
                    field_count = len(filtered)
                    events.append({
                        "type": "flow_change",
                        "timestamp": entry.timestamp,
                        "actor": entry.actor,
                        "summary": f"updated traffic flow {entry.object_repr} ({field_count} field{'s' if field_count != 1 else ''})",
                        "icon": "pencil",
                        "color": "indigo",
                        "changes": filtered,
                    })

    # 6. Tunnel interface allocation events
    tunnel_interfaces = vpn_request.tunnel_interfaces.select_related("site", "address_pool")
    for ti in tunnel_interfaces:
        ip_detail = ""
        if ti.local_ip and ti.remote_ip:
            ip_detail = f" — {ti.subnet_cidr or ''} (local {ti.local_ip}, remote {ti.remote_ip})"
        elif ti.local_ip:
            ip_detail = f" — local {ti.local_ip}"

        events.append({
            "type": "tunnel_allocated",
            "timestamp": ti.created_at,
            "actor": None,
            "summary": f"allocated tunnel.{ti.tunnel_number} on {ti.site.name} ({ti.site.code}){ip_detail}",
            "icon": "tunnel",
            "color": "teal",
            "allocation": {
                "tunnel_number": ti.tunnel_number,
                "site": str(ti.site),
                "local_ip": ti.local_ip or "--",
                "remote_ip": ti.remote_ip or "--",
                "subnet": ti.subnet_cidr or "--",
                "vendor_ep": ti.vendor_endpoint_ip or "--",
                "pool": str(ti.address_pool) if ti.address_pool else "--",
            },
        })

    # 7. NAT mapping allocation events
    nat_mappings = vpn_request.nat_mappings.select_related("site", "nat_pool")
    for nm in nat_mappings:
        arrow = "→" if nm.direction == "outbound" else "←"
        events.append({
            "type": "nat_allocated",
            "timestamp": nm.created_at,
            "actor": None,
            "summary": (
                f"allocated {nm.get_direction_display()} NAT {nm.nat_address} "
                f"{arrow} {nm.real_address} on {nm.site.name} ({nm.site.code})"
            ),
            "icon": "nat",
            "color": "purple",
            "nat": {
                "direction": nm.get_direction_display(),
                "site": str(nm.site),
                "nat_address": nm.nat_address,
                "real_address": nm.real_address,
                "pool": nm.nat_pool.cidr if nm.nat_pool else "--",
            },
        })

    # Sort chronologically
    events.sort(key=lambda e: e["timestamp"])
    return events


def _build_request_snapshot(vpn_request):
    """Build a list of (label, value) pairs for the current request data."""
    snapshot = []
    for field in VpnRequest._meta.get_fields():
        if not hasattr(field, "name") or field.name in SNAPSHOT_EXCLUDE:
            continue
        # Skip reverse relations and M2M
        if field.many_to_many or field.one_to_many:
            continue
        name = field.name
        label = FIELD_LABELS.get(name, name.replace("_", " ").title())
        try:
            display_method = getattr(vpn_request, f"get_{name}_display", None)
            if display_method and callable(display_method):
                value = display_method()
            else:
                value = getattr(vpn_request, name, "")
        except Exception:
            value = ""
        if value is None or value == "":
            value = "(empty)"
        snapshot.append({"label": label, "value": str(value)})
    return snapshot


def _build_nat_packet_walks(vpn_request, tunnel_interfaces, nat_mappings):
    """
    One packet-walk per unique NAT translation: what the sender targets (the
    published NAT address), the header rewrites at our firewall (destination
    NAT plus symmetric source NAT), and what the far side sees.

    DR pairs produce one walk covering both firewalls (same NAT address).
    """
    tunnels_by_site = {}
    for ti in tunnel_interfaces:
        tunnels_by_site.setdefault(ti.site_id, []).append(ti)

    groups = {}
    for nm in nat_mappings:
        key = (nm.direction, nm.nat_address, nm.real_address, nm.traffic_flow_id)
        groups.setdefault(key, []).append(nm)

    walks = []
    for (direction, nat_address, real_address, _flow_id), group in groups.items():
        flow = group[0].traffic_flow
        source = flow.source_cidr if flow else "any"
        protocol = flow.protocol.upper() if flow else "ANY"
        ports = (flow.destination_ports or "any") if flow else "any"
        if protocol in ("ICMP", "ANY"):
            ports = ""

        firewalls = []
        for nm in group:
            snats = []
            if direction == "outbound":
                for ti in tunnels_by_site.get(nm.site_id, []):
                    if ti.local_ip:
                        snats.append({"label": f"tunnel.{ti.tunnel_number}", "ip": ti.local_ip})
            firewalls.append({"site": nm.site, "snats": snats})

        # What the receiving side sees as the packet's source
        if direction == "outbound":
            first_snat = next(
                (s for fw in firewalls for s in fw["snats"]), None
            )
            seen_source = first_snat["ip"] if first_snat else "tunnel interface IP"
        else:
            seen_source = "firewall inside IP"

        walks.append({
            "direction": direction,
            "is_outbound": direction == "outbound",
            "nat_address": nat_address,
            "real_address": real_address,
            "source": source,
            "protocol": protocol,
            "ports": ports,
            "firewalls": firewalls,
            "dr_shared": len(group) > 1,
            "seen_source": seen_source,
        })

    walks.sort(key=lambda w: (w["direction"], w["nat_address"]))
    return walks


@login_required
def request_list_view(request):
    scope = request.GET.get("scope", "mine")
    qs = VpnRequest.objects.select_related("vendor", "requester")
    if scope == "mine":
        qs = qs.filter(requester=request.user)

    return render(request, "vpn/request_list.html", {
        "nav_active": "my-requests",
        "requests_json": json.dumps({"scope": scope}),
    })


@login_required
def request_detail_view(request, pk):
    vpn_request = get_object_or_404(
        VpnRequest.objects.select_related("vendor", "requester"),
        pk=pk,
    )
    flows = list(vpn_request.flows.values(
        "id", "source_cidr", "destination_cidr", "direction",
        "protocol", "destination_ports", "description",
    ))
    applications = list(vpn_request.applications.values_list("name", flat=True))
    approval_records = vpn_request.approval_records.select_related("reviewer").all()

    can_approve_infosec = (
        request.user.is_infosec_approver
        and vpn_request.status == "submitted"
    )
    can_approve_network = (
        request.user.is_network_approver
        and vpn_request.status == "infosec_approved"
    )

    topology_props = {
        "vendorEndpointsCount": vpn_request.vendor_endpoints_count,
        "topologyType": vpn_request.topology_type,
        "vendorEndpoint1Ip": vpn_request.vendor_endpoint_1_ip or "",
        "vendorEndpoint2Ip": vpn_request.vendor_endpoint_2_ip or "",
        "ourSite1Name": str(vpn_request.our_endpoint_1_site) if vpn_request.our_endpoint_1_site else "",
        "ourSite2Name": str(vpn_request.our_endpoint_2_site) if vpn_request.our_endpoint_2_site else "",
    }

    workflow_json = json.dumps({"currentStatus": vpn_request.status})

    # Build unified audit timeline
    audit_timeline = _build_audit_timeline(vpn_request, approval_records)
    request_snapshot = _build_request_snapshot(vpn_request)

    # Tunnel allocations
    tunnel_interfaces = vpn_request.tunnel_interfaces.select_related("site", "address_pool")
    # NAT mappings (inbound/outbound) per endpoint
    nat_mappings = vpn_request.nat_mappings.select_related("site", "nat_pool", "traffic_flow")
    allocation_count = tunnel_interfaces.count() + nat_mappings.count()
    has_allocations = allocation_count > 0

    # Why are there no NAT mappings? Distinguish "not yet", "none required"
    # (all destinations globally unique) and "allocation failed — retry".
    from apps.vpn.api.approvals import NAT_ALLOCATABLE_STATUSES
    from apps.vpn.services.nat import compute_nat_specs

    nat_stage_reached = vpn_request.status in NAT_ALLOCATABLE_STATUSES
    nat_required = False
    if not nat_mappings.exists():
        nat_required = bool(compute_nat_specs(vpn_request))
    nat_allocation_missing = nat_stage_reached and nat_required
    can_allocate_nat = nat_allocation_missing and request.user.is_network_approver

    # Packet-walk visualization of each NAT translation
    nat_packet_walks = _build_nat_packet_walks(
        vpn_request, tunnel_interfaces, nat_mappings
    )

    # PAN-OS set commands per endpoint site, rendered through the resolved
    # config template (request override → global → built-in default)
    panos_configs = rendered_site_configs(vpn_request)
    config_template_source = panos_configs[0]["template_source"] if panos_configs else "default"
    can_edit_config_template = request.user.is_network_approver

    return render(request, "vpn/request_detail.html", {
        "nav_active": "my-requests",
        "vpn_request": vpn_request,
        "flows": flows,
        "applications": applications,
        "flows_json": json.dumps({"requestId": vpn_request.pk}),
        "topology_json": json.dumps(topology_props),
        "approval_records": approval_records,
        "can_approve_infosec": can_approve_infosec,
        "can_approve_network": can_approve_network,
        "approval_actions_json": json.dumps({"requestId": vpn_request.pk}),
        "workflow_json": workflow_json,
        "audit_timeline": audit_timeline,
        "request_snapshot": request_snapshot,
        "tunnel_interfaces": tunnel_interfaces,
        "nat_mappings": nat_mappings,
        "allocation_count": allocation_count,
        "has_allocations": has_allocations,
        "nat_stage_reached": nat_stage_reached,
        "nat_required": nat_required,
        "nat_allocation_missing": nat_allocation_missing,
        "can_allocate_nat": can_allocate_nat,
        "nat_packet_walks": nat_packet_walks,
        "panos_configs": panos_configs,
        "config_template_source": config_template_source,
        "can_edit_config_template": can_edit_config_template,
    })


@login_required
def request_config_download_view(request, pk):
    """Download the rendered PAN-OS set commands as a plain-text file."""
    vpn_request = get_object_or_404(VpnRequest, pk=pk)
    site_id = request.GET.get("site")

    blocks = []
    for cfg in rendered_site_configs(vpn_request):
        if site_id and str(cfg["site"].pk) != site_id:
            continue
        if not cfg["supported"]:
            continue
        if cfg["text"]:
            blocks.append(cfg["text"].rstrip("\n"))

    body = "\n\n".join(blocks)
    if body:
        body += "\n"
    response = HttpResponse(body, content_type="text/plain; charset=utf-8")
    filename = f"{vpn_request.reference_number.lower()}-panos-set-commands.txt"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def request_delete_view(request, pk):
    vpn_request = get_object_or_404(VpnRequest, pk=pk)
    if request.method == "POST":
        vpn_request.delete()
        return redirect("ui:request-list")
    return render(request, "vpn/request_confirm_delete.html", {
        "nav_active": "my-requests",
        "vpn_request": vpn_request,
    })
