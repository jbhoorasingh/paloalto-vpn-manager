import re

import netaddr
from auditlog.registry import auditlog
from django.core.exceptions import ValidationError
from django.db import models

from .application import Application

RFC1918_SPACE = netaddr.IPSet([
    netaddr.IPNetwork("10.0.0.0/8"),
    netaddr.IPNetwork("172.16.0.0/12"),
    netaddr.IPNetwork("192.168.0.0/16"),
])


def is_rfc1918(cidr):
    """True if the CIDR falls inside private RFC-1918 space."""
    if not cidr:
        return False
    try:
        network = netaddr.IPNetwork(cidr)
    except (netaddr.AddrFormatError, ValueError):
        return False
    return netaddr.IPSet([network]).issubset(RFC1918_SPACE)


class FlowProtocol(models.TextChoices):
    TCP = "tcp", "TCP"
    UDP = "udp", "UDP"
    ICMP = "icmp", "ICMP"
    ANY = "any", "Any"


class FlowDirection(models.TextChoices):
    """
    Who initiates the connection. Determines which boundary NAT pool the
    flow's mapping is carved from (outbound vs inbound) — values match
    core.NatDirection on purpose.
    """
    OUTBOUND = "outbound", "Outbound (We → Vendor)"
    INBOUND = "inbound", "Inbound (Vendor → Us)"


def validate_cidr(value):
    """Validate CIDR notation (e.g. 10.0.0.0/24)."""
    if not value:
        return
    import netaddr
    try:
        netaddr.IPNetwork(value)
    except (netaddr.AddrFormatError, ValueError):
        raise ValidationError(f"'{value}' is not a valid CIDR notation.")


PORT_RANGE_RE = re.compile(r"^\d+(-\d+)?$")


def validate_ports(value):
    """Validate port specification, e.g. '443,8443,10000-10100'."""
    if not value:
        return
    for part in value.split(","):
        part = part.strip()
        if not PORT_RANGE_RE.match(part):
            raise ValidationError(f"'{part}' is not a valid port or port range.")
        if "-" in part:
            low, high = part.split("-")
            if int(low) > int(high):
                raise ValidationError(f"Invalid port range: {part}")
            if int(high) > 65535:
                raise ValidationError(f"Port number exceeds 65535: {high}")
        else:
            if int(part) > 65535:
                raise ValidationError(f"Port number exceeds 65535: {part}")


class TrafficFlow(models.Model):
    vpn_request = models.ForeignKey(
        "vpn.VpnRequest", on_delete=models.CASCADE, related_name="flows"
    )
    source_cidr = models.CharField(max_length=50, validators=[validate_cidr])
    destination_cidr = models.CharField(max_length=50, validators=[validate_cidr])
    direction = models.CharField(
        max_length=10, choices=FlowDirection.choices, default=FlowDirection.OUTBOUND,
        help_text="Who initiates this flow — picks the boundary NAT pool (outbound vs inbound)",
    )
    protocol = models.CharField(max_length=10, choices=FlowProtocol.choices, default=FlowProtocol.TCP)
    destination_ports = models.CharField(
        max_length=200, blank=True, validators=[validate_ports],
        help_text="Comma-separated ports or ranges, e.g. 443,8443,10000-10100",
    )
    application = models.ForeignKey(
        Application, on_delete=models.SET_NULL, null=True, blank=True, related_name="traffic_flows"
    )
    description = models.CharField(max_length=300, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.source_cidr} → {self.destination_cidr} ({self.get_protocol_display()})"

    def clean(self):
        super().clean()
        # Ports are meaningless for ICMP/Any — drop whatever the form had in
        # the field before it was disabled.
        if self.protocol in (FlowProtocol.ICMP, FlowProtocol.ANY):
            self.destination_ports = ""

        # Boundary-NAT rule: private destinations are NAT'd one-to-one, so
        # they must be a single host. Globally-unique (public) destinations
        # are not NAT'd and may be any prefix size.
        if is_rfc1918(self.destination_cidr):
            try:
                prefixlen = netaddr.IPNetwork(self.destination_cidr).prefixlen
            except (netaddr.AddrFormatError, ValueError):
                prefixlen = None
            if prefixlen is not None and prefixlen != 32:
                raise ValidationError({
                    "destination_cidr": (
                        "Private (RFC-1918) destinations must be a /32 host address — "
                        "destination NAT is one-to-one. Use one flow per host, or a "
                        "public (globally-unique) range."
                    )
                })


auditlog.register(
    TrafficFlow,
    exclude_fields=["id", "order"],
)
