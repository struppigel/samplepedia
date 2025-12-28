from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from samples.models import AnalysisTask


class Command(BaseCommand):
    help = 'Creates a contributor group with permission to submit analysis tasks'

    def handle(self, *args, **options):
        # Get or create the contributor group
        group, created = Group.objects.get_or_create(name='contributor')
        
        if created:
            self.stdout.write(self.style.SUCCESS('Created "contributor" group'))
        else:
            self.stdout.write(self.style.WARNING('"contributor" group already exists'))
        
        # Get the AnalysisTask content type
        content_type = ContentType.objects.get_for_model(AnalysisTask)
        
        # Get the add_analysistask permission
        permission = Permission.objects.get(
            codename='add_analysistask',
            content_type=content_type
        )
        
        # Add permission to group if not already added
        if permission not in group.permissions.all():
            group.permissions.add(permission)
            self.stdout.write(self.style.SUCCESS(
                f'Added "add_analysistask" permission to "contributor" group'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'Permission already assigned to group'
            ))
        
        self.stdout.write(self.style.SUCCESS(
            'Contributor group setup complete. Add users to this group to allow them to submit tasks.'
        ))
