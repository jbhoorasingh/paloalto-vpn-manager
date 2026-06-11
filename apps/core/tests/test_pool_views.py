import pytest
from django.urls import reverse

from apps.core.models import NatPool, TunnelAddressPool
from apps.core.tests.factories import NatPoolFactory, SiteFactory, TunnelAddressPoolFactory
from apps.vpn.models.tunnel import TunnelInterface
from apps.vpn.tests.factories import VpnRequestFactory


@pytest.mark.django_db
class TestPoolList:
    def test_requires_login(self, client):
        response = client.get(reverse("ui:pool-list"))
        assert response.status_code == 302

    def test_lists_pools_with_utilization(self, client_authenticated):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        TunnelAddressPoolFactory(site=site, cidr="10.255.0.0/24")
        response = client_authenticated.get(reverse("ui:pool-list"))
        assert response.status_code == 200
        assert len(response.context["nat_rows"]) == 1
        assert len(response.context["tunnel_rows"]) == 1
        # /24 tunnel pool carves 64 /30s, none used yet
        assert response.context["tunnel_rows"][0]["total"] == 64
        assert response.context["tunnel_rows"][0]["used"] == 0

    def test_site_filter(self, client_authenticated):
        site1 = SiteFactory()
        site2 = SiteFactory()
        NatPoolFactory(site=site1, cidr="10.111.96.0/24")
        NatPoolFactory(site=site2, cidr="10.111.97.0/24")
        response = client_authenticated.get(reverse("ui:pool-list"), {"site": site1.pk})
        assert len(response.context["nat_rows"]) == 1
        assert response.context["nat_rows"][0]["pool"].site == site1


@pytest.mark.django_db
class TestNatPoolCrud:
    def test_create(self, client_authenticated):
        site = SiteFactory()
        response = client_authenticated.post(reverse("ui:nat-pool-create"), {
            "site": site.pk,
            "direction": "outbound",
            "cidr": "10.111.96.0/24",
            "description": "Test pool",
            "is_active": "on",
        })
        assert response.status_code == 302
        pool = NatPool.objects.get(site=site)
        assert pool.cidr == "10.111.96.0/24"
        assert pool.is_active is True

    def test_create_invalid_cidr_shows_errors(self, client_authenticated):
        site = SiteFactory()
        response = client_authenticated.post(reverse("ui:nat-pool-create"), {
            "site": site.pk,
            "direction": "outbound",
            "cidr": "not-a-cidr",
            "is_active": "on",
        })
        assert response.status_code == 200
        assert "cidr" in response.context["errors"]
        assert NatPool.objects.count() == 0

    def test_create_overlap_rejected(self, client_authenticated):
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        response = client_authenticated.post(reverse("ui:nat-pool-create"), {
            "site": site.pk,
            "direction": "inbound",
            "cidr": "10.111.96.0/25",
            "is_active": "on",
        })
        assert response.status_code == 200
        assert NatPool.objects.count() == 1

    def test_create_shared_pool(self, client_authenticated):
        from apps.core.tests.factories import DrPeerFactory
        peer = DrPeerFactory()
        response = client_authenticated.post(reverse("ui:nat-pool-create"), {
            "scope": "shared",
            "dr_peer": peer.pk,
            "direction": "outbound",
            "cidr": "10.111.200.0/24",
            "is_active": "on",
        })
        assert response.status_code == 302
        pool = NatPool.objects.get(cidr="10.111.200.0/24")
        assert pool.scope == "shared"
        assert pool.site is None
        assert pool.dr_peer == peer

    def test_create_shared_pool_without_peer_rejected(self, client_authenticated):
        response = client_authenticated.post(reverse("ui:nat-pool-create"), {
            "scope": "shared",
            "direction": "outbound",
            "cidr": "10.111.200.0/24",
            "is_active": "on",
        })
        assert response.status_code == 200
        assert "dr_peer" in response.context["errors"]
        assert NatPool.objects.count() == 0

    def test_shared_pools_visible_under_any_site_filter(self, client_authenticated):
        from apps.core.tests.factories import DrPeerFactory
        site = SiteFactory()
        NatPoolFactory(site=site, direction="outbound", cidr="10.111.96.0/24")
        NatPoolFactory(
            site=None, scope="shared", dr_peer=DrPeerFactory(),
            direction="outbound", cidr="10.111.200.0/24",
        )
        response = client_authenticated.get(reverse("ui:pool-list"), {"site": site.pk})
        assert len(response.context["nat_rows"]) == 2


