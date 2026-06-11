from django.db import models


class TunnelInterface(models.Model):
    vpn_request = models.ForeignKey(
        "vpn.VpnRequest", on_delete=models.CASCADE, related_name="tunnel_interfaces"
    )
    site = models.ForeignKey(
        "core.Site", on_delete=models.PROTECT, related_name="tunnel_interfaces"
    )
    tunnel_number = models.PositiveIntegerField(
        help_text="Tunnel interface number assigned from site range"
    )
    local_ip = models.GenericIPAddressField(
        null=True, blank=True, help_text="Our side of the /30"
    )
    remote_ip = models.GenericIPAddressField(
        null=True, blank=True, help_text="Vendor side of the /30"
    )
    subnet_cidr = models.CharField(
        max_length=50, blank=True, help_text="The /30 subnet, e.g. 10.255.0.0/30"
    )
    address_pool = models.ForeignKey(
        "core.TunnelAddressPool", on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Source pool (null for APIPA/mutual)"
    )
    vendor_endpoint_ip = models.GenericIPAddressField(
        null=True, blank=True, help_text="Which vendor endpoint this tunnel connects to"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("site", "tunnel_number")
        ordering = ["vpn_request", "site", "tunnel_number"]

    def __str__(self):
        return f"tunnel.{self.tunnel_number} @ {self.site.code} — {self.subnet_cidr or 'unassigned'}"
