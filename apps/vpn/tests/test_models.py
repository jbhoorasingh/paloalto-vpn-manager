import pytest
from django.core.exceptions import ValidationError

from apps.vpn.models import TrafficFlow, VpnRequest
from apps.vpn.models.flow import validate_cidr, validate_ports

from .factories import (
    ApplicationFactory,
    TrafficFlowFactory,
    VendorContactFactory,
    VendorFactory,
    VpnRequestFactory,
)


@pytest.mark.django_db
class TestVendor:
    def test_create_vendor(self):
        vendor = VendorFactory(name="Acme Corp")
        assert vendor.name == "Acme Corp"
        assert vendor.status == "active"
        assert str(vendor) == "Acme Corp"

    def test_vendor_contacts(self):
        vendor = VendorFactory()
        contact = VendorContactFactory(vendor=vendor, is_primary=True)
        assert vendor.contacts.count() == 1
        assert contact.is_primary is True
        assert vendor.name in str(contact)


@pytest.mark.django_db
class TestApplication:
    def test_create_application(self):
        app = ApplicationFactory(name="SAP Portal")
        assert app.name == "SAP Portal"
        assert app.criticality == "medium"

    def test_application_str(self):
        app = ApplicationFactory(name="Trading System")
        assert str(app) == "Trading System"


@pytest.mark.django_db
class TestVpnRequest:
    def test_create_request(self):
        req = VpnRequestFactory()
        assert req.reference_number.startswith("VPN-")
        assert len(req.reference_number) == 12  # VPN- + 8 hex chars
        assert req.status == "draft"

    def test_request_str(self):
        req = VpnRequestFactory(title="Test VPN")
        assert req.reference_number in str(req)
        assert "Test VPN" in str(req)

    def test_request_with_applications(self):
        app1 = ApplicationFactory()
        app2 = ApplicationFactory()
        req = VpnRequestFactory(applications=[app1, app2])
        assert req.applications.count() == 2

    def test_validate_for_submission_missing_vendor(self):
        req = VpnRequestFactory(vendor=None)
        errors = req.validate_for_submission()
        assert any("vendor" in e.lower() for e in errors)

    def test_validate_for_submission_missing_title(self):
        req = VpnRequestFactory(title="")
        errors = req.validate_for_submission()
        assert any("title" in e.lower() for e in errors)

    def test_validate_for_submission_missing_apps(self):
        req = VpnRequestFactory()
        errors = req.validate_for_submission()
        assert any("application" in e.lower() for e in errors)

    def test_validate_for_submission_missing_flows(self):
        req = VpnRequestFactory()
        errors = req.validate_for_submission()
        assert any("flow" in e.lower() for e in errors)

    def test_validate_for_submission_allows_nat_not_sure(self):
        app = ApplicationFactory()
        req = VpnRequestFactory(nat_supported=None, applications=[app])
        TrafficFlowFactory(vpn_request=req)
        errors = req.validate_for_submission()
        assert not any("nat" in e.lower() for e in errors)


@pytest.mark.django_db
class TestTrafficFlow:
    def test_create_flow(self):
        flow = TrafficFlowFactory()
        assert flow.source_cidr == "10.0.0.0/24"
        assert flow.destination_cidr == "192.168.1.10/32"
        assert flow.protocols == "tcp"
        assert flow.protocol_list == ["tcp"]

    def test_private_destination_must_be_host(self):
        from django.core.exceptions import ValidationError
        flow = TrafficFlowFactory.build(
            vpn_request=TrafficFlowFactory().vpn_request,
            destination_cidr="10.20.30.0/24",
        )
        with pytest.raises(ValidationError, match="RFC-1918"):
            flow.full_clean()

    def test_private_host_destination_ok(self):
        flow = TrafficFlowFactory(destination_cidr="10.20.30.40/32")
        flow.full_clean()  # should not raise

    def test_public_destination_range_ok(self):
        # Globally-unique destinations are not NAT'd — any prefix is fine
        flow = TrafficFlowFactory(destination_cidr="198.51.100.0/24")
        flow.full_clean()  # should not raise

    def test_flow_str(self):
        flow = TrafficFlowFactory()
        assert "10.0.0.0/24" in str(flow)
        assert "192.168.1.10/32" in str(flow)

    def test_multi_protocol_normalized(self):
        flow = TrafficFlowFactory(protocols="tcp, udp ,icmp")
        flow.full_clean()
        assert flow.protocols == "tcp,udp,icmp"
        assert flow.protocol_list == ["tcp", "udp", "icmp"]
        assert flow.has_port_protocol is True

    def test_any_cannot_combine_with_others(self):
        flow = TrafficFlowFactory.build(
            vpn_request=TrafficFlowFactory().vpn_request,
            destination_cidr="172.16.5.10/32", protocols="any,tcp",
        )
        with pytest.raises(ValidationError, match="Any"):
            flow.full_clean()

    def test_unknown_protocol_rejected(self):
        flow = TrafficFlowFactory.build(
            vpn_request=TrafficFlowFactory().vpn_request,
            destination_cidr="172.16.5.10/32", protocols="tcp,sctp",
        )
        with pytest.raises(ValidationError, match="Unknown protocol"):
            flow.full_clean()

    def test_ports_cleared_for_icmp_only(self):
        flow = TrafficFlowFactory(
            destination_cidr="172.16.5.10/32", protocols="icmp", destination_ports="443"
        )
        flow.full_clean()
        assert flow.destination_ports == ""

    def test_ports_kept_when_any_port_protocol_present(self):
        flow = TrafficFlowFactory(
            destination_cidr="172.16.5.10/32", protocols="udp,icmp", destination_ports="1194"
        )
        flow.full_clean()
        assert flow.destination_ports == "1194"

    def test_valid_cidr(self):
        validate_cidr("10.0.0.0/24")
        validate_cidr("192.168.1.0/32")
        validate_cidr("0.0.0.0/0")

    def test_invalid_cidr(self):
        with pytest.raises(ValidationError):
            validate_cidr("not-a-cidr")
        with pytest.raises(ValidationError):
            validate_cidr("999.999.999.999/24")

    def test_valid_ports(self):
        validate_ports("443")
        validate_ports("80,443")
        validate_ports("443,8443,10000-10100")
        validate_ports("22")

    def test_invalid_ports(self):
        with pytest.raises(ValidationError):
            validate_ports("abc")
        with pytest.raises(ValidationError):
            validate_ports("99999")  # > 65535
        with pytest.raises(ValidationError):
            validate_ports("100-50")  # low > high

    def test_flow_ordering(self):
        req = VpnRequestFactory()
        f1 = TrafficFlowFactory(vpn_request=req, order=2)
        f2 = TrafficFlowFactory(vpn_request=req, order=1)
        flows = list(req.flows.all())
        assert flows[0] == f2
        assert flows[1] == f1
