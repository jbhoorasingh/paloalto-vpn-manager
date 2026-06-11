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
