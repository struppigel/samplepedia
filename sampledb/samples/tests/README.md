# Test Suite for Samplepedia

## Overview

This directory contains comprehensive tests for the Samplepedia application, focusing on analysis task submission functionality.

## Test Files

### `test_sample_list.py`

Test suite for sample list view functionality with 4 main test classes:

#### 1. **SampleListUnauthenticatedTestCase** - Unauthenticated User Tests
Tests behavior for users who are not logged in:
- ✅ Landing page shown when accessing root without parameters
- ✅ Browse parameter shows sample list
- ✅ Search/filter shows list (regression test for redirect bug)
- ✅ Difficulty filter works for unauthenticated users
- ✅ Tag filter works for unauthenticated users
- ✅ Multiple filters work together

#### 2. **SampleListAuthenticatedTestCase** - Authenticated User Tests
Tests behavior for logged-in users:
- ✅ Authenticated users see list directly without params
- ✅ Favorites filter works for authenticated users
- ✅ Search and filter work together for authenticated users

#### 3. **SampleListSortingTestCase** - Sorting Tests
Tests sorting functionality:
- ✅ Sort by SHA256 ascending
- ✅ Sort by SHA256 descending
- ✅ Sort by difficulty

#### 4. **SampleListPaginationTestCase** - Pagination Tests
Tests pagination behavior:
- ✅ First page has 25 items
- ✅ Second page has remaining items
- ✅ Pagination preserves filters

### `test_task_submission.py`

Comprehensive test suite for task submission workflow with 4 main test classes:

#### 1. **AnalysisTaskFormTestCase** - Form Validation Tests
Tests the `AnalysisTaskForm` validation logic:
- ✅ Core fields (SHA256, download_link, etc.) are required
- ✅ Regular users must provide reference solutions
- ✅ Staff users can submit without reference solutions
- ✅ Onsite solutions must have content
- ✅ External solutions (blog/paper/video) must have URLs
- ✅ MalwareBazaar and MalShare URLs are accepted
- ✅ Regular users cannot use arbitrary download URLs
- ✅ Staff users can use any download URL
- ✅ Expert difficulty is excluded from form choices

#### 2. **TaskSubmissionViewTestCase** - Integration Tests
Tests the complete submission workflow through the view:
- ✅ Submission requires authentication
- ✅ GET request renders the form correctly
- ✅ Regular users can submit with blog/paper/video reference solutions
- ✅ Regular users can submit with onsite reference solutions
- ✅ Staff users can submit without reference solutions
- ✅ Tags and tools are normalized to lowercase
- ✅ Duplicate SHA256 hashes are rejected
- ✅ Image selection works correctly (placeholder)

#### 3. **TaskEditPermissionTestCase** - Permission Tests
Tests edit permissions for analysis tasks:
- ✅ Authors can edit their own tasks
- ✅ Non-authors cannot edit others' tasks
- ✅ Staff users can edit any task
- ✅ Contributors can edit any task

## Running the Tests

### Run all tests:
```bash
cd sampledb
python manage.py test samples
```

### Run specific test file:
```bash
python manage.py test samples.tests.test_task_submission
python manage.py test samples.tests.test_sample_list
python manage.py test samples.tests.test_solutions
```

### Run specific test class:
```bash
python manage.py test samples.tests.test_task_submission.AnalysisTaskFormTestCase
python manage.py test samples.tests.test_sample_list.SampleListUnauthenticatedTestCase
```

### Run specific test method:
```bash
python manage.py test samples.tests.test_task_submission.AnalysisTaskFormTestCase.test_form_requires_core_fields
python manage.py test samples.tests.test_sample_list.SampleListUnauthenticatedTestCase.test_search_shows_list_for_unauthenticated
```

### Run with verbose output:
```bash
python manage.py test samples --verbosity=2
```

### Run with coverage (requires coverage.py):
```bash
pip install coverage
coverage run --source='.' manage.py test samples
coverage report
coverage html  # Generate HTML report in htmlcov/
```

## Test Coverage

Current test coverage focuses on:
- ✅ Form validation logic
- ✅ User permission handling
- ✅ Reference solution requirements
- ✅ Data normalization (lowercase
- ✅ Sample list filtering and search (unauthenticated users)
- ✅ Landing page vs list view routing
- ✅ Sorting and pagination
- ✅ Solution CRUD operations and permissions
- ✅ Solution hiding functionality (hidden_until field) tags/tools)
- ✅ URL validation for download links
- ✅ SHA256 uniqueness constraints

