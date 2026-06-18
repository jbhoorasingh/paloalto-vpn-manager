import logging

import netaddr
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.core.models import DrPeer, NatDirection, NatPool, NatPoolScope
from apps.vpn.models.flow import is_rfc1918
from apps.vpn.models.nat import NatMapping

logger = logging.getLogger(__name__)


def _directions_for(vpn_request):
    """Map a request's directionality to the NAT directions it needs."""
    directionality = vpn_request.directionality
    if directionality == "we_initiate":
        return [NatDirection.OUTBOUND]
    if directionality == "vendor_initiates":
        return [NatDirection.INBOUND]
    if directionality == "both":
        return [NatDirection.OUTBOUND, NatDirection.INBOUND]
    # Unknown/blank — default to outbound so something is provisioned.
    return [NatDirection.OUTBOUND]


def directions_for_flow(flow, vpn_request):
    """
    NAT directions a single flow needs.

    The flow's own direction is authoritative — it identifies who initiates
    and therefore which boundary NAT pool (inbound vs outbound) the mapping
    is carved from. Flows without an explicit direction (legacy rows) fall
    back to the request-level directionality.
    """
    if flow.direction:
        return [NatDirection(flow.direction)]
    return _directions_for(vpn_request)


def endpoint_sites(vpn_request):
    """
    The distinct endpoint sites (firewalls) that participate, honoring the
    explicit our-side endpoint count. A count of 1 means a single firewall even
    if a stale Site 2 is still set; a count of 2 includes both — a DR pair that
    draws from the shared NAT pool.
    """
    candidates = [vpn_request.our_endpoint_1_site]
    if vpn_request.our_endpoints_count == 2:
        candidates.append(vpn_request.our_endpoint_2_site)
    sites = []
    for site in candidates:
        if site and site not in sites:
            sites.append(site)
    return sites


def _next_available_nat_address(site, direction, prefixlen, dr_peer=None):
    """
    Carve the next free block of size ``prefixlen`` from the active NAT pools
    for the given direction.

    A ``site`` means that site's specific pools (single-site requests);
    ``site=None`` with a ``dr_peer`` means the peer's shared pools — the same
    address is provisioned at both DR endpoints, so used addresses are checked
    across ALL sites.

    Returns (nat_address_cidr, pool).
    """
    if site is None:
        pools = NatPool.objects.filter(
            scope=NatPoolScope.SHARED, dr_peer=dr_peer, direction=direction,
            is_active=True,
        ).order_by("pk")
        if not pools.exists():
            peer_name = dr_peer.name if dr_peer else "the DR peer"
            raise ValidationError(
                f"No active shared {direction} NAT pools configured for "
                f"DR peer '{peer_name}'."
            )
        used_qs = NatMapping.objects.filter(direction=direction)
    else:
        pools = NatPool.objects.filter(
            site=site, scope=NatPoolScope.SITE, direction=direction, is_active=True
        ).order_by("pk")
        if not pools.exists():
            raise ValidationError(
                f"No active {direction} NAT pools configured for site {site.code}."
            )
        used_qs = NatMapping.objects.filter(site=site, direction=direction)

    # Expand already-allocated addresses to the set of individual IPs they
    # cover so we never hand out an overlap.
    used_ips = netaddr.IPSet()
    for addr in used_qs.exclude(nat_address="").values_list("nat_address", flat=True):
        try:
            used_ips.add(netaddr.IPNetwork(addr))
        except (netaddr.AddrFormatError, ValueError):
            continue

    for pool in pools:
        try:
            parent = netaddr.IPNetwork(pool.cidr)
        except (netaddr.AddrFormatError, ValueError):
            continue
        if parent.prefixlen > prefixlen:
            # Pool is smaller than the block we need; skip it.
            continue

        for subnet in parent.subnet(prefixlen):
            if not (used_ips & netaddr.IPSet([subnet])):
                return str(subnet), pool

    where = "shared (DR)" if site is None else f"site {site.code}"
    raise ValidationError(
        f"{direction.capitalize()} NAT pools exhausted for {where} "
        f"(need a /{prefixlen})."
    )


