from decouple import config
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create superuser from environment variables (or .env)'

    def handle(self, *args, **options):
        User = get_user_model()
        username = config('ADMIN_USERNAME', default='')
        email = config('ADMIN_EMAIL', default='')
        password = config('ADMIN_PASSWORD', default='')

        if not all([username, email, password]):
            self.stdout.write(self.style.WARNING(
                'Skipping admin creation - ADMIN_USERNAME, ADMIN_EMAIL, or ADMIN_PASSWORD not set'
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists'))
        else:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully'))
