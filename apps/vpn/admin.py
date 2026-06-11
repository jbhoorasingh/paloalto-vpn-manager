from django.contrib import admin

from .models import (
    Application,
    NatMapping,
    TrafficFlow,
    TunnelInterface,
    Vendor,
    VendorContact,
    VpnRequest,
    VpnRequestApplication,
)


class VendorContactInline(admin.TabularInline):
    model = VendorContact
    extra = 1


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "domain", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "domain")
    inlines = [VendorContactInline]


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "criticality", "created_at")
    list_filter = ("criticality",)
    search_fields = ("name",)


class TrafficFlowInline(admin.TabularInline):
    model = TrafficFlow
    extra = 0


class VpnRequestApplicationInline(admin.TabularInline):
    model = VpnRequestApplication
    extra = 1


class TunnelInterfaceInline(admin.TabularInline):
    model = TunnelInterface
    extra = 0
    readonly_fields = (
        "site", "tunnel_number", "local_ip", "remote_ip",
        "subnet_cidr", "address_pool", "vendor_endpoint_ip",
    )


class NatMappingInline(admin.TabularInline):
    model = NatMapping
    extra = 0
    fields = ("site", "direction", "nat_address", "real_address", "nat_pool", "traffic_flow", "description")


@admin.register(VpnRequest)
class VpnRequestAdmin(admin.ModelAdmin):
    list_display = ("reference_number", "title", "vendor", "requester", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("reference_number", "title")
    readonly_fields = ("reference_number", "status")
    inlines = [VpnRequestApplicationInline, TrafficFlowInline, TunnelInterfaceInline, NatMappingInline]


@admin.register(NatMapping)
class NatMappingAdmin(admin.ModelAdmin):
    list_display = ("vpn_request", "site", "direction", "nat_address", "real_address", "created_at")
    list_filter = ("direction", "site")
    search_fields = ("nat_address", "real_address", "vpn_request__reference_number")
