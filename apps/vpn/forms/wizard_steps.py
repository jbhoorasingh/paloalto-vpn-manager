from django import forms

from apps.vpn.models import TrafficFlow, VpnRequest


class StepVendorForm(forms.Form):
    vendor_id = forms.IntegerField()


class StepAppsDataForm(forms.Form):
    title = forms.CharField(max_length=300)
    purpose = forms.CharField(required=False)
    directionality = forms.ChoiceField(choices=[("", "---")] + list(VpnRequest.directionality.field.choices))
    data_description = forms.CharField(required=False)
    data_classification = forms.CharField(max_length=50, required=False)
    application_ids = forms.CharField(required=False, help_text="Comma-separated app IDs")


class StepTopologyForm(forms.Form):
    vendor_endpoints_count = forms.IntegerField(min_value=1, max_value=2)
    topology_type = forms.ChoiceField(
        choices=[("", "---")] + list(VpnRequest._meta.get_field("topology_type").choices),
        required=False,
    )
    vendor_endpoint_1_ip = forms.GenericIPAddressField(required=False)
    vendor_endpoint_2_ip = forms.GenericIPAddressField(required=False)
    our_endpoint_1_site_id = forms.IntegerField(required=False)
    our_endpoint_2_site_id = forms.IntegerField(required=False)


class StepCryptoForm(forms.Form):
    ike_version = forms.ChoiceField(choices=[("1", "IKEv1"), ("2", "IKEv2")])
    auth_method = forms.ChoiceField(choices=[("psk", "Pre-Shared Key"), ("certificate", "Certificate")])
    ike_encryption = forms.CharField(max_length=50, required=False)
    ike_integrity = forms.CharField(max_length=50, required=False)
    ike_dh_group = forms.CharField(max_length=20, required=False)
    ike_lifetime = forms.IntegerField(required=False)
    dpd_enabled = forms.BooleanField(required=False)
    ipsec_encryption = forms.CharField(max_length=50, required=False)
    ipsec_integrity = forms.CharField(max_length=50, required=False)
    ipsec_pfs_group = forms.CharField(max_length=20, required=False)
    ipsec_lifetime = forms.IntegerField(required=False)
    tunnel_mode = forms.CharField(max_length=20, required=False)


class StepRoutingForm(forms.Form):
    routing_type = forms.ChoiceField(
        choices=[("static", "Static"), ("bgp", "BGP")],
        required=False,
    )
    bgp_local_asn = forms.IntegerField(required=False)
    bgp_remote_asn = forms.IntegerField(required=False)
    bgp_peer_ip_local = forms.GenericIPAddressField(required=False)
    bgp_peer_ip_remote = forms.GenericIPAddressField(required=False)
    bgp_auth_enabled = forms.BooleanField(required=False)
    nat_supported = forms.NullBooleanField(required=False)
    nat_exception_reason = forms.CharField(required=False)


STEP_FORMS = {
    1: StepVendorForm,
    2: StepAppsDataForm,
    3: StepTopologyForm,
    4: StepCryptoForm,
    5: StepRoutingForm,
}