@pytest.mark.django_db
class TestDrPeerViews:
    def test_create(self, client_authenticated):
        from apps.core.models import DrPeer
        site1, site2 = SiteFactory(), SiteFactory()
        response = client_authenticated.post(reverse("ui:dr-peer-create"), {
            "name": "East pair",
            "primary_site": site1.pk,
            "secondary_site": site2.pk,
            "is_active": "on",
        })
        assert response.status_code == 302
        peer = DrPeer.objects.get(name="East pair")
        assert peer.primary_site == site1
        assert peer.secondary_site == site2

    def test_create_same_site_rejected(self, client_authenticated):
        from apps.core.models import DrPeer
        site = SiteFactory()
        response = client_authenticated.post(reverse("ui:dr-peer-create"), {
            "name": "bad",
            "primary_site": site.pk,
            "secondary_site": site.pk,
            "is_active": "on",
        })
        assert response.status_code == 200
        assert DrPeer.objects.count() == 0

    def test_delete_removes_its_shared_pools(self, client_authenticated):
        from apps.core.tests.factories import DrPeerFactory
        peer = DrPeerFactory()
        NatPoolFactory(
            site=None, scope="shared", dr_peer=peer,
            direction="outbound", cidr="10.111.200.0/24",
        )
        response = client_authenticated.post(reverse("ui:dr-peer-delete", args=[peer.pk]))
        assert response.status_code == 302
        assert NatPool.objects.count() == 0

    def test_listed_on_pools_page(self, client_authenticated):
        from apps.core.tests.factories import DrPeerFactory
        peer = DrPeerFactory()
        response = client_authenticated.get(reverse("ui:pool-list"))
        assert response.status_code == 200
        assert peer.name in response.content.decode()

    def test_edit(self, client_authenticated):
        pool = NatPoolFactory(cidr="10.111.96.0/24", description="old")
        response = client_authenticated.post(reverse("ui:nat-pool-edit", args=[pool.pk]), {
            "site": pool.site.pk,
            "direction": pool.direction,
            "cidr": pool.cidr,
            "description": "updated",
            "is_active": "on",
        })
        assert response.status_code == 302
        pool.refresh_from_db()
        assert pool.description == "updated"

    def test_delete(self, client_authenticated):
        pool = NatPoolFactory()
        response = client_authenticated.post(reverse("ui:nat-pool-delete", args=[pool.pk]))
        assert response.status_code == 302
        assert NatPool.objects.count() == 0

    def test_delete_requires_post(self, client_authenticated):
        pool = NatPoolFactory()
        client_authenticated.get(reverse("ui:nat-pool-delete", args=[pool.pk]))
        assert NatPool.objects.count() == 1


@pytest.mark.django_db
class TestTunnelPoolCrud:
    def test_create(self, client_authenticated):
        site = SiteFactory()
        response = client_authenticated.post(reverse("ui:tunnel-pool-create"), {
            "site": site.pk,
            "cidr": "10.255.0.0/24",
            "is_active": "on",
        })
        assert response.status_code == 302
        assert TunnelAddressPool.objects.filter(site=site, cidr="10.255.0.0/24").exists()

    def test_create_too_small_rejected(self, client_authenticated):
        site = SiteFactory()
        response = client_authenticated.post(reverse("ui:tunnel-pool-create"), {
            "site": site.pk,
            "cidr": "10.255.0.0/31",
            "is_active": "on",
        })
        assert response.status_code == 200
        assert TunnelAddressPool.objects.count() == 0

    def test_delete(self, client_authenticated):
        pool = TunnelAddressPoolFactory()
        response = client_authenticated.post(reverse("ui:tunnel-pool-delete", args=[pool.pk]))
        assert response.status_code == 302
        assert TunnelAddressPool.objects.count() == 0


