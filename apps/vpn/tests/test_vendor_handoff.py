import pytest
from django.urls import reverse

from apps.core.tests.factories import SiteFactory
from apps.vpn.models import VpnRequest
from apps.vpn.models.nat import NatMapping
from apps.vpn.models.tunnel import TunnelInterface
from apps.vpn.services.vendor_handoff import build_handoff_context

from .factories import TrafficFlowFactory, VpnRequestFactory

# Internal service address the vendor must never see (only its published NAT).
INTERNAL_REAL = "10.10.70.100"
PUBLISHED_NAT = "10.111.100.5/32"


def _provisioned_request(status="network_approved", routing_type="bgp", vendor_cidrs=""):
    site = SiteFactory(
        public_ip="203.0.113.10", bgp_asn=65001,
        management_type="standalone", template_name="", device_group="",
    )
    req = VpnRequestFactory(
        directionality="both", routing_type=routing_type, bgp_remote_asn=65100,
        our_endpoint_1_site=site, vendor_endpoint_1_ip="198.51.100.10",
        vendor_cidrs=vendor_cidrs,
        ike_encryption="aes-256-cbc", ike_integrity="sha256", ike_dh_group="14",
        ipsec_encryption="aes-256-gcm", ipsec_integrity="sha256", ipsec_pfs_group="14",
    )
    in_flow = TrafficFlowFactory(
        vpn_request=req, direction="inbound",
        source_cidr="198.51.100.0/24", destination_cidr=f"{INTERNAL_REAL}/32",
        protocols="tcp", destination_ports="443",
    )
    TunnelInterface.objects.create(
        vpn_request=req, site=site, tunnel_number=101,
        local_ip="10.255.0.1", remote_ip="10.255.0.2",
        subnet_cidr="10.255.0.0/30", vendor_endpoint_ip="198.51.100.10",
    )
    NatMapping.objects.create(
        vpn_request=req, site=site, direction="inbound",
        nat_address=PUBLISHED_NAT, real_address=f"{INTERNAL_REAL}/32",
        traffic_flow=in_flow, description="HL7 inbound",
    )
    # Bypass the protected FSM field to reach a provisioned status directly.
    VpnRequest.objects.filter(pk=req.pk).update(status=status)
    return VpnRequest.objects.get(pk=req.pk)


@pytest.mark.django_db
class TestHandoffContext:
    def test_peering_crypto_and_published_nat(self):
        ctx = build_handoff_context(_provisioned_request())
        row = ctx["tunnel_rows"][0]
        assert row["our_inside_ip"] == "10.255.0.1"
        assert row["vendor_inside_ip"] == "10.255.0.2"
        assert row["our_public_ip"] == "203.0.113.10"
        assert row["our_asn"] == 65001
        assert row["vendor_asn"] == 65100
        assert ctx["crypto"]["ike_encryption"] == "AES-256-CBC"
        assert ctx["crypto"]["ipsec_encryption"] == "AES-256-GCM"
        assert [r["address"] for r in ctx["reachable"]] == [PUBLISHED_NAT]

    def test_inbound_flow_uses_published_nat_not_internal_address(self):
        ctx = build_handoff_context(_provisioned_request())
        inbound = [f for f in ctx["flow_rows"] if f["direction"] == "inbound"]
        assert inbound, "expected an inbound flow row"
        assert inbound[0]["dst"] == PUBLISHED_NAT
        # Internal real address must not leak into any flow row.
        assert all(INTERNAL_REAL not in f["dst"] for f in ctx["flow_rows"])

    def test_static_routing_lists_vendor_cidrs(self):
        ctx = build_handoff_context(
            _provisioned_request(routing_type="static", vendor_cidrs="172.20.0.0/24, 172.20.1.0/24")
        )
        assert ctx["is_bgp"] is False
        assert ctx["vendor_cidrs"] == ["172.20.0.0/24", "172.20.1.0/24"]


@pytest.mark.django_db
class TestHandoffView:
    def test_renders_for_provisioned_request(self, client_authenticated):
        req = _provisioned_request()
        resp = client_authenticated.get(reverse("ui:request-vendor-handoff", args=[req.pk]))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "10.255.0.1" in body          # tunnel peering IP
        assert "65100" in body               # vendor ASN
        assert PUBLISHED_NAT in body         # published NAT address
        # The PSK is called out as out-of-band, never embedded; the internal
        # real service address must not leak (only its published NAT).
        assert "exchanged out-of-band" in body
        assert "<PRE-SHARED-KEY>" not in body
        assert INTERNAL_REAL not in body

    def test_redirects_before_network_approval(self, client_authenticated):
        req = VpnRequestFactory()  # draft
        resp = client_authenticated.get(reverse("ui:request-vendor-handoff", args=[req.pk]))
        assert resp.status_code == 302

    def test_detail_button_gated_by_status(self, client_authenticated):
        provisioned = _provisioned_request()
        draft = VpnRequestFactory()
        shown = client_authenticated.get(reverse("ui:request-detail", args=[provisioned.pk]))
        hidden = client_authenticated.get(reverse("ui:request-detail", args=[draft.pk]))
        assert "Vendor Handoff" in shown.content.decode()
        assert "Vendor Handoff" not in hidden.content.decode()
