import pytest
from django.core.exceptions import ValidationError

from apps.core.models import NatPool
from apps.core.tests.factories import NatPoolFactory, SiteFactory, UserFactory
from apps.vpn.models.nat import NatMapping
from apps.vpn.services.nat import (
    _next_available_nat_address,
    allocate_nat_mappings,
    compute_nat_specs,
)
from apps.vpn.services.workflow import approve_infosec, submit_request

from .factories import ApplicationFactory, TrafficFlowFactory, VpnRequestFactory


def _make_submittable_request(**kwargs):
    app = ApplicationFactory()
    req = VpnRequestFactory(
        title="Test VPN",
        nat_supported=True,
        applications=[app],
        **kwargs,
    )
    TrafficFlowFactory(vpn_request=req)
    return req


# ── NatPool model validation ─────────────────────────────────────────


@pytest.mark.django_db
class TestNatPoolModel:
    def test_valid_pool(self):
        pool = NatPoolFactory(cidr="10.111.96.0/24")
        pool.full_clean()  # should not raise

    def test_invalid_cidr(self):
        site = SiteFactory()
        pool = NatPool(site=site, direction="outbound", cidr="not-a-cidr")
        with pytest.raises(ValidationError):
            pool.full_clean()

    def test_overlap_rejected(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        dup = NatPool(site=site, direction="inbound", cidr="10.111.96.128/25")
        with pytest.raises(ValidationError, match="Overlaps"):
            dup.full_clean()

    def test_non_overlapping_directions_ok(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        other = NatPool(site=site, direction="inbound", cidr="10.111.100.0/24")
        other.full_clean()  # disjoint range — fine


# ── _next_available_nat_address ──────────────────────────────────────


@pytest.mark.django_db
class TestNextAvailableNatAddress:
    def test_first_host_slash32(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        addr, pool = _next_available_nat_address(site, "outbound", 32)
        assert addr == "10.111.96.0/32"
        assert pool is not None

    def test_skips_used(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        req = VpnRequestFactory()
        NatMapping.objects.create(
            vpn_request=req, site=site, direction="outbound",
            nat_address="10.111.96.0/32", real_address="10.10.70.100",
        )
        addr, _ = _next_available_nat_address(site, "outbound", 32)
        assert addr == "10.111.96.1/32"

    def test_subrange_prefix_matches_flow(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        addr, _ = _next_available_nat_address(site, "outbound", 28)
        assert addr == "10.111.96.0/28"

    def test_no_pool_raises(self):
        site = SiteFactory()
        with pytest.raises(ValidationError, match="No active"):
            _next_available_nat_address(site, "outbound", 32)

    def test_exhausted_raises(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/32")
        req = VpnRequestFactory()
        NatMapping.objects.create(
            vpn_request=req, site=site, direction="outbound",
            nat_address="10.111.96.0/32", real_address="10.10.70.100",
        )
        with pytest.raises(ValidationError, match="exhausted"):
            _next_available_nat_address(site, "outbound", 32)

    def test_direction_isolated(self):
        """An outbound allocation does not consume inbound pool space."""
        site = SiteFactory()
        NatPoolFactory(site=site, direction="inbound", cidr="10.111.100.0/24")
        with pytest.raises(ValidationError, match="No active"):
            _next_available_nat_address(site, "outbound", 32)


# ── compute_nat_specs ────────────────────────────────────────────────


@pytest.mark.django_db
class TestComputeNatSpecs:
    def test_we_initiate_outbound_only(self):
        site = SiteFactory()
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.10.70.100/32")
        specs = compute_nat_specs(req)
        assert len(specs) == 1
        assert specs[0]["direction"] == "outbound"
        assert specs[0]["real_address"] == "10.10.70.100/32"
        assert specs[0]["prefixlen"] == 32

    def test_vendor_initiates_inbound_only(self):
        site = SiteFactory()
        req = VpnRequestFactory(directionality="vendor_initiates", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.108.100.0/24")
        specs = compute_nat_specs(req)
        assert len(specs) == 1
        assert specs[0]["direction"] == "inbound"
        assert specs[0]["prefixlen"] == 24

    def test_both_directions(self):
        # A "both" request carries flows of each direction; one spec per flow
        site = SiteFactory()
        req = VpnRequestFactory(directionality="both", our_endpoint_1_site=site)
        TrafficFlowFactory(
            vpn_request=req, direction="outbound", destination_cidr="172.16.5.10/32"
        )
        TrafficFlowFactory(
            vpn_request=req, direction="inbound", destination_cidr="10.10.70.100/32"
        )
        specs = compute_nat_specs(req)
        assert len(specs) == 2
        directions = {s["direction"] for s in specs}
        assert directions == {"inbound", "outbound"}

    def test_blank_direction_falls_back_to_directionality(self):
        # Legacy rows (pre-backfill) without a direction follow the request
        site = SiteFactory()
        req = VpnRequestFactory(directionality="vendor_initiates", our_endpoint_1_site=site)
        flow = TrafficFlowFactory(vpn_request=req, destination_cidr="10.10.70.100/32")
        type(flow).objects.filter(pk=flow.pk).update(direction="")
        specs = compute_nat_specs(req)
        assert len(specs) == 1
        assert specs[0]["direction"] == "inbound"

    def test_multi_endpoint(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        req = VpnRequestFactory(
            directionality="we_initiate",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
        )
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.10.70.100/32")
        specs = compute_nat_specs(req)
        assert len(specs) == 2
        assert {s["site"] for s in specs} == {site1, site2}

    def test_flow_direction_overrides_request_directionality(self):
        site = SiteFactory()
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(
            vpn_request=req, direction="inbound", destination_cidr="10.10.70.100/32"
        )
        specs = compute_nat_specs(req)
        assert len(specs) == 1
        assert specs[0]["direction"] == "inbound"

    def test_mixed_flow_directions_one_mapping_each(self):
        # A "both" request with explicit per-flow directions gets one mapping
        # per flow (from the right pool), not the inbound×outbound product.
        site = SiteFactory()
        req = VpnRequestFactory(directionality="both", our_endpoint_1_site=site)
        out_flow = TrafficFlowFactory(
            vpn_request=req, direction="outbound", destination_cidr="172.16.5.10/32"
        )
        in_flow = TrafficFlowFactory(
            vpn_request=req, direction="inbound", destination_cidr="10.10.70.100/32"
        )
        specs = compute_nat_specs(req)
        assert len(specs) == 2
        by_flow = {s["flow"]: s["direction"] for s in specs}
        assert by_flow[out_flow] == "outbound"
        assert by_flow[in_flow] == "inbound"


# ── allocate_nat_mappings (integration) ──────────────────────────────


@pytest.mark.django_db
class TestAllocateNatMappings:
    def test_outbound_allocation(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.10.70.100/32")
        allocate_nat_mappings(req)
        assert req.nat_mappings.count() == 1
        m = req.nat_mappings.first()
        assert m.direction == "outbound"
        assert m.nat_address == "10.111.96.0/32"
        assert m.real_address == "10.10.70.100/32"
        assert m.nat_pool is not None

    def test_both_directions_need_both_pools(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        NatPoolFactory(site=site, direction="inbound", cidr="10.111.100.0/24")
        req = VpnRequestFactory(directionality="both", our_endpoint_1_site=site)
        TrafficFlowFactory(
            vpn_request=req, direction="outbound", destination_cidr="172.16.5.10/32"
        )
        TrafficFlowFactory(
            vpn_request=req, direction="inbound", destination_cidr="10.10.70.100/32"
        )
        allocate_nat_mappings(req)
        assert req.nat_mappings.count() == 2
        out = req.nat_mappings.get(direction="outbound")
        inb = req.nat_mappings.get(direction="inbound")
        assert out.nat_address.startswith("10.111.96.")
        assert inb.nat_address.startswith("10.111.100.")

    def test_mixed_flow_directions_draw_from_matching_pools(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        NatPoolFactory(site=site, direction="inbound", cidr="10.111.100.0/24")
        req = VpnRequestFactory(directionality="both", our_endpoint_1_site=site)
        TrafficFlowFactory(
            vpn_request=req, direction="outbound", destination_cidr="172.16.5.10/32"
        )
        TrafficFlowFactory(
            vpn_request=req, direction="inbound", destination_cidr="10.10.70.100/32"
        )
        allocate_nat_mappings(req)
        # One mapping per flow — each carved from the pool matching its direction
        assert req.nat_mappings.count() == 2
        out = req.nat_mappings.get(direction="outbound")
        inb = req.nat_mappings.get(direction="inbound")
        assert out.nat_address.startswith("10.111.96.")
        assert out.real_address == "172.16.5.10/32"
        assert inb.nat_address.startswith("10.111.100.")
        assert inb.real_address == "10.10.70.100/32"

    def test_idempotent(self):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.10.70.100/32")
        allocate_nat_mappings(req)
        allocate_nat_mappings(req)  # no-op
        assert req.nat_mappings.count() == 1

    def test_full_workflow_infosec_creates_nat_mappings(self):
        """Submit → InfoSec approve → NAT mappings created from endpoint pools."""
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        reviewer = UserFactory(roles=["infosec_approver"])

        req = _make_submittable_request(
            directionality="we_initiate",
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site,
        )
        submit_request(req)
        approve_infosec(req, reviewer, comments="ok")

        req = type(req).objects.get(pk=req.pk)  # re-fetch (FSM protected)
        assert req.status == "infosec_approved"
        assert req.nat_mappings.count() >= 1

    def test_missing_pool_does_not_break_workflow(self):
        """No NAT pool configured: approval still succeeds, no mappings created."""
        site = SiteFactory()  # no NAT pools
        reviewer = UserFactory(roles=["infosec_approver"])

        req = _make_submittable_request(
            directionality="we_initiate",
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site,
        )
        submit_request(req)
        approve_infosec(req, reviewer)

        req = type(req).objects.get(pk=req.pk)
        assert req.status == "infosec_approved"
        assert req.nat_mappings.count() == 0
