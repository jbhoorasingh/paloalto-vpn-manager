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
from apps.vpn.services.workflow import approve_infosec, approve_network, submit_request

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

    def test_shared_pool_must_not_have_site(self):
        site = SiteFactory()
        pool = NatPool(site=site, scope="shared", direction="outbound", cidr="10.111.200.0/24")
        with pytest.raises(ValidationError, match="must not be tied"):
            pool.full_clean()

    def test_site_pool_requires_site(self):
        pool = NatPool(site=None, scope="site", direction="outbound", cidr="10.111.200.0/24")
        with pytest.raises(ValidationError, match="require a site"):
            pool.full_clean()

    def test_shared_pool_valid(self):
        from apps.core.tests.factories import DrPeerFactory
        pool = NatPool(
            site=None, scope="shared", dr_peer=DrPeerFactory(),
            direction="outbound", cidr="10.111.200.0/24",
        )
        pool.full_clean()  # should not raise

    def test_shared_pool_requires_dr_peer(self):
        pool = NatPool(site=None, scope="shared", direction="outbound", cidr="10.111.200.0/24")
        with pytest.raises(ValidationError, match="DR peer"):
            pool.full_clean()

    def test_site_pool_must_not_have_dr_peer(self):
        from apps.core.tests.factories import DrPeerFactory
        site = SiteFactory()
        pool = NatPool(
            site=site, scope="site", dr_peer=DrPeerFactory(),
            direction="outbound", cidr="10.111.96.0/24",
        )
        with pytest.raises(ValidationError, match="must not have a DR peer"):
            pool.full_clean()

    def test_shared_pool_cannot_overlap_any_site_pool(self):
        from apps.core.tests.factories import DrPeerFactory
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        pool = NatPool(
            site=None, scope="shared", dr_peer=DrPeerFactory(),
            direction="inbound", cidr="10.111.96.0/25",
        )
        with pytest.raises(ValidationError, match="Overlaps"):
            pool.full_clean()


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
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.108.100.5/32")
        specs = compute_nat_specs(req)
        assert len(specs) == 1
        assert specs[0]["direction"] == "inbound"
        assert specs[0]["prefixlen"] == 32

    def test_public_destination_skipped(self):
        # Globally-unique destinations are reachable as-is — no NAT mapping
        site = SiteFactory()
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="198.51.100.0/24")
        assert compute_nat_specs(req) == []

    def test_mixed_public_and_private_destinations(self):
        site = SiteFactory()
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="198.51.100.10/32")
        private = TrafficFlowFactory(vpn_request=req, destination_cidr="172.16.5.10/32")
        specs = compute_nat_specs(req)
        assert len(specs) == 1
        assert specs[0]["flow"] == private

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

    def test_multi_endpoint_is_one_shared_spec(self):
        # DR pair: ONE address carved from shared pools, provisioned at both sites
        site1 = SiteFactory()
        site2 = SiteFactory()
        req = VpnRequestFactory(
            directionality="we_initiate",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
        )
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.10.70.100/32")
        specs = compute_nat_specs(req)
        assert len(specs) == 1
        assert specs[0]["sites"] == [site1, site2]
        assert specs[0]["shared"] is True

    def test_single_site_spec_not_shared(self):
        site = SiteFactory()
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="10.10.70.100/32")
        specs = compute_nat_specs(req)
        assert specs[0]["sites"] == [site]
        assert specs[0]["shared"] is False

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


# ── DR-shared allocation ─────────────────────────────────────────────


