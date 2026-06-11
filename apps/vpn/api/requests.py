from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.vpn.models import VpnRequest


EDITABLE_STATUSES = ("draft", "infosec_changes_requested", "network_changes_requested")


def can_edit_request(req, user):
    """The requester (or an admin, on their behalf) may edit drafts and changes-requested requests."""
    if req.status not in EDITABLE_STATUSES:
        return False
    return req.requester_id == user.pk or user.is_admin_role


def serialize_request_summary(req, user=None):
    return {
        "id": req.pk,
        "reference_number": req.reference_number,
        "title": req.title,
        "vendor_name": req.vendor.name if req.vendor else "",
        "status": req.status,
        "status_display": req.get_status_display(),
        "created_at": req.created_at.isoformat(),
        "updated_at": req.updated_at.isoformat(),
        "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
        "requester": req.requester.get_full_name() or req.requester.username,
        "can_edit": can_edit_request(req, user) if user is not None else False,
    }


def serialize_request_detail(req):
    summary = serialize_request_summary(req)
    summary.update({
        "purpose": req.purpose,
        "directionality": req.directionality,
        "data_description": req.data_description,
        "data_classification": req.data_classification,
        "vendor_endpoints_count": req.vendor_endpoints_count,
        "topology_type": req.topology_type,
        "vendor_endpoint_1_ip": req.vendor_endpoint_1_ip or "",
        "vendor_endpoint_2_ip": req.vendor_endpoint_2_ip or "",
        "ike_version": req.ike_version,
        "auth_method": req.auth_method,
        "ike_encryption": req.ike_encryption,
        "ike_integrity": req.ike_integrity,
        "routing_type": req.routing_type,
        "nat_supported": req.nat_supported,
        "flow_count": req.flows.count(),
        "application_names": list(req.applications.values_list("name", flat=True)),
        "nat_mappings": serialize_nat_mappings(req),
    })
    return summary


def serialize_nat_mappings(req):
    """Serialize the NAT mappings allocated for a request, grouped per endpoint."""
    mappings = req.nat_mappings.select_related("site", "nat_pool")
    return [
        {
            "id": m.pk,
            "site": str(m.site),
            "site_code": m.site.code,
            "direction": m.direction,
            "direction_display": m.get_direction_display(),
            "nat_address": m.nat_address,
            "real_address": m.real_address,
            "pool": m.nat_pool.cidr if m.nat_pool else "",
            "description": m.description,
        }
        for m in mappings
    ]


@login_required
@require_http_methods(["GET"])
def request_list(request):
    """List VPN requests filtered by role/ownership."""
    qs = VpnRequest.objects.select_related("vendor", "requester")

    # Filters
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)

    scope = request.GET.get("scope", "mine")
    if scope == "mine":
        qs = qs.filter(requester=request.user)
    # 'all' scope shows everything (for admins)

    requests_data = [serialize_request_summary(r, user=request.user) for r in qs[:100]]
    return JsonResponse({"requests": requests_data})


@login_required
@require_http_methods(["GET"])
def request_detail(request, pk):
    """Get detailed VPN request data."""
    try:
        vpn_req = VpnRequest.objects.select_related("vendor", "requester").get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    return JsonResponse(serialize_request_detail(vpn_req))
