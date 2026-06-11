import pytest
from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from apps.core.tests.factories import SiteFactory, UserFactory
from apps.vpn.models import ConfigTemplate, VpnRequest
from apps.vpn.models.config_template import DEFAULT_CONFIG_TEMPLATE
from apps.vpn.models.nat import NatMapping
from apps.vpn.models.tunnel import TunnelInterface
from apps.vpn.services.config_render import (
    render_template,
    rendered_site_configs,
    resolve_template,
)
from apps.vpn.services.panos import config_as_text, generate_panos_config

from .factories import TrafficFlowFactory, VpnRequestFactory


@pytest.fixture
def network_client(client, db):
    user = UserFactory(roles=["network"])
    client.force_login(user)
    return client


def _request_with_config(site=None):
    site = site or SiteFactory(management_type="standalone", template_name="", device_group="")
    req = VpnRequestFactory(
        our_endpoint_1_site=site,
        vendor_endpoint_1_ip="198.51.100.10",
        vendor_cidrs="172.16.0.0/24",
    )
    flow = TrafficFlowFactory(vpn_request=req, destination_cidr="172.16.5.10/32")
    TunnelInterface.objects.create(
        vpn_request=req, site=site, tunnel_number=101,
        local_ip="10.255.0.1", remote_ip="10.255.0.2",
        subnet_cidr="10.255.0.0/30", vendor_endpoint_ip="198.51.100.10",
    )
    NatMapping.objects.create(
        vpn_request=req, site=site, direction="outbound",
        nat_address="10.111.96.10/32", real_address="172.16.5.10/32",
        traffic_flow=flow,
    )
    return req, site


@pytest.mark.django_db
class TestRendering:
    def test_default_template_matches_generator_output(self):
        req, site = _request_with_config()
        rendered = rendered_site_configs(req)[0]
        generator_text = config_as_text(generate_panos_config(req)[0])
        assert rendered["template_source"] == "default"
        assert rendered["render_error"] is None
        assert rendered["text"].rstrip("\n") == generator_text.rstrip("\n")

    def test_customized_global_template_used(self):
        req, _ = _request_with_config()
        template = ConfigTemplate.get_global()
        template.content = "# {{ reference }} for {{ site.code }}\n" + DEFAULT_CONFIG_TEMPLATE
        template.save()
        rendered = rendered_site_configs(req)[0]
        assert rendered["template_source"] == "global"
        assert rendered["text"].startswith(f"# {req.reference_number.lower()} for")

    def test_request_override_beats_global(self):
        req, _ = _request_with_config()
        global_template = ConfigTemplate.get_global()
        global_template.content = "GLOBAL"
        global_template.save()
        req.config_template_override = "OVERRIDE {{ request.reference_number }}"
        req.save()
        rendered = rendered_site_configs(req)[0]
        assert rendered["template_source"] == "request"
        assert rendered["text"].strip() == f"OVERRIDE {req.reference_number}"

    def test_broken_template_falls_back_with_error(self):
        req, _ = _request_with_config()
        req.config_template_override = "{% for x in %}"  # invalid syntax
        req.save()
        rendered = rendered_site_configs(req)[0]
        assert rendered["render_error"] is not None
        # Fallback keeps the generator output usable
        assert "set network ike crypto-profiles" in rendered["text"]

    def test_render_template_never_raises(self):
        text, error = render_template("{{ undefined_thing.attr.attr }}", {})
        assert text == ""
        assert error is None or "Template error" in error

    def test_sandbox_blocks_unsafe_access(self):
        # Context holds plain dicts only, but even sandbox escapes must not raise
        text, error = render_template(
            "{{ ''.__class__.__mro__ }}", {"sections": []}
        )
        assert error is not None  # SecurityError surfaced as template error

    def test_resolve_template_sources(self):
        req, _ = _request_with_config()
        assert resolve_template(req)[1] == "default"
        ConfigTemplate.get_global().__class__.objects.filter(name="global").update(content="X")
        assert resolve_template(req)[1] == "global"
        req.config_template_override = "Y"
        assert resolve_template(req)[1] == "request"


@pytest.mark.django_db
class TestGlobalTemplateView:
    def test_requires_network_role(self, client):
        user = UserFactory(roles=["requester"])
        client.force_login(user)
        response = client.get(reverse("ui:config-template"))
        assert response.status_code == 403

    def test_get_shows_template(self, network_client):
        response = network_client.get(reverse("ui:config-template"))
        assert response.status_code == 200
        assert "Available Variables" in response.content.decode()

    def test_save_is_audit_logged(self, network_client):
        response = network_client.post(reverse("ui:config-template"), {
            "content": "HELLO {{ reference }}",
        })
        assert response.status_code == 200
        template = ConfigTemplate.get_global()
        assert template.content == "HELLO {{ reference }}"
        ct = ContentType.objects.get_for_model(ConfigTemplate)
        entries = LogEntry.objects.filter(content_type=ct, object_pk=str(template.pk))
        assert entries.exists()
        latest = entries.order_by("-timestamp").first()
        assert latest.actor is not None
        assert "content" in (latest.changes or {})

    def test_syntax_error_not_saved(self, network_client):
        original = ConfigTemplate.get_global().content
        response = network_client.post(reverse("ui:config-template"), {
            "content": "{% for x in %}",
        })
        assert response.status_code == 200
        assert "syntax error" in response.content.decode().lower()
        assert ConfigTemplate.get_global().content == original

    def test_reset_to_default(self, network_client):
        template = ConfigTemplate.get_global()
        template.content = "custom"
        template.save()
        network_client.post(reverse("ui:config-template"), {"reset": "1"})
        template.refresh_from_db()
        assert template.content == DEFAULT_CONFIG_TEMPLATE


@pytest.mark.django_db
class TestRequestOverrideView:
    def test_requires_network_role(self, client):
        req, _ = _request_with_config()
        client.force_login(UserFactory(roles=["requester"]))
        response = client.get(reverse("ui:request-config-template", args=[req.pk]))
        assert response.status_code == 403

    def test_save_override_logged_on_request(self, network_client):
        req, _ = _request_with_config()
        response = network_client.post(
            reverse("ui:request-config-template", args=[req.pk]),
            {"content": "PER-VPN {{ reference }}"},
        )
        assert response.status_code == 302
        req = VpnRequest.objects.get(pk=req.pk)
        assert req.config_template_override == "PER-VPN {{ reference }}"
        ct = ContentType.objects.get_for_model(VpnRequest)
        entry = (
            LogEntry.objects.filter(content_type=ct, object_pk=str(req.pk))
            .order_by("-timestamp").first()
        )
        assert "config_template_override" in (entry.changes or {})
        assert entry.actor is not None

    def test_remove_override(self, network_client):
        req, _ = _request_with_config()
        req.config_template_override = "X"
        req.save()
        response = network_client.post(
            reverse("ui:request-config-template", args=[req.pk]),
            {"remove": "1"},
        )
        assert response.status_code == 302
        req = VpnRequest.objects.get(pk=req.pk)
        assert req.config_template_override == ""

    def test_download_uses_override(self, network_client):
        req, _ = _request_with_config()
        req.config_template_override = "ONLY-THIS-LINE"
        req.save()
        response = network_client.get(
            reverse("ui:request-config-download", args=[req.pk])
        )
        assert response.content.decode().strip() == "ONLY-THIS-LINE"
