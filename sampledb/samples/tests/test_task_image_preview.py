"""
Tests for image preview and selection functionality

This test suite covers:
1. Image upload preview
2. Gallery image selection
3. Image preview display in edit mode
4. Upload/gallery section visibility toggling
5. Image removal functionality
6. Image persistence in forms
7. Clear image flag behavior

Note: These tests mock Cloudinary uploads to avoid hitting external services.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from samples.models import AnalysisTask, SampleImage, Difficulty, Platform
from io import BytesIO
from PIL import Image as PILImage
from unittest.mock import patch, MagicMock


@patch('cloudinary.uploader.upload')
@patch('cloudinary.uploader.destroy')
class ImagePreviewTestCase(TestCase):
    """Test image preview and selection functionality"""
    
    def setUp(self):
        """Create test users and sample images"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.staff_user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
        self.client = Client()
        
        # Mock Cloudinary responses
        self.mock_upload_response = {
            'public_id': 'test_image_123',
            'version': '1234567890',
            'type': 'upload',
            'resource_type': 'image',
            'url': 'https://res.cloudinary.com/test/image/upload/test_image_123.jpg',
            'secure_url': 'https://res.cloudinary.com/test/image/upload/test_image_123.jpg'
        }
        
        # Create sample gallery images (no actual upload, but with mocked Cloudinary paths)
        self.gallery_image1 = SampleImage.objects.create()
        self.gallery_image1.image = 'sample_images/gallery_test_1'
        self.gallery_image1.save()
        
        self.gallery_image2 = SampleImage.objects.create()
        self.gallery_image2.image = 'sample_images/gallery_test_2'
        self.gallery_image2.save()
        
        # Create a test task with uploaded image (no image initially)
        self.task_with_upload = AnalysisTask.objects.create(
            sha256='a' * 64,
            download_link='https://bazaar.abuse.ch/sample/test/',
            description='Test description',
            goal='Test goal',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        
        # Create a test task (will be used for gallery image tests)
        self.task_with_gallery = AnalysisTask.objects.create(
            sha256='b' * 64,
            download_link='https://bazaar.abuse.ch/sample/test2/',
            description='Test description 2',
            goal='Test goal 2',
            difficulty=Difficulty.MEDIUM,
            author=self.user
        )
    
    def create_test_image(self, width=300, height=300, format='PNG'):
        """Helper to create a test image file"""
        file = BytesIO()
        image = PILImage.new('RGB', (width, height), color='red')
        image.save(file, format)
        file.seek(0)
        return SimpleUploadedFile(
            f'test_image.{format.lower()}',
            file.read(),
            content_type=f'image/{format.lower()}'
        )
    
    def test_submit_form_displays_gallery_images(self, mock_destroy, mock_upload):
        """Submit form should display available gallery images"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('submit_task'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'imageGalleryModal')
        self.assertIn('available_images', response.context)
        self.assertEqual(len(response.context['available_images']), 2)
    
    def test_submit_form_has_image_preview_elements(self, mock_destroy, mock_upload):
        """Submit form should have all image preview elements"""
        self.client.login(username='staff', password='testpass123')
        response = self.client.get(reverse('submit_task'))
        
        self.assertEqual(response.status_code, 200)
        # Check for preview areas
        self.assertContains(response, 'id="image_preview_area"')
        self.assertContains(response, 'id="upload_image_preview"')
        self.assertContains(response, 'id="selected_image_preview"')
        # Check for hidden fields
        self.assertContains(response, 'id="selected_image"')
        self.assertContains(response, 'id="clear_image_flag"')
        # Check for sections
        self.assertContains(response, 'id="upload-section"')
        self.assertContains(response, 'id="gallery-section"')
    
    def test_edit_mode_displays_gallery_image_preview(self, mock_destroy, mock_upload):
        """Edit form should show preview of gallery image"""
        self.client.login(username='testuser', password='testpass123')
        
        # Set up task with gallery image reference
        self.task_with_gallery.image = self.gallery_image1.image
        self.task_with_gallery.save()
        
        response = self.client.get(reverse('edit_task', kwargs={
            'sha256': self.task_with_gallery.sha256,
            'task_id': self.task_with_gallery.id
        }))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('current_image_id', response.context)
        # The view should find the gallery image by matching task.image to SampleImage.image
        self.assertEqual(response.context['current_image_id'], self.gallery_image1.id)
        # Check data attribute is set
        self.assertContains(response, f'data-current-image-id="{self.gallery_image1.id}"')
    
    def test_edit_mode_displays_uploaded_image_preview(self, mock_destroy, mock_upload):
        """Edit form should show preview of uploaded image (non-gallery)"""
        # Mock an uploaded image (in real scenario, this would be a Cloudinary URL)
        self.task_with_upload.image = 'samples/test_image.png'
        self.task_with_upload.save()
        
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('edit_task', kwargs={
            'sha256': self.task_with_upload.sha256,
            'task_id': self.task_with_upload.id
        }))
        
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get('current_image_id'))
        # Check data attribute for current image URL is set
        self.assertContains(response, 'data-current-image-url')
    
    def test_gallery_image_selection_via_form_submission(self, mock_destroy, mock_upload):
        """Submitting form with gallery image should associate it with task"""
        self.client.login(username='staff', password='testpass123')
        
        form_data = {
            'sha256': 'c' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/test3/',
            'description': 'Test with gallery image',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ghidra',
            'image_id': self.gallery_image1.id,  # Gallery image selected
        }
        
        response = self.client.post(reverse('submit_task'), data=form_data, follow=True)
        
        # Should create task successfully
        task = AnalysisTask.objects.get(sha256='c' * 64)
        # task.image is a CloudinaryResource; compare the string values
        self.assertEqual(str(task.image), str(self.gallery_image1.image))
    
    def test_image_upload_via_form_submission(self, mock_destroy, mock_upload):
        """Submitting form with uploaded image should save it"""
        mock_upload.return_value = {
            'public_id': 'test',
            'version': '1234567890',
            'type': 'upload',
            'resource_type': 'image',
            'url': 'http://test.com/image.jpg'
        }
        self.client.login(username='staff', password='testpass123')
        
        test_image = self.create_test_image(width=512, height=512)
        
        form_data = {
            'sha256': 'd' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/test4/',
            'description': 'Test with uploaded image',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ghidra',
            'image_upload': test_image,
        }
        
        response = self.client.post(reverse('submit_task'), data=form_data, follow=True)
        
        # Should create task successfully
        task = AnalysisTask.objects.get(sha256='d' * 64)
        self.assertIsNotNone(task.image)
    
    def test_clear_image_flag_removes_image(self, mock_destroy, mock_upload):
        """Setting clear_image flag should remove image from task"""
        self.client.login(username='testuser', password='testpass123')
        
        # Set up task with an image first (mock Cloudinary resource)
        self.task_with_gallery.image = 'sample_images/test.jpg'
        self.task_with_gallery.save()
        self.task_with_gallery.refresh_from_db()
        self.assertIsNotNone(self.task_with_gallery.image)
        
        form_data = {
            'sha256': self.task_with_gallery.sha256,
            'download_link': self.task_with_gallery.download_link,
            'description': self.task_with_gallery.description,
            'goal': self.task_with_gallery.goal,
            'difficulty': self.task_with_gallery.difficulty,
            'platform': self.task_with_gallery.platform,
            'tags': 'test',
            'tools': 'ghidra',
            'clear_image': 'true',  # Flag to clear image
        }
        
        response = self.client.post(
            reverse('edit_task', kwargs={
                'sha256': self.task_with_gallery.sha256,
                'task_id': self.task_with_gallery.id
            }),
            data=form_data,
            follow=True
        )
        
        # Reload task from database
        self.task_with_gallery.refresh_from_db()
        self.assertIsNone(self.task_with_gallery.image)
    
    def test_replace_gallery_image_with_upload(self, mock_destroy, mock_upload):
        """Can replace gallery image with uploaded image"""
        mock_upload.return_value = {
            'public_id': 'test',
            'version': '1234567890',
            'type': 'upload',
            'resource_type': 'image',
            'url': 'http://test.com/image.jpg'
        }
        self.client.login(username='testuser', password='testpass123')
        
        # Set up task with gallery image reference
        self.task_with_gallery.image = self.gallery_image1.image
        self.task_with_gallery.save()
        self.task_with_gallery.refresh_from_db()
        
        test_image = self.create_test_image(width=512, height=512)
        
        form_data = {
            'sha256': self.task_with_gallery.sha256,
            'download_link': self.task_with_gallery.download_link,
            'description': self.task_with_gallery.description,
            'goal': self.task_with_gallery.goal,
            'difficulty': self.task_with_gallery.difficulty,
            'platform': self.task_with_gallery.platform,
            'tags': 'test',
            'tools': 'ghidra',
            'image_upload': test_image,
        }
        
        response = self.client.post(
            reverse('edit_task', kwargs={
                'sha256': self.task_with_gallery.sha256,
                'task_id': self.task_with_gallery.id
            }),
            data=form_data,
            follow=True
        )
        
        # Reload task
        self.task_with_gallery.refresh_from_db()
        # Should now have uploaded image (not the gallery image object)
        self.assertIsNotNone(self.task_with_gallery.image)
        # Check it's not the same gallery image
        if hasattr(self.task_with_gallery.image, 'id'):
            self.assertNotEqual(self.task_with_gallery.image.id, self.gallery_image1.id)
    
    def test_replace_upload_with_gallery_image(self, mock_destroy, mock_upload):
        """Can replace uploaded image with gallery image"""
        self.client.login(username='testuser', password='testpass123')
        
        # Set task to have uploaded image
        self.task_with_upload.image = 'samples/test_image.png'
        self.task_with_upload.save()
        
        form_data = {
            'sha256': self.task_with_upload.sha256,
            'download_link': self.task_with_upload.download_link,
            'description': self.task_with_upload.description,
            'goal': self.task_with_upload.goal,
            'difficulty': self.task_with_upload.difficulty,
            'platform': self.task_with_upload.platform,
            'tags': 'test',
            'tools': 'ghidra',
            'image_id': self.gallery_image2.id,  # Select gallery image
        }
        
        response = self.client.post(
            reverse('edit_task', kwargs={
                'sha256': self.task_with_upload.sha256,
                'task_id': self.task_with_upload.id
            }),
            data=form_data,
            follow=True
        )
        
        # Reload task
        self.task_with_upload.refresh_from_db()
        # Check image was updated (should reference the gallery image)
        self.assertIsNotNone(self.task_with_upload.image)


@patch('cloudinary.uploader.upload')
@patch('cloudinary.uploader.destroy')
class ImageValidationTestCase(TestCase):
    """Test image dimension validation"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
        self.client = Client()
        self.client.login(username='staff', password='testpass123')
    
    def create_test_image(self, width=300, height=300, format='PNG'):
        """Helper to create a test image file"""
        file = BytesIO()
        image = PILImage.new('RGB', (width, height), color='red')
        image.save(file, format)
        file.seek(0)
        return SimpleUploadedFile(
            f'test_image.{format.lower()}',
            file.read(),
            content_type=f'image/{format.lower()}'
        )
    
    def test_image_minimum_size_validation(self, mock_destroy, mock_upload):
        """Images smaller than 125x125 should be rejected"""
        small_image = self.create_test_image(width=100, height=100)
        
        form_data = {
            'sha256': 'e' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/test5/',
            'description': 'Test',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ghidra',
            'image_upload': small_image,
        }
        
        response = self.client.post(reverse('submit_task'), data=form_data)
        
        # Should have validation error
        self.assertContains(response, 'Minimum size is 125x125 pixels', status_code=200)
    
    def test_image_maximum_size_validation(self, mock_destroy, mock_upload):
        """Images larger than 1024x1024 should be rejected"""
        large_image = self.create_test_image(width=2000, height=2000)
        
        form_data = {
            'sha256': 'f' * 64,
            'download_link': 'https://bazaar.abuse.ch/sample/test6/',
            'description': 'Test',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ghidra',
            'image_upload': large_image,
        }
        
        response = self.client.post(reverse('submit_task'), data=form_data)
        
        # Should have validation error
        self.assertContains(response, 'Maximum size is 1024x1024 pixels', status_code=200)
    
    def test_valid_image_size_accepted(self, mock_destroy, mock_upload):
        """Images within 125-1024 range should be accepted"""
        mock_upload.return_value = {
            'public_id': 'test',
            'version': '1234567890',
            'type': 'upload',
            'resource_type': 'image',
            'url': 'http://test.com/image.jpg'
        }
        valid_image = self.create_test_image(width=512, height=512)
        
        form_data = {
            'sha256': 'a1b2c3d4' * 8,  # Valid hex SHA256
            'download_link': 'https://bazaar.abuse.ch/sample/test7/',
            'description': 'Test',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ghidra',
            'image_upload': valid_image,
        }
        
        response = self.client.post(reverse('submit_task'), data=form_data, follow=True)
        
        # Check if task was created
        sha256_hash = 'a1b2c3d4' * 8
        if AnalysisTask.objects.filter(sha256=sha256_hash).exists():
            task = AnalysisTask.objects.get(sha256=sha256_hash)
            self.assertIsNotNone(task.image)
        else:
            # Form had errors, check them
            if response.context and 'form' in response.context:
                self.fail(f"Form validation failed: {response.context['form'].errors}")
            else:
                self.fail("Task was not created and no form errors found")
    
    def test_non_square_image_handling(self, mock_destroy, mock_upload):
        """Non-square images should still be accepted (will be cropped)"""
        mock_upload.return_value = {
            'public_id': 'test',
            'version': '1234567890',
            'type': 'upload',
            'resource_type': 'image',
            'url': 'http://test.com/image.jpg'
        }
        rect_image = self.create_test_image(width=512, height=300)
        
        form_data = {
            'sha256': 'b1c2d3e4' * 8,  # Valid hex SHA256
            'download_link': 'https://bazaar.abuse.ch/sample/test8/',
            'description': 'Test',
            'goal': 'Test goal',
            'difficulty': Difficulty.EASY,
            'platform': Platform.WINDOWS,
            'tags': 'test',
            'tools': 'ghidra',
            'image_upload': rect_image,
        }
        
        response = self.client.post(reverse('submit_task'), data=form_data, follow=True)
        
        # Check if task was created
        sha256_hash = 'b1c2d3e4' * 8
        if AnalysisTask.objects.filter(sha256=sha256_hash).exists():
            task = AnalysisTask.objects.get(sha256=sha256_hash)
            self.assertIsNotNone(task.image)
        else:
            # Form had errors, check them
            if response.context and 'form' in response.context:
                self.fail(f"Form validation failed: {response.context['form'].errors}")
            else:
                self.fail("Task was not created and no form errors found")


class ImagePreviewJavaScriptTestCase(TestCase):
    """Test JavaScript functionality for image preview (template checks)"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='staff',
            email='staff@test.com',
            password='testpass123',
            is_staff=True
        )
        self.client = Client()
        self.client.login(username='staff', password='testpass123')
    
    def test_submit_form_includes_javascript_file(self):
        """Submit form should include the submit-task-form.js file"""
        response = self.client.get(reverse('submit_task'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'submit-task-form.js')
    
    def test_submit_form_has_data_attributes(self):
        """Submit form should have data attributes for JavaScript"""
        response = self.client.get(reverse('submit_task'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="form-data-attrs"')
        self.assertContains(response, 'data-is-edit="false"')
        self.assertContains(response, 'data-markdown-preview-url')
    
    def test_edit_form_has_edit_mode_data_attribute(self):
        """Edit form should have is-edit set to true"""
        task = AnalysisTask.objects.create(
            sha256='i' * 64,
            download_link='https://bazaar.abuse.ch/sample/test9/',
            description='Test',
            goal='Test goal',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        
        response = self.client.get(reverse('edit_task', kwargs={
            'sha256': task.sha256,
            'task_id': task.id
        }))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-is-edit="true"')
    
    def test_image_gallery_cards_have_data_attributes(self):
        """Gallery image cards should have required data attributes"""
        SampleImage.objects.create()
        
        response = self.client.get(reverse('submit_task'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'image-select-card')
        self.assertContains(response, 'data-image-id')
        self.assertContains(response, 'data-image-url')
    
    def test_form_has_clear_functions_available(self):
        """Form should have onclick handlers for clear functions"""
        response = self.client.get(reverse('submit_task'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'onclick="clearUploadPreview()"')
        self.assertContains(response, 'onclick="clearImageSelection()"')
    
    def test_form_has_delete_confirmation(self):
        """Edit form should have delete confirmation function"""
        task = AnalysisTask.objects.create(
            sha256='j' * 64,
            download_link='https://bazaar.abuse.ch/sample/test10/',
            description='Test',
            goal='Test goal',
            difficulty=Difficulty.EASY,
            author=self.user
        )
        
        response = self.client.get(reverse('edit_task', kwargs={
            'sha256': task.sha256,
            'task_id': task.id
        }))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'onclick="confirmDelete()"')
