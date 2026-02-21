# Generated migration for converting existing on-site solutions to Article-based solutions

from django.db import migrations


def migrate_onsite_solutions_to_articles(apps, schema_editor):
    """
    Convert all existing on-site solutions that use the content field
    to use the new Article model instead.
    """
    Solution = apps.get_model('samples', 'Solution')
    Article = apps.get_model('samples', 'Article')
    
    # Get all on-site solutions that have content in the old field
    onsite_solutions = Solution.objects.filter(
        solution_type='onsite',
        article__isnull=True  # Only migrate those not already using Article
    ).exclude(content='')
    
    migrated_count = 0
    
    for solution in onsite_solutions:
        # Create an Article for this solution
        article = Article.objects.create(
            title=solution.title,
            content=solution.content,
            author=solution.author,
            # created_at and updated_at will be set to now, which is acceptable
            # view_count starts at 0, which is also acceptable for the migration
        )
        
        # Link the article to the solution
        solution.article = article
        solution.save(update_fields=['article'])
        
        migrated_count += 1
    
    if migrated_count > 0:
        print(f"Successfully migrated {migrated_count} on-site solution(s) to use Article model.")


def reverse_migration(apps, schema_editor):
    """
    Reverse the migration by unlinking articles from solutions.
    Note: This keeps the Article records for safety - they can be manually deleted if needed.
    """
    Solution = apps.get_model('samples', 'Solution')
    
    # Unlink articles from solutions (but keep the Article records)
    onsite_solutions = Solution.objects.filter(
        solution_type='onsite',
        article__isnull=False
    )
    
    for solution in onsite_solutions:
        solution.article = None
        solution.save(update_fields=['article'])


class Migration(migrations.Migration):

    dependencies = [
        ('samples', '0016_alter_solution_content_article_solution_article_and_more'),
    ]

    operations = [
        migrations.RunPython(
            migrate_onsite_solutions_to_articles,
            reverse_migration
        ),
    ]
