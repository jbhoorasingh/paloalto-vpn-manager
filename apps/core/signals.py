from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Role, User, UserRole


@receiver(post_save, sender=User)
def ensure_superuser_has_all_roles(sender, instance, **kwargs):
    """Automatically grant all roles to superusers."""
    if instance.is_superuser:
        existing = set(instance.user_roles.values_list("role", flat=True))
        for role_value, _ in Role.choices:
            if role_value not in existing:
                UserRole.objects.get_or_create(user=instance, role=role_value)
        # Invalidate the cached role_values
        instance.invalidate_role_cache()
