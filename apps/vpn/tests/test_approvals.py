import json

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.tests.factories import UserFactory
from apps.vpn.models import ApprovalRecord
from apps.vpn.services.workflow import (
    approve_infosec,
    approve_network,
    reject_request,
    request_infosec_changes,
    request_network_changes,
    submit_request,
)

from .factories import ApplicationFactory, TrafficFlowFactory, VpnRequestFactory


def make_submitted_request(**kwargs):
    """Create and submit a VPN request."""
    app = ApplicationFactory()
    req = VpnRequestFactory(
        title="Test VPN",
        nat_supported=True,
        applications=[app],
        **kwargs,
    )
    TrafficFlowFactory(vpn_request=req)
    submit_request(req)
    return req


# ── Workflow Tests ──


@pytest.mark.django_db
class TestApprovalWorkflow:
    def test_approve_infosec_from_submitted(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        approve_infosec(req, reviewer)
        assert req.status == "infosec_approved"

    def test_request_infosec_changes_from_submitted(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        request_infosec_changes(req, reviewer, comments="Fix the CIDRs")
        assert req.status == "infosec_changes_requested"

    def test_reject_from_submitted(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        reject_request(req, reviewer)
        assert req.status == "rejected"

    def test_approve_infosec_creates_approval_record(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        approve_infosec(req, reviewer, comments="Looks good")
        record = ApprovalRecord.objects.get(vpn_request=req)
        assert record.stage == "infosec"
        assert record.decision == "approved"
        assert record.reviewer == reviewer
        assert record.comments == "Looks good"

    def test_request_changes_creates_approval_record(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        request_infosec_changes(req, reviewer, comments="Needs more detail")
        record = ApprovalRecord.objects.get(vpn_request=req)
        assert record.stage == "infosec"
        assert record.decision == "changes_requested"
        assert record.comments == "Needs more detail"

    def test_reject_creates_approval_record(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        reject_request(req, reviewer, comments="Not allowed")
        record = ApprovalRecord.objects.get(vpn_request=req)
        assert record.stage == "infosec"
        assert record.decision == "rejected"
        assert record.comments == "Not allowed"

    def test_approve_infosec_from_wrong_state_raises(self):
        reviewer = UserFactory(roles=["infosec"])
        app = ApplicationFactory()
        req = VpnRequestFactory(title="Test VPN", nat_supported=True, applications=[app])
        TrafficFlowFactory(vpn_request=req)
        # Still in draft
        with pytest.raises(ValidationError):
            approve_infosec(req, reviewer)

    def test_resubmit_after_changes_requested(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        request_infosec_changes(req, reviewer, comments="Fix CIDRs")
        assert req.status == "infosec_changes_requested"

        # Resubmit
        req.resubmit_from_infosec()
        req.save()
        assert req.status == "submitted"

        # Can be approved again
        approve_infosec(req, reviewer, comments="Now it's good")
        assert req.status == "infosec_approved"
        assert ApprovalRecord.objects.filter(vpn_request=req).count() == 2

    def test_reject_from_infosec_approved_records_network_stage(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        approve_infosec(req, reviewer)
        assert req.status == "infosec_approved"

        reject_request(req, reviewer, comments="Actually no")
        assert req.status == "rejected"
        reject_record = ApprovalRecord.objects.filter(
            vpn_request=req, decision="rejected"
        ).first()
        assert reject_record.stage == "network"

    def test_approve_without_comments(self):
        reviewer = UserFactory(roles=["infosec"])
        req = make_submitted_request()
        approve_infosec(req, reviewer)
        record = ApprovalRecord.objects.get(vpn_request=req)
        assert record.comments == ""

    def test_reject_from_wrong_state_raises(self):
        reviewer = UserFactory(roles=["infosec"])
        app = ApplicationFactory()
        req = VpnRequestFactory(title="Test VPN", nat_supported=True, applications=[app])
        TrafficFlowFactory(vpn_request=req)
        # Still in draft
        with pytest.raises(ValidationError):
            reject_request(req, reviewer)


@pytest.mark.django_db
class TestNetworkApprovalWorkflow:
    def _infosec_approved_request(self, **kwargs):
        req = make_submitted_request(**kwargs)
        approve_infosec(req, UserFactory(roles=["infosec"]))
        return req

    def test_approve_network_from_infosec_approved(self):
        reviewer = UserFactory(roles=["network"])
        req = self._infosec_approved_request()
        approve_network(req, reviewer)
        assert req.status == "network_approved"
        record = ApprovalRecord.objects.get(
            vpn_request=req, stage=ApprovalRecord.Stage.NETWORK
        )
        assert record.decision == ApprovalRecord.Decision.APPROVED

    def test_request_network_changes(self):
        reviewer = UserFactory(roles=["network"])
        req = self._infosec_approved_request()
        request_network_changes(req, reviewer, comments="Routing concerns")
        assert req.status == "network_changes_requested"

    def test_approve_network_from_wrong_state_raises(self):
        reviewer = UserFactory(roles=["network"])
        req = make_submitted_request()  # not yet infosec-approved
        with pytest.raises(ValidationError):
            approve_network(req, reviewer)

    def test_network_approval_assigns_nat_ips(self):
        from apps.core.tests.factories import NatPoolFactory, SiteFactory

        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        req = self._infosec_approved_request(
            directionality="we_initiate",
            vendor_endpoint_1_ip="1.2.3.4",
            our_endpoint_1_site=site,
        )
        # InfoSec approval no longer assigns NAT
        assert req.nat_mappings.count() == 0
        approve_network(req, UserFactory(roles=["network"]))
        req = type(req).objects.get(pk=req.pk)
        assert req.status == "network_approved"
        assert req.nat_mappings.count() == 1
        assert req.nat_mappings.first().nat_address.startswith("10.111.96.")


# ── API Tests ──


@pytest.fixture
def infosec_user(db):
    return UserFactory(roles=["infosec"])


@pytest.fixture
def infosec_client(client, infosec_user):
    client.force_login(infosec_user)
    return client


@pytest.fixture
def requester_user(db):
    return UserFactory(roles=["requester"])


@pytest.fixture
def requester_client(client, requester_user):
    client.force_login(requester_user)
    return client


@pytest.fixture
def network_user(db):
    return UserFactory(roles=["network"])


@pytest.fixture
def network_client(client, network_user):
    client.force_login(network_user)
    return client


@pytest.fixture
def admin_user(db):
    return UserFactory(roles=["admin"])


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.mark.django_db
class TestApprovalAPI:
    def test_approve_infosec_as_infosec_user(self, infosec_client):
        req = make_submitted_request()
        response = infosec_client.post(
            reverse("vpn-api:approve-infosec", args=[req.pk]),
            data=json.dumps({"comments": "Approved"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["status"] == "infosec_approved"

    def test_approve_infosec_as_requester_forbidden(self, requester_client):
        req = make_submitted_request()
        response = requester_client.post(
            reverse("vpn-api:approve-infosec", args=[req.pk]),
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_approve_infosec_as_admin_allowed(self, admin_client):
        req = make_submitted_request()
        response = admin_client.post(
            reverse("vpn-api:approve-infosec", args=[req.pk]),
            data=json.dumps({"comments": "Admin approved"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "infosec_approved"

    def test_request_changes_with_comments(self, infosec_client):
        req = make_submitted_request()
        response = infosec_client.post(
            reverse("vpn-api:request-infosec-changes", args=[req.pk]),
            data=json.dumps({"comments": "Fix the CIDRs please"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "infosec_changes_requested"
        record = ApprovalRecord.objects.get(vpn_request=req)
        assert record.comments == "Fix the CIDRs please"

    def test_reject_with_comments(self, infosec_client):
        req = make_submitted_request()
        response = infosec_client.post(
            reverse("vpn-api:reject-request", args=[req.pk]),
            data=json.dumps({"comments": "Not compliant"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "rejected"
        record = ApprovalRecord.objects.get(vpn_request=req)
        assert record.comments == "Not compliant"

    def test_approve_from_wrong_status(self, infosec_client):
        app = ApplicationFactory()
        req = VpnRequestFactory(title="Test VPN", nat_supported=True, applications=[app])
        TrafficFlowFactory(vpn_request=req)
        # Still draft
        response = infosec_client.post(
            reverse("vpn-api:approve-infosec", args=[req.pk]),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_approval_queue_returns_submitted_requests(self, infosec_client):
        make_submitted_request()
        make_submitted_request()
        response = infosec_client.get(reverse("vpn-api:approval-queue"))
        assert response.status_code == 200
        data = response.json()
        assert len(data["requests"]) == 2

    def test_approve_network_as_network_user(self, network_client):
        req = make_submitted_request()
        approve_infosec(req, UserFactory(roles=["infosec"]))
        response = network_client.post(
            reverse("vpn-api:approve-network", args=[req.pk]),
            data=json.dumps({"comments": "Network approved"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "network_approved"

    def test_approve_network_as_infosec_forbidden(self, infosec_client):
        req = make_submitted_request()
        approve_infosec(req, UserFactory(roles=["infosec"]))
        response = infosec_client.post(
            reverse("vpn-api:approve-network", args=[req.pk]),
            content_type="application/json",
        )
        assert response.status_code == 403

    def test_request_network_changes_endpoint(self, network_client):
        req = make_submitted_request()
        approve_infosec(req, UserFactory(roles=["infosec"]))
        response = network_client.post(
            reverse("vpn-api:request-network-changes", args=[req.pk]),
            data=json.dumps({"comments": "Use other DC"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json()["status"] == "network_changes_requested"

    def test_queue_shows_infosec_approved_to_network_approver(self, network_client):
        req = make_submitted_request()
        approve_infosec(req, UserFactory(roles=["infosec"]))
        make_submitted_request()  # submitted — not network's stage
        response = network_client.get(reverse("vpn-api:approval-queue"))
        assert response.status_code == 200
        data = response.json()
        assert len(data["requests"]) == 1
        assert data["requests"][0]["reference_number"] == req.reference_number

    def test_approval_queue_excludes_drafts(self, infosec_client):
        make_submitted_request()
        VpnRequestFactory()  # draft
        response = infosec_client.get(reverse("vpn-api:approval-queue"))
        data = response.json()
        assert len(data["requests"]) == 1
        assert data["requests"][0]["status"] == "submitted"

    def test_approval_queue_forbidden_for_requester(self, requester_client):
        response = requester_client.get(reverse("vpn-api:approval-queue"))
        assert response.status_code == 403

    def test_approval_history_endpoint(self, infosec_client):
        req = make_submitted_request()
        infosec_client.post(
            reverse("vpn-api:approve-infosec", args=[req.pk]),
            data=json.dumps({"comments": "Looks good"}),
            content_type="application/json",
        )
        response = infosec_client.get(
            reverse("vpn-api:approval-history", args=[req.pk])
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["approvals"]) == 1
        assert data["approvals"][0]["decision"] == "approved"
        assert data["approvals"][0]["comments"] == "Looks good"
