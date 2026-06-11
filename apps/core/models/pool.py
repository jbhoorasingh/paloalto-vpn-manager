import netaddr
from django.core.exceptions import ValidationError
from django.db import models


class TunnelAddressPool(models.Model):
    site = models.ForeignKey(
        "core.Site", on_delete=models.CASCADE, related_name="tunnel_address_pools"
    )
    cidr = models.CharField(
        max_length=50,
        help_text="Parent CIDR from which /30 subnets are carved, e.g. 10.255.0.0/24",
    )
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("site", "cidr")
        ordering = ["site", "cidr"]

    def __str__(self):
        return f"{self.site.code} — {self.cidr}"

    def clean(self):
        super().clean()
        # Validate CIDR format
        try:
            network = netaddr.IPNetwork(self.cidr)
        except (netaddr.AddrFormatError, ValueError):
            raise ValidationError({"cidr": f"'{self.cidr}' is not a valid CIDR notation."})

        if network.prefixlen > 30:
            raise ValidationError({"cidr": "Pool CIDR must be /30 or larger to carve /30 subnets."})

        # Check overlap with other active pools on the same site
        if self.is_active:
            existing = TunnelAddressPool.objects.filter(
                site=self.site, is_active=True
            ).exclude(pk=self.pk)
            for pool in existing:
                try:
                    existing_net = netaddr.IPNetwork(pool.cidr)
                except (netaddr.AddrFormatError, ValueError):
                    continue
                if network.network in existing_net or existing_net.network in network:
                    raise ValidationError({
                        "cidr": f"Overlaps with existing pool {pool.cidr} on this site."
                    })
