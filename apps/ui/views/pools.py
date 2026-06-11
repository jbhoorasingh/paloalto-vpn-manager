import netaddr
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import NatDirection, NatPool, Site, TunnelAddressPool
from apps.vpn.models.tunnel import TunnelInterface


def _nat_pool_usage(pool):
    """Return (used_ips, total_ips, percent) for a NAT pool."""
    try:
        total = netaddr.IPNetwork(pool.cidr).size
    except (netaddr.AddrFormatError, ValueError):
        return 0, 0, 0
    used = 0
    for addr in pool.mappings.values_list("nat_address", flat=True):
        try:
            used += netaddr.IPNetwork(addr).size
        except (netaddr.AddrFormatError, ValueError):
            continue
    percent = round(used / total * 100) if total else 0
    return used, total, percent


def _tunnel_pool_usage(pool):
    """Return (used /30s, total /30s, percent) for a tunnel address pool."""
    try:
        network = netaddr.IPNetwork(pool.cidr)
    except (netaddr.AddrFormatError, ValueError):
        return 0, 0, 0
    total = 2 ** (30 - network.prefixlen) if network.prefixlen <= 30 else 0
    used = TunnelInterface.objects.filter(address_pool=pool).count()
    percent = round(used / total * 100) if total else 0
    return used, total, percent


@login_required
def pool_list_view(request):
    site_id = request.GET.get("site", "")

    nat_pools = NatPool.objects.select_related("site")
    tunnel_pools = TunnelAddressPool.objects.select_related("site")
    if site_id:
        nat_pools = nat_pools.filter(site_id=site_id)
        tunnel_pools = tunnel_pools.filter(site_id=site_id)

    nat_rows = []
    for pool in nat_pools:
        used, total, percent = _nat_pool_usage(pool)
        nat_rows.append({"pool": pool, "used": used, "total": total, "percent": percent})

    tunnel_rows = []
    for pool in tunnel_pools:
        used, total, percent = _tunnel_pool_usage(pool)
        tunnel_rows.append({"pool": pool, "used": used, "total": total, "percent": percent})

    return render(request, "pools/list.html", {
        "nav_active": "pool-list",
        "nat_rows": nat_rows,
        "tunnel_rows": tunnel_rows,
        "sites": Site.objects.all(),
        "selected_site": site_id,
    })


def _pool_form_context(form_title, pool=None, errors=None, form_data=None):
    return {
        "nav_active": "pool-list",
        "form_title": form_title,
        "pool": pool,
        "errors": errors or {},
        "form_data": form_data or {},
        "sites": Site.objects.filter(is_active=True),
        "directions": NatDirection.choices,
    }


def _save_nat_pool(request, pool):
    pool.site_id = request.POST.get("site") or None
    pool.direction = request.POST.get("direction", "")
    pool.cidr = request.POST.get("cidr", "").strip()
    pool.description = request.POST.get("description", "").strip()
    pool.is_active = "is_active" in request.POST
    pool.full_clean()
    pool.save()


@login_required
def nat_pool_create_view(request):
    if request.method == "POST":
        pool = NatPool()
        try:
            _save_nat_pool(request, pool)
            return redirect("ui:pool-list")
        except ValidationError as e:
            return render(request, "pools/nat_form.html", _pool_form_context(
                "Add NAT Pool", errors=e.message_dict, form_data=request.POST,
            ))
    return render(request, "pools/nat_form.html", _pool_form_context("Add NAT Pool"))


@login_required
def nat_pool_edit_view(request, pk):
    pool = get_object_or_404(NatPool, pk=pk)
    if request.method == "POST":
        try:
            _save_nat_pool(request, pool)
            return redirect("ui:pool-list")
        except ValidationError as e:
            return render(request, "pools/nat_form.html", _pool_form_context(
                "Edit NAT Pool", pool=pool, errors=e.message_dict, form_data=request.POST,
            ))
    return render(request, "pools/nat_form.html", _pool_form_context("Edit NAT Pool", pool=pool))


@login_required
def nat_pool_delete_view(request, pk):
    pool = get_object_or_404(NatPool, pk=pk)
    if request.method == "POST":
        pool.delete()
    return redirect("ui:pool-list")


def _save_tunnel_pool(request, pool):
    pool.site_id = request.POST.get("site") or None
    pool.cidr = request.POST.get("cidr", "").strip()
    pool.description = request.POST.get("description", "").strip()
    pool.is_active = "is_active" in request.POST
    pool.full_clean()
    pool.save()


@login_required
def tunnel_pool_create_view(request):
    if request.method == "POST":
        pool = TunnelAddressPool()
        try:
            _save_tunnel_pool(request, pool)
            return redirect("ui:pool-list")
        except ValidationError as e:
            return render(request, "pools/tunnel_form.html", _pool_form_context(
                "Add Tunnel Address Pool", errors=e.message_dict, form_data=request.POST,
            ))
    return render(request, "pools/tunnel_form.html", _pool_form_context("Add Tunnel Address Pool"))


@login_required
def tunnel_pool_edit_view(request, pk):
    pool = get_object_or_404(TunnelAddressPool, pk=pk)
    if request.method == "POST":
        try:
            _save_tunnel_pool(request, pool)
            return redirect("ui:pool-list")
        except ValidationError as e:
            return render(request, "pools/tunnel_form.html", _pool_form_context(
                "Edit Tunnel Address Pool", pool=pool, errors=e.message_dict, form_data=request.POST,
            ))
    return render(request, "pools/tunnel_form.html", _pool_form_context(
        "Edit Tunnel Address Pool", pool=pool,
    ))


@login_required
def tunnel_pool_delete_view(request, pk):
    pool = get_object_or_404(TunnelAddressPool, pk=pk)
    if request.method == "POST":
        pool.delete()
    return redirect("ui:pool-list")


@login_required
def tunnel_interface_list_view(request):
    site_id = request.GET.get("site", "")
    q = request.GET.get("q", "")

    interfaces = TunnelInterface.objects.select_related(
        "site", "address_pool", "vpn_request", "vpn_request__vendor"
    )
    if site_id:
        interfaces = interfaces.filter(site_id=site_id)
    if q:
        interfaces = interfaces.filter(vpn_request__reference_number__icontains=q)

    return render(request, "pools/tunnel_interfaces.html", {
        "nav_active": "tunnel-interface-list",
        "interfaces": interfaces,
        "sites": Site.objects.all(),
        "selected_site": site_id,
        "q": q,
    })


@login_required
def tunnel_interface_edit_view(request, pk):
    iface = get_object_or_404(
        TunnelInterface.objects.select_related("site", "vpn_request"), pk=pk
    )
    errors = {}
    if request.method == "POST":
        iface.local_ip = request.POST.get("local_ip", "").strip() or None
        iface.remote_ip = request.POST.get("remote_ip", "").strip() or None
        iface.subnet_cidr = request.POST.get("subnet_cidr", "").strip()
        iface.vendor_endpoint_ip = request.POST.get("vendor_endpoint_ip", "").strip() or None
        try:
            iface.full_clean()
            iface.save()
            return redirect("ui:tunnel-interface-list")
        except ValidationError as e:
            errors = e.message_dict
    return render(request, "pools/tunnel_interface_form.html", {
        "nav_active": "tunnel-interface-list",
        "iface": iface,
        "errors": errors,
    })


@login_required
def tunnel_interface_release_view(request, pk):
    iface = get_object_or_404(TunnelInterface, pk=pk)
    if request.method == "POST":
        iface.delete()
    return redirect("ui:tunnel-interface-list")
