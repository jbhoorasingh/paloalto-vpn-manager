import json

import pytest
from django.urls import reverse

from apps.core.tests.factories import UserFactory
from apps.vpn.models import TrafficFlow, VpnRequest

from .factories import (
    ApplicationFactory,
    TrafficFlowFactory,
    VendorFactory,
    VpnRequestFactory,
)


@pytest.fixture
def api_user(db):
    return UserFactory()


@pytest.fixture
def api_client(client, api_user):
    client.force_login(api_user)
    return client


@pytest.mark.django_db
class TestWizardAPI:
    def test_create_draft(self, api_client, api_user):
        response = api_client.post(
            reverse("vpn-api:wizard-create"),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "draft"
        assert VpnRequest.objects.filter(pk=data["id"], requester=api_user).exists()

    def test_load_draft(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user, title="My VPN")
        response = api_client.get(reverse("vpn-api:wizard-load", args=[req.pk]))
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "My VPN"

    def test_load_draft_not_found(self, api_client):
        response = api_client.get(reverse("vpn-api:wizard-load", args=[9999]))
        assert response.status_code == 404

    def test_save_step_vendor(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        vendor = VendorFactory()
        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 1]),
            data=json.dumps({"vendor_id": vendor.pk}),
            content_type="application/json",
        )
        assert response.status_code == 200
        req = VpnRequest.objects.get(pk=req.pk)
        assert req.vendor_id == vendor.pk

    def test_save_step_apps_data(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        app = ApplicationFactory()
        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 2]),
            data=json.dumps({
                "title": "Updated Title",
                "purpose": "Testing",
                "directionality": "we_initiate",
                "application_ids": [app.pk],
            }),
            content_type="application/json",
        )
        assert response.status_code == 200
        req = VpnRequest.objects.get(pk=req.pk)
        assert req.title == "Updated Title"
        assert req.applications.count() == 1

    def test_save_step_invalid_step(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 99]),
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_submit_success(self, api_client, api_user):
        app = ApplicationFactory()
        req = VpnRequestFactory(
            requester=api_user,
            title="Test VPN",
            nat_supported=True,
            applications=[app],
        )
        TrafficFlowFactory(vpn_request=req)

        response = api_client.post(
            reverse("vpn-api:wizard-submit", args=[req.pk]),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"

    def test_submit_validation_error(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user, title="", vendor=None, nat_supported=None)
        response = api_client.post(
            reverse("vpn-api:wizard-submit", args=[req.pk]),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.json()
        assert "errors" in data

    def test_unauthenticated_access(self, client):
        response = client.post(reverse("vpn-api:wizard-create"))
        assert response.status_code == 302  # redirect to login

    def test_save_step_invalid_asn_text(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 5]),
            data=json.dumps({"bgp_remote_asn": "coool cool cool", "routing_type": "bgp"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.json()
        assert "field_errors" in data
        assert "bgp_remote_asn" in data["field_errors"]

    def test_save_step_asn_out_of_range(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 5]),
            data=json.dumps({"bgp_remote_asn": 5000000000, "routing_type": "bgp"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.json()
        assert "bgp_remote_asn" in data["field_errors"]

    def test_save_step_valid_asn(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 5]),
            data=json.dumps({"bgp_remote_asn": 65100, "routing_type": "bgp"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        req = VpnRequest.objects.get(pk=req.pk)
        assert req.bgp_remote_asn == 65100

    def test_save_step_in_changes_requested(self, api_client, api_user):
        """Wizard save works when request is in infosec_changes_requested state."""
        app = ApplicationFactory()
        req = VpnRequestFactory(
            requester=api_user,
            title="Test VPN",
            nat_supported=True,
            applications=[app],
        )
        TrafficFlowFactory(vpn_request=req)
        # Walk through FSM to infosec_changes_requested
        req = VpnRequest.objects.get(pk=req.pk)
        req.submit()
        req.save()
        req = VpnRequest.objects.get(pk=req.pk)
        req.request_infosec_changes()
        req.save()

        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 2]),
            data=json.dumps({"title": "Updated After Changes"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        req = VpnRequest.objects.get(pk=req.pk)
        assert req.title == "Updated After Changes"

    def test_resubmit_from_infosec(self, api_client, api_user):
        """Submit endpoint triggers resubmit when in infosec_changes_requested."""
        app = ApplicationFactory()
        req = VpnRequestFactory(
            requester=api_user,
            title="Test VPN",
            nat_supported=True,
            applications=[app],
        )
        TrafficFlowFactory(vpn_request=req)
        # Walk through FSM
        req = VpnRequest.objects.get(pk=req.pk)
        req.submit()
        req.save()
        req = VpnRequest.objects.get(pk=req.pk)
        req.request_infosec_changes()
        req.save()

        response = api_client.post(
            reverse("vpn-api:wizard-submit", args=[req.pk]),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "submitted"

    def test_cannot_edit_submitted_request(self, api_client, api_user):
        """Wizard save returns 404 for submitted status (not editable)."""
        app = ApplicationFactory()
        req = VpnRequestFactory(
            requester=api_user,
            title="Test VPN",
            nat_supported=True,
            applications=[app],
        )
        TrafficFlowFactory(vpn_request=req)
        req = VpnRequest.objects.get(pk=req.pk)
        req.submit()
        req.save()

        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 2]),
            data=json.dumps({"title": "Should Fail"}),
            content_type="application/json",
        )
        assert response.status_code == 404

    def test_save_step_invalid_ip(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.patch(
            reverse("vpn-api:wizard-save-step", args=[req.pk, 3]),
            data=json.dumps({"vendor_endpoint_1_ip": "40.10.11.50.0"}),
            content_type="application/json",
        )
        assert response.status_code == 400
        data = response.json()
        assert "vendor_endpoint_1_ip" in data["field_errors"]


@pytest.mark.django_db
class TestVendorAPI:
    def test_list_vendors(self, api_client):
        VendorFactory(name="Acme Corp")
        VendorFactory(name="Beta Inc")
        response = api_client.get(reverse("vpn-api:vendor-list"))
        assert response.status_code == 200
        data = response.json()
        assert len(data["vendors"]) == 2

    def test_search_vendors(self, api_client):
        VendorFactory(name="Acme Corp")
        VendorFactory(name="Beta Inc")
        response = api_client.get(reverse("vpn-api:vendor-list") + "?q=acme")
        data = response.json()
        assert len(data["vendors"]) == 1
        assert data["vendors"][0]["name"] == "Acme Corp"

    def test_create_vendor(self, api_client):
        response = api_client.post(
            reverse("vpn-api:vendor-create"),
            data=json.dumps({"name": "New Vendor", "domain": "new.com"}),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Vendor"

    def test_create_vendor_no_name(self, api_client):
        response = api_client.post(
            reverse("vpn-api:vendor-create"),
            data=json.dumps({"name": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestFlowsAPI:
    def test_list_flows(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        TrafficFlowFactory(vpn_request=req)
        TrafficFlowFactory(vpn_request=req)
        response = api_client.get(
            reverse("vpn-api:flow-list-create", args=[req.pk])
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["flows"]) == 2

    def test_create_flow(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.post(
            reverse("vpn-api:flow-list-create", args=[req.pk]),
            data=json.dumps({
                "source_cidr": "10.1.0.0/16",
                "destination_cidr": "172.16.0.0/24",
                "protocol": "tcp",
                "destination_ports": "443,8443",
                "description": "HTTPS traffic",
            }),
            content_type="application/json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_cidr"] == "10.1.0.0/16"

    def test_create_flow_invalid_cidr(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.post(
            reverse("vpn-api:flow-list-create", args=[req.pk]),
            data=json.dumps({
                "source_cidr": "not-valid",
                "destination_cidr": "172.16.0.0/24",
                "protocol": "tcp",
            }),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_update_flow(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        flow = TrafficFlowFactory(vpn_request=req)
        response = api_client.patch(
            reverse("vpn-api:flow-detail", args=[flow.pk]),
            data=json.dumps({"destination_ports": "8080"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        flow.refresh_from_db()
        assert flow.destination_ports == "8080"

    def test_delete_flow(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        flow = TrafficFlowFactory(vpn_request=req)
        response = api_client.delete(
            reverse("vpn-api:flow-detail", args=[flow.pk])
        )
        assert response.status_code == 200
        assert not TrafficFlow.objects.filter(pk=flow.pk).exists()

    def test_cannot_edit_other_users_flow(self, api_client, api_user):
        other_user = UserFactory()
        req = VpnRequestFactory(requester=other_user)
        flow = TrafficFlowFactory(vpn_request=req)
        response = api_client.patch(
            reverse("vpn-api:flow-detail", args=[flow.pk]),
            data=json.dumps({"destination_ports": "8080"}),
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_create_flow_with_direction(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user, directionality="we_initiate")
        response = api_client.post(
            reverse("vpn-api:flow-list-create", args=[req.pk]),
            data=json.dumps({
                "source_cidr": "172.16.0.0/24",
                "destination_cidr": "10.10.70.100/32",
                "direction": "inbound",
                "protocol": "tcp",
            }),
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["direction"] == "inbound"

    def test_create_flow_direction_defaults_from_directionality(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user, directionality="vendor_initiates")
        response = api_client.post(
            reverse("vpn-api:flow-list-create", args=[req.pk]),
            data=json.dumps({
                "source_cidr": "172.16.0.0/24",
                "destination_cidr": "10.10.70.100/32",
                "protocol": "tcp",
            }),
            content_type="application/json",
        )
        assert response.status_code == 201
        assert response.json()["direction"] == "inbound"

    def test_create_flow_invalid_direction_rejected(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        response = api_client.post(
            reverse("vpn-api:flow-list-create", args=[req.pk]),
            data=json.dumps({
                "source_cidr": "10.1.0.0/16",
                "destination_cidr": "172.16.0.0/24",
                "direction": "sideways",
                "protocol": "tcp",
            }),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_update_flow_direction(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user)
        flow = TrafficFlowFactory(vpn_request=req, direction="outbound")
        response = api_client.patch(
            reverse("vpn-api:flow-detail", args=[flow.pk]),
            data=json.dumps({"direction": "inbound"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        flow.refresh_from_db()
        assert flow.direction == "inbound"


@pytest.mark.django_db
class TestRequestsAPI:
    def test_list_my_requests(self, api_client, api_user):
        VpnRequestFactory(requester=api_user)
        VpnRequestFactory(requester=api_user)
        VpnRequestFactory()  # another user's request
        response = api_client.get(reverse("vpn-api:request-list") + "?scope=mine")
        data = response.json()
        assert len(data["requests"]) == 2

    def test_list_all_requests(self, api_client, api_user):
        VpnRequestFactory(requester=api_user)
        VpnRequestFactory()
        response = api_client.get(reverse("vpn-api:request-list") + "?scope=all")
        data = response.json()
        assert len(data["requests"]) == 2

    def test_request_detail(self, api_client, api_user):
        req = VpnRequestFactory(requester=api_user, title="Detail Test")
        response = api_client.get(
            reverse("vpn-api:request-detail", args=[req.pk])
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Detail Test"

    def test_filter_by_status(self, api_client, api_user):
        VpnRequestFactory(requester=api_user)  # draft
        response = api_client.get(
            reverse("vpn-api:request-list") + "?scope=mine&status=draft"
        )
        data = response.json()
        assert len(data["requests"]) == 1
        assert data["requests"][0]["status"] == "draft"
