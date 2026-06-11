import json
import logging
import random

import netaddr
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import TunnelAddressPool
from apps.vpn.models.tunnel import TunnelInterface

logger = logging.getLogger(__name__)


def compute_tunnel_list(vpn_request):
    """
    Compute the list of tunnels needed based on topology.

    Returns list of dicts: [{"site": Site, "vendor_ep_ip": str, "index": int}, ...]
    """
    site1 = vpn_request.our_endpoint_1_site
    site2 = vpn_request.our_endpoint_2_site
    ep1_ip = vpn_request.vendor_endpoint_1_ip or ""
    ep2_ip = vpn_request.vendor_endpoint_2_ip or ""
    count = vpn_request.vendor_endpoints_count
    topo = vpn_request.topology_type

    tunnels = []
    idx = 0

    if count == 1:
        # Both our sites connect to vendor EP1
        if site1:
            tunnels.append({"site": site1, "vendor_ep_ip": ep1_ip, "index": idx})
            idx += 1
        if site2:
            tunnels.append({"site": site2, "vendor_ep_ip": ep1_ip, "index": idx})
            idx += 1
    elif count == 2 and topo == "bow_tie":
        # All four cross-connections
        if site1:
            tunnels.append({"site": site1, "vendor_ep_ip": ep1_ip, "index": idx})
            idx += 1
            tunnels.append({"site": site1, "vendor_ep_ip": ep2_ip, "index": idx})
            idx += 1
        if site2:
            tunnels.append({"site": site2, "vendor_ep_ip": ep1_ip, "index": idx})
            idx += 1
            tunnels.append({"site": site2, "vendor_ep_ip": ep2_ip, "index": idx})
            idx += 1
    else:
        # Matched pairs (or default for 2 endpoints)
        if site1:
            tunnels.append({"site": site1, "vendor_ep_ip": ep1_ip, "index": idx})
            idx += 1
        if site2:
            tunnels.append({"site": site2, "vendor_ep_ip": ep2_ip, "index": idx})
            idx += 1

    return tunnels


def _next_available_tunnel_number(site):
    """Return the next available tunnel interface number for a site."""
    start = site.tunnel_interface_start
    end = site.tunnel_interface_end

    if start is None or end is None:
        raise ValidationError(
            f"Site {site.code} does not have a tunnel interface range configured."
        )

    used = set(
        TunnelInterface.objects.filter(site=site).values_list("tunnel_number", flat=True)
    )

    for num in range(start, end + 1):
        if num not in used:
            return num

    raise ValidationError(
        f"Tunnel interface range exhausted for site {site.code} ({start}-{end})."
    )


def _allocate_from_pool(site):
    """
    Allocate the next available /30 from the site's tunnel address pools.

    Returns (local_ip, remote_ip, subnet_cidr, pool).
    """
    pools = TunnelAddressPool.objects.filter(site=site, is_active=True).order_by("pk")
    if not pools.exists():
        raise ValidationError(
            f"No active tunnel address pools configured for site {site.code}."
        )

    # Collect all existing /30 allocations on this site
    used_subnets = set(
        TunnelInterface.objects.filter(site=site)
        .exclude(subnet_cidr="")
        .values_list("subnet_cidr", flat=True)
    )

    for pool in pools:
        try:
            parent = netaddr.IPNetwork(pool.cidr)
        except (netaddr.AddrFormatError, ValueError):
            continue

        for subnet in parent.subnet(30):
            cidr_str = str(subnet)
            if cidr_str not in used_subnets:
                hosts = list(subnet.iter_hosts())
                return str(hosts[0]), str(hosts[1]), cidr_str, pool

    raise ValidationError(
        f"All tunnel address pools exhausted for site {site.code}."
    )


def _allocate_apipa(site):
    """
    Allocate a random unused APIPA /30 for a site.

    Returns (local_ip, remote_ip, subnet_cidr).
    """
    # Collect existing APIPA allocations on this site
    used_subnets = set(
        TunnelInterface.objects.filter(site=site, subnet_cidr__startswith="169.254.")
        .values_list("subnet_cidr", flat=True)
    )

    # Build candidates: 169.254.1.0/30 through 169.254.254.252/30
    candidates = []
    for second_octet in range(1, 255):
        for fourth_octet in range(0, 256, 4):
            cidr_str = f"169.254.{second_octet}.{fourth_octet}/30"
            if cidr_str not in used_subnets:
                candidates.append(cidr_str)

    if not candidates:
        raise ValidationError(
            f"APIPA address space exhausted for site {site.code}."
        )

    chosen = random.choice(candidates)
    subnet = netaddr.IPNetwork(chosen)
    hosts = list(subnet.iter_hosts())
    return str(hosts[0]), str(hosts[1]), chosen


@transaction.atomic
def allocate_tunnel_interfaces(vpn_request):
    """
    Main entry point: allocate tunnel interfaces for a VPN request.

    Idempotent — if allocations already exist, returns without changes.
    """
    if vpn_request.tunnel_interfaces.exists():
        return

    tunnel_specs = compute_tunnel_list(vpn_request)
    assignment = vpn_request.tunnel_ip_assignment

    # Parse mutual IPs if needed
    mutual_ips = []
    if assignment == "mutual":
        raw = vpn_request.mutual_tunnel_ips
        if raw:
            try:
                mutual_ips = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                mutual_ips = []

    for spec in tunnel_specs:
        site = spec["site"]
        tunnel_number = _next_available_tunnel_number(site)

        local_ip = None
        remote_ip = None
        subnet_cidr = ""
        pool = None

        if assignment == "we_assign":
            local_ip, remote_ip, subnet_cidr, pool = _allocate_from_pool(site)
        elif assignment == "apipa":
            local_ip, remote_ip, subnet_cidr = _allocate_apipa(site)
        elif assignment == "mutual":
            idx = spec["index"]
            if idx < len(mutual_ips):
                entry = mutual_ips[idx]
                local_ip = entry.get("local_ip") or None
                remote_ip = entry.get("remote_ip") or None

        TunnelInterface.objects.create(
            vpn_request=vpn_request,
            site=site,
            tunnel_number=tunnel_number,
            local_ip=local_ip,
            remote_ip=remote_ip,
            subnet_cidr=subnet_cidr,
            address_pool=pool,
            vendor_endpoint_ip=spec["vendor_ep_ip"] or None,
        )

        logger.info(
            "%s: assigned tunnel.%d @ %s — local=%s remote=%s subnet=%s vendor_ep=%s (method=%s)",
            vpn_request.reference_number,
            tunnel_number,
            site.code,
            local_ip or "n/a",
            remote_ip or "n/a",
            subnet_cidr or "n/a",
            spec["vendor_ep_ip"] or "n/a",
            assignment,
        )

    logger.info(
        "%s: allocated %d tunnel interfaces total",
        vpn_request.reference_number,
        len(tunnel_specs),
    )
