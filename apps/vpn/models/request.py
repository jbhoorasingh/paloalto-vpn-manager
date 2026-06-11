import uuid

from auditlog.registry import auditlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django_fsm import FSMField, transition

from apps.core.models import Site

from .application import Application
from .vendor import Vendor


class RequestStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    INFOSEC_APPROVED = "infosec_approved", "InfoSec Approved"
    INFOSEC_CHANGES_REQUESTED = "infosec_changes_requested", "InfoSec Changes Requested"
    NETWORK_APPROVED = "network_approved", "Network Approved"
    NETWORK_CHANGES_REQUESTED = "network_changes_requested", "Network Changes Requested"
    REJECTED = "rejected", "Rejected"
    SCHEDULED = "scheduled", "Scheduled"
    DEPLOY_READY = "deploy_ready", "Deploy Ready"
    DEPLOYED = "deployed", "Deployed"
    ACTIVE = "active", "Active"
    RECERT_DUE = "recert_due", "Recert Due"
    RECERT_IN_REVIEW = "recert_in_review", "Recert In Review"
    RECERT_APPROVED = "recert_approved", "Recert Approved"
    DECOMMISSION_REQUESTED = "decommission_requested", "Decommission Requested"
    DECOMMISSION_APPROVED = "decommission_approved", "Decommission Approved"
    DECOMMISSIONED = "decommissioned", "Decommissioned"


class Directionality(models.TextChoices):
    WE_INITIATE = "we_initiate", "We Initiate"
    VENDOR_INITIATES = "vendor_initiates", "Vendor Initiates"
    BOTH = "both", "Both Can Initiate"


class TopologyType(models.TextChoices):
    BOW_TIE = "bow_tie", "Bow Tie"
    MATCHED_PAIRS = "matched_pairs", "Matched Pairs"


class IkeVersion(models.TextChoices):
    V1 = "1", "IKEv1"
    V2 = "2", "IKEv2"


class AuthMethod(models.TextChoices):
    PSK = "psk", "Pre-Shared Key"
    CERTIFICATE = "certificate", "Certificate"


class RoutingType(models.TextChoices):
    STATIC = "static", "Static"
    BGP = "bgp", "BGP"


class TunnelIpAssignment(models.TextChoices):
    WE_ASSIGN = "we_assign", "We Assign (from tunnel IP pool)"
    MUTUAL = "mutual", "Mutually Agreed"
    APIPA = "apipa", "APIPA (169.254.x.x)"


def generate_reference_number():
    return f"VPN-{uuid.uuid4().hex[:8].upper()}"


