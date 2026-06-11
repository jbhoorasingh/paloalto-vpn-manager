import pytest
from django.urls import reverse

from apps.core.models import User, UserRole
from apps.core.tests.factories import UserFactory


@pytest.fixture
def admin_user(db):
    return UserFactory(roles=["admin"], is_staff=True)


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def regular_user(db):
    return UserFactory(roles=["requester"])


@pytest.fixture
def regular_client(client, regular_user):
    client.force_login(regular_user)
    return client


@pytest.mark.django_db
class TestUserManagement:
    def test_user_list_admin_access(self, admin_client):
        response = admin_client.get(reverse("ui:user-list"))
        assert response.status_code == 200

    def test_user_list_non_admin_denied(self, regular_client):
        response = regular_client.get(reverse("ui:user-list"))
        assert response.status_code == 403

    def test_user_create(self, admin_client):
        response = admin_client.post(
            reverse("ui:user-create"),
            data={
                "username": "newuser",
                "password": "securepass123",
                "first_name": "New",
                "last_name": "User",
                "email": "new@example.com",
                "roles": ["requester", "infosec"],
                "department": "Engineering",
                "distribution_list_email": "",
                "is_active": "on",
            },
        )
        assert response.status_code == 302  # redirect to list
        assert User.objects.filter(username="newuser").exists()
        user = User.objects.get(username="newuser")
        assert user.first_name == "New"
        assert user.has_role("requester")
        assert user.has_role("infosec")
        assert user.is_active is True

    def test_user_edit(self, admin_client):
        target = UserFactory(roles=["requester"], department="Old Dept")
        response = admin_client.post(
            reverse("ui:user-edit", args=[target.pk]),
            data={
                "username": target.username,
                "first_name": target.first_name,
                "last_name": target.last_name,
                "email": target.email,
                "roles": ["infosec", "network"],
                "department": "Security",
                "distribution_list_email": "",
                "is_active": "on",
            },
        )
        assert response.status_code == 302
        target.refresh_from_db()
        target.invalidate_role_cache()
        assert target.has_role("infosec")
        assert target.has_role("network")
        assert not target.has_role("requester")
        assert target.department == "Security"

    def test_user_search(self, admin_client):
        UserFactory(username="findme_test")
        UserFactory(username="dontfind")
        response = admin_client.get(reverse("ui:user-list") + "?q=findme")
        assert response.status_code == 200
        content = response.content.decode()
        assert "findme_test" in content
        assert "dontfind" not in content
