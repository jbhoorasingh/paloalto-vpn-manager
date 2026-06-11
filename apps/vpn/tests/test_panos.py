import pytest

from apps.core.tests.factories import SiteFactory
from apps.vpn.models.nat import NatMapping
from apps.vpn.models.tunnel import TunnelInterface
from apps.vpn.services.panos import (
    PSK_PLACEHOLDER,
    config_as_text,
    generate_panos_config,
    generate_site_config,
)

from .factories import TrafficFlowFactory, VpnRequestFactory


def _all_commands(cfg):
    return [cmd for section in cfg["sections"] for cmd in section["commands"]]


def _make_request_with_tunnel(site=None, **kwargs):
    site = site or SiteFactory()
    kwargs.setdefault("vendor_endpoint_1_ip", "198.51.100.10")
    kwargs.setdefault("vendor_cidrs", "172.16.0.0/24")
    req = VpnRequestFactory(our_endpoint_1_site=site, **kwargs)
    ti = TunnelInterface.objects.create(
        vpn_request=req,
        site=site,
        tunnel_number=101,
        local_ip="10.255.0.1",
        remote_ip="10.255.0.2",
        subnet_cidr="10.255.0.0/30",
        vendor_endpoint_ip="198.51.100.10",
    )
    return req, site, ti


@pytest.mark.django_db
class TestCryptoProfiles:
    def test_ike_crypto_profile(self):
        req, site, _ = _make_request_with_tunnel()
        cfg = generate_site_config(req, site)
        commands = _all_commands(cfg)
        base = req.reference_number.lower()
        # Names without whitespace are not quoted
        prefix = f"set template {site.template_name} config "
        assert f"{prefix}network ike crypto-profiles ike-crypto-profiles {base}-ike encryption aes-256-cbc" in commands
        assert f"{prefix}network ike crypto-profiles ike-crypto-profiles {base}-ike hash sha256" in commands
        assert f"{prefix}network ike crypto-profiles ike-crypto-profiles {base}-ike dh-group group14" in commands
        assert f"{prefix}network ike crypto-profiles ike-crypto-profiles {base}-ike lifetime seconds 28800" in commands

    def test_gcm_gets_authentication_none(self):
        req, site, _ = _make_request_with_tunnel()
        cfg = generate_site_config(req, site)
        commands = _all_commands(cfg)
        base = req.reference_number.lower()
        gcm_lines = [c for c in commands if f"{base}-ipsec esp" in c]
        assert any("esp encryption aes-256-gcm" in c for c in gcm_lines)
        assert any("esp authentication none" in c for c in gcm_lines)
        assert not any("esp authentication sha256" in c for c in gcm_lines)

    def test_cbc_keeps_authentication(self):
        site = SiteFactory()
        req, _, _ = _make_request_with_tunnel(site=site, ipsec_encryption="aes-256-cbc")
        cfg = generate_site_config(req, site)
        commands = _all_commands(cfg)
        assert any("esp authentication sha256" in c for c in commands)


