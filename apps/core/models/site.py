from django.core.exceptions import ValidationError
from django.db import models


class Site(models.Model):
    class DeviceBrand(models.TextChoices):
        PALO_ALTO = "palo_alto", "Palo Alto"
        CISCO = "cisco", "Cisco"
        FORTINET = "fortinet", "Fortinet"
        JUNIPER = "juniper", "Juniper"
        CHECK_POINT = "check_point", "Check Point"
        OTHER = "other", "Other"

    class ManagementType(models.TextChoices):
        CENTRALIZED = "centralized", "Centrally Managed"
        STANDALONE = "standalone", "Standalone"

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True, help_text="Short identifier, e.g. 'region1'")
    location = models.CharField(max_length=200, blank=True)
    datacenter = models.CharField(max_length=100, blank=True)
    public_ip = models.GenericIPAddressField(null=True, blank=True)
    bgp_asn = models.PositiveIntegerField(null=True, blank=True, help_text="BGP Autonomous System Number")

    # Device information
    device_brand = models.CharField(
        max_length=20, choices=DeviceBrand.choices, blank=True,
        help_text="Firewall/device brand"
    )
    management_type = models.CharField(
        max_length=20, choices=ManagementType.choices, blank=True,
        help_text="Centrally managed or standalone"
    )
    management_platform = models.CharField(
        max_length=100, blank=True,
        help_text="Management platform name, e.g. Panorama"
    )
    device_group = models.CharField(
        max_length=100, blank=True,
        help_text="Device group in management platform"
    )
    template_name = models.CharField(
        max_length=100, blank=True,
        help_text="Template/template stack in management platform"
    )

    # Tunnel interface allocation
    tunnel_interface_start = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Start of tunnel interface number range (e.g. 100)"
    )
    tunnel_interface_end = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="End of tunnel interface number range (e.g. 199)"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"

    def clean(self):
        super().clean()
        start = self.tunnel_interface_start
        end = self.tunnel_interface_end
        if start is not None and end is not None and start >= end:
            raise ValidationError({
                "tunnel_interface_end": "Tunnel interface end must be greater than start."
            })


class DrPeer(models.Model):
    """
    A DR pair of firewalls (Sites). Two-site VPN requests whose endpoints
    match a DR peer draw their NAT addresses from the peer's shared NAT
    pools — the same address is provisioned at both members, advertised from
    both, and the secondary prepends its AS so the primary path is preferred.
    """

    name = models.CharField(max_length=100, unique=True, help_text="e.g. 'East Coast DR pair'")
    primary_site = models.OneToOneField(
        Site, on_delete=models.PROTECT, related_name="dr_peer_as_primary",
        help_text="Preferred site — advertised without AS-path prepend",
    )
    secondary_site = models.OneToOneField(
        Site, on_delete=models.PROTECT, related_name="dr_peer_as_secondary",
        help_text="Failover site — advertises the same NAT ranges with AS-path prepend",
    )
    description = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "DR peer"

    def __str__(self):
        return f"{self.name} ({self.primary_site.code} ⇄ {self.secondary_site.code})"

    @property
    def site_pks(self):
        return {self.primary_site_id, self.secondary_site_id}

    @classmethod
    def for_sites(cls, site_a, site_b):
        """Find the active DR peer containing exactly these two sites (any order)."""
        if not site_a or not site_b:
            return None
        pks = {site_a.pk, site_b.pk}
        for peer in cls.objects.filter(is_active=True).filter(
            models.Q(primary_site__in=pks) | models.Q(secondary_site__in=pks)
        ):
            if peer.site_pks == pks:
                return peer
        return None

    def clean(self):
        super().clean()
        if self.primary_site_id and self.primary_site_id == self.secondary_site_id:
            raise ValidationError({
                "secondary_site": "Primary and secondary must be different sites."
            })
        # A firewall belongs to at most one DR peer, in either role.
        for field in ("primary_site_id", "secondary_site_id"):
            site_id = getattr(self, field)
            if not site_id:
                continue
            conflict = (
                DrPeer.objects.exclude(pk=self.pk)
                .filter(models.Q(primary_site_id=site_id) | models.Q(secondary_site_id=site_id))
                .first()
            )
            if conflict:
                raise ValidationError({
                    field.replace("_id", ""): f"Site is already part of DR peer '{conflict.name}'."
                })
