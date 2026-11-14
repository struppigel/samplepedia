from django.test import TestCase


class SampleTestCase(TestCase):
    """Base class for view tests. Create shared data in setUpTestData with the factories."""

    def login_as(self, user):
        """Log the test client in without going through the login form."""
        self.client.force_login(user)
