from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    REQUESTER = "requester", "Requester"
    INFOSEC_APPROVER = "infosec", "InfoSec Approver"
    NETWORK_APPROVER = "network", "Network Approver"
    DEPLOYER = "deployer", "Deployer"
    ADMIN = "admin", "Administrator"


class User(AbstractUser):
    department = models.CharField(max_length=100, blank=True)
    distribution_list_email = models.EmailField(blank=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        roles_display = ", ".join(
            dict(Role.choices).get(r, r) for r in self.role_values
        ) or "No Role"
        return f"{self.get_full_name() or self.username} ({roles_display})"

    @property
    def role_values(self):
        """Return set of role strings for this user."""
        if not hasattr(self, "_cached_roles"):
            self._cached_roles = set(
                self.user_roles.values_list("role", flat=True)
            )
        return self._cached_roles

    def has_role(self, role):
        return role in self.role_values

    def invalidate_role_cache(self):
        if hasattr(self, "_cached_roles"):
            del self._cached_roles

    @property
    def is_infosec_approver(self):
        roles = self.role_values
        return Role.INFOSEC_APPROVER in roles or Role.ADMIN in roles

    @property
    def is_network_approver(self):
        roles = self.role_values
        return Role.NETWORK_APPROVER in roles or Role.ADMIN in roles

    @property
    def is_deployer(self):
        roles = self.role_values
        return Role.DEPLOYER in roles or Role.ADMIN in roles

    @property
    def is_admin_role(self):
        return Role.ADMIN in self.role_values


class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.CharField(max_length=20, choices=Role.choices)

    class Meta:
        unique_together = ("user", "role")
        ordering = ["role"]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"
