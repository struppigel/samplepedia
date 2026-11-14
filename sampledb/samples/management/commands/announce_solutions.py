from datetime import timedelta

from django.core.management.base import BaseCommand

from samples.services.announcements import DEFAULT_MAX_AGE, announce_solution, due_solutions


class Command(BaseCommand):
    help = (
        'Announces solutions on Discord whose hidden period has ended (and retries failed '
        'announcements). Runs hourly as a Railway cron service, see railway.cron.json.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List what would be announced, post nothing')
        parser.add_argument(
            '--max-age-days', type=int, default=DEFAULT_MAX_AGE.days,
            help='Skip solutions that became visible longer ago than this (default: %(default)s)',
        )

    def handle(self, *args, dry_run=False, max_age_days=DEFAULT_MAX_AGE.days, **options):
        solutions = list(due_solutions(max_age=timedelta(days=max_age_days)))
        if dry_run:
            for solution in solutions:
                self.stdout.write(f'Would announce solution {solution.pk}: {solution}')
            self.stdout.write(f'{len(solutions)} solution(s) due')
            return

        announced = sum(announce_solution(solution) for solution in solutions)
        not_posted = len(solutions) - announced
        # Exit normally even when Discord failed: the next run retries, and a
        # failed cron run in Railway would only hide that it is working
        style = self.style.WARNING if not_posted else self.style.SUCCESS
        self.stdout.write(style(f'Announced {announced}, not posted {not_posted}'))