@pytest.mark.django_db
class TestDrSharedAllocation:
    def _dr_request(self, site1, site2, **kwargs):
        req = VpnRequestFactory(
            directionality="we_initiate",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
            **kwargs,
        )
        TrafficFlowFactory(vpn_request=req, destination_cidr="172.16.5.10/32")
        return req

    def _peer_with_pool(self, site1, site2, cidr="10.111.200.0/24", direction="outbound"):
        from apps.core.tests.factories import DrPeerFactory
        peer = DrPeerFactory(primary_site=site1, secondary_site=site2)
        NatPoolFactory(
            site=None, scope="shared", dr_peer=peer, direction=direction, cidr=cidr
        )
        return peer

    def test_dr_pair_gets_same_address_at_both_sites(self):
        site1, site2 = SiteFactory(), SiteFactory()
        self._peer_with_pool(site1, site2)
        req = self._dr_request(site1, site2)
        allocate_nat_mappings(req)
        assert req.nat_mappings.count() == 2
        addresses = set(req.nat_mappings.values_list("nat_address", flat=True))
        assert addresses == {"10.111.200.0/32"}  # same NAT IP at both endpoints
        assert set(req.nat_mappings.values_list("site_id", flat=True)) == {site1.pk, site2.pk}

    def test_endpoint_order_does_not_matter(self):
        # Request picked the peer's secondary as endpoint 1 — still matches
        site1, site2 = SiteFactory(), SiteFactory()
        self._peer_with_pool(site1, site2)
        req = self._dr_request(site2, site1)
        allocate_nat_mappings(req)
        assert req.nat_mappings.count() == 2

    def test_two_sites_without_dr_peer_rejected(self):
        site1, site2 = SiteFactory(), SiteFactory()
        # Site-specific pools exist but the pair is not configured as a DR peer
        NatPoolFactory(site=site1, direction="outbound", cidr="10.111.96.0/24")
        NatPoolFactory(site=site2, direction="outbound", cidr="10.111.97.0/24")
        req = self._dr_request(site1, site2)
        with pytest.raises(ValidationError, match="not configured as a DR peer"):
            allocate_nat_mappings(req)

    def test_dr_peer_without_pools_rejected(self):
        from apps.core.tests.factories import DrPeerFactory
        site1, site2 = SiteFactory(), SiteFactory()
        DrPeerFactory(primary_site=site1, secondary_site=site2)  # no pools
        req = self._dr_request(site1, site2)
        with pytest.raises(ValidationError, match="No active shared outbound NAT pools"):
            allocate_nat_mappings(req)

    def test_pools_of_other_peer_not_used(self):
        site1, site2 = SiteFactory(), SiteFactory()
        other1, other2 = SiteFactory(), SiteFactory()
        self._peer_with_pool(other1, other2)  # different pair's pool
        from apps.core.tests.factories import DrPeerFactory
        DrPeerFactory(primary_site=site1, secondary_site=site2)
        req = self._dr_request(site1, site2)
        with pytest.raises(ValidationError, match="No active shared outbound NAT pools"):
            allocate_nat_mappings(req)

    def test_consecutive_dr_requests_get_distinct_addresses(self):
        site1, site2 = SiteFactory(), SiteFactory()
        self._peer_with_pool(site1, site2)
        first = self._dr_request(site1, site2)
        allocate_nat_mappings(first)
        second = self._dr_request(site1, site2)
        allocate_nat_mappings(second)
        assert set(first.nat_mappings.values_list("nat_address", flat=True)) == {"10.111.200.0/32"}
        assert set(second.nat_mappings.values_list("nat_address", flat=True)) == {"10.111.200.1/32"}

    def test_single_site_does_not_use_shared_pools(self):
        site = SiteFactory()
        other1, other2 = SiteFactory(), SiteFactory()
        self._peer_with_pool(other1, other2)
        req = VpnRequestFactory(directionality="we_initiate", our_endpoint_1_site=site)
        TrafficFlowFactory(vpn_request=req, destination_cidr="172.16.5.10/32")
        with pytest.raises(ValidationError, match=f"site {site.code}"):
            allocate_nat_mappings(req)


@pytest.mark.django_db
class TestDrPeerModel:
    def test_same_site_twice_rejected(self):
        from apps.core.models import DrPeer
        site = SiteFactory()
        peer = DrPeer(name="bad", primary_site=site, secondary_site=site)
        with pytest.raises(ValidationError, match="different sites"):
            peer.full_clean()

    def test_site_cannot_join_two_peers(self):
        from apps.core.models import DrPeer
        from apps.core.tests.factories import DrPeerFactory
        existing = DrPeerFactory()
        peer = DrPeer(
            name="second",
            primary_site=existing.secondary_site,
            secondary_site=SiteFactory(),
        )
        with pytest.raises(ValidationError, match="already part of DR peer"):
            peer.full_clean()

    def test_for_sites_matches_either_order(self):
        from apps.core.models import DrPeer
        from apps.core.tests.factories import DrPeerFactory
        peer = DrPeerFactory()
        assert DrPeer.for_sites(peer.primary_site, peer.secondary_site) == peer
        assert DrPeer.for_sites(peer.secondary_site, peer.primary_site) == peer
        assert DrPeer.for_sites(peer.primary_site, SiteFactory()) is None


# ── NAT packet-walk visualization ────────────────────────────────────


