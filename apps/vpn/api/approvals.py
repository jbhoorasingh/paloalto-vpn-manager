import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.vpn.api.requests import serialize_request_summary
from apps.vpn.models import ApprovalRecord, VpnRequest
from apps.vpn.services.workflow import (
    approve_infosec,
    approve_network,
    reject_request,
    request_infosec_changes,
    request_network_changes,
)


@login_required
@require_http_methods(["POST"])
def approve_infosec_view(request, pk):
    """InfoSec approver approves a submitted request."""
    if not request.user.is_infosec_approver:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        vpn_req = VpnRequest.objects.select_related("vendor", "requester").get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    comments = body.get("comments", "")

    try:
        approve_infosec(vpn_req, request.user, comments)
    except ValidationError as e:
        errors = e.messages if hasattr(e, "messages") else [str(e)]
        return JsonResponse({"error": errors[0]}, status=400)

    return JsonResponse({
        "ok": True,
        "status": vpn_req.status,
        "reference_number": vpn_req.reference_number,
    })


@login_required
@require_http_methods(["POST"])
def request_infosec_changes_view(request, pk):
    """InfoSec approver requests changes on a submitted request."""
    if not request.user.is_infosec_approver:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        vpn_req = VpnRequest.objects.select_related("vendor", "requester").get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    comments = body.get("comments", "")

    try:
        request_infosec_changes(vpn_req, request.user, comments)
    except ValidationError as e:
        errors = e.messages if hasattr(e, "messages") else [str(e)]
        return JsonResponse({"error": errors[0]}, status=400)

    return JsonResponse({
        "ok": True,
        "status": vpn_req.status,
        "reference_number": vpn_req.reference_number,
    })


@login_required
@require_http_methods(["POST"])
def approve_network_view(request, pk):
    """Network approver approves an InfoSec-approved request; NAT IPs are assigned here."""
    if not request.user.is_network_approver:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        vpn_req = VpnRequest.objects.select_related("vendor", "requester").get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    comments = body.get("comments", "")

    try:
        approve_network(vpn_req, request.user, comments)
    except ValidationError as e:
        errors = e.messages if hasattr(e, "messages") else [str(e)]
        return JsonResponse({"error": errors[0]}, status=400)

    return JsonResponse({
        "ok": True,
        "status": vpn_req.status,
        "reference_number": vpn_req.reference_number,
        "nat_warning": getattr(vpn_req, "nat_allocation_error", None),
    })


@login_required
@require_http_methods(["POST"])
def request_network_changes_view(request, pk):
    """Network approver requests changes on an InfoSec-approved request."""
    if not request.user.is_network_approver:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        vpn_req = VpnRequest.objects.select_related("vendor", "requester").get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    comments = body.get("comments", "")

    try:
        request_network_changes(vpn_req, request.user, comments)
    except ValidationError as e:
        errors = e.messages if hasattr(e, "messages") else [str(e)]
        return JsonResponse({"error": errors[0]}, status=400)

    return JsonResponse({
        "ok": True,
        "status": vpn_req.status,
        "reference_number": vpn_req.reference_number,
    })


@login_required
@require_http_methods(["POST"])
def reject_view(request, pk):
    """InfoSec approver rejects a request."""
    if not request.user.is_infosec_approver:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        vpn_req = VpnRequest.objects.select_related("vendor", "requester").get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}

    comments = body.get("comments", "")

    try:
        reject_request(vpn_req, request.user, comments)
    except ValidationError as e:
        errors = e.messages if hasattr(e, "messages") else [str(e)]
        return JsonResponse({"error": errors[0]}, status=400)

    return JsonResponse({
        "ok": True,
        "status": vpn_req.status,
        "reference_number": vpn_req.reference_number,
    })


# Statuses in which NAT (re-)allocation is allowed — network approval onwards.
NAT_ALLOCATABLE_STATUSES = (
    "network_approved", "scheduled", "deploy_ready", "deployed", "active",
)


@login_required
@require_http_methods(["POST"])
def allocate_nat_view(request, pk):
    """
    (Re-)run NAT allocation for an approved request — used when the automatic
    allocation at network approval failed (e.g. missing pools) and the pools
    have since been fixed.
    """
    if not request.user.is_network_approver:
        return JsonResponse({"error": "Permission denied"}, status=403)

    try:
        vpn_req = VpnRequest.objects.get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    if vpn_req.status not in NAT_ALLOCATABLE_STATUSES:
        return JsonResponse(
            {"error": "NAT can only be allocated once the request is network approved."},
            status=400,
        )

    from apps.vpn.services.nat import allocate_nat_mappings

    try:
        allocate_nat_mappings(vpn_req)
    except ValidationError as e:
        msg = "; ".join(e.messages) if hasattr(e, "messages") else str(e)
        return JsonResponse({"error": msg}, status=400)

    return JsonResponse({"ok": True, "mappings": vpn_req.nat_mappings.count()})


@login_required
@require_http_methods(["GET"])
def approval_queue(request):
    """List requests awaiting the caller's review stage(s)."""
    statuses = []
    if request.user.is_infosec_approver:
        statuses.append("submitted")
    if request.user.is_network_approver:
        statuses.append("infosec_approved")
    if not statuses:
        return JsonResponse({"error": "Permission denied"}, status=403)

    qs = VpnRequest.objects.select_related("vendor", "requester").filter(
        status__in=statuses
    )
    requests_data = [serialize_request_summary(r, user=request.user) for r in qs[:100]]
    return JsonResponse({"requests": requests_data})


@login_required
@require_http_methods(["GET"])
def approval_history(request, pk):
    """List approval records for a specific request."""
    try:
        vpn_req = VpnRequest.objects.get(pk=pk)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    records = vpn_req.approval_records.select_related("reviewer").all()
    data = [
        {
            "id": r.pk,
            "stage": r.stage,
            "stage_display": r.get_stage_display(),
            "decision": r.decision,
            "decision_display": r.get_decision_display(),
            "reviewer": r.reviewer.get_full_name() or r.reviewer.username,
            "comments": r.comments,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]
    return JsonResponse({"approvals": data})
