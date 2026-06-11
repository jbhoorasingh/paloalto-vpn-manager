import pytest
from django.urls import reverse

from apps.core.tests.factories import SiteFactory
from apps.vpn.models.tunnel import TunnelInterface
from apps.vpn.tests.factories import VpnRequestFactory


def _make_deployable_request(**kwargs):
    site = kwargs.pop("site", None) or SiteFactory(
        management_type="standalone", template_name="", device_group=""
    )
    req = VpnRequestFactory(
        our_endpoint_1_site=site,
        vendor_endpoint_1_ip="198.51.100.10",
        vendor_cidrs="172.16.0.0/24",
        **kwargs,
    )
    TunnelInterface.objects.create(
        vpn_request=req, site=site, tunnel_number=101,
        local_ip="10.255.0.1", remote_ip="10.255.0.2",
        subnet_cidr="10.255.0.0/30", vendor_endpoint_ip="198.51.100.10",
    )
    return req, site


@pytest.mark.django_db
class TestDeploymentListView:
    def test_requires_login(self, client):
        response = client.get(reverse("ui:deployment"))
        assert response.status_code == 302

    def test_lists_requests_with_tunnels(self, client_authenticated):
        req, _ = _make_deployable_request()
        VpnRequestFactory()  # no tunnels — must not appear
        response = client_authenticated.get(reverse("ui:deployment"))
        assert response.status_code == 200
        deployments = list(response.context["deployments"])
        assert deployments == [req]
        assert deployments[0].num_tunnels == 1

    def test_links_to_detail_page(self, client_authenticated):
        req, _ = _make_deployable_request()
        response = client_authenticated.get(reverse("ui:deployment"))
        body = response.content.decode()
        assert reverse("ui:deployment-detail", args=[req.pk]) in body
        # Configs are no longer rendered on the list page
        assert "set network ike gateway" not in body

    def test_status_filter(self, client_authenticated):
        _make_deployable_request()  # status: draft
        response = client_authenticated.get(
            reverse("ui:deployment"), {"status": "deploy_ready"}
        )
        assert len(response.context["deployments"]) == 0
        response = client_authenticated.get(reverse("ui:deployment"), {"status": ""})
        assert len(response.context["deployments"]) == 1


@pytest.mark.django_db
class TestDeploymentDetailView:
    def test_requires_login(self, client):
        req, _ = _make_deployable_request()
        response = client.get(reverse("ui:deployment-detail", args=[req.pk]))
        assert response.status_code == 302

    def test_404_for_request_without_tunnels(self, client_authenticated):
        req = VpnRequestFactory()
        response = client_authenticated.get(
            reverse("ui:deployment-detail", args=[req.pk])
        )
        assert response.status_code == 404

    def test_per_tunnel_commands_rendered(self, client_authenticated):
        req, _ = _make_deployable_request()
        response = client_authenticated.get(
            reverse("ui:deployment-detail", args=[req.pk])
        )
        assert response.status_code == 200
        body = response.content.decode()
        assert "tunnel.101" in body
        base = req.reference_number.lower()
        assert f"set network ike gateway {base}-gw1" in body
        # Shared block present too
        assert f"set network ike crypto-profiles ike-crypto-profiles {base}-ike" in body

    def test_multiple_tunnels(self, client_authenticated):
        req, site = _make_deployable_request()
        TunnelInterface.objects.create(
            vpn_request=req, site=site, tunnel_number=102,
            local_ip="10.255.0.5", remote_ip="10.255.0.6",
            subnet_cidr="10.255.0.4/30", vendor_endpoint_ip="198.51.100.10",
        )
        response = client_authenticated.get(
            reverse("ui:deployment-detail", args=[req.pk])
        )
        assert response.context["tunnel_count"] == 2
        site_cfg = response.context["site_configs"][0]
        assert len(site_cfg["tunnels"]) == 2
        assert all(block["text"] for block in site_cfg["tunnels"])