## Areas for Future Testing

Additional tests that could be added:

### Frontend/Integration Tests
- **Markdown editor integration**: Test localStorage synchronization between submit_task.html and markdown_editor.html
- **Form field retention**: Test that all fields (including difficulty) are preserved when navigating to/from markdown editor
- **Image gallery**: Test image selection modal and preview functionality
- **Auto-fill SHA256**: Test automatic extraction of SHA256 from MalwareBazaar/MalShare URLs

### Backend Tests
- **Discord notifications**: Test that submissions trigger Discord webhooks correctly
- **Email notifications**: Test notification system for task creation
- **Tag/tool management**: Test taggit integration more thoroughly
- **Cloudinary integration**: Test actual image upload/retrieval
- **Solution CRUD**: Test solution creation, editing, deletion workflows
- **Comment functionality**: Test django-comments integration
- **Like/favorite system**: Test user interactions with tasks

### Performance Tests
- **Pagination**: Test task list pagination with large datasets
- **Search/filter**: Test filtering by tags, tools, difficulty, author, course
- **Database queries**: Test N+1 query optimization

### Security Tests
- **XSS prevention**: Test markdown rendering sanitization
- **CSRF protection**: Test CSRF token validation
- **SQL injection**: Test query parameterization
- **Permission bypass attempts**: Test unauthorized access attempts

## Test Data Conventions

The tests use the following conventions:
- **SHA256 hashes**: Single character repeated 64 times (e.g., 'a' * 64, 'b' * 64) for easy identification
- **User credentials**: All test users use password 'testpass123'
- **Download URLs**: Use bazaar.abuse.ch with test SHA256s

## Testing Redirects in Production-like Environments

**IMPORTANT**: When testing redirects with `assertRedirects()`, always use `fetch_redirect_response=False` parameter:

```python
self.assertRedirects(
    response,
    reverse('sample_detail', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
    fetch_redirect_response=False  # Required for production-like settings
)
```

**Why this is necessary:**
- In production, `DEBUG=False` is set along with security settings like `SECURE_SSL_REDIRECT`
- When `fetch_redirect_response=True` (default), Django tries to follow the redirect and fetch the target page
- With `SECURE_SSL_REDIRECT=True`, this can cause SSL-related errors in test environments
- Using `fetch_redirect_response=False` only verifies that the redirect happens to the correct URL without fetching it

**When to use:**
- ✅ All `assertRedirects()` calls should use `fetch_redirect_response=False`
- ✅ Even for simple redirects like login redirects
- ✅ Especially for redirects after POST requests (form submissions, deletions, etc.)

**Example from test_solutions.py:**
```python
def test_unauthenticated_cannot_create_solution(self):
    """Test that unauthenticated users cannot create solutions"""
    response = self.client.post(
        reverse('create_solution', kwargs={'sha256': self.task.sha256, 'task_id': self.task.id}),
        {
            'title': 'Test',
            'solution_type': SolutionType.BLOG,
            'url': 'https://example.com'
        }
    )
    
    # Should redirect to login - fetch_redirect_response=False for production compatibility
    expected_url = f"/login/?next=/sample/{self.task.sha256}/{self.task.id}/solution/add/"
    self.assertRedirects(response, expected_url, fetch_redirect_response=False)
    self.assertEqual(Solution.objects.count(), 0)
```

**Don't use `follow=True` as a workaround:**
- `follow=True` follows all redirects and returns the final page
- This is useful when you need to test the final rendered page content
- But for redirect testing, use `assertRedirects()` with `fetch_redirect_response=False` instead

## Continuous Integration

These tests can be integrated into CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
name: Django Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: cd sampledb && python manage.py test samples
```

## Debugging Failed Tests

If tests fail:

1. **Check test output**: Look for assertion errors and traceback
2. **Run with verbosity**: Add `--verbosity=2` for detailed output
3. **Use pdb**: Add `import pdb; pdb.set_trace()` to pause execution
4. **Check database state**: Tests use isolated test database, so no risk to production data
5. **Review migrations**: Ensure all migrations are applied with `python manage.py migrate`

## Contributing

When adding new features:
1. Write tests first (TDD approach)
2. Ensure all existing tests pass
3. Aim for >80% code coverage
4. Document test purpose and assertions clearly
