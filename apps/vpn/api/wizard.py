import ipaddress
import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.vpn.models import Application, VpnRequest, VpnRequestApplication
from apps.vpn.services.workflow import resubmit_request, submit_request

EDITABLE_STATUSES = ("draft", "infosec_changes_requested", "network_changes_requested")


def serialize_request(req):
    """Serialize a VpnRequest to a dict for JSON response."""
    return {
        "id": req.pk,
        "reference_number": req.reference_number,
        "status": req.status,
        "vendor_id": req.vendor_id,
        "vendor_name": req.vendor.name if req.vendor else "",
        "title": req.title,
        "purpose": req.purpose,
        "directionality": req.directionality,
        "data_description": req.data_description,
        "data_classification": req.data_classification,
        "application_ids": list(req.applications.values_list("pk", flat=True)),
        "vendor_endpoints_count": req.vendor_endpoints_count,
        "topology_type": req.topology_type,
        "vendor_endpoint_1_ip": req.vendor_endpoint_1_ip or "",
        "vendor_endpoint_2_ip": req.vendor_endpoint_2_ip or "",
        "our_endpoint_1_site_id": req.our_endpoint_1_site_id,
        "our_endpoint_2_site_id": req.our_endpoint_2_site_id,
        "ike_version": req.ike_version,
        "auth_method": req.auth_method,
        "ike_encryption": req.ike_encryption,
        "ike_integrity": req.ike_integrity,
        "ike_dh_group": req.ike_dh_group,
        "ike_lifetime": req.ike_lifetime,
        "dpd_enabled": req.dpd_enabled,
        "ipsec_encryption": req.ipsec_encryption,
        "ipsec_integrity": req.ipsec_integrity,
        "ipsec_pfs_group": req.ipsec_pfs_group,
        "ipsec_lifetime": req.ipsec_lifetime,
        "tunnel_mode": req.tunnel_mode,
        "routing_type": req.routing_type,
        "vendor_cidrs": req.vendor_cidrs,
        "bgp_local_asn": req.bgp_local_asn,
        "bgp_remote_asn": req.bgp_remote_asn,
        "bgp_remote_asn_2": req.bgp_remote_asn_2,
        "bgp_peer_ip_local": req.bgp_peer_ip_local or "",
        "bgp_peer_ip_remote": req.bgp_peer_ip_remote or "",
        "bgp_auth_enabled": req.bgp_auth_enabled,
        "tunnel_ip_assignment": req.tunnel_ip_assignment,
        "mutual_tunnel_ips": req.mutual_tunnel_ips,
        "nat_supported": req.nat_supported,
        "nat_exception_reason": req.nat_exception_reason,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "updated_at": req.updated_at.isoformat() if req.updated_at else None,
        "submitted_at": req.submitted_at.isoformat() if req.submitted_at else None,
    }


@login_required
@require_http_methods(["GET"])
def wizard_load(request, pk):
    """Load full draft data for the wizard."""
    try:
        vpn_req = VpnRequest.objects.select_related("vendor").get(pk=pk, requester=request.user)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    data = serialize_request(vpn_req)

    # Include reviewer comments when in a changes-requested state
    if vpn_req.status in ("infosec_changes_requested", "network_changes_requested"):
        latest_review = (
            vpn_req.approval_records
            .filter(decision="changes_requested")
            .order_by("-created_at")
            .select_related("reviewer")
            .first()
        )
        if latest_review:
            data["reviewer_comments"] = latest_review.comments
            data["reviewer_name"] = (
                latest_review.reviewer.get_full_name()
                or latest_review.reviewer.username
            )
            data["review_stage"] = latest_review.get_stage_display()

    return JsonResponse(data)


@login_required
@require_http_methods(["POST"])
def wizard_create(request):
    """Create a new draft VPN request."""
    vpn_req = VpnRequest.objects.create(requester=request.user)
    return JsonResponse(serialize_request(vpn_req), status=201)


