from django.conf import settings
from django.db import models


class ApprovalRecord(models.Model):
    class Decision(models.TextChoices):
        APPROVED = "approved", "Approved"
        CHANGES_REQUESTED = "changes_requested", "Changes Requested"
        REJECTED = "rejected", "Rejected"

    class Stage(models.TextChoices):
        INFOSEC = "infosec", "InfoSec"
        NETWORK = "network", "Network"

    vpn_request = models.ForeignKey(
        "vpn.VpnRequest",
        on_delete=models.CASCADE,
        related_name="approval_records",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_reviews",
    )
    stage = models.CharField(max_length=20, choices=Stage.choices)
    decision = models.CharField(max_length=20, choices=Decision.choices)
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.vpn_request.reference_number} - {self.get_stage_display()} {self.get_decision_display()}"
