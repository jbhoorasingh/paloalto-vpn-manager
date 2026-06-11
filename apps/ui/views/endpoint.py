from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import Site, TunnelAddressPool


@login_required
def endpoint_list_view(request):
    q = request.GET.get("q", "")
    endpoints = Site.objects.all()
    if q:
        endpoints = endpoints.filter(name__icontains=q)
    return render(request, "endpoint/list.html", {
        "nav_active": "endpoint-list",
        "endpoints": endpoints,
        "q": q,
    })


def _sync_tunnel_pools(site, raw_cidrs):
    """Sync tunnel address pools from a newline-separated CIDR string."""
    new_cidrs = {c.strip() for c in raw_cidrs.splitlines() if c.strip()}
    existing = {p.cidr: p for p in site.tunnel_address_pools.all()}

    # Remove pools no longer listed
    for cidr, pool in existing.items():
        if cidr not in new_cidrs:
            pool.delete()

    # Add new pools
    for cidr in new_cidrs:
        if cidr not in existing:
            TunnelAddressPool.objects.get_or_create(site=site, cidr=cidr)


@login_required
def endpoint_create_view(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip()
        if name and code:
            site = Site.objects.create(
                name=name,
                code=code,
                location=request.POST.get("location", ""),
                datacenter=request.POST.get("datacenter", ""),
                public_ip=request.POST.get("public_ip", "").strip() or None,
                bgp_asn=request.POST.get("bgp_asn", "").strip() or None,
                device_brand=request.POST.get("device_brand", ""),
                management_type=request.POST.get("management_type", ""),
                management_platform=request.POST.get("management_platform", ""),
                device_group=request.POST.get("device_group", ""),
                template_name=request.POST.get("template_name", ""),
                tunnel_interface_start=request.POST.get("tunnel_interface_start", "").strip() or None,
                tunnel_interface_end=request.POST.get("tunnel_interface_end", "").strip() or None,
                is_active="is_active" in request.POST,
            )
            raw_pools = request.POST.get("tunnel_address_pools", "")
            _sync_tunnel_pools(site, raw_pools)
            return redirect("ui:endpoint-list")
    return render(request, "endpoint/form.html", {
        "nav_active": "endpoint-list",
        "form_title": "Add Endpoint",
        "device_brands": Site.DeviceBrand.choices,
        "management_types": Site.ManagementType.choices,
    })


@login_required
def endpoint_edit_view(request, pk):
    endpoint = get_object_or_404(Site, pk=pk)
    if request.method == "POST":
        endpoint.name = request.POST.get("name", endpoint.name).strip()
        endpoint.code = request.POST.get("code", endpoint.code).strip()
        endpoint.location = request.POST.get("location", endpoint.location)
        endpoint.datacenter = request.POST.get("datacenter", endpoint.datacenter)
        endpoint.public_ip = request.POST.get("public_ip", "").strip() or None
        endpoint.bgp_asn = request.POST.get("bgp_asn", "").strip() or None
        endpoint.device_brand = request.POST.get("device_brand", "")
        endpoint.management_type = request.POST.get("management_type", "")
        endpoint.management_platform = request.POST.get("management_platform", "")
        endpoint.device_group = request.POST.get("device_group", "")
        endpoint.template_name = request.POST.get("template_name", "")
        endpoint.tunnel_interface_start = request.POST.get("tunnel_interface_start", "").strip() or None
        endpoint.tunnel_interface_end = request.POST.get("tunnel_interface_end", "").strip() or None
        endpoint.is_active = "is_active" in request.POST
        endpoint.save()
        raw_pools = request.POST.get("tunnel_address_pools", "")
        _sync_tunnel_pools(endpoint, raw_pools)
        return redirect("ui:endpoint-list")

    tunnel_pools = "\n".join(
        endpoint.tunnel_address_pools.values_list("cidr", flat=True)
    )
    return render(request, "endpoint/form.html", {
        "nav_active": "endpoint-list",
        "form_title": "Edit Endpoint",
        "endpoint": endpoint,
        "device_brands": Site.DeviceBrand.choices,
        "management_types": Site.ManagementType.choices,
        "tunnel_pools": tunnel_pools,
    })
