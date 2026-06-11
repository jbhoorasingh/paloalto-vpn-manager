import pytest
from django.core.exceptions import ValidationError
from django_fsm import TransitionNotAllowed

from .factories import ApplicationFactory, TrafficFlowFactory, VpnRequestFactory


def make_submittable_request(**kwargs):
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


# Transition path to reach each state from draft
TRANSITION_PATHS = {
    "draft": [],
    "submitted": ["submit"],
    "infosec_approved": ["submit", "approve_infosec"],
    "infosec_changes_requested": ["submit", "request_infosec_changes"],
    "network_approved": ["submit", "approve_infosec", "approve_network"],
    "network_changes_requested": ["submit", "approve_infosec", "request_network_changes"],
    "rejected": ["submit", "reject"],
    "scheduled": ["submit", "approve_infosec", "approve_network", "schedule"],
    "deploy_ready": ["submit", "approve_infosec", "approve_network", "schedule", "mark_deploy_ready"],
    "deployed": ["submit", "approve_infosec", "approve_network", "schedule", "mark_deploy_ready", "deploy"],
    "active": ["submit", "approve_infosec", "approve_network", "schedule", "mark_deploy_ready", "deploy", "activate"],
    "recert_due": [
        "submit", "approve_infosec", "approve_network", "schedule",
        "mark_deploy_ready", "deploy", "activate", "mark_recert_due",
    ],
    "recert_in_review": [
        "submit", "approve_infosec", "approve_network", "schedule",
        "mark_deploy_ready", "deploy", "activate", "mark_recert_due", "start_recert_review",
    ],
    "decommission_requested": [
        "submit", "approve_infosec", "approve_network", "schedule",
        "mark_deploy_ready", "deploy", "activate", "request_decommission",
    ],
    "decommission_approved": [
        "submit", "approve_infosec", "approve_network", "schedule",
        "mark_deploy_ready", "deploy", "activate", "request_decommission", "approve_decommission",
    ],
    "decommissioned": [
        "submit", "approve_infosec", "approve_network", "schedule",
        "mark_deploy_ready", "deploy", "activate", "request_decommission",
        "approve_decommission", "decommission",
    ],
}


def advance_to_state(req, target_state):
    """Walk the FSM transition chain to reach target_state from draft."""
    path = TRANSITION_PATHS.get(target_state)
    if path is None:
        raise ValueError(f"Unknown target state: {target_state}")
    for method_name in path:
        getattr(req, method_name)()
        req.save()
    assert req.status == target_state


@pytest.mark.django_db
class TestFSMTransitions:
    @pytest.mark.parametrize("source,method,expected_target,should_succeed", [
        ("draft", "submit", "submitted", True),
        ("submitted", "approve_infosec", "infosec_approved", True),
        ("submitted", "request_infosec_changes", "infosec_changes_requested", True),
        ("submitted", "reject", "rejected", True),
        ("infosec_changes_requested", "resubmit_from_infosec", "submitted", True),
        ("infosec_approved", "approve_network", "network_approved", True),
        ("infosec_approved", "request_network_changes", "network_changes_requested", True),
        ("infosec_approved", "reject", "rejected", True),
        ("network_changes_requested", "resubmit_from_network", "infosec_approved", True),
        ("network_approved", "schedule", "scheduled", True),
        ("scheduled", "mark_deploy_ready", "deploy_ready", True),
        ("deploy_ready", "deploy", "deployed", True),
        ("deployed", "activate", "active", True),
        ("active", "mark_recert_due", "recert_due", True),
        ("recert_due", "start_recert_review", "recert_in_review", True),
        ("recert_in_review", "approve_recert", "active", True),
        ("active", "request_decommission", "decommission_requested", True),
        ("decommission_requested", "approve_decommission", "decommission_approved", True),
        ("decommission_approved", "decommission", "decommissioned", True),
    ])
    def test_valid_transitions(self, source, method, expected_target, should_succeed):
        req = make_submittable_request()
        advance_to_state(req, source)

        transition_fn = getattr(req, method)
        if should_succeed:
            transition_fn()
            req.save()
            assert req.status == expected_target

    @pytest.mark.parametrize("source,method", [
        ("draft", "approve_infosec"),
        ("draft", "approve_network"),
        ("draft", "reject"),
        ("submitted", "approve_network"),
        ("submitted", "schedule"),
        ("infosec_approved", "submit"),
        ("network_approved", "approve_infosec"),
        ("active", "submit"),
        ("decommissioned", "activate"),
    ])
    def test_invalid_transitions(self, source, method):
        req = make_submittable_request()
        advance_to_state(req, source)

        transition_fn = getattr(req, method)
        with pytest.raises(TransitionNotAllowed):
            transition_fn()

    def test_submit_validates_required_fields(self):
        req = VpnRequestFactory(title="", vendor=None, nat_supported=None)
        with pytest.raises(ValidationError):
            req.submit()

    def test_submit_sets_submitted_at(self):
        req = make_submittable_request()
        req.submit()
        req.save()
        assert req.submitted_at is not None
        assert req.status == "submitted"

    def test_submit_requires_vendor(self):
        app = ApplicationFactory()
        req = VpnRequestFactory(vendor=None, title="Test", nat_supported=True, applications=[app])
        TrafficFlowFactory(vpn_request=req)
        with pytest.raises(ValidationError):
            req.submit()

    def test_submit_requires_applications(self):
        req = VpnRequestFactory(title="Test", nat_supported=True)
        TrafficFlowFactory(vpn_request=req)
        with pytest.raises(ValidationError):
            req.submit()

    def test_submit_requires_flows(self):
        app = ApplicationFactory()
        req = VpnRequestFactory(title="Test", nat_supported=True, applications=[app])
        with pytest.raises(ValidationError):
            req.submit()

    def test_submit_allows_nat_not_sure(self):
        app = ApplicationFactory()
        req = VpnRequestFactory(title="Test", nat_supported=None, applications=[app])
        TrafficFlowFactory(vpn_request=req)
        req.submit()
        req.save()
        assert req.status == "submitted"
