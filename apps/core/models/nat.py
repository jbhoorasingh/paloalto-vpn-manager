import netaddr
from django.core.exceptions import ValidationError
from django.db import models


class NatDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound (Vendor → Us)"
    OUTBOUND = "outbound", "Outbound (We → Vendor)"


class NatPool(models.Model):
    """
    A pre-allocated IPAM range used to NAT VPN traffic at the firewall boundary.

    Per the NAT framework, every region (Site) gets two dedicated ranges:
      * outbound — addresses internal services target; DNATs to the real vendor host
      * inbound  — addresses vendors target; DNATs to the real internal service

    Individual VPN connections carve /32 host mappings or sub-ranges out of these
    pools (see vpn.NatMapping). Ranges must never overlap with internal RFC-1918
    space or with each other, so route advertisement stays unambiguous.
    """

    site = models.ForeignKey(
        "core.Site", on_delete=models.CASCADE, related_name="nat_pools"
    )
    direction = models.CharField(
        max_length=10,
        choices=NatDirection.choices,
        help_text="Whether this pool NATs inbound (vendor→us) or outbound (us→vendor) traffic",
    )
    cidr = models.CharField(
        max_length=50,
        help_text="Dedicated NAT range, e.g. 10.111.96.0/24 (outbound) or 10.111.100.0/24 (inbound)",
    )
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("site", "direction", "cidr")
        ordering = ["site", "direction", "cidr"]

    def __str__(self):
        return f"{self.site.code} — {self.get_direction_display()} {self.cidr}"

    def clean(self):
        super().clean()
        # Validate CIDR format
        try:
            network = netaddr.IPNetwork(self.cidr)
        except (netaddr.AddrFormatError, ValueError):
            raise ValidationError({"cidr": f"'{self.cidr}' is not a valid CIDR notation."})

        # Check overlap with any other active NAT pool on the same site (either
        # direction). Inbound and outbound ranges must stay disjoint so a NAT'd
        # address is unambiguous when advertised into the routing fabric.
        if self.is_active:
            existing = NatPool.objects.filter(
                site=self.site, is_active=True
            ).exclude(pk=self.pk)
            for pool in existing:
                try:
                    existing_net = netaddr.IPNetwork(pool.cidr)
                except (netaddr.AddrFormatError, ValueError):
                    continue
                if network.network in existing_net or existing_net.network in network:
                    raise ValidationError({
                        "cidr": f"Overlaps with existing NAT pool {pool.cidr} on this site."
                    })
