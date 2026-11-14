from django.shortcuts import get_object_or_404

from ..models import AnalysisTask


def get_task_or_404(sha256, task_id):
    """The task of a /sample/<sha256>/<task_id>/ URL; the id and the hash must both match."""
    return get_object_or_404(AnalysisTask, id=task_id, sha256=sha256.lower())
