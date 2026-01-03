# Test Suite for Samplepedia

## Overview

This directory contains comprehensive tests for the Samplepedia application, focusing on analysis task submission functionality.

## Test Files

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
python manage.py test samples.test_task_submission
```

### Run specific test class:
```bash
python manage.py test samples.test_task_submission.AnalysisTaskFormTestCase
```

### Run specific test method:
```bash
python manage.py test samples.test_task_submission.AnalysisTaskFormTestCase.test_form_requires_core_fields
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
- ✅ Data normalization (lowercase tags/tools)
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
