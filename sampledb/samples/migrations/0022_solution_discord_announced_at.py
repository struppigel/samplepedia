"""
Track when each solution was announced on Discord, so hidden solutions can be
announced once their hidden period ends (manage.py announce_solutions).

Every existing solution counts as announced: visible ones were announced when
they were created, and so were hidden ones, which the code before this
migration announced immediately. Without this, the first run of
announce_solutions would post all of them again.
"""
from django.db import migrations, models
from django.db.models.functions import Coalesce


def mark_existing_solutions_announced(apps, schema_editor):
    Solution = apps.get_model('samples', 'Solution')
    Solution.objects.filter(discord_announced_at__isnull=True).update(
        discord_announced_at=Coalesce('hidden_until', 'created_at'),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0021_remove_legacy_content_and_like_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='solution',
            name='discord_announced_at',
            field=models.DateTimeField(blank=True, editable=False, null=True, verbose_name='Announced on Discord at'),
        ),
        migrations.RunPython(mark_existing_solutions_announced, migrations.RunPython.noop),
    ]
