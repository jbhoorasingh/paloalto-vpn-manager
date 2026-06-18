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


# Protocols whose flows carry destination ports (and therefore generate a
# PAN-OS service object). ICMP/Any do not.
PORT_PROTOCOLS = ("tcp", "udp")
VALID_PROTOCOLS = {choice.value for choice in FlowProtocol}


def parse_protocols(value):
    """Normalize a protocols value (CSV string or list) to an ordered list."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        tokens = value
    else:
        tokens = str(value).split(",")
    seen = []
    for token in tokens:
        token = str(token).strip().lower()
        if token and token not in seen:
            seen.append(token)
    return seen


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
    protocols = models.CharField(
        max_length=20, default="tcp",
        help_text="Comma-separated protocols (tcp,udp,icmp) or 'any' for all IP protocols",
    )
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

    @property
    def protocol_list(self):
        """The flow's protocols as an ordered list, e.g. ['tcp', 'udp']."""
        return parse_protocols(self.protocols)

    @property
    def has_port_protocol(self):
        """True if any selected protocol uses ports (tcp/udp)."""
        return any(p in PORT_PROTOCOLS for p in self.protocol_list)

    def protocols_display(self):
        """Human-readable protocol list, e.g. 'TCP, UDP'."""
        labels = {c.value: c.label for c in FlowProtocol}
        return ", ".join(labels.get(p, p.upper()) for p in self.protocol_list)

    def __str__(self):
        return f"{self.source_cidr} → {self.destination_cidr} ({self.protocols_display()})"

    def clean(self):
        super().clean()
        # Normalize and validate the protocol set.
        protocols = parse_protocols(self.protocols)
        invalid = [p for p in protocols if p not in VALID_PROTOCOLS]
        if invalid:
            raise ValidationError({
                "protocols": f"Unknown protocol(s): {', '.join(invalid)}."
            })
        if not protocols:
            raise ValidationError({"protocols": "Select at least one protocol."})
        if "any" in protocols and len(protocols) > 1:
            raise ValidationError({
                "protocols": "'Any' covers all protocols and can't be combined with others."
            })
        self.protocols = ",".join(protocols)

        # Ports only apply to tcp/udp — drop whatever the form had in the field
        # when no port-based protocol is selected (icmp-only / any).
        if not self.has_port_protocol:
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
