import json

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.vpn.models import VpnRequest


@login_required
def dashboard_view(request):
    user_requests = VpnRequest.objects.filter(requester=request.user).select_related("vendor")

    # Stats
    stats = {
        "total": user_requests.count(),
        "draft": user_requests.filter(status="draft").count(),
        "submitted": user_requests.filter(status="submitted").count(),
        "active": user_requests.filter(status="active").count(),
        "pending_approval": user_requests.filter(
            status__in=["submitted", "infosec_approved"]
        ).count(),
    }

    return render(request, "dashboard/index.html", {
        "nav_active": "dashboard",
        "stats_json": json.dumps(stats),
        "requests_json": json.dumps({"scope": "mine"}),
    })