@pytest.mark.django_db
class TestTunnelInterfaceViews:
    def _make_interface(self, **kwargs):
        site = kwargs.pop("site", None) or SiteFactory()
        req = kwargs.pop("vpn_request", None) or VpnRequestFactory(our_endpoint_1_site=site)
        defaults = {
            "tunnel_number": 101,
            "local_ip": "10.255.0.1",
            "remote_ip": "10.255.0.2",
            "subnet_cidr": "10.255.0.0/30",
        }
        defaults.update(kwargs)
        return TunnelInterface.objects.create(vpn_request=req, site=site, **defaults)

    def test_list(self, client_authenticated):
        iface = self._make_interface()
        response = client_authenticated.get(reverse("ui:tunnel-interface-list"))
        assert response.status_code == 200
        assert list(response.context["interfaces"]) == [iface]

    def test_list_filters_by_site_and_reference(self, client_authenticated):
        iface1 = self._make_interface()
        iface2 = self._make_interface()
        response = client_authenticated.get(
            reverse("ui:tunnel-interface-list"), {"site": iface1.site.pk}
        )
        assert list(response.context["interfaces"]) == [iface1]
        response = client_authenticated.get(
            reverse("ui:tunnel-interface-list"),
            {"q": iface2.vpn_request.reference_number},
        )
        assert list(response.context["interfaces"]) == [iface2]

    def test_edit_addressing(self, client_authenticated):
        iface = self._make_interface()
        response = client_authenticated.post(
            reverse("ui:tunnel-interface-edit", args=[iface.pk]),
            {
                "local_ip": "169.254.10.1",
                "remote_ip": "169.254.10.2",
                "subnet_cidr": "169.254.10.0/30",
                "vendor_endpoint_ip": "198.51.100.20",
            },
        )
        assert response.status_code == 302
        iface.refresh_from_db()
        assert iface.local_ip == "169.254.10.1"
        assert iface.remote_ip == "169.254.10.2"
        assert iface.vendor_endpoint_ip == "198.51.100.20"

    def test_edit_invalid_ip_shows_errors(self, client_authenticated):
        iface = self._make_interface()
        response = client_authenticated.post(
            reverse("ui:tunnel-interface-edit", args=[iface.pk]),
            {"local_ip": "not-an-ip", "remote_ip": "", "subnet_cidr": "", "vendor_endpoint_ip": ""},
        )
        assert response.status_code == 200
        assert "local_ip" in response.context["errors"]

    def test_release(self, client_authenticated):
        iface = self._make_interface()
        response = client_authenticated.post(
            reverse("ui:tunnel-interface-release", args=[iface.pk])
        )
        assert response.status_code == 302
        assert TunnelInterface.objects.count() == 0

    def test_release_requires_post(self, client_authenticated):
        iface = self._make_interface()
        client_authenticated.get(reverse("ui:tunnel-interface-release", args=[iface.pk]))
        assert TunnelInterface.objects.count() == 1


@pytest.mark.django_db
class TestConfigDownload:
    def test_download_returns_text_attachment(self, client_authenticated):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req = VpnRequestFactory(
            our_endpoint_1_site=site,
            vendor_endpoint_1_ip="198.51.100.10",
        )
        TunnelInterface.objects.create(
            vpn_request=req, site=site, tunnel_number=101,
            local_ip="10.255.0.1", remote_ip="10.255.0.2",
            subnet_cidr="10.255.0.0/30", vendor_endpoint_ip="198.51.100.10",
        )
        response = client_authenticated.get(
            reverse("ui:request-config-download", args=[req.pk])
        )
        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/plain")
        assert "attachment" in response["Content-Disposition"]
        body = response.content.decode()
        assert "set network interface tunnel units tunnel.101" in body

    def test_detail_page_renders_config_tab(self, client_authenticated):
        site = SiteFactory()
        req = VpnRequestFactory(our_endpoint_1_site=site)
        response = client_authenticated.get(reverse("ui:request-detail", args=[req.pk]))
        assert response.status_code == 200
        assert len(response.context["panos_configs"]) == 1
