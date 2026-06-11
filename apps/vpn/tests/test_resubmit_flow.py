"""
Regression tests: a request in a changes-requested state (InfoSec OR Network)
must never be stuck — the requester, and an admin acting on their behalf, can
edit it through the wizard and resubmit.
"""

import json

import pytest
from django.urls import reverse

from apps.core.tests.factories import UserFactory
from apps.vpn.services.workflow import (
    approve_infosec,
    request_infosec_changes,
    request_network_changes,
    submit_request,
)
from apps.vpn.tests.factories import ApplicationFactory, TrafficFlowFactory, VpnRequestFactory

CHANGES_STATES = ["infosec_changes_requested", "network_changes_requested"]
# Where each changes-requested state lands after resubmission
RESUBMIT_TARGET = {
    "infosec_changes_requested": "submitted",
    "network_changes_requested": "infosec_approved",
}


def _request_in(status, requester):
    app = ApplicationFactory()
    req = VpnRequestFactory(
        title="Test VPN", nat_supported=True, applications=[app], requester=requester
    )
    TrafficFlowFactory(vpn_request=req)
    submit_request(req)
    if status == "infosec_changes_requested":
        request_infosec_changes(req, UserFactory(roles=["infosec"]))
    elif status == "network_changes_requested":
        approve_infosec(req, UserFactory(roles=["infosec"]))
        req = type(req).objects.get(pk=req.pk)
        request_network_changes(req, UserFactory(roles=["network"]))
    return type(req).objects.get(pk=req.pk)


def _exercise_edit_and_resubmit(client, req, status):
    """Full path: detail button → wizard page → load → save step → resubmit."""
    detail = client.get(reverse("ui:request-detail", args=[req.pk]))
    assert "Edit &amp; Resubmit" in detail.content.decode(), f"no edit button at {status}"

    page = client.get(reverse("ui:wizard-edit", args=[req.pk]))
    assert page.status_code == 200

    load = client.get(reverse("vpn-api:wizard-load", args=[req.pk]))
    assert load.status_code == 200
    assert load.json().get("reviewer_comments") is not None

    save = client.patch(
        reverse("vpn-api:wizard-save-step", args=[req.pk, 2]),
        data=json.dumps({
            "title": "updated title", "purpose": "p",
            "data_description": "d", "data_classification": "internal",
        }),
        content_type="application/json",
    )
    assert save.status_code == 200, f"step save failed at {status}: {save.content}"

    submit = client.post(
        reverse("vpn-api:wizard-submit", args=[req.pk]), content_type="application/json"
    )
    assert submit.status_code == 200, f"resubmit failed at {status}: {submit.content}"
    assert submit.json()["status"] == RESUBMIT_TARGET[status]


@pytest.mark.django_db
@pytest.mark.parametrize("status", CHANGES_STATES)
class TestResubmitFlow:
    def test_requester_can_edit_and_resubmit(self, client, status):
        requester = UserFactory(roles=["requester"])
        client.force_login(requester)
        req = _request_in(status, requester)
        _exercise_edit_and_resubmit(client, req, status)

    def test_admin_can_edit_and_resubmit_for_requester(self, client, status):
        requester = UserFactory(roles=["requester"])
        admin = UserFactory(roles=["admin"])
        client.force_login(admin)
        req = _request_in(status, requester)
        _exercise_edit_and_resubmit(client, req, status)

    def test_other_users_still_cannot_edit(self, client, status):
        requester = UserFactory(roles=["requester"])
        outsider = UserFactory(roles=["requester"])
        client.force_login(outsider)
        req = _request_in(status, requester)

        detail = client.get(reverse("ui:request-detail", args=[req.pk]))
        assert "Edit &amp; Resubmit" not in detail.content.decode()
        assert client.get(reverse("ui:wizard-edit", args=[req.pk])).status_code == 404
        assert client.get(reverse("vpn-api:wizard-load", args=[req.pk])).status_code == 404
        submit = client.post(
            reverse("vpn-api:wizard-submit", args=[req.pk]), content_type="application/json"
        )
        assert submit.status_code == 404

    def test_request_list_marks_row_editable(self, client, status):
        requester = UserFactory(roles=["requester"])
        client.force_login(requester)
        req = _request_in(status, requester)
        response = client.get(reverse("vpn-api:request-list"))
        rows = {r["id"]: r for r in response.json()["requests"]}
        assert rows[req.pk]["can_edit"] is True

    def test_admin_can_edit_flows_during_resubmission(self, client, status):
        requester = UserFactory(roles=["requester"])
        admin = UserFactory(roles=["admin"])
        client.force_login(admin)
        req = _request_in(status, requester)
        response = client.post(
            reverse("vpn-api:flow-list-create", args=[req.pk]),
            data=json.dumps({
                "source_cidr": "10.5.0.0/24",
                "destination_cidr": "172.16.9.9/32",
                "direction": "outbound",
                "protocol": "tcp",
                "destination_ports": "443",
            }),
            content_type="application/json",
        )
        assert response.status_code == 201
