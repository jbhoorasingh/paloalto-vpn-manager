import pytest

from apps.core.models import Role, User

from .factories import SiteFactory, UserFactory


@pytest.mark.django_db
class TestUser:
    def test_create_user(self):
        user = UserFactory(username="testuser", roles=["requester"])
        assert user.username == "testuser"
        assert user.has_role(Role.REQUESTER)
        assert "(Requester)" in str(user)

    def test_user_roles(self):
        for role_value, role_label in Role.choices:
            user = UserFactory(roles=[role_value])
            assert user.has_role(role_value)

    def test_multiple_roles(self):
        user = UserFactory(roles=["infosec", "network"])
        assert user.has_role("infosec")
        assert user.has_role("network")
        assert user.is_infosec_approver is True
        assert user.is_network_approver is True
        assert user.is_deployer is False

    def test_is_infosec_approver(self):
        user = UserFactory(roles=[Role.INFOSEC_APPROVER])
        assert user.is_infosec_approver is True
        assert user.is_network_approver is False

    def test_is_network_approver(self):
        user = UserFactory(roles=[Role.NETWORK_APPROVER])
        assert user.is_network_approver is True
        assert user.is_infosec_approver is False

    def test_is_deployer(self):
        user = UserFactory(roles=[Role.DEPLOYER])
        assert user.is_deployer is True

    def test_admin_has_all_roles(self):
        user = UserFactory(roles=[Role.ADMIN])
        assert user.is_infosec_approver is True
        assert user.is_network_approver is True
        assert user.is_deployer is True
        assert user.is_admin_role is True

    def test_user_str_with_full_name(self):
        user = UserFactory(first_name="John", last_name="Doe", roles=["requester"])
        assert "John Doe" in str(user)

    def test_department_and_dl(self):
        user = UserFactory(department="Engineering", distribution_list_email="eng@example.com")
        assert user.department == "Engineering"
        assert user.distribution_list_email == "eng@example.com"


@pytest.mark.django_db
class TestSite:
    def test_create_site(self):
        site = SiteFactory(name="Region 1", code="region1")
        assert site.name == "Region 1"
        assert site.code == "region1"
        assert site.is_active is True

    def test_site_str(self):
        site = SiteFactory(name="Region 1", code="region1")
        assert str(site) == "Region 1 (region1)"

    def test_site_unique_code(self):
        SiteFactory(code="unique1")
        with pytest.raises(Exception):
            SiteFactory(code="unique1")