@pytest.mark.django_db
class TestPanoramaVsStandalone:
    def test_standalone_has_no_template_prefix(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        TrafficFlowFactory(vpn_request=req)
        cfg = generate_site_config(req, site)
        commands = _all_commands(cfg)
        assert all(not c.startswith("set template") for c in commands)
        assert all(not c.startswith("set device-group") for c in commands)
        assert any(c.startswith("set network ike gateway") for c in commands)
        assert any(c.startswith("set rulebase security rules") for c in commands)

    def test_centralized_uses_template_and_device_group(self):
        site = SiteFactory()  # centralized by default
        req, _, _ = _make_request_with_tunnel(site=site)
        TrafficFlowFactory(vpn_request=req)
        cfg = generate_site_config(req, site)
        commands = _all_commands(cfg)
        assert any(c.startswith(f"set template {site.template_name} config network") for c in commands)
        assert any(c.startswith(f"set device-group {site.device_group} pre-rulebase") for c in commands)

    def test_unsupported_brand_skipped(self):
        site = SiteFactory(device_brand="cisco")
        req, _, _ = _make_request_with_tunnel(site=site)
        cfg = generate_site_config(req, site)
        assert cfg["supported"] is False
        assert "Cisco" in cfg["reason"]
        assert cfg["sections"] == []


@pytest.mark.django_db
class TestTunnelAndGateway:
    def test_tunnel_interface_commands(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, ti = _make_request_with_tunnel(site=site)
        commands = _all_commands(generate_site_config(req, site))
        assert "set network interface tunnel units tunnel.101 ip 10.255.0.1/30" in commands
        assert "set zone vpn-vendor network layer3 tunnel.101" in commands
        assert "set network virtual-router default interface tunnel.101" in commands

    def test_ike_gateway_psk_and_peer(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="", public_ip="203.0.113.10")
        req, _, _ = _make_request_with_tunnel(site=site)
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        assert f"set network ike gateway {base}-gw1 authentication pre-shared-key key {PSK_PLACEHOLDER}" in commands
        assert f"set network ike gateway {base}-gw1 protocol version ikev2" in commands
        assert f"set network ike gateway {base}-gw1 peer-address ip 198.51.100.10" in commands
        assert f"set network ike gateway {base}-gw1 local-address ip 203.0.113.10" in commands

    def test_ipsec_tunnel_ties_gateway_profile_interface(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        assert f"set network tunnel ipsec {base}-vpn1 auto-key ike-gateway {base}-gw1" in commands
        assert f"set network tunnel ipsec {base}-vpn1 auto-key ipsec-crypto-profile {base}-ipsec" in commands
        assert f"set network tunnel ipsec {base}-vpn1 tunnel-interface tunnel.101" in commands

    def test_no_tunnels_yields_note(self):
        site = SiteFactory()
        req = VpnRequestFactory(our_endpoint_1_site=site)
        cfg = generate_site_config(req, site)
        assert any("No tunnel interfaces allocated" in n for n in cfg["notes"])
        titles = [s["title"] for s in cfg["sections"]]
        assert "IKE Gateways" not in titles


@pytest.mark.django_db
class TestRouting:
    def test_static_routes_per_vendor_cidr(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(
            site=site, vendor_cidrs="172.16.0.0/24\n172.17.0.0/24"
        )
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        assert f"set network virtual-router default routing-table ip static-route {base}-rt1 destination 172.16.0.0/24" in commands
        assert f"set network virtual-router default routing-table ip static-route {base}-rt1 interface tunnel.101" in commands
        assert f"set network virtual-router default routing-table ip static-route {base}-rt1 nexthop ip 10.255.0.2" in commands
        assert f"set network virtual-router default routing-table ip static-route {base}-rt2 destination 172.17.0.0/24" in commands

    def test_bgp_peering(self):
        site = SiteFactory(
            management_type="standalone", template_name="", device_group="",
            bgp_asn=65001, public_ip="203.0.113.10",
        )
        req, _, _ = _make_request_with_tunnel(
            site=site, routing_type="bgp", bgp_remote_asn=65100,
        )
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        vr = "set network virtual-router default"
        assert f"{vr} protocol bgp enable yes" in commands
        assert f"{vr} protocol bgp local-as 65001" in commands
        assert f"{vr} protocol bgp router-id 203.0.113.10" in commands
        assert f"{vr} protocol bgp peer-group {base}-pg type ebgp" in commands
        assert f"{vr} protocol bgp peer-group {base}-pg peer {base}-peer1 peer-as 65100" in commands
        assert f"{vr} protocol bgp peer-group {base}-pg peer {base}-peer1 local-address interface tunnel.101 ip 10.255.0.1/30" in commands
        assert f"{vr} protocol bgp peer-group {base}-pg peer {base}-peer1 peer-address ip 10.255.0.2" in commands


@pytest.mark.django_db
class TestNatAndSecurity:
    def test_outbound_nat_rule(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        flow = TrafficFlowFactory(
            vpn_request=req, source_cidr="10.0.0.0/24",
            destination_cidr="172.16.5.10/32", destination_ports="443",
        )
        NatMapping.objects.create(
            vpn_request=req, site=site, direction="outbound",
            nat_address="10.111.96.10/32", real_address="172.16.5.10/32",
            traffic_flow=flow,
        )
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        nat = f"set rulebase nat rules {base}-nat-out1"
        assert f"{nat} from trust" in commands
        assert f"{nat} to vpn-vendor" in commands
        assert f"{nat} destination 10.111.96.10/32" in commands
        assert f"{nat} destination-translation translated-address 172.16.5.10/32" in commands

    def test_inbound_nat_rule_reverses_zones(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site, directionality="vendor_initiates")
        flow = TrafficFlowFactory(
            vpn_request=req, source_cidr="172.16.0.0/24",
            destination_cidr="10.10.70.100/32",
        )
        NatMapping.objects.create(
            vpn_request=req, site=site, direction="inbound",
            nat_address="10.111.100.5/32", real_address="10.10.70.100/32",
            traffic_flow=flow,
        )
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        nat = f"set rulebase nat rules {base}-nat-in1"
        assert f"{nat} from vpn-vendor" in commands
        assert f"{nat} to trust" in commands

    def test_security_rule_uses_nat_address_and_service_object(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        flow = TrafficFlowFactory(
            vpn_request=req, source_cidr="10.0.0.0/24",
            destination_cidr="172.16.5.10/32", protocol="tcp",
            destination_ports="443,8443",
        )
        NatMapping.objects.create(
            vpn_request=req, site=site, direction="outbound",
            nat_address="10.111.96.10/32", real_address="172.16.5.10/32",
            traffic_flow=flow,
        )
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        assert f"set service {base}-svc1 protocol tcp port 443,8443" in commands
        sec = f"set rulebase security rules {base}-sec1"
        assert f"{sec} from trust" in commands
        assert f"{sec} to vpn-vendor" in commands
        assert f"{sec} source 10.0.0.0/24" in commands
        assert f"{sec} destination 10.111.96.10/32" in commands
        assert f"{sec} service {base}-svc1" in commands
        assert f"{sec} action allow" in commands

    def test_security_rule_zones_follow_flow_direction(self):
        # Flow direction overrides request directionality for zone selection
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site, directionality="we_initiate")
        TrafficFlowFactory(
            vpn_request=req, direction="inbound",
            source_cidr="172.16.0.0/24", destination_cidr="10.10.70.100/32",
            protocol="any", destination_ports="",
        )
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        sec = f"set rulebase security rules {base}-sec1"
        assert f"{sec} from vpn-vendor" in commands
        assert f"{sec} to trust" in commands

    def test_security_rule_falls_back_to_real_destination(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        TrafficFlowFactory(
            vpn_request=req, source_cidr="10.0.0.0/24",
            destination_cidr="172.16.5.10/32", destination_ports="",
            protocol="icmp",
        )
        base = req.reference_number.lower()
        commands = _all_commands(generate_site_config(req, site))
        sec = f"set rulebase security rules {base}-sec1"
        assert f"{sec} destination 172.16.5.10/32" in commands
        assert f"{sec} service any" in commands


@pytest.mark.django_db
class TestPerTunnelStructure:
    def test_tunnel_blocks_contain_their_own_commands(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, ti1 = _make_request_with_tunnel(site=site)
        ti2 = TunnelInterface.objects.create(
            vpn_request=req, site=site, tunnel_number=102,
            local_ip="10.255.0.5", remote_ip="10.255.0.6",
            subnet_cidr="10.255.0.4/30", vendor_endpoint_ip="198.51.100.10",
        )
        cfg = generate_site_config(req, site)
        assert len(cfg["tunnels"]) == 2
        block1, block2 = cfg["tunnels"]
        assert block1["label"] == "tunnel.101"
        assert block2["label"] == "tunnel.102"

        block1_cmds = [c for s in block1["sections"] for c in s["commands"]]
        block2_cmds = [c for s in block2["sections"] for c in s["commands"]]
        # Each block only mentions its own tunnel unit
        assert any("tunnel.101" in c for c in block1_cmds)
        assert not any("tunnel.102" in c for c in block1_cmds)
        assert any("tunnel.102" in c for c in block2_cmds)
        # Gateway indexes stay aligned with the site-level numbering
        base = req.reference_number.lower()
        assert any(f"{base}-gw1" in c for c in block1_cmds)
        assert any(f"{base}-gw2" in c for c in block2_cmds)
        # Per-tunnel static routes live in the block, one per vendor CIDR
        assert any("static-route" in c and "tunnel.101" in c for c in block1_cmds)

    def test_shared_sections_hold_site_level_config(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        flow = TrafficFlowFactory(vpn_request=req, destination_ports="443")
        NatMapping.objects.create(
            vpn_request=req, site=site, direction="outbound",
            nat_address="10.111.96.10/32", real_address="192.168.1.0/24",
            traffic_flow=flow,
        )
        cfg = generate_site_config(req, site)
        shared_titles = [s["title"] for s in cfg["shared_sections"]]
        assert "IKE Crypto Profile" in shared_titles
        assert "IPsec Crypto Profile" in shared_titles
        assert "NAT Policy" in shared_titles
        assert "Security Policy" in shared_titles
        # Per-tunnel commands never leak into shared sections
        shared_cmds = [c for s in cfg["shared_sections"] for c in s["commands"]]
        assert not any("ike gateway" in c for c in shared_cmds)

    def test_bgp_split_between_shared_and_tunnel_blocks(self):
        site = SiteFactory(
            management_type="standalone", template_name="", device_group="",
            bgp_asn=65001,
        )
        req, _, _ = _make_request_with_tunnel(site=site, routing_type="bgp", bgp_remote_asn=65100)
        cfg = generate_site_config(req, site)
        shared_cmds = [c for s in cfg["shared_sections"] for c in s["commands"]]
        assert any("protocol bgp enable yes" in c for c in shared_cmds)
        assert any("protocol bgp local-as 65001" in c for c in shared_cmds)
        assert not any("peer-as" in c for c in shared_cmds)
        block_cmds = [c for s in cfg["tunnels"][0]["sections"] for c in s["commands"]]
        assert any("peer-as 65100" in c for c in block_cmds)

    def test_flattened_sections_cover_all_tunnel_commands(self):
        # The legacy flattened view must contain every per-tunnel command
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        cfg = generate_site_config(req, site)
        flattened = set(_all_commands(cfg))
        for block in cfg["tunnels"]:
            for section in block["sections"]:
                for cmd in section["commands"]:
                    assert cmd in flattened


@pytest.mark.django_db
class TestMultiSite:
    def test_generates_one_config_per_distinct_site(self):
        site1 = SiteFactory()
        site2 = SiteFactory()
        req = VpnRequestFactory(
            our_endpoint_1_site=site1, our_endpoint_2_site=site2,
            vendor_endpoint_1_ip="198.51.100.10",
        )
        configs = generate_panos_config(req)
        assert [c["site"] for c in configs] == [site1, site2]

    def test_same_site_twice_deduplicated(self):
        site = SiteFactory()
        req = VpnRequestFactory(
            our_endpoint_1_site=site, our_endpoint_2_site=site,
        )
        configs = generate_panos_config(req)
        assert len(configs) == 1

    def test_config_as_text_has_no_comment_lines(self):
        site = SiteFactory(management_type="standalone", template_name="", device_group="")
        req, _, _ = _make_request_with_tunnel(site=site)
        text = config_as_text(generate_site_config(req, site))
        assert text
        for line in text.splitlines():
            assert line == "" or line.startswith("set ")
