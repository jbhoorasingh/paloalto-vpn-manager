from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.vpn.models import Application, Vendor


@login_required
def vendor_list_view(request):
    q = request.GET.get("q", "")
    vendors = Vendor.objects.all()
    if q:
        vendors = vendors.filter(name__icontains=q)
    return render(request, "vendor/list.html", {
        "nav_active": "vendor-list",
        "vendors": vendors,
        "q": q,
    })


@login_required
def vendor_create_view(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            Vendor.objects.create(
                name=name,
                domain=request.POST.get("domain", ""),
                support_email=request.POST.get("support_email", ""),
                support_phone=request.POST.get("support_phone", ""),
                created_by=request.user,
            )
            return redirect("ui:vendor-list")
    return render(request, "vendor/form.html", {
        "nav_active": "vendor-list",
        "form_title": "Add Vendor",
    })


@login_required
def vendor_edit_view(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.method == "POST":
        vendor.name = request.POST.get("name", vendor.name).strip()
        vendor.domain = request.POST.get("domain", vendor.domain)
        vendor.support_email = request.POST.get("support_email", vendor.support_email)
        vendor.support_phone = request.POST.get("support_phone", vendor.support_phone)
        vendor.save()
        return redirect("ui:vendor-list")
    return render(request, "vendor/form.html", {
        "nav_active": "vendor-list",
        "form_title": "Edit Vendor",
        "vendor": vendor,
    })


@login_required
def application_list_view(request):
    q = request.GET.get("q", "")
    applications = Application.objects.select_related("owner").all()
    if q:
        applications = applications.filter(name__icontains=q)
    return render(request, "vendor/application_list.html", {
        "nav_active": "application-list",
        "applications": applications,
        "q": q,
    })


@login_required
def application_create_view(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if name:
            Application.objects.create(
                name=name,
                owner=request.user,
                distribution_list_email=request.POST.get("distribution_list_email", ""),
                criticality=request.POST.get("criticality", "medium"),
                description=request.POST.get("description", ""),
            )
            return redirect("ui:application-list")
    return render(request, "vendor/application_form.html", {
        "nav_active": "application-list",
        "form_title": "Add Application",
        "criticality_choices": Application.Criticality.choices,
    })


@login_required
def application_edit_view(request, pk):
    app = get_object_or_404(Application, pk=pk)
    if request.method == "POST":
        app.name = request.POST.get("name", app.name).strip()
        app.distribution_list_email = request.POST.get("distribution_list_email", app.distribution_list_email)
        app.criticality = request.POST.get("criticality", app.criticality)
        app.description = request.POST.get("description", app.description)
        app.save()
        return redirect("ui:application-list")
    return render(request, "vendor/application_form.html", {
        "nav_active": "application-list",
        "form_title": "Edit Application",
        "application": app,
        "criticality_choices": Application.Criticality.choices,
    })