class VpnRequest(models.Model):
    # Identity
    reference_number = models.CharField(
        max_length=20, unique=True, default=generate_reference_number, editable=False
    )

    # Relations
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, null=True, blank=True, related_name="vpn_requests")
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vpn_requests"
    )
    applications = models.ManyToManyField(Application, through="VpnRequestApplication", blank=True)

    # Business
    title = models.CharField(max_length=300, blank=True)
    purpose = models.TextField(blank=True)
    directionality = models.CharField(
        max_length=20, choices=Directionality.choices, blank=True
    )
    data_description = models.TextField(blank=True)
    data_classification = models.CharField(max_length=50, blank=True)

    # Topology
    vendor_endpoints_count = models.PositiveSmallIntegerField(
        default=1, choices=((1, "1"), (2, "2"))
    )
    topology_type = models.CharField(
        max_length=20, choices=TopologyType.choices, blank=True
    )
    vendor_endpoint_1_ip = models.GenericIPAddressField(null=True, blank=True)
    vendor_endpoint_2_ip = models.GenericIPAddressField(null=True, blank=True)
    our_endpoint_1_site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True, related_name="vpn_endpoint_1_requests"
    )
    our_endpoint_2_site = models.ForeignKey(
        Site, on_delete=models.SET_NULL, null=True, blank=True, related_name="vpn_endpoint_2_requests"
    )

    # IKE (Phase 1)
    ike_version = models.CharField(max_length=2, choices=IkeVersion.choices, default=IkeVersion.V2)
    auth_method = models.CharField(max_length=20, choices=AuthMethod.choices, default=AuthMethod.PSK)
    ike_encryption = models.CharField(max_length=50, blank=True, help_text="e.g. aes-256-cbc")
    ike_integrity = models.CharField(max_length=50, blank=True, help_text="e.g. sha256")
    ike_dh_group = models.CharField(max_length=20, blank=True, help_text="e.g. 14, 19, 20")
    ike_lifetime = models.PositiveIntegerField(null=True, blank=True, help_text="Lifetime in seconds")
    dpd_enabled = models.BooleanField(default=True)

    # IPsec (Phase 2)
    ipsec_encryption = models.CharField(max_length=50, blank=True, help_text="e.g. aes-256-gcm")
    ipsec_integrity = models.CharField(max_length=50, blank=True, help_text="e.g. sha256")
    ipsec_pfs_group = models.CharField(max_length=20, blank=True, help_text="PFS DH group")
    ipsec_lifetime = models.PositiveIntegerField(null=True, blank=True, help_text="Lifetime in seconds")
    tunnel_mode = models.CharField(max_length=20, default="tunnel", blank=True)

    # Routing
    routing_type = models.CharField(max_length=10, choices=RoutingType.choices, blank=True)
    vendor_cidrs = models.TextField(
        blank=True, help_text="Vendor CIDRs for static routing (one per line or comma-separated)"
    )
    bgp_local_asn = models.PositiveIntegerField(null=True, blank=True)
    bgp_remote_asn = models.PositiveIntegerField(null=True, blank=True, help_text="Vendor ASN for endpoint 1")
    bgp_remote_asn_2 = models.PositiveIntegerField(null=True, blank=True, help_text="Vendor ASN for endpoint 2 (if different)")
    bgp_peer_ip_local = models.GenericIPAddressField(null=True, blank=True)
    bgp_peer_ip_remote = models.GenericIPAddressField(null=True, blank=True)
    bgp_auth_enabled = models.BooleanField(default=False)
    tunnel_ip_assignment = models.CharField(
        max_length=20, choices=TunnelIpAssignment.choices, blank=True, default="",
        help_text="How tunnel interface IPs are assigned"
    )
    mutual_tunnel_ips = models.TextField(
        blank=True, default="",
        help_text='JSON: per-tunnel local/remote IPs when tunnel_ip_assignment is "mutual"'
    )

    # NAT
    nat_supported = models.BooleanField(null=True, blank=True)
    nat_exception_reason = models.TextField(blank=True)

    # FSM
    status = FSMField(default=RequestStatus.DRAFT, choices=RequestStatus.choices, protected=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference_number} - {self.title or 'Untitled'}"

    def validate_for_submission(self):
        """Check all required fields before submission."""
        errors = []
        if not self.vendor_id:
            errors.append("A vendor must be selected.")
        if not self.applications.exists():
            errors.append("At least one application is required.")
        if not self.flows.exists():
            errors.append("At least one traffic flow is required.")
        if not self.title:
            errors.append("A title is required.")
        return errors

    # === FSM Transitions ===

    @transition(field=status, source=RequestStatus.DRAFT, target=RequestStatus.SUBMITTED)
    def submit(self):
        from django.utils import timezone
        errors = self.validate_for_submission()
        if errors:
            raise ValidationError(errors)
        self.submitted_at = timezone.now()

    @transition(field=status, source=RequestStatus.SUBMITTED, target=RequestStatus.INFOSEC_APPROVED)
    def approve_infosec(self):
        pass

    @transition(field=status, source=RequestStatus.SUBMITTED, target=RequestStatus.INFOSEC_CHANGES_REQUESTED)
    def request_infosec_changes(self):
        pass

    @transition(
        field=status,
        source=[RequestStatus.SUBMITTED, RequestStatus.INFOSEC_APPROVED],
        target=RequestStatus.REJECTED,
    )
    def reject(self):
        pass

    @transition(
        field=status, source=RequestStatus.INFOSEC_CHANGES_REQUESTED, target=RequestStatus.SUBMITTED
    )
    def resubmit_from_infosec(self):
        from django.utils import timezone
        self.submitted_at = timezone.now()

    @transition(field=status, source=RequestStatus.INFOSEC_APPROVED, target=RequestStatus.NETWORK_APPROVED)
    def approve_network(self):
        pass

    @transition(
        field=status, source=RequestStatus.INFOSEC_APPROVED, target=RequestStatus.NETWORK_CHANGES_REQUESTED
    )
    def request_network_changes(self):
        pass

    @transition(
        field=status, source=RequestStatus.NETWORK_CHANGES_REQUESTED, target=RequestStatus.INFOSEC_APPROVED
    )
    def resubmit_from_network(self):
        pass

    @transition(field=status, source=RequestStatus.NETWORK_APPROVED, target=RequestStatus.SCHEDULED)
    def schedule(self):
        pass

    @transition(field=status, source=RequestStatus.SCHEDULED, target=RequestStatus.DEPLOY_READY)
    def mark_deploy_ready(self):
        pass

    @transition(field=status, source=RequestStatus.DEPLOY_READY, target=RequestStatus.DEPLOYED)
    def deploy(self):
        pass

    @transition(field=status, source=RequestStatus.DEPLOYED, target=RequestStatus.ACTIVE)
    def activate(self):
        pass

    @transition(field=status, source=RequestStatus.ACTIVE, target=RequestStatus.RECERT_DUE)
    def mark_recert_due(self):
        pass

    @transition(field=status, source=RequestStatus.RECERT_DUE, target=RequestStatus.RECERT_IN_REVIEW)
    def start_recert_review(self):
        pass

    @transition(field=status, source=RequestStatus.RECERT_IN_REVIEW, target=RequestStatus.ACTIVE)
    def approve_recert(self):
        pass

    @transition(field=status, source=RequestStatus.ACTIVE, target=RequestStatus.DECOMMISSION_REQUESTED)
    def request_decommission(self):
        pass

    @transition(
        field=status, source=RequestStatus.DECOMMISSION_REQUESTED, target=RequestStatus.DECOMMISSION_APPROVED
    )
    def approve_decommission(self):
        pass

    @transition(
        field=status, source=RequestStatus.DECOMMISSION_APPROVED, target=RequestStatus.DECOMMISSIONED
    )
    def decommission(self):
        pass


class VpnRequestApplication(models.Model):
    vpn_request = models.ForeignKey(VpnRequest, on_delete=models.CASCADE)
    application = models.ForeignKey(Application, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("vpn_request", "application")

    def __str__(self):
        return f"{self.vpn_request.reference_number} - {self.application.name}"


auditlog.register(
    VpnRequest,
    exclude_fields=["id", "created_at", "updated_at"],
)
