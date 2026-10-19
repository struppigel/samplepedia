"""
Tests for @ mention functionality in comments

This test suite covers:
1. Notification creation when users are @mentioned in comments
2. Mentioned users receive notifications with correct verb
3. Non-mentioned users don't receive mention-specific notifications
4. Invalid/non-existent usernames don't cause errors
5. Users don't receive notifications when mentioning themselves
6. Multiple mentions in a single comment
7. Duplicate mentions are handled correctly
8. Notification content and metadata
"""

from unittest.mock import Mock

from django.contrib.contenttypes.models import ContentType
from django_comments.models import Comment

from samples.models import AnalysisTask, Notification
from samples.signals import notify_on_comment
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_task, make_user

MENTION_VERB = 'mentioned you in a comment'


class CommentMentionNotificationTestCase(SampleTestCase):
    """Test @ mention notifications in comments"""

    @classmethod
    def setUpTestData(cls):
        # The comments below @mention these usernames
        cls.user1 = make_user('commenter')
        cls.user2 = make_user('mentioned')
        cls.user3 = make_user('also_mentioned')
        cls.task_author = make_user()

        cls.task = make_task(author=cls.task_author, sha256='a' * 64)
        cls.content_type = ContentType.objects.get_for_model(AnalysisTask)

    def post_comment(self, user, text):
        """Comment on the task and run the comment_was_posted handler by hand, as the view would"""
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=user,
            user_name=user.username,
            user_email=user.email,
            comment=text,
            site_id=1
        )
        notify_on_comment(sender=Comment, comment=comment, request=Mock())
        return comment

    def test_mentioned_user_receives_notification(self):
        """Test that @mentioned user receives a notification with correct verb"""
        self.post_comment(self.user1, 'Hey @mentioned, check this out!')

        notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(notifications.count(), 1)

        notification = notifications.first()
        self.assertEqual(notification.verb, MENTION_VERB)
        self.assertEqual(notification.actor, self.user1)
        self.assertEqual(notification.target, self.task)
        self.assertIn('mentioned you', notification.description)

    def test_multiple_mentions_in_comment(self):
        """Test that multiple @mentions create notifications for all users"""
        self.post_comment(self.user1, 'Hey @mentioned and @also_mentioned, look at this!')

        user2_notifications = Notification.objects.filter(recipient=self.user2, verb=MENTION_VERB)
        user3_notifications = Notification.objects.filter(recipient=self.user3, verb=MENTION_VERB)
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(user3_notifications.count(), 1)

    def test_self_mention_no_notification(self):
        """Test that users don't receive notifications when mentioning themselves"""
        self.post_comment(self.user1, 'I think @commenter should handle this')

        self_notifications = Notification.objects.filter(recipient=self.user1, verb=MENTION_VERB)
        self.assertEqual(self_notifications.count(), 0)

    def test_invalid_username_no_error(self):
        """Test that @mentioning non-existent users doesn't cause errors"""
        try:
            self.post_comment(self.user1, 'Hey @nonexistentuser123, check this!')
        except Exception as e:
            self.fail(f"Invalid username mention caused exception: {e}")

        self.assertEqual(Notification.objects.filter(verb=MENTION_VERB).count(), 0)

    def test_task_author_receives_both_notifications(self):
        """Test that task author receives regular comment notification, not mention if not mentioned"""
        self.post_comment(self.user1, 'This is interesting, @mentioned!')

        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 1)
        self.assertEqual(author_notifications.first().verb, 'commented')

        mentioned_notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(mentioned_notifications.count(), 1)
        self.assertEqual(mentioned_notifications.first().verb, MENTION_VERB)

    def test_mention_with_special_characters(self):
        """Test that only valid usernames are extracted (alphanumeric and underscore)"""
        self.post_comment(self.user1, 'Email me at test@example.com or contact @mentioned')

        # Only @mentioned creates a notification; @example matches the pattern but is no user
        mention_notifications = Notification.objects.filter(verb=MENTION_VERB)
        self.assertEqual(mention_notifications.count(), 1)
        self.assertEqual(mention_notifications.first().recipient, self.user2)

    def test_duplicate_mentions_single_notification(self):
        """Test that mentioning same user multiple times creates only one notification"""
        self.post_comment(self.user1, 'Hey @mentioned, I need @mentioned to review this. Thanks @mentioned!')

        notifications = Notification.objects.filter(recipient=self.user2, verb=MENTION_VERB)
        self.assertEqual(notifications.count(), 1)

    def test_notification_metadata(self):
        """Test that notification contains correct metadata"""
        self.post_comment(self.user1, 'Hey @mentioned!')

        notification = Notification.objects.get(recipient=self.user2, verb=MENTION_VERB)
        self.assertEqual(notification.actor, self.user1)
        self.assertEqual(notification.target, self.task)
        self.assertTrue('sha256' in notification.data)
        self.assertEqual(notification.data['sha256'], self.task.sha256[:12])
        self.assertTrue(notification.unread)

    def test_task_author_notified_on_comment(self):
        """Test that task author receives notification when someone comments"""
        self.post_comment(self.user1, 'Great analysis task!')

        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 1)

        notification = author_notifications.first()
        self.assertEqual(notification.verb, 'commented')
        self.assertEqual(notification.actor, self.user1)
        self.assertEqual(notification.target, self.task)
        self.assertIn('commented', notification.description)

    def test_task_author_not_notified_for_own_comment(self):
        """Test that task author doesn't receive notification when commenting on their own task"""
        self.post_comment(self.task_author, 'Adding my own comment')

        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 0)

    def test_previous_commenters_notified(self):
        """Test that previous commenters receive notifications on new comments"""
        self.post_comment(self.user2, 'First comment')
        Notification.objects.all().delete()

        self.post_comment(self.user3, 'Second comment')

        # User2 (previous commenter) should be notified
        user2_notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(user2_notifications.first().verb, 'commented')

        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 1)

        # User3 (the commenter) should not be notified
        user3_notifications = Notification.objects.filter(recipient=self.user3)
        self.assertEqual(user3_notifications.count(), 0)

    def test_multiple_previous_commenters_all_notified(self):
        """Test that all previous commenters receive notifications"""
        self.post_comment(self.user1, 'First')
        self.post_comment(self.user2, 'Second')
        Notification.objects.all().delete()

        # Should notify user1, user2 and the task author
        self.post_comment(self.user3, 'Third')

        user1_notifications = Notification.objects.filter(recipient=self.user1)
        user2_notifications = Notification.objects.filter(recipient=self.user2)
        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(user1_notifications.count(), 1)
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(author_notifications.count(), 1)

        # User3 (the commenter) should not be notified
        user3_notifications = Notification.objects.filter(recipient=self.user3)
        self.assertEqual(user3_notifications.count(), 0)

    def test_no_duplicate_notifications(self):
        """Test that users don't receive duplicate notifications if they're both mentioned and previous commenter"""
        self.post_comment(self.user2, 'First comment')
        Notification.objects.all().delete()

        # User1 mentions user2, who already commented
        self.post_comment(self.user1, 'Hey @mentioned, what do you think?')

        # Only one notification, and the mention verb takes precedence
        user2_notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(user2_notifications.first().verb, MENTION_VERB)

    def test_email_address_is_not_a_mention(self):
        """'name@mentioned' in an e-mail address must not notify the user 'mentioned'"""
        self.post_comment(self.user1, 'Write to someone@mentioned for details')

        self.assertFalse(Notification.objects.filter(recipient=self.user2, verb=MENTION_VERB).exists())

    def test_query_count_does_not_grow_with_participants(self):
        """Saving the comment, finding the recipients and one bulk insert: 6 queries however many"""
        for _ in range(2):
            self.post_comment(make_user(), 'Earlier comment')
        with self.assertNumQueries(6):
            self.post_comment(self.user1, 'Hi @mentioned and @also_mentioned')
        for _ in range(5):
            self.post_comment(make_user(), 'Earlier comment')
        with self.assertNumQueries(6):
            self.post_comment(self.user1, 'Hi again @mentioned')
