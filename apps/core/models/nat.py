import netaddr
from django.core.exceptions import ValidationError
from django.db import models


class NatDirection(models.TextChoices):
    INBOUND = "inbound", "Inbound (Vendor → Us)"
    OUTBOUND = "outbound", "Outbound (We → Vendor)"


class NatPoolScope(models.TextChoices):
    SITE = "site", "Site-specific"
    SHARED = "shared", "Shared (DR pair)"


class NatPool(models.Model):
    """
    A pre-allocated IPAM range used to NAT VPN traffic at the firewall boundary.

    Two scopes:
      * site-specific — used by single-site VPN requests; tied to one Site.
      * shared (DR)   — used by two-site (DR pair) requests; not tied to a Site.
        The same NAT address is provisioned at BOTH endpoints and advertised
        from both, with AS-path prepend making the primary site preferred, so
        a tunnel failure at one site fails over to the same NAT address at
        the other.

    Per direction:
      * outbound — addresses internal services target; DNATs to the real vendor host
      * inbound  — addresses vendors target; DNATs to the real internal service

    Individual VPN connections carve /32 host mappings or sub-ranges out of these
    pools (see vpn.NatMapping). Ranges must never overlap with internal RFC-1918
    space or with each other, so route advertisement stays unambiguous.
    """

    site = models.ForeignKey(
        "core.Site", on_delete=models.CASCADE, related_name="nat_pools",
        null=True, blank=True,
        help_text="Owning site for site-specific pools; empty for shared (DR) pools",
    )
    scope = models.CharField(
        max_length=10, choices=NatPoolScope.choices, default=NatPoolScope.SITE,
        help_text="Site-specific (single-site requests) or shared (DR-pair requests)",
    )
    dr_peer = models.ForeignKey(
        "core.DrPeer", on_delete=models.CASCADE, related_name="nat_pools",
        null=True, blank=True,
        help_text="Owning DR peer for shared pools; empty for site-specific pools",
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
        if self.site:
            owner = self.site.code
        elif self.dr_peer:
            owner = self.dr_peer.name
        else:
            owner = "shared"
        return f"{owner} — {self.get_direction_display()} {self.cidr}"

    def clean(self):
        super().clean()
        # Scope/owner consistency
        if self.scope == NatPoolScope.SHARED:
            if self.site_id:
                raise ValidationError({"site": "Shared (DR) pools must not be tied to a site."})
            if not self.dr_peer_id:
                raise ValidationError({"dr_peer": "Shared pools must be assigned to a DR peer."})
        else:
            if not self.site_id:
                raise ValidationError({"site": "Site-specific pools require a site."})
            if self.dr_peer_id:
                raise ValidationError({"dr_peer": "Site-specific pools must not have a DR peer."})

        # Validate CIDR format
        try:
            network = netaddr.IPNetwork(self.cidr)
        except (netaddr.AddrFormatError, ValueError):
            raise ValidationError({"cidr": f"'{self.cidr}' is not a valid CIDR notation."})

        # Overlap rules: a NAT'd address must be unambiguous when advertised
        # into the routing fabric. Site pools must not overlap pools on the
        # same site or any shared pool; shared pools must not overlap ANY
        # active pool anywhere (they are provisioned at every DR endpoint).
        if self.is_active:
            from django.db.models import Q

            if self.scope == NatPoolScope.SHARED:
                existing = NatPool.objects.filter(is_active=True)
            else:
                existing = NatPool.objects.filter(is_active=True).filter(
                    Q(site=self.site) | Q(scope=NatPoolScope.SHARED)
                )
            for pool in existing.exclude(pk=self.pk):
                try:
                    existing_net = netaddr.IPNetwork(pool.cidr)
                except (netaddr.AddrFormatError, ValueError):
                    continue
                if network.network in existing_net or existing_net.network in network:
                    raise ValidationError({
                        "cidr": f"Overlaps with existing NAT pool {pool} ({pool.cidr})."
                    })
