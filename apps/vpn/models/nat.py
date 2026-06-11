from django.db import models

from apps.core.models import NatDirection


class NatMapping(models.Model):
    """
    A concrete NAT translation carved out of a site's NatPool for one VPN request.

    Each mapping ties a published, NAT'd address (``nat_address``, drawn from the
    site's inbound or outbound NatPool) to the real backend it translates to
    (``real_address``):

      * outbound (we → vendor): internal services target ``nat_address``; the
        firewall DNATs it to the real vendor host (``real_address``).
      * inbound  (vendor → us): the vendor targets ``nat_address``; the firewall
        DNATs it to the real internal service (``real_address``).

    Mappings are scoped to an endpoint (Site) because NAT fires on the inside
    interface of the firewall at that region, preserving traffic symmetry.
    """

    vpn_request = models.ForeignKey(
        "vpn.VpnRequest", on_delete=models.CASCADE, related_name="nat_mappings"
    )
    site = models.ForeignKey(
        "core.Site", on_delete=models.PROTECT, related_name="nat_mappings",
        help_text="The endpoint/firewall region where this NAT rule lives",
    )
    direction = models.CharField(
        max_length=10, choices=NatDirection.choices,
        help_text="Inbound (vendor→us) or outbound (us→vendor)",
    )
    nat_pool = models.ForeignKey(
        "core.NatPool", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="mappings", help_text="Source pool this address was allocated from",
    )
    nat_address = models.CharField(
        max_length=50,
        help_text="The NAT'd address/range carved from the pool, e.g. 10.111.96.10/32",
    )
    real_address = models.CharField(
        max_length=50,
        help_text="The real backend it translates to (vendor host for outbound, internal service for inbound)",
    )
    traffic_flow = models.ForeignKey(
        "vpn.TrafficFlow", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="nat_mappings", help_text="The traffic flow this mapping serves",
    )
    description = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("site", "direction", "nat_address")
        ordering = ["vpn_request", "site", "direction", "nat_address"]

    def __str__(self):
        arrow = "→" if self.direction == NatDirection.OUTBOUND else "←"
        return f"{self.get_direction_display()}: {self.nat_address} {arrow} {self.real_address} @ {self.site.code}"
