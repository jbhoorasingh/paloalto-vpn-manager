from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.core.models import Role, User, UserRole
from apps.core.permissions import role_required


@role_required("admin")
def user_list_view(request):
    q = request.GET.get("q", "")
    users = User.objects.prefetch_related("user_roles").all()
    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )
    return render(request, "user/list.html", {
        "nav_active": "user-list",
        "users": users,
        "q": q,
        "role_choices": Role.choices,
    })


@role_required("admin")
def user_create_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        if username and password:
            edit_user = User(
                username=username,
                first_name=request.POST.get("first_name", "").strip(),
                last_name=request.POST.get("last_name", "").strip(),
                email=request.POST.get("email", "").strip(),
                department=request.POST.get("department", "").strip(),
                distribution_list_email=request.POST.get("distribution_list_email", "").strip(),
                is_active=request.POST.get("is_active") == "on",
            )
            edit_user.set_password(password)
            edit_user.save()
            # Assign roles
            selected_roles = request.POST.getlist("roles")
            for role in selected_roles:
                if role in dict(Role.choices):
                    UserRole.objects.create(user=edit_user, role=role)
            return redirect("ui:user-list")
    return render(request, "user/form.html", {
        "nav_active": "user-list",
        "form_title": "Add User",
        "role_choices": Role.choices,
    })


@role_required("admin")
def user_edit_view(request, pk):
    edit_user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        edit_user.username = request.POST.get("username", edit_user.username).strip()
        edit_user.first_name = request.POST.get("first_name", edit_user.first_name).strip()
        edit_user.last_name = request.POST.get("last_name", edit_user.last_name).strip()
        edit_user.email = request.POST.get("email", edit_user.email).strip()
        edit_user.department = request.POST.get("department", edit_user.department).strip()
        edit_user.distribution_list_email = request.POST.get(
            "distribution_list_email", edit_user.distribution_list_email
        ).strip()
        edit_user.is_active = request.POST.get("is_active") == "on"
        password = request.POST.get("password", "").strip()
        if password:
            edit_user.set_password(password)
        edit_user.save()
        # Update roles: replace all with the new selection
        selected_roles = request.POST.getlist("roles")
        edit_user.user_roles.all().delete()
        for role in selected_roles:
            if role in dict(Role.choices):
                UserRole.objects.create(user=edit_user, role=role)
        return redirect("ui:user-list")

    current_roles = set(edit_user.user_roles.values_list("role", flat=True))
    return render(request, "user/form.html", {
        "nav_active": "user-list",
        "form_title": "Edit User",
        "edit_user": edit_user,
        "current_roles": current_roles,
        "role_choices": Role.choices,
    })
