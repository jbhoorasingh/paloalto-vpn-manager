import logging

from django.core.exceptions import ValidationError
from django_fsm import can_proceed

from apps.vpn.models.approval import ApprovalRecord

logger = logging.getLogger(__name__)


def submit_request(vpn_request):
    """Validate and submit a VPN request (draft → submitted)."""
    if not can_proceed(vpn_request.submit):
        raise ValidationError("Cannot submit request from its current status.")
    vpn_request.submit()
    vpn_request.save()
    return vpn_request


def approve_infosec(vpn_request, reviewer, comments=""):
    """Approve a request at the InfoSec stage (submitted → infosec_approved)."""
    if not can_proceed(vpn_request.approve_infosec):
        raise ValidationError("Cannot approve this request from its current status.")
    vpn_request.approve_infosec()
    vpn_request.save()
    ApprovalRecord.objects.create(
        vpn_request=vpn_request,
        reviewer=reviewer,
        stage=ApprovalRecord.Stage.INFOSEC,
        decision=ApprovalRecord.Decision.APPROVED,
        comments=comments,
    )

    # Allocate tunnel interfaces after InfoSec approval
    from apps.vpn.services.allocation import allocate_tunnel_interfaces

    try:
        allocate_tunnel_interfaces(vpn_request)
    except (ValidationError, Exception):
        logger.exception(
            "Tunnel allocation failed for %s", vpn_request.reference_number
        )

    # Allocate inbound/outbound NAT mappings from the endpoint NAT pools
    from apps.vpn.services.nat import allocate_nat_mappings

    try:
        allocate_nat_mappings(vpn_request)
    except (ValidationError, Exception):
        logger.exception(
            "NAT allocation failed for %s", vpn_request.reference_number
        )

    return vpn_request


def request_infosec_changes(vpn_request, reviewer, comments=""):
    """Request changes at the InfoSec stage (submitted → infosec_changes_requested)."""
    if not can_proceed(vpn_request.request_infosec_changes):
        raise ValidationError("Cannot request changes from this request's current status.")
    vpn_request.request_infosec_changes()
    vpn_request.save()
    ApprovalRecord.objects.create(
        vpn_request=vpn_request,
        reviewer=reviewer,
        stage=ApprovalRecord.Stage.INFOSEC,
        decision=ApprovalRecord.Decision.CHANGES_REQUESTED,
        comments=comments,
    )
    return vpn_request


def resubmit_request(vpn_request):
    """Re-validate and resubmit a VPN request after changes were requested."""
    errors = vpn_request.validate_for_submission()
    if errors:
        raise ValidationError(errors)

    if vpn_request.status == "infosec_changes_requested":
        if not can_proceed(vpn_request.resubmit_from_infosec):
            raise ValidationError("Cannot resubmit from its current status.")
        vpn_request.resubmit_from_infosec()
    elif vpn_request.status == "network_changes_requested":
        if not can_proceed(vpn_request.resubmit_from_network):
            raise ValidationError("Cannot resubmit from its current status.")
        vpn_request.resubmit_from_network()
    else:
        raise ValidationError("Request is not in a changes-requested state.")

    vpn_request.save()
    return vpn_request


def reject_request(vpn_request, reviewer, comments=""):
    """Reject a request (submitted|infosec_approved → rejected)."""
    if not can_proceed(vpn_request.reject):
        raise ValidationError("Cannot reject this request from its current status.")
    # Determine stage based on current status
    stage = (
        ApprovalRecord.Stage.NETWORK
        if vpn_request.status == "infosec_approved"
        else ApprovalRecord.Stage.INFOSEC
    )
    vpn_request.reject()
    vpn_request.save()
    ApprovalRecord.objects.create(
        vpn_request=vpn_request,
        reviewer=reviewer,
        stage=stage,
        decision=ApprovalRecord.Decision.REJECTED,
        comments=comments,
    )
    return vpn_request
