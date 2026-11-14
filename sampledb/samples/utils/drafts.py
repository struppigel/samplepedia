"""
Forgetting browser drafts once the server has accepted them.

The editors autosave to localStorage (static/js/drafts.js). A view that has
saved the submitted content calls clear_drafts(request, 'task-form') before
redirecting; the next page lists those names in <meta name="sp-clear-drafts">,
and drafts.js removes them. A submission that fails validation keeps its draft.
"""
SESSION_KEY = 'sp_drafts_to_clear'


def clear_drafts(request, *names):
    """Have the next rendered page clear these drafts (names as in static/js/drafts.js)."""
    pending = set(request.session.get(SESSION_KEY, []))
    request.session[SESSION_KEY] = sorted(pending | set(names))


def pop_drafts_to_clear(request):
    session = getattr(request, 'session', None)
    if session is None:
        return []
    return session.pop(SESSION_KEY, [])
