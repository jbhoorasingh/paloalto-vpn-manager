import json

import pytest
from django.core.exceptions import ValidationError

from apps.core.tests.factories import SiteFactory, TunnelAddressPoolFactory, UserFactory
from apps.vpn.models.tunnel import TunnelInterface
from apps.vpn.services.allocation import (
    _allocate_apipa,
    _allocate_from_pool,
    _next_available_tunnel_number,
    allocate_tunnel_interfaces,
    compute_tunnel_list,
)
from apps.vpn.services.workflow import approve_infosec, submit_request

from .factories import ApplicationFactory, TrafficFlowFactory, VpnRequestFactory


def _make_submittable_request(**kwargs):
    """Create a VpnRequest that passes all submission validations."""
    app = ApplicationFactory()
    req = VpnRequestFactory(
        title="Test VPN",
        nat_supported=True,
        applications=[app],
        **kwargs,
    )
    TrafficFlowFactory(vpn_request=req)
    return req


# ── compute_tunnel_list ──────────────────────────────────────────────


@pytest.mark.django_db
class TestComputeTunnelList:
    def test_single_ep_two_tunnels(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        req = VpnRequestFactory(
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
        )
        tunnels = compute_tunnel_list(req)
        assert len(tunnels) == 2
        assert tunnels[0]["site"] == site1
        assert tunnels[0]["vendor_ep_ip"] == "1.2.3.4"
        assert tunnels[1]["site"] == site2
        assert tunnels[1]["vendor_ep_ip"] == "1.2.3.4"

    def test_bow_tie_four_tunnels(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        req = VpnRequestFactory(
            vendor_endpoints_count=2,
            topology_type="bow_tie",
            vendor_endpoint_1_ip="1.2.3.4",
            vendor_endpoint_2_ip="5.6.7.8",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
        )
        tunnels = compute_tunnel_list(req)
        assert len(tunnels) == 4
        # site1 -> EP1, site1 -> EP2, site2 -> EP1, site2 -> EP2
        assert tunnels[0]["site"] == site1
        assert tunnels[0]["vendor_ep_ip"] == "1.2.3.4"
        assert tunnels[1]["site"] == site1
        assert tunnels[1]["vendor_ep_ip"] == "5.6.7.8"
        assert tunnels[2]["site"] == site2
        assert tunnels[3]["site"] == site2

    def test_matched_pairs_two_tunnels(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        req = VpnRequestFactory(
            vendor_endpoints_count=2,
            topology_type="matched_pairs",
            vendor_endpoint_1_ip="1.2.3.4",
            vendor_endpoint_2_ip="5.6.7.8",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
        )
        tunnels = compute_tunnel_list(req)
        assert len(tunnels) == 2
        assert tunnels[0]["site"] == site1
        assert tunnels[0]["vendor_ep_ip"] == "1.2.3.4"
        assert tunnels[1]["site"] == site2
        assert tunnels[1]["vendor_ep_ip"] == "5.6.7.8"


# ── _next_available_tunnel_number ────────────────────────────────────


@pytest.mark.django_db
class TestNextTunnelNumber:
    def test_first_picks_start(self):
        site = SiteFactory(tunnel_interface_start=100, tunnel_interface_end=199)
        num = _next_available_tunnel_number(site)
        assert num == 100

    def test_skips_used(self):
        site = SiteFactory(tunnel_interface_start=100, tunnel_interface_end=199)
        req = VpnRequestFactory()
        TunnelInterface.objects.create(
            vpn_request=req, site=site, tunnel_number=100
        )
        num = _next_available_tunnel_number(site)
        assert num == 101

    def test_exhausted_raises(self):
        site = SiteFactory(tunnel_interface_start=100, tunnel_interface_end=100)
        req = VpnRequestFactory()
        TunnelInterface.objects.create(
            vpn_request=req, site=site, tunnel_number=100
        )
        with pytest.raises(ValidationError, match="exhausted"):
            _next_available_tunnel_number(site)


# ── _allocate_from_pool ──────────────────────────────────────────────


@pytest.mark.django_db
class TestAllocateFromPool:
    def test_first_slash30(self):
        site = SiteFactory()
        TunnelAddressPoolFactory(site=site, cidr="10.255.0.0/24")
        local_ip, remote_ip, subnet, pool = _allocate_from_pool(site)
        assert subnet == "10.255.0.0/30"
        assert local_ip == "10.255.0.1"
        assert remote_ip == "10.255.0.2"
        assert pool is not None

    def test_skips_used(self):
        site = SiteFactory()
        TunnelAddressPoolFactory(site=site, cidr="10.255.0.0/24")
        req = VpnRequestFactory()
        TunnelInterface.objects.create(
            vpn_request=req, site=site, tunnel_number=100,
            subnet_cidr="10.255.0.0/30",
        )
        local_ip, remote_ip, subnet, pool = _allocate_from_pool(site)
        assert subnet == "10.255.0.4/30"
        assert local_ip == "10.255.0.5"
        assert remote_ip == "10.255.0.6"

    def test_exhausted_raises(self):
        site = SiteFactory()
        # /30 has exactly one /30 subnet
        TunnelAddressPoolFactory(site=site, cidr="10.255.0.0/30")
        req = VpnRequestFactory()
        TunnelInterface.objects.create(
            vpn_request=req, site=site, tunnel_number=100,
            subnet_cidr="10.255.0.0/30",
        )
        with pytest.raises(ValidationError, match="exhausted"):
            _allocate_from_pool(site)


# ── _allocate_apipa ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestAllocateApipa:
    def test_valid_apipa(self):
        site = SiteFactory()
        local_ip, remote_ip, subnet = _allocate_apipa(site)
        assert subnet.startswith("169.254.")
        assert local_ip.startswith("169.254.")
        assert remote_ip.startswith("169.254.")

    def test_no_overlap(self):
        site = SiteFactory()
        results = set()
        for _ in range(5):
            local_ip, remote_ip, subnet = _allocate_apipa(site)
            assert subnet not in results
            results.add(subnet)
            req = VpnRequestFactory()
            TunnelInterface.objects.create(
                vpn_request=req, site=site,
                tunnel_number=100 + len(results),
                subnet_cidr=subnet,
            )


# ── allocate_tunnel_interfaces (integration) ─────────────────────────


@pytest.mark.django_db
class TestAllocateTunnelInterfaces:
    def test_we_assign(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        TunnelAddressPoolFactory(site=site1, cidr="10.255.0.0/24")
        TunnelAddressPoolFactory(site=site2, cidr="10.255.1.0/24")
        req = VpnRequestFactory(
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
            tunnel_ip_assignment="we_assign",
        )
        allocate_tunnel_interfaces(req)
        assert req.tunnel_interfaces.count() == 2
        ti1 = req.tunnel_interfaces.filter(site=site1).first()
        assert ti1.local_ip == "10.255.0.1"
        assert ti1.remote_ip == "10.255.0.2"
        assert ti1.tunnel_number == 100

    def test_mutual(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        mutual_data = json.dumps([
            {"local_ip": "10.0.0.1", "remote_ip": "10.0.0.2"},
            {"local_ip": "10.0.1.1", "remote_ip": "10.0.1.2"},
        ])
        req = VpnRequestFactory(
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
            tunnel_ip_assignment="mutual",
            mutual_tunnel_ips=mutual_data,
        )
        allocate_tunnel_interfaces(req)
        assert req.tunnel_interfaces.count() == 2
        ti1 = req.tunnel_interfaces.filter(site=site1).first()
        assert ti1.local_ip == "10.0.0.1"
        assert ti1.remote_ip == "10.0.0.2"

    def test_apipa(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        req = VpnRequestFactory(
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
            tunnel_ip_assignment="apipa",
        )
        allocate_tunnel_interfaces(req)
        assert req.tunnel_interfaces.count() == 2
        for ti in req.tunnel_interfaces.all():
            assert ti.subnet_cidr.startswith("169.254.")

    def test_idempotent(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        TunnelAddressPoolFactory(site=site1, cidr="10.255.0.0/24")
        TunnelAddressPoolFactory(site=site2, cidr="10.255.1.0/24")
        req = VpnRequestFactory(
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
            tunnel_ip_assignment="we_assign",
        )
        allocate_tunnel_interfaces(req)
        allocate_tunnel_interfaces(req)  # second call is no-op
        assert req.tunnel_interfaces.count() == 2

    def test_full_workflow_infosec_creates_allocations(self):
        """Submit → InfoSec approve → tunnel allocations created."""
        site1 = SiteFactory()
        site2 = SiteFactory()
        TunnelAddressPoolFactory(site=site1, cidr="10.255.0.0/24")
        TunnelAddressPoolFactory(site=site2, cidr="10.255.1.0/24")
        reviewer = UserFactory(roles=["infosec_approver"])

        req = _make_submittable_request(
            vendor_endpoints_count=1,
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site1,
            our_endpoint_2_site=site2,
            tunnel_ip_assignment="we_assign",
        )
        submit_request(req)
        approve_infosec(req, reviewer, comments="Looks good")

        req = type(req).objects.get(pk=req.pk)  # re-fetch (FSM protected)
        assert req.status == "infosec_approved"
        assert req.tunnel_interfaces.count() == 2
