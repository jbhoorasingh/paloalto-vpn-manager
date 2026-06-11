import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from apps.vpn.models import Vendor, VendorContact


@login_required
@require_http_methods(["GET"])
def vendor_list(request):
    """List/search vendors."""
    qs = Vendor.objects.filter(status=Vendor.Status.ACTIVE)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(name__icontains=q)

    vendors = [
        {
            "id": v.id,
            "name": v.name,
            "domain": v.domain,
            "support_email": v.support_email,
        }
        for v in qs[:50]
    ]
    return JsonResponse({"vendors": vendors})


@login_required
@require_http_methods(["POST"])
def vendor_create(request):
    """Create a vendor inline from the wizard."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    name = data.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Vendor name is required"}, status=400)

    vendor = Vendor.objects.create(
        name=name,
        domain=data.get("domain", ""),
        support_email=data.get("support_email", ""),
        support_phone=data.get("support_phone", ""),
        created_by=request.user,
    )
    return JsonResponse({
        "id": vendor.id,
        "name": vendor.name,
        "domain": vendor.domain,
    }, status=201)


@login_required
@require_http_methods(["GET"])
def vendor_contacts(request, pk):
    """List contacts for a vendor."""
    try:
        vendor = Vendor.objects.get(pk=pk)
    except Vendor.DoesNotExist:
        return JsonResponse({"error": "Vendor not found"}, status=404)

    contacts = [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "role": c.role,
            "is_primary": c.is_primary,
        }
        for c in vendor.contacts.all()
    ]
    return JsonResponse({"contacts": contacts})
