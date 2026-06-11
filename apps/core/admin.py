from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import NatPool, Site, TunnelAddressPool, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "display_roles", "department", "is_staff")
    list_filter = ("user_roles__role", "is_staff", "is_active")
    inlines = [UserRoleInline]
    fieldsets = BaseUserAdmin.fieldsets + (
        ("VPN Platform", {"fields": ("department", "distribution_list_email")}),
    )

    @admin.display(description="Roles")
    def display_roles(self, obj):
        return ", ".join(obj.user_roles.values_list("role", flat=True)) or "—"


class TunnelAddressPoolInline(admin.TabularInline):
    model = TunnelAddressPool
    extra = 1


class NatPoolInline(admin.TabularInline):
    model = NatPool
    extra = 1
    fields = ("direction", "cidr", "description", "is_active")


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "location", "datacenter", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "code")
    inlines = [TunnelAddressPoolInline, NatPoolInline]


@admin.register(NatPool)
class NatPoolAdmin(admin.ModelAdmin):
    list_display = ("site", "scope", "direction", "cidr", "is_active", "created_at")
    list_filter = ("scope", "direction", "is_active", "site")
    search_fields = ("cidr", "site__code", "site__name")
