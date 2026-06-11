from django.urls import path

from .views import (
    approval,
    config_template,
    dashboard,
    deployment,
    endpoint,
    pools,
    request_detail,
    user,
    vendor,
    wizard,
)

app_name = "ui"

urlpatterns = [
    # Dashboard
    path("", dashboard.dashboard_view, name="dashboard"),

    # Vendors
    path("vendors/", vendor.vendor_list_view, name="vendor-list"),
    path("vendors/create/", vendor.vendor_create_view, name="vendor-create"),
    path("vendors/<int:pk>/edit/", vendor.vendor_edit_view, name="vendor-edit"),

    # Applications
    path("applications/", vendor.application_list_view, name="application-list"),
    path("applications/create/", vendor.application_create_view, name="application-create"),
    path("applications/<int:pk>/edit/", vendor.application_edit_view, name="application-edit"),

    # Endpoints
    path("endpoints/", endpoint.endpoint_list_view, name="endpoint-list"),
    path("endpoints/create/", endpoint.endpoint_create_view, name="endpoint-create"),
    path("endpoints/<int:pk>/edit/", endpoint.endpoint_edit_view, name="endpoint-edit"),

    # Address pools
    path("pools/", pools.pool_list_view, name="pool-list"),
    path("pools/nat/create/", pools.nat_pool_create_view, name="nat-pool-create"),
    path("pools/nat/<int:pk>/edit/", pools.nat_pool_edit_view, name="nat-pool-edit"),
    path("pools/nat/<int:pk>/delete/", pools.nat_pool_delete_view, name="nat-pool-delete"),
    path("pools/dr-peers/create/", pools.dr_peer_create_view, name="dr-peer-create"),
    path("pools/dr-peers/<int:pk>/edit/", pools.dr_peer_edit_view, name="dr-peer-edit"),
    path("pools/dr-peers/<int:pk>/delete/", pools.dr_peer_delete_view, name="dr-peer-delete"),
    path("pools/tunnel/create/", pools.tunnel_pool_create_view, name="tunnel-pool-create"),
    path("pools/tunnel/<int:pk>/edit/", pools.tunnel_pool_edit_view, name="tunnel-pool-edit"),
    path("pools/tunnel/<int:pk>/delete/", pools.tunnel_pool_delete_view, name="tunnel-pool-delete"),

    # Tunnel interfaces
    path("tunnels/", pools.tunnel_interface_list_view, name="tunnel-interface-list"),
    path("tunnels/<int:pk>/edit/", pools.tunnel_interface_edit_view, name="tunnel-interface-edit"),
    path("tunnels/<int:pk>/release/", pools.tunnel_interface_release_view, name="tunnel-interface-release"),

    # Wizard
    path("vpn/new/", wizard.wizard_create_view, name="wizard-create"),
    path("vpn/<int:pk>/edit/", wizard.wizard_edit_view, name="wizard-edit"),

    # Requests
    path("vpn/requests/", request_detail.request_list_view, name="request-list"),
    path("vpn/requests/<int:pk>/", request_detail.request_detail_view, name="request-detail"),
    path("vpn/requests/<int:pk>/delete/", request_detail.request_delete_view, name="request-delete"),
    path("vpn/requests/<int:pk>/config/download/", request_detail.request_config_download_view, name="request-config-download"),
    path("vpn/requests/<int:pk>/config/template/", config_template.request_config_template_view, name="request-config-template"),

    # Config templates (document layout + segments)
    path("config-template/", config_template.config_template_view, name="config-template"),
    path("config-template/<str:name>/", config_template.config_template_edit_view, name="config-template-edit"),

    # Users (admin-only)
    path("users/", user.user_list_view, name="user-list"),
    path("users/create/", user.user_create_view, name="user-create"),
    path("users/<int:pk>/edit/", user.user_edit_view, name="user-edit"),

    # Approvals
    path("approvals/", approval.approval_queue_view, name="approvals-queue"),

    # Deployment
    path("deployment/", deployment.deployment_list_view, name="deployment"),
    path("deployment/<int:pk>/", deployment.deployment_detail_view, name="deployment-detail"),
]
