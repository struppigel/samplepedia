"""
Tests for the shared list-page partials: pagination (_pagination.html) keeps the
active filters and renders numbered links where the view asks for them, the filter
bar (_filter_bar.html) shows the right controls per list, empty tables span every
column, the task detail page renders with and without its sidebar, and the
solutions showcase produces well-formed links.
"""
import re
from html.parser import HTMLParser
from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.urls import reverse

from samples.models import Difficulty
from samples.tests.base import SampleTestCase
from samples.tests.factories import (
    make_article, make_onsite_solution, make_solution, make_task, make_user,
)


class PageParser(HTMLParser):
    """Collects pagination links, table cells and <a> nesting from a rendered page."""

    def __init__(self):
        super().__init__()
        self.page_links = []      # query dicts of a.page-link hrefs
        self.active_pages = []    # text of the current page item
        self.ellipses = 0
        self.header_cells = 0
        self.colspans = []
        self.open_links = 0
        self.max_link_depth = 0
        self.unmatched_link_ends = 0
        self._in_thead = False
        self._capture = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get('class') or '').split()
        if tag == 'a':
            self.open_links += 1
            self.max_link_depth = max(self.max_link_depth, self.open_links)
            if 'page-link' in classes:
                self.page_links.append(parse_qs(urlparse(attrs['href']).query))
        elif tag == 'li' and 'page-item' in classes:
            if 'active' in classes:
                self._capture = 'active'
            elif 'disabled' in classes:
                self._capture = 'disabled'
        elif tag == 'thead':
            self._in_thead = True
        elif tag == 'th' and self._in_thead:
            self.header_cells += 1
        elif tag == 'td' and 'colspan' in attrs:
            self.colspans.append(int(attrs['colspan']))

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.open_links:
                self.open_links -= 1
            else:
                self.unmatched_link_ends += 1
        elif tag == 'thead':
            self._in_thead = False
        elif tag == 'li':
            self._capture = None

    def handle_data(self, data):
        text = data.strip()
        if not text or self._capture is None:
            return
        if self._capture == 'active':
            self.active_pages.append(text)
        elif text == '…':
            self.ellipses += 1


def parse(response):
    parser = PageParser()
    parser.feed(response.content.decode())
    return parser


def single(values):
    """parse_qs values as plain strings"""
    return {key: value[0] for key, value in values.items()}


class PaginationKeepsFiltersTestCase(SampleTestCase):
    """Every paginated list links to the next page without dropping its query parameters"""

    @classmethod
    def setUpTestData(cls):
        cls.viewer = make_user()
        cls.author = make_user('prolific')
        for _ in range(3):
            task = make_task(author=cls.author, difficulty=Difficulty.EASY)
            make_solution(task=task)
            make_article(author=cls.viewer)
        make_task(author=cls.author, difficulty=Difficulty.EXPERT)

    def setUp(self):
        self.login_as(self.viewer)

    def next_links(self, url, params):
        return [single(link) for link in parse(self.client.get(url, params)).page_links]

    @mock.patch('samples.views.samples.TASKS_PER_PAGE', 2)
    def test_task_list(self):
        links = self.next_links(reverse('sample_list'), {'browse': '1', 'difficulty': 'easy'})
        self.assertIn({'browse': '1', 'difficulty': 'easy', 'page': '2'}, links)

    @mock.patch('samples.views.solutions.SOLUTIONS_PER_PAGE', 2)
    def test_solution_list(self):
        links = self.next_links(reverse('solution_list'), {'difficulty': 'easy', 'sort': 'title'})
        self.assertIn({'difficulty': 'easy', 'sort': 'title', 'page': '2'}, links)

    @mock.patch('samples.views.auth.PROFILE_ROWS_PER_PAGE', 2)
    def test_profile_tables_keep_each_others_page(self):
        links = self.next_links(reverse('user_profile', args=['prolific']), {'tasks_page': '2'})
        self.assertIn({'tasks_page': '2', 'solutions_page': '2'}, links)
        self.assertIn({'tasks_page': '1'}, links)

    @mock.patch('samples.views.articles.ARTICLES_PER_PAGE', 2)
    def test_article_list(self):
        links = self.next_links(reverse('article_list'), {'sort': 'title'})
        self.assertEqual(links, [{'sort': 'title', 'page': '2'}])

    def test_single_page_has_no_pagination(self):
        response = self.client.get(reverse('sample_list'), {'browse': '1'})
        self.assertNotContains(response, 'page-link')


class NumberedPaginationTestCase(SampleTestCase):
    """Ranking and showcase show numbered page links, eliding the far ones"""

    PAGES = 12

    @classmethod
    def setUpTestData(cls):
        liker = make_user()
        for _ in range(cls.PAGES):
            # one liked task gives its author a positive score, and a public solution
            task = make_task(author=make_user())
            task.favorited_by.add(liker)
            make_solution(task=task)

    def assertNumbered(self, response, param_extra):
        parser = parse(response)
        numbers = [single(link)['page'] for link in parser.page_links]
        # previous, 1, …, 4 5 [6] 7 8, …, 12, next
        self.assertEqual(numbers, ['5', '1', '4', '5', '7', '8', '12', '7'])
        self.assertEqual(parser.active_pages, ['6'])
        self.assertEqual(parser.ellipses, 2)
        for link in parser.page_links:
            self.assertEqual({key: value for key, value in single(link).items() if key != 'page'}, param_extra)

    @mock.patch('samples.views.auth.RANKING_PER_PAGE', 1)
    def test_ranking(self):
        response = self.client.get(reverse('ranking'), {'page': '6', 'x': 'y'})
        self.assertNumbered(response, {'x': 'y'})

    @mock.patch('samples.views.solutions.SHOWCASE_PER_PAGE', 1)
    def test_showcase(self):
        response = self.client.get(reverse('solutions_showcase'), {'page': '6'})
        self.assertNumbered(response, {})


