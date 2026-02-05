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

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django_comments.models import Comment
from samples.models import AnalysisTask, Notification, Difficulty


class CommentMentionNotificationTestCase(TestCase):
    """Test @ mention notifications in comments"""
    
    def setUp(self):
        """Create test users and analysis task"""
        self.user1 = User.objects.create_user(
            username='commenter',
            password='testpass123',
            email='commenter@test.com'
        )
        self.user2 = User.objects.create_user(
            username='mentioned',
            password='testpass123',
            email='mentioned@test.com'
        )
        self.user3 = User.objects.create_user(
            username='also_mentioned',
            password='testpass123',
            email='also@test.com'
        )
        self.task_author = User.objects.create_user(
            username='taskauthor',
            password='testpass123',
            email='author@test.com'
        )
        
        self.task = AnalysisTask.objects.create(
            sha256='a' * 64,
            goal='Test malware analysis for comments',
            difficulty=Difficulty.EASY,
            author=self.task_author
        )
        
        self.client = Client()
        self.content_type = ContentType.objects.get_for_model(AnalysisTask)
    
    def test_mentioned_user_receives_notification(self):
        """Test that @mentioned user receives a notification with correct verb"""
        # Clear any existing notifications
        Notification.objects.all().delete()
        
        # Create a comment with a mention
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='Hey @mentioned, check this out!',
            site_id=1
        )
        
        # Manually trigger the signal (in real app, signal fires automatically)
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # Check that mentioned user received notification
        notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(notifications.count(), 1)
        
        notification = notifications.first()
        self.assertEqual(notification.verb, 'mentioned you in a comment')
        self.assertEqual(notification.actor, self.user1)
        self.assertEqual(notification.target, self.task)
        self.assertIn('mentioned you', notification.description)
    
    def test_multiple_mentions_in_comment(self):
        """Test that multiple @mentions create notifications for all users"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='Hey @mentioned and @also_mentioned, look at this!',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # Both mentioned users should have notifications
        user2_notifications = Notification.objects.filter(
            recipient=self.user2,
            verb='mentioned you in a comment'
        )
        user3_notifications = Notification.objects.filter(
            recipient=self.user3,
            verb='mentioned you in a comment'
        )
        
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(user3_notifications.count(), 1)
    
    def test_self_mention_no_notification(self):
        """Test that users don't receive notifications when mentioning themselves"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='I think @commenter should handle this',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # User should not receive notification for mentioning themselves
        self_notifications = Notification.objects.filter(
            recipient=self.user1,
            verb='mentioned you in a comment'
        )
        self.assertEqual(self_notifications.count(), 0)
    
    def test_invalid_username_no_error(self):
        """Test that @mentioning non-existent users doesn't cause errors"""
        Notification.objects.all().delete()
        
        # Should not raise any exceptions
        try:
            comment = Comment.objects.create(
                content_type=self.content_type,
                object_pk=self.task.id,
                user=self.user1,
                user_name=self.user1.username,
                user_email=self.user1.email,
                comment='Hey @nonexistentuser123, check this!',
                site_id=1
            )
            
            from samples.signals import notify_on_comment
            from unittest.mock import Mock
            request = Mock()
            notify_on_comment(sender=Comment, comment=comment, request=request)
            
        except Exception as e:
            self.fail(f"Invalid username mention caused exception: {e}")
        
        # No notifications should be created for non-existent user
        all_notifications = Notification.objects.filter(
            verb='mentioned you in a comment'
        )
        self.assertEqual(all_notifications.count(), 0)
    
    def test_task_author_receives_both_notifications(self):
        """Test that task author receives regular comment notification, not mention if not mentioned"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='This is interesting, @mentioned!',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # Task author should receive regular comment notification (not mention)
        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 1)
        self.assertEqual(author_notifications.first().verb, 'commented')
        
        # Mentioned user should receive mention notification
        mentioned_notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(mentioned_notifications.count(), 1)
        self.assertEqual(mentioned_notifications.first().verb, 'mentioned you in a comment')
    
    def test_mention_with_special_characters(self):
        """Test that only valid usernames are extracted (alphanumeric and underscore)"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='Email me at test@example.com or contact @mentioned',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # Only the valid @mentioned should create notification
        # @example should not (even though it matches pattern)
        mention_notifications = Notification.objects.filter(
            verb='mentioned you in a comment'
        )
        self.assertEqual(mention_notifications.count(), 1)
        self.assertEqual(mention_notifications.first().recipient, self.user2)
    
    def test_duplicate_mentions_single_notification(self):
        """Test that mentioning same user multiple times creates only one notification"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='Hey @mentioned, I need @mentioned to review this. Thanks @mentioned!',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # Should only create one notification despite multiple mentions
        notifications = Notification.objects.filter(
            recipient=self.user2,
            verb='mentioned you in a comment'
        )
        self.assertEqual(notifications.count(), 1)
    
    def test_notification_metadata(self):
        """Test that notification contains correct metadata"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='Hey @mentioned!',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        notification = Notification.objects.get(
            recipient=self.user2,
            verb='mentioned you in a comment'
        )
        
        # Check metadata
        self.assertEqual(notification.actor, self.user1)
        self.assertEqual(notification.target, self.task)
        self.assertTrue('sha256' in notification.data)
        self.assertEqual(notification.data['sha256'], self.task.sha256[:12])
        self.assertTrue(notification.unread)
    
    def test_task_author_notified_on_comment(self):
        """Test that task author receives notification when someone comments"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='Great analysis task!',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # Task author should receive notification
        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 1)
        
        notification = author_notifications.first()
        self.assertEqual(notification.verb, 'commented')
        self.assertEqual(notification.actor, self.user1)
        self.assertEqual(notification.target, self.task)
        self.assertIn('commented', notification.description)
    
    def test_task_author_not_notified_for_own_comment(self):
        """Test that task author doesn't receive notification when commenting on their own task"""
        Notification.objects.all().delete()
        
        comment = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.task_author,
            user_name=self.task_author.username,
            user_email=self.task_author.email,
            comment='Adding my own comment',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment, request=request)
        
        # Task author should not receive notification for their own comment
        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 0)
    
    def test_previous_commenters_notified(self):
        """Test that previous commenters receive notifications on new comments"""
        Notification.objects.all().delete()
        
        # User2 comments first
        comment1 = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user2,
            user_name=self.user2.username,
            user_email=self.user2.email,
            comment='First comment',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment1, request=request)
        
        # Clear notifications from first comment
        Notification.objects.all().delete()
        
        # User3 comments second
        comment2 = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user3,
            user_name=self.user3.username,
            user_email=self.user3.email,
            comment='Second comment',
            site_id=1
        )
        
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment2, request=request)
        
        # User2 (previous commenter) should be notified
        user2_notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(user2_notifications.first().verb, 'commented')
        
        # Task author should also be notified
        author_notifications = Notification.objects.filter(recipient=self.task_author)
        self.assertEqual(author_notifications.count(), 1)
        
        # User3 (the commenter) should not be notified
        user3_notifications = Notification.objects.filter(recipient=self.user3)
        self.assertEqual(user3_notifications.count(), 0)
    
    def test_multiple_previous_commenters_all_notified(self):
        """Test that all previous commenters receive notifications"""
        Notification.objects.all().delete()
        
        # User1 comments
        comment1 = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='First',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment1, request=request)
        
        # User2 comments
        comment2 = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user2,
            user_name=self.user2.username,
            user_email=self.user2.email,
            comment='Second',
            site_id=1
        )
        
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment2, request=request)
        
        # Clear notifications
        Notification.objects.all().delete()
        
        # User3 comments (should notify user1, user2, and task_author)
        comment3 = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user3,
            user_name=self.user3.username,
            user_email=self.user3.email,
            comment='Third',
            site_id=1
        )
        
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment3, request=request)
        
        # All previous commenters should be notified
        user1_notifications = Notification.objects.filter(recipient=self.user1)
        user2_notifications = Notification.objects.filter(recipient=self.user2)
        author_notifications = Notification.objects.filter(recipient=self.task_author)
        
        self.assertEqual(user1_notifications.count(), 1)
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(author_notifications.count(), 1)
        
        # User3 should not be notified
        user3_notifications = Notification.objects.filter(recipient=self.user3)
        self.assertEqual(user3_notifications.count(), 0)
    
    def test_no_duplicate_notifications(self):
        """Test that users don't receive duplicate notifications if they're both mentioned and previous commenter"""
        Notification.objects.all().delete()
        
        # User2 comments first
        comment1 = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user2,
            user_name=self.user2.username,
            user_email=self.user2.email,
            comment='First comment',
            site_id=1
        )
        
        from samples.signals import notify_on_comment
        from unittest.mock import Mock
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment1, request=request)
        
        # Clear notifications
        Notification.objects.all().delete()
        
        # User1 comments and mentions user2 (who already commented)
        comment2 = Comment.objects.create(
            content_type=self.content_type,
            object_pk=self.task.id,
            user=self.user1,
            user_name=self.user1.username,
            user_email=self.user1.email,
            comment='Hey @mentioned, what do you think?',
            site_id=1
        )
        
        request = Mock()
        notify_on_comment(sender=Comment, comment=comment2, request=request)
        
        # User2 should receive only ONE notification (as mentioned user, with mention verb taking precedence)
        user2_notifications = Notification.objects.filter(recipient=self.user2)
        self.assertEqual(user2_notifications.count(), 1)
        self.assertEqual(user2_notifications.first().verb, 'mentioned you in a comment')
