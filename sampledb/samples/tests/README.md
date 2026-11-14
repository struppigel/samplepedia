# Samplepedia tests

## Running

From `sampledb/` with the virtualenv active:

```powershell
python manage.py test samples                       # everything, about 5 seconds
python manage.py test samples.tests.test_solutions  # one module
python manage.py test samples --parallel            # what the Railway build runs
```

The Railway build (`railway.json`) runs the suite before `collectstatic`; a failing test stops the deploy.

## Test environment

`settings.py` detects a test run (`'test' in sys.argv`) and then:

- uses an in-memory SQLite database;
- hashes passwords with MD5 (PBKDF2 made the suite ~15x slower);
- blanks every `DISCORD_WEBHOOK_*`, so a local `.env` with real webhooks can't be posted to;
- disables Turnstile validation (it would call Cloudflare);
- configures a fixed fake Cloudinary account (image URLs render; uploads are mocked in the tests);
- quiets the `samples` logger to WARNING.

So the suite needs no `.env`, network or credentials.

## Writing tests

- Subclass `SampleTestCase` (`base.py`) and create shared data in `setUpTestData` with the factories in
  `factories.py`: `make_user`, `make_staff`, `make_task`, `make_article`, `make_solution`,
  `make_onsite_solution` (always backed by an Article). Every factory accepts field overrides.
  Tasks don't announce themselves on Discord unless you pass `send_discord_notification=True`.
- Log in with `self.login_as(user)`; use `self.client.login(...)` only when the login itself is under test.
- Assert redirects with `assertRedirects(..., fetch_redirect_response=False)` and the expected target.
- List pages must stay constant-query: see `QueryCountTestCase` in `test_visibility.py`.
- Code that creates solutions, likes or notifications should be tested through the services
  (`samples/services/`) as well as the views that call them.

## Guardrail tests

These scan the code rather than exercise it, and fail with a list of offending lines:

- `test_design_system.py` - design tokens (raw values only in `static/css/tokens.css`, every token
  defined and used, no `!important`, dark mode via tokens only, no Bootstrap 4/AdminLTE classes).
- `test_frontend.py` - no inline scripts, `on*=` handlers, `javascript:` URLs, hardcoded app URLs in JS,
  cookie parsing or `display` toggling (rules in `frontend_rules.py`, which also runs on its own:
  `python samples/tests/frontend_rules.py [file filter]`).

## Files

| File | Covers |
|---|---|
| `test_account_deletion.py` | deleting an account: form, view, cascades, comment anonymization, last-superuser guard |
| `test_announcements.py` | Discord announcement once per solution; hidden ones via `announce_solutions` after `hidden_until`, retries, max age |
| `test_comment_notifications.py` | comment and @mention notifications, recipients, query count |
| `test_design_system.py` | design-system guardrails (see above) and the Discord colors read from tokens.css |
| `test_discord.py` | webhook choice per difficulty, embed links, failures logged not raised |
| `test_draft_article_publishing.py` | choosing a draft article as a solution or reference solution, article list buttons |
| `test_editors.py` | markdown editor hooks and draft clearing after a successful save |
| `test_emails.py` | verification, resend, password reset and e-mail change mails end to end |
| `test_form_templates.py` | account pages render fields, errors, Turnstile and password rules |
| `test_forms.py` | shared form rules: e-mail checks, ArticleForm, gallery image ids |
| `test_frontend.py` | front-end guardrails (see above) |
| `test_frontend_pages.py` | data-* hooks carry the right URLs; `mention_links` |
| `test_legal_pages.py` | impressum and privacy policy per language; e-mail template rendering |
| `test_likes.py` | liking tasks and solutions, aggregated like notifications, notification icons and pagination |
| `test_list_templates.py` | pagination keeps filters, filter bar, SHA256 cells, detail sidebar, showcase markup |
| `test_migrations.py` | data migrations 0019 (legacy solution content into Articles) and 0022 (existing solutions count as announced) |
| `test_regressions.py` | duplicate titles, hidden-solution leaks, editor re-renders, canonical task URLs |
| `test_sample_list.py` | task list: filtering, sorting, pagination, landing page |
| `test_scoring.py` | scores and ranks against the original per-object algorithm |
| `test_security.py` | CSP headers and reports, markdown sanitizing, safe redirects, likes require POST, comment posting |
| `test_solution_service.py` | `services/solutions.py`: Articles, drafts, title uniqueness |
| `test_solutions.py` | solution create/edit/delete, permissions, likes, listing, on-site solutions, hiding |
| `test_task_image_preview.py` | task images: upload, gallery selection, validation, preview markup |
| `test_task_submission.py` | task submission and editing, reference solutions, permissions |
| `test_view_count.py` | task and article view counters |
| `test_visibility.py` | who sees hidden solutions on every page, delete rules, query counts |
