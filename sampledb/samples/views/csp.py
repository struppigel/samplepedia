import json
import logging

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)

MAX_REPORT_BYTES = 10_000


@csrf_exempt  # browsers send reports without cookies or tokens
@require_POST
def csp_report(request):
    """Log Content-Security-Policy violation reports sent by browsers."""
    if len(request.body) > MAX_REPORT_BYTES:
        return HttpResponseBadRequest()
    try:
        report = json.loads(request.body).get('csp-report', {})
    except (ValueError, AttributeError):
        return HttpResponseBadRequest()
    logger.warning(
        'CSP violation: %s blocked %s on %s',
        report.get('violated-directive') or report.get('effective-directive'),
        report.get('blocked-uri'),
        report.get('document-uri'),
    )
    return HttpResponse(status=204)
