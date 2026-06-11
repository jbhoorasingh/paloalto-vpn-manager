from django.db import migrations


def backfill_direction(apps, schema_editor):
    """Give pre-existing flows an explicit direction from their request's directionality."""
    TrafficFlow = apps.get_model("vpn", "TrafficFlow")
    TrafficFlow.objects.filter(
        direction="", vpn_request__directionality="vendor_initiates"
    ).update(direction="inbound")
    TrafficFlow.objects.filter(direction="").update(direction="outbound")


class Migration(migrations.Migration):

    dependencies = [
        ("vpn", "0010_trafficflow_direction"),
    ]

    operations = [
        migrations.RunPython(backfill_direction, migrations.RunPython.noop),
    ]
