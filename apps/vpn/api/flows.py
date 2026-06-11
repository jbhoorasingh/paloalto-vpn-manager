import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.vpn.models import TrafficFlow, VpnRequest


def serialize_flow(flow):
    return {
        "id": flow.pk,
        "source_cidr": flow.source_cidr,
        "destination_cidr": flow.destination_cidr,
        "direction": flow.direction,
        "protocol": flow.protocol,
        "destination_ports": flow.destination_ports,
        "application_id": flow.application_id,
        "description": flow.description,
        "order": flow.order,
    }


def _default_direction(vpn_request):
    """Default a new flow's direction from the request's directionality."""
    if vpn_request.directionality == "vendor_initiates":
        return "inbound"
    return "outbound"


@login_required
@require_http_methods(["GET", "POST"])
def flow_list_create(request, request_pk):
    """List flows or add a new flow to a VPN request."""
    if request.method == "GET":
        # Any authenticated user can view flows
        try:
            vpn_req = VpnRequest.objects.get(pk=request_pk)
        except VpnRequest.DoesNotExist:
            return JsonResponse({"error": "Request not found"}, status=404)
        flows = [serialize_flow(f) for f in vpn_req.flows.all()]
        return JsonResponse({"flows": flows})

    # POST — only the requester can add flows
    try:
        vpn_req = VpnRequest.objects.get(pk=request_pk, requester=request.user)
    except VpnRequest.DoesNotExist:
        return JsonResponse({"error": "Request not found"}, status=404)

    # POST — create
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    flow = TrafficFlow(
        vpn_request=vpn_req,
        source_cidr=data.get("source_cidr", ""),
        destination_cidr=data.get("destination_cidr", ""),
        direction=data.get("direction") or _default_direction(vpn_req),
        protocol=data.get("protocol", "tcp"),
        destination_ports=data.get("destination_ports", ""),
        application_id=data.get("application_id") or None,
        description=data.get("description", ""),
        order=data.get("order", 0),
    )
    try:
        flow.full_clean()
    except ValidationError as e:
        return JsonResponse({"errors": e.message_dict}, status=400)

    flow.save()
    return JsonResponse(serialize_flow(flow), status=201)


@login_required
@require_http_methods(["PATCH", "DELETE"])
def flow_detail(request, pk):
    """Edit or delete a traffic flow."""
    try:
        flow = TrafficFlow.objects.select_related("vpn_request").get(pk=pk)
    except TrafficFlow.DoesNotExist:
        return JsonResponse({"error": "Flow not found"}, status=404)

    if flow.vpn_request.requester != request.user:
        return JsonResponse({"error": "Permission denied"}, status=403)

    if request.method == "DELETE":
        flow.delete()
        return JsonResponse({"ok": True})

    # PATCH
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    for field in ("source_cidr", "destination_cidr", "direction", "protocol",
                  "destination_ports", "description", "order"):
        if field in data:
            setattr(flow, field, data[field])
    if "application_id" in data:
        flow.application_id = data["application_id"] or None

    try:
        flow.full_clean()
    except ValidationError as e:
        return JsonResponse({"errors": e.message_dict}, status=400)

    flow.save()
    return JsonResponse(serialize_flow(flow))
