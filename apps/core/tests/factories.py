import factory

from apps.core.models import NatPool, Site, TunnelAddressPool, User, UserRole


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    department = factory.Faker("company")

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        password = extracted or "testpass123"
        self.set_password(password)
        if create:
            self.save()

    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for role in extracted:
                UserRole.objects.create(user=self, role=role)
        else:
            # Default to requester if no roles specified
            UserRole.objects.create(user=self, role="requester")


class SiteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Site

    name = factory.Sequence(lambda n: f"Site {n}")
    code = factory.Sequence(lambda n: f"site{n}")
    location = factory.Faker("city")
    datacenter = factory.Faker("company")
    public_ip = factory.Faker("ipv4")
    bgp_asn = 65001
    device_brand = "palo_alto"
    management_type = "centralized"
    management_platform = "Panorama"
    device_group = "DG-Internet-Edge"
    template_name = "TS-Internet-Edge"
    tunnel_interface_start = 100
    tunnel_interface_end = 199
    is_active = True


class TunnelAddressPoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TunnelAddressPool

    site = factory.SubFactory(SiteFactory)
    cidr = "10.255.0.0/24"
    description = "Default tunnel pool"
    is_active = True


class NatPoolFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = NatPool

    site = factory.SubFactory(SiteFactory)
    direction = "outbound"
    cidr = "10.111.96.0/24"
    description = "Default NAT pool"
    is_active = True
