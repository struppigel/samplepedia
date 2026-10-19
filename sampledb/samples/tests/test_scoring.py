"""
Tests for samples/scoring.py. The original per-object scoring loop serves as
the reference implementation that the single-query annotations must match.
"""
from django.contrib.auth.models import User
from django.urls import reverse

from samples.models import DIFFICULTY_POINTS, AnalysisTask, Difficulty, Solution
from samples.scoring import annotate_scores, rank_of, ranked_users, scored_user
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_onsite_solution, make_solution, make_task, make_user


def reference_score(user):
    """Score as it used to be computed: loop over the user's tasks and solutions."""
    total = 0
    for task in AnalysisTask.objects.filter(author=user):
        total += task.favorited_by.count() * DIFFICULTY_POINTS[task.difficulty]
    for solution in Solution.objects.filter(author=user).select_related('analysis_task'):
        total += solution.liked_by.count() * DIFFICULTY_POINTS[solution.analysis_task.difficulty]
    return total


class ScoringTestCase(SampleTestCase):
    @classmethod
    def setUpTestData(cls):
        fans = [make_user() for _ in range(4)]
        # Task author: likes on tasks of every difficulty
        cls.author = make_user('author')
        for count, difficulty in enumerate(Difficulty.values, start=1):
            task = make_task(author=cls.author, difficulty=difficulty)
            task.favorited_by.add(*fans[:count])
        # Solver: liked solutions on someone else's tasks, plus one unliked
        cls.solver = make_user('solver')
        expert_task = make_task(difficulty=Difficulty.EXPERT)
        make_solution(task=expert_task, author=cls.solver).liked_by.add(*fans[:3])
        make_onsite_solution(task=make_task(difficulty=Difficulty.EASY), author=cls.solver).liked_by.add(fans[0])
        make_solution(task=expert_task, author=cls.solver)
        # Both kinds of likes on the same user
        cls.mixed = make_user('mixed')
        make_task(author=cls.mixed, difficulty=Difficulty.MEDIUM).favorited_by.add(fans[0])
        make_solution(task=make_task(difficulty=Difficulty.ADVANCED), author=cls.mixed).liked_by.add(fans[1])
        # No likes at all
        cls.nobody = make_user('nobody')
        make_task(author=cls.nobody)

    def test_points_cover_every_difficulty(self):
        self.assertEqual(set(DIFFICULTY_POINTS), set(Difficulty.values))

    def test_scores_match_reference_for_every_user(self):
        for user in annotate_scores(User.objects.all()):
            with self.subTest(user=user.username):
                self.assertEqual(user.score, reference_score(user))

    def test_like_breakdown(self):
        author = scored_user(self.author)
        self.assertEqual(
            [author.task_likes_easy, author.task_likes_medium, author.task_likes_advanced, author.task_likes_expert],
            [1, 2, 3, 4],
        )
        self.assertEqual(author.solution_likes_easy, 0)

        solver = scored_user(self.solver)
        self.assertEqual(solver.solution_likes_expert, 3)
        self.assertEqual(solver.solution_likes_easy, 1)
        self.assertEqual(solver.task_likes_easy, 0)

    def test_counts(self):
        solver = scored_user(self.solver)
        self.assertEqual(solver.solution_count, 3)
        self.assertEqual(solver.task_count, 0)

    def test_ranking_order_and_ranks(self):
        ranked = list(ranked_users())
        self.assertEqual([u.score for u in ranked], sorted((u.score for u in ranked), reverse=True))
        self.assertNotIn(self.nobody.pk, [u.pk for u in ranked])
        for position, user in enumerate(ranked, start=1):
            self.assertEqual(rank_of(user), position)

    def test_no_score_no_rank(self):
        self.assertIsNone(rank_of(scored_user(self.nobody)))

    def test_ties_go_to_the_earlier_account(self):
        first, second = make_user(), make_user()
        for user in (first, second):
            make_task(author=user, difficulty=Difficulty.EASY).favorited_by.add(self.nobody)
        self.assertLess(rank_of(scored_user(first)), rank_of(scored_user(second)))

    def test_ranking_page(self):
        response = self.client.get(reverse('ranking'))
        self.assertEqual(response.status_code, 200)
        first = response.context['page_obj'][0]
        self.assertEqual(first.rank, 1)
        self.assertContains(response, reverse('user_profile', args=[first.username]))

    def test_profile_shows_score_and_rank(self):
        self.login_as(self.solver)
        response = self.client.get(reverse('user_profile', args=['solver']))
        self.assertEqual(response.context['user_score'], reference_score(self.solver))
        self.assertEqual(response.context['user_rank'], rank_of(scored_user(self.solver)))
        self.assertEqual(response.context['solution_likes_expert'], 3)
