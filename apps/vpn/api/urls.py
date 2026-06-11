from django.urls import path

from . import approvals, flows, requests, vendors, wizard

app_name = "vpn-api"

urlpatterns = [
    # Wizard
    path("wizard/create/", wizard.wizard_create, name="wizard-create"),
    path("wizard/<int:pk>/", wizard.wizard_load, name="wizard-load"),
    path("wizard/<int:pk>/step/<int:step>/", wizard.wizard_save_step, name="wizard-save-step"),
    path("wizard/<int:pk>/submit/", wizard.wizard_submit, name="wizard-submit"),

    # Vendors
    path("vendors/", vendors.vendor_list, name="vendor-list"),
    path("vendors/create/", vendors.vendor_create, name="vendor-create"),
    path("vendors/<int:pk>/contacts/", vendors.vendor_contacts, name="vendor-contacts"),

    # Flows
    path("requests/<int:request_pk>/flows/", flows.flow_list_create, name="flow-list-create"),
    path("flows/<int:pk>/", flows.flow_detail, name="flow-detail"),

    # Requests
    path("requests/", requests.request_list, name="request-list"),
    path("requests/<int:pk>/", requests.request_detail, name="request-detail"),

    # Approvals
    path("approvals/queue/", approvals.approval_queue, name="approval-queue"),
    path("requests/<int:pk>/approve-infosec/", approvals.approve_infosec_view, name="approve-infosec"),
    path("requests/<int:pk>/request-infosec-changes/", approvals.request_infosec_changes_view, name="request-infosec-changes"),
    path("requests/<int:pk>/approve-network/", approvals.approve_network_view, name="approve-network"),
    path("requests/<int:pk>/request-network-changes/", approvals.request_network_changes_view, name="request-network-changes"),
    path("requests/<int:pk>/reject/", approvals.reject_view, name="reject-request"),
    path("requests/<int:pk>/approvals/", approvals.approval_history, name="approval-history"),
]
