from django.db import migrations, models
from django.db.models import F


def copy_protocol_to_protocols(apps, schema_editor):
    """Preserve each flow's single protocol as the new comma-separated value."""
    TrafficFlow = apps.get_model("vpn", "TrafficFlow")
    TrafficFlow.objects.update(protocols=F("protocol"))


def copy_protocols_to_protocol(apps, schema_editor):
    """Reverse: keep the first protocol when collapsing back to a single field."""
    TrafficFlow = apps.get_model("vpn", "TrafficFlow")
    for flow in TrafficFlow.objects.all():
        first = (flow.protocols or "tcp").split(",")[0].strip() or "tcp"
        flow.protocol = first
        flow.save(update_fields=["protocol"])


def set_our_endpoints_count(apps, schema_editor):
    """Existing two-site requests are DR pairs — keep them at 2."""
    VpnRequest = apps.get_model("vpn", "VpnRequest")
    VpnRequest.objects.filter(our_endpoint_2_site__isnull=False).update(
        our_endpoints_count=2
    )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("vpn", "0013_vpnrequest_config_template_override_configtemplate"),
    ]

    operations = [
        migrations.AddField(
            model_name="trafficflow",
            name="protocols",
            field=models.CharField(
                default="tcp",
                help_text="Comma-separated protocols (tcp,udp,icmp) or 'any' for all IP protocols",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="vpnrequest",
            name="our_endpoints_count",
            field=models.PositiveSmallIntegerField(
                choices=[(1, "1"), (2, "2")],
                default=1,
                help_text="1 = single firewall on our side; 2 = DR-paired endpoints drawing from the shared NAT pool",
            ),
        ),
        migrations.RunPython(copy_protocol_to_protocols, copy_protocols_to_protocol),
        migrations.RunPython(set_our_endpoints_count, noop),
        migrations.RemoveField(
            model_name="trafficflow",
            name="protocol",
        ),
    ]