def compute_nat_specs(vpn_request):
    """
    Build the list of NAT mappings needed for a request.

    One spec per (traffic flow × flow direction), listing the endpoint
    site(s) it provisions. Two-site requests are DR pairs: ONE NAT address is
    carved from the shared pools and provisioned at BOTH endpoints, so a
    tunnel failure at one site fails over to the same address at the other.
    Single-site requests draw from that site's specific pools.

    Each flow's own direction decides which NAT pool (inbound vs outbound) it
    draws from; legacy flows without a direction fall back to the
    request-level directionality.

    Multiple flows that target the SAME destination in the same direction share
    ONE NAT address — NAT is per-destination and protocol-agnostic, so a single
    DNAT/SNAT pair covers every flow to that host. Specs are therefore grouped
    by (direction, real_address), each carrying the list of flows it serves.

    Only private (RFC-1918) destinations are NAT'd — validation forces those
    to /32 hosts, giving one-to-one mappings. Globally-unique (public)
    destinations are reachable as-is and get no mapping. ``real_address`` is
    the flow's destination — the real vendor host for outbound, the real
    internal service for inbound.

    Returns list of dicts: {sites, shared, direction, real_address, prefixlen,
    flows, flow}. ``flow`` is a representative (first) flow for back-compat.
    """
    sites = endpoint_sites(vpn_request)
    shared = len(sites) > 1
    flows = list(vpn_request.flows.all())

    # Group flows by (direction, real_address); preserve first-seen order.
    groups = {}
    order = []
    for flow in flows:
        real = flow.destination_cidr
        if not real:
            continue
        # Globally-unique destination — no boundary NAT required.
        if not is_rfc1918(real):
            continue
        for direction in directions_for_flow(flow, vpn_request):
            key = (direction, real)
            if key not in groups:
                groups[key] = []
                order.append(key)
            groups[key].append(flow)

    specs = []
    for direction, real in order:
        group_flows = groups[(direction, real)]
        try:
            prefixlen = netaddr.IPNetwork(real).prefixlen
        except (netaddr.AddrFormatError, ValueError):
            prefixlen = 32
        specs.append({
            "sites": sites,
            "shared": shared,
            "direction": direction,
            "real_address": real,
            "prefixlen": prefixlen,
            "flows": group_flows,
            "flow": group_flows[0],
        })
    return specs


@transaction.atomic
def allocate_nat_mappings(vpn_request):
    """
    Allocate inbound/outbound NAT mappings for a VPN request from the endpoint
    NAT pools.

    Idempotent — if mappings already exist, returns without changes.
    """
    if vpn_request.nat_mappings.exists():
        return

    specs = compute_nat_specs(vpn_request)
    created = 0

    # Two-site requests must match a configured DR peer — that peer's shared
    # pools own the NAT addressing for the pair.
    dr_peer = None
    if specs and specs[0]["shared"]:
        site_a, site_b = specs[0]["sites"][0], specs[0]["sites"][1]
        dr_peer = DrPeer.for_sites(site_a, site_b)
        if dr_peer is None:
            raise ValidationError(
                f"Sites {site_a.code} and {site_b.code} are not configured as a "
                "DR peer — create the DR peer (and its shared NAT pools) under "
                "Address Pools first."
            )

    for spec in specs:
        # DR pairs carve once from the peer's shared pools and provision the
        # same address at every endpoint; single-site requests use site pools.
        pool_site = None if spec["shared"] else spec["sites"][0]
        nat_address, pool = _next_available_nat_address(
            pool_site, spec["direction"], spec["prefixlen"], dr_peer=dr_peer
        )

        # One mapping covers every flow to this destination; record the
        # distinct flow descriptions so the intent isn't lost. Cap at the
        # column width — create() skips validation, and Postgres rejects
        # over-length values (SQLite would silently accept them).
        descriptions = [f.description for f in spec["flows"] if f.description]
        description = "; ".join(dict.fromkeys(descriptions))
        max_len = NatMapping._meta.get_field("description").max_length
        if len(description) > max_len:
            description = description[: max_len - 1] + "…"

        for site in spec["sites"]:
            NatMapping.objects.create(
                vpn_request=vpn_request,
                site=site,
                direction=spec["direction"],
                nat_pool=pool,
                nat_address=nat_address,
                real_address=spec["real_address"],
                traffic_flow=spec["flow"],
                description=description,
            )
            created += 1

            logger.info(
                "%s: NAT %s mapping %s → %s @ %s (pool %s%s)",
                vpn_request.reference_number,
                spec["direction"],
                nat_address,
                spec["real_address"],
                site.code,
                pool.cidr if pool else "n/a",
                ", DR-shared" if spec["shared"] else "",
            )

    logger.info(
        "%s: allocated %d NAT mappings total",
        vpn_request.reference_number,
        created,
    )
