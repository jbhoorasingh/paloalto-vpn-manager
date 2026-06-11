import factory

from apps.core.tests.factories import SiteFactory, UserFactory
from apps.vpn.models import (
    Application,
    TrafficFlow,
    Vendor,
    VendorContact,
    VpnRequest,
    VpnRequestApplication,
)


class VendorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Vendor

    name = factory.Sequence(lambda n: f"Vendor {n}")
    domain = factory.LazyAttribute(lambda o: f"{o.name.lower().replace(' ', '')}.com")
    support_email = factory.LazyAttribute(lambda o: f"support@{o.domain}")
    status = Vendor.Status.ACTIVE
    created_by = factory.SubFactory(UserFactory)


class VendorContactFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VendorContact

    vendor = factory.SubFactory(VendorFactory)
    name = factory.Faker("name")
    email = factory.Faker("email")
    phone = factory.Faker("phone_number")
    role = VendorContact.ContactRole.TECHNICAL
    is_primary = False


class ApplicationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Application

    name = factory.Sequence(lambda n: f"Application {n}")
    owner = factory.SubFactory(UserFactory)
    criticality = Application.Criticality.MEDIUM
    description = factory.Faker("sentence")


class VpnRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VpnRequest
        skip_postgeneration_save = True

    vendor = factory.SubFactory(VendorFactory)
    requester = factory.SubFactory(UserFactory)
    title = factory.Sequence(lambda n: f"VPN Request {n}")
    purpose = factory.Faker("sentence")
    directionality = "we_initiate"
    vendor_endpoints_count = 1
    ike_version = "2"
    auth_method = "psk"
    ike_encryption = "aes-256-cbc"
    ike_integrity = "sha256"
    ike_dh_group = "14"
    ike_lifetime = 28800
    ipsec_encryption = "aes-256-gcm"
    ipsec_integrity = "sha256"
    ipsec_pfs_group = "14"
    ipsec_lifetime = 3600
    routing_type = "static"
    nat_supported = True

    class Params:
        with_apps = factory.Trait(
            _apps=factory.PostGeneration(lambda obj, create, extracted, **kwargs: None)
        )

    @factory.post_generation
    def applications(self, create, extracted, **kwargs):
        if not create or not extracted:
            return
        for app in extracted:
            VpnRequestApplication.objects.create(vpn_request=self, application=app)


class TrafficFlowFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TrafficFlow

    vpn_request = factory.SubFactory(VpnRequestFactory)
    source_cidr = "10.0.0.0/24"
    destination_cidr = "192.168.1.10/32"
    direction = factory.LazyAttribute(
        lambda o: "inbound" if o.vpn_request.directionality == "vendor_initiates" else "outbound"
    )
    protocol = "tcp"
    destination_ports = "443"
    description = factory.Faker("sentence")
    order = factory.Sequence(lambda n: n)
