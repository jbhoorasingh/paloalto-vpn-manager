import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def approval_queue_view(request):
    return render(request, "approvals/queue.html", {
        "nav_active": "approvals-queue",
        "queue_json": json.dumps({}),
    })