# Mapping of step number to the VpnRequest fields that step can update
STEP_FIELDS = {
    1: ["vendor_id"],
    2: ["title", "purpose", "directionality", "data_description", "data_classification"],
    3: [
        "vendor_endpoints_count", "topology_type",
        "vendor_endpoint_1_ip", "vendor_endpoint_2_ip",
        "our_endpoint_1_site_id", "our_endpoint_2_site_id",
    ],
    4: [
        "ike_version", "auth_method", "ike_encryption", "ike_integrity",
        "ike_dh_group", "ike_lifetime", "dpd_enabled",
        "ipsec_encryption", "ipsec_integrity", "ipsec_pfs_group",
        "ipsec_lifetime", "tunnel_mode",
    ],
    5: [
        "routing_type", "vendor_cidrs", "bgp_local_asn", "bgp_remote_asn",
        "bgp_remote_asn_2", "bgp_peer_ip_local", "bgp_peer_ip_remote",
        "bgp_auth_enabled", "tunnel_ip_assignment", "mutual_tunnel_ips",
        "nat_supported", "nat_exception_reason",
    ],
    6: [],  # Flows — managed via flows API
    7: [],  # Review — no fields to save
}

# Integer fields that need type coercion
INT_FIELDS = {
    "vendor_endpoints_count", "ike_lifetime", "ipsec_lifetime",
    "bgp_local_asn", "bgp_remote_asn", "bgp_remote_asn_2", "vendor_id",
    "our_endpoint_1_site_id", "our_endpoint_2_site_id",
}
ASN_FIELDS = {"bgp_local_asn", "bgp_remote_asn", "bgp_remote_asn_2"}
BOOL_FIELDS = {"dpd_enabled", "bgp_auth_enabled"}
NULLABLE_BOOL_FIELDS = {"nat_supported"}


@login_required
@require_http_methods(["PATCH"])
def wizard_save_step(request, pk, step):
    """Save data for a specific wizard step (autosave)."""
    if step not in STEP_FIELDS:
        return JsonResponse({"error": f"Invalid step: {step}"}, status=400)

    try:
        vpn_req = VpnRequest.objects.get(pk=pk, requester=request.user, status__in=EDITABLE_STATUSES)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Editable request not found"}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    allowed_fields = STEP_FIELDS[step]
    update_fields = []
    validation_errors = {}

    for field in allowed_fields:
        if field in data:
            value = data[field]
            # Type coercion
            if field in INT_FIELDS:
                if value not in (None, "", "null"):
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        validation_errors[field] = "Must be a valid number."
                        continue
                    if field in ASN_FIELDS and not (1 <= value <= 4294967295):
                        validation_errors[field] = "ASN must be between 1 and 4,294,967,295."
                        continue
                else:
                    value = None
            elif field in BOOL_FIELDS:
                value = bool(value)
            elif field in NULLABLE_BOOL_FIELDS:
                if value is None or value == "null" or value == "":
                    value = None
                else:
                    value = bool(value)
            # Empty strings for IP fields should be None; validate non-empty IPs
            if field.endswith("_ip"):
                if value in ("", None):
                    value = None
                else:
                    try:
                        ipaddress.ip_address(value)
                    except ValueError:
                        validation_errors[field] = f"'{value}' is not a valid IP address."
                        continue
            setattr(vpn_req, field, value)
            update_fields.append(field)

    if validation_errors:
        return JsonResponse({"error": "Validation failed", "field_errors": validation_errors}, status=400)

    # Handle application_ids for step 2
    if step == 2 and "application_ids" in data:
        app_ids = data["application_ids"]
        if isinstance(app_ids, list):
            VpnRequestApplication.objects.filter(vpn_request=vpn_req).delete()
            for app_id in app_ids:
                try:
                    app = Application.objects.get(pk=app_id)
                    VpnRequestApplication.objects.create(vpn_request=vpn_req, application=app)
                except Application.DoesNotExist:
                    pass

    if update_fields:
        from django.utils import timezone
        update_dict = {f: getattr(vpn_req, f) for f in update_fields}
        update_dict["updated_at"] = timezone.now()
        VpnRequest.objects.filter(pk=vpn_req.pk).update(**update_dict)

    return JsonResponse({"ok": True})


@login_required
@require_http_methods(["POST"])
def wizard_submit(request, pk):
    """Validate all fields and submit the request (FSM transition)."""
    try:
        vpn_req = VpnRequest.objects.select_related("vendor").get(
            pk=pk, requester=request.user, status__in=EDITABLE_STATUSES
        )
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Editable request not found"}, status=404)

    try:
        if vpn_req.status == "draft":
            submit_request(vpn_req)
        else:
            resubmit_request(vpn_req)
    except ValidationError as e:
        errors = e.messages if hasattr(e, "messages") else [str(e)]
        return JsonResponse({"errors": errors}, status=400)

    return JsonResponse({"ok": True, "status": vpn_req.status, "reference_number": vpn_req.reference_number})