class FilterBarTestCase(SampleTestCase):
    """The task and solution lists share one filter bar with list-specific controls"""

    @classmethod
    def setUpTestData(cls):
        cls.viewer = make_user()

    def setUp(self):
        self.login_as(self.viewer)

    def test_task_list_has_favorites_and_submit(self):
        response = self.client.get(reverse('sample_list'), {'browse': '1'})
        for name in ('q', 'difficulty', 'platform', 'tag', 'favorites'):
            self.assertContains(response, f'name="{name}"')
        self.assertNotContains(response, 'name="solution_type"')
        self.assertContains(response, 'id="submitTaskBtn"')
        self.assertContains(response, 'placeholder="Search SHA256"')

    def test_solution_list_has_solution_type(self):
        response = self.client.get(reverse('solution_list'))
        for name in ('q', 'solution_type', 'difficulty', 'platform', 'tag'):
            self.assertContains(response, f'name="{name}"')
        self.assertNotContains(response, 'name="favorites"')
        self.assertNotContains(response, 'id="submitTaskBtn"')

    def test_clear_button_only_when_filtered(self):
        url = reverse('solution_list')
        self.assertNotContains(self.client.get(url), '>Clear</a>')
        self.assertContains(self.client.get(url, {'solution_type': 'blog'}), f'href="{url}" class="btn btn-sm btn-secondary me-2">Clear</a>')
        self.assertContains(
            self.client.get(reverse('sample_list'), {'browse': '1', 'favorites': 'true'}),
            'href="/?browse=true" class="btn btn-sm btn-secondary me-2">Clear</a>',
        )


class EmptyTableTestCase(SampleTestCase):
    """The "nothing found" row spans every column of its table"""

    def assertSpansAllColumns(self, url, params):
        self.login_as(make_user())
        parser = parse(self.client.get(url, params))
        self.assertEqual(parser.colspans, [parser.header_cells])

    def test_task_list(self):
        self.assertSpansAllColumns(reverse('sample_list'), {'browse': '1', 'q': 'nothing-matches'})

    def test_solution_list(self):
        self.assertSpansAllColumns(reverse('solution_list'), {'q': 'nothing-matches'})


class DetailSidebarTestCase(SampleTestCase):
    """The task page widens for the image/video sidebar only when there is one"""

    def get(self, task):
        return self.client.get(task.get_absolute_url())

    def test_without_sidebar(self):
        response = self.get(make_task())
        self.assertFalse(response.context['has_sidebar'])
        self.assertContains(response, 'max-width: 1200px;')
        self.assertNotContains(response, 'max-width: 1600px;')
        self.assertNotContains(response, 'youtube.com/embed/')
        self.assertContains(response, '<h1 class="page-title">Sample</h1>')

    def test_with_task_video(self):
        response = self.get(make_task(youtube_id='abcdefghijk'))
        self.assertTrue(response.context['has_sidebar'])
        self.assertContains(response, 'max-width: 1600px;')
        self.assertContains(response, 'col-md-4')
        self.assertContains(response, 'youtube.com/embed/abcdefghijk', count=1)
        self.assertNotContains(response, 'Solution by')

    def test_with_solution_video(self):
        solution = make_solution(url='https://www.youtube.com/watch?v=ZYXWVUTSRQP', title='Video walkthrough')
        response = self.get(solution.analysis_task)
        self.assertTrue(response.context['has_sidebar'])
        self.assertContains(response, 'youtube.com/embed/ZYXWVUTSRQP', count=1)
        self.assertContains(response, 'Video walkthrough')
        self.assertContains(response, 'Solution by')


class ShowcaseMarkupTestCase(SampleTestCase):
    """Cards of onsite and external solutions open and close every link they start"""

    def test_links_are_balanced(self):
        make_onsite_solution()
        make_solution(url='https://example.com/writeup')
        response = self.client.get(reverse('solutions_showcase'))
        parser = parse(response)
        self.assertEqual(parser.open_links, 0)
        self.assertEqual(parser.unmatched_link_ends, 0)
        self.assertEqual(parser.max_link_depth, 1)
        content = response.content.decode()
        self.assertEqual(len(re.findall(r'<a[\s>]', content)), content.count('</a>'))


class PageTitleTestCase(SampleTestCase):
    """List pages name themselves "<Page> - Samplepedia" """

    def test_titles(self):
        self.login_as(make_user())
        pages = {
            reverse('sample_list') + '?browse=1': 'Training Samples',
            reverse('solution_list'): 'Solutions Overview',
            reverse('solutions_showcase'): 'Latest Solutions',
            reverse('ranking'): 'User Ranking',
            reverse('article_list'): 'My Articles',
            reverse('notification_list'): 'Notifications',
        }
        for url, title in pages.items():
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), f'<title>{title} - Samplepedia</title>')