@pytest.mark.django_db
class TestNatPacketWalk:
    def _request_with_mapping(self, direction="outbound", sites=None):
        from apps.vpn.models.tunnel import TunnelInterface

        sites = sites or [SiteFactory()]
        req = VpnRequestFactory(
            directionality="we_initiate" if direction == "outbound" else "vendor_initiates",
            our_endpoint_1_site=sites[0],
            our_endpoint_2_site=sites[1] if len(sites) > 1 else None,
        )
        flow = TrafficFlowFactory(
            vpn_request=req, direction=direction,
            source_cidr="10.5.0.0/24", destination_cidr="172.16.9.9/32",
            protocol="tcp", destination_ports="443",
        )
        for i, site in enumerate(sites):
            TunnelInterface.objects.create(
                vpn_request=req, site=site, tunnel_number=101,
                local_ip=f"10.255.{i}.1", remote_ip=f"10.255.{i}.2",
                subnet_cidr=f"10.255.{i}.0/30",
            )
            NatMapping.objects.create(
                vpn_request=req, site=site, direction=direction,
                nat_address="10.111.96.10/32", real_address="172.16.9.9/32",
                traffic_flow=flow,
            )
        return req

    def test_outbound_walk_shows_target_rewrites_and_far_side(self, client_authenticated):
        from django.urls import reverse

        req = self._request_with_mapping("outbound")
        response = client_authenticated.get(reverse("ui:request-detail", args=[req.pk]))
        walks = response.context["nat_packet_walks"]
        assert len(walks) == 1
        walk = walks[0]
        assert walk["is_outbound"] is True
        assert walk["source"] == "10.5.0.0/24"          # who sends
        assert walk["nat_address"] == "10.111.96.10/32"  # what clients target
        assert walk["real_address"] == "172.16.9.9/32"   # what it becomes
        assert walk["seen_source"] == "10.255.0.1"       # SNAT to tunnel IP
        body = response.content.decode()
        assert "NAT Packet Walk" in body
        assert "10.111.96.10/32" in body
        assert "sees source" in body

    def test_inbound_walk_snats_to_inside_interface(self, client_authenticated):
        from django.urls import reverse

        req = self._request_with_mapping("inbound")
        response = client_authenticated.get(reverse("ui:request-detail", args=[req.pk]))
        walk = response.context["nat_packet_walks"][0]
        assert walk["is_outbound"] is False
        assert walk["seen_source"] == "firewall inside IP"
        assert "Vendor Hosts" in response.content.decode()

    def test_dr_pair_renders_one_walk_with_both_firewalls(self, client_authenticated):
        from django.urls import reverse

        sites = [SiteFactory(), SiteFactory()]
        req = self._request_with_mapping("outbound", sites=sites)
        response = client_authenticated.get(reverse("ui:request-detail", args=[req.pk]))
        walks = response.context["nat_packet_walks"]
        assert len(walks) == 1  # same translation, not duplicated per site
        assert walks[0]["dr_shared"] is True
        assert len(walks[0]["firewalls"]) == 2
        assert "DR pair" in response.content.decode()

    def test_no_walks_without_mappings(self, client_authenticated):
        from django.urls import reverse

        req = VpnRequestFactory(our_endpoint_1_site=SiteFactory())
        response = client_authenticated.get(reverse("ui:request-detail", args=[req.pk]))
        assert response.context["nat_packet_walks"] == []
        assert "NAT Packet Walk" not in response.content.decode()


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

    def test_full_workflow_network_approval_assigns_nat(self):
        """Submit → InfoSec approve (no NAT) → Network approve → NAT IPs assigned."""
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")

        req = _make_submittable_request(
            directionality="we_initiate",
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site,
        )
        submit_request(req)
        approve_infosec(req, UserFactory(roles=["infosec"]), comments="ok")

        req = type(req).objects.get(pk=req.pk)  # re-fetch (FSM protected)
        assert req.status == "infosec_approved"
        assert req.nat_mappings.count() == 0  # NAT waits for Network approval

        approve_network(req, UserFactory(roles=["network"]), comments="ok")
        req = type(req).objects.get(pk=req.pk)
        assert req.status == "network_approved"
        assert req.nat_mappings.count() >= 1

    def test_detail_page_flags_missing_nat_allocation(self, client_authenticated):
        from django.urls import reverse

        site = SiteFactory()  # no pools → allocation fails silently at approval
        req = _make_submittable_request(
            directionality="we_initiate", our_endpoint_1_site=site,
        )
        submit_request(req)
        approve_infosec(req, UserFactory(roles=["infosec"]))
        req = type(req).objects.get(pk=req.pk)
        approve_network(req, UserFactory(roles=["network"]))

        response = client_authenticated.get(reverse("ui:request-detail", args=[req.pk]))
        assert response.context["nat_allocation_missing"] is True
        assert "NAT IPs have not been assigned" in response.content.decode()

    def test_detail_page_shows_no_nat_required_for_public_destinations(self, client_authenticated):
        from django.urls import reverse

        site = SiteFactory()
        req = _make_submittable_request(
            directionality="we_initiate", our_endpoint_1_site=site,
        )
        req.flows.all().delete()
        TrafficFlowFactory(vpn_request=req, destination_cidr="198.51.100.0/24")
        submit_request(req)
        approve_infosec(req, UserFactory(roles=["infosec"]))
        req = type(req).objects.get(pk=req.pk)
        approve_network(req, UserFactory(roles=["network"]))

        response = client_authenticated.get(reverse("ui:request-detail", args=[req.pk]))
        assert response.context["nat_allocation_missing"] is False
        assert "No NAT required" in response.content.decode()

    def test_missing_pool_does_not_break_workflow(self):
        """No NAT pool configured: network approval still succeeds, no mappings created."""
        site = SiteFactory()  # no NAT pools

        req = _make_submittable_request(
            directionality="we_initiate",
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site,
        )
        submit_request(req)
        approve_infosec(req, UserFactory(roles=["infosec"]))
        req = type(req).objects.get(pk=req.pk)
        approve_network(req, UserFactory(roles=["network"]))

        req = type(req).objects.get(pk=req.pk)
        assert req.status == "network_approved"
        assert req.nat_mappings.count() == 0
