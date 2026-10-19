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

from io import BytesIO
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image as PILImage

from samples.models import AnalysisTask, Difficulty, Platform, SampleImage
from samples.tests.base import SampleTestCase
from samples.tests.factories import make_staff, make_task, make_user

# What the mocked cloudinary.uploader.upload returns for an accepted image
UPLOAD_RESULT = {
    'public_id': 'test',
    'version': '1234567890',
    'type': 'upload',
    'resource_type': 'image',
    'url': 'http://test.com/image.jpg',
}


def create_test_image(width=300, height=300, format='PNG'):
    """An in-memory image file for the upload field"""
    file = BytesIO()
    PILImage.new('RGB', (width, height), color='red').save(file, format)
    return SimpleUploadedFile(
        f'test_image.{format.lower()}',
        file.getvalue(),
        content_type=f'image/{format.lower()}'
    )


def submit_data(**fields):
    """POST data for a new task: the fields every submission here shares, plus the given ones"""
    return {
        'goal': 'Test goal',
        'difficulty': Difficulty.EASY,
        'platform': Platform.WINDOWS,
        'tags': 'test',
        'tools': 'ghidra',
        **fields,
    }


def edit_data(task, **fields):
    """POST data that re-submits the task's current values, plus the given fields"""
    return {
        'sha256': task.sha256,
        'download_link': task.download_link,
        'description': task.description,
        'goal': task.goal,
        'difficulty': task.difficulty,
        'platform': task.platform,
        'tags': 'test',
        'tools': 'ghidra',
        **fields,
    }


def edit_url(task):
    return reverse('edit_task', kwargs={'sha256': task.sha256, 'task_id': task.id})


@patch('cloudinary.uploader.upload')
@patch('cloudinary.uploader.destroy')
class ImagePreviewTestCase(SampleTestCase):
    """Test image preview and selection functionality"""

    @classmethod
    def setUpTestData(cls):
        cls.user = make_user()
        cls.staff_user = make_staff()

        # Gallery images with Cloudinary paths; assigning a path doesn't upload anything
        cls.gallery_image1 = SampleImage.objects.create(image='sample_images/gallery_test_1')
        cls.gallery_image2 = SampleImage.objects.create(image='sample_images/gallery_test_2')

        # The edit tests post these values back, so they must pass form validation
        cls.task_with_upload = make_task(
            author=cls.user,
            sha256='a' * 64,
            download_link='https://bazaar.abuse.ch/sample/test/',
            description='Test description',
            goal='Test goal',
            difficulty=Difficulty.EASY,
        )
        cls.task_with_gallery = make_task(
            author=cls.user,
            sha256='b' * 64,
            download_link='https://bazaar.abuse.ch/sample/test2/',
            description='Test description 2',
            goal='Test goal 2',
            difficulty=Difficulty.MEDIUM,
        )

    def test_submit_form_displays_gallery_images(self, mock_destroy, mock_upload):
        """Submit form should display available gallery images"""
        self.login_as(self.staff_user)
        response = self.client.get(reverse('submit_task'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'imageGalleryModal')
        self.assertIn('available_images', response.context)
        self.assertEqual(len(response.context['available_images']), 2)

    def test_submit_form_has_image_preview_elements(self, mock_destroy, mock_upload):
        """Submit form should have all image preview elements"""
        self.login_as(self.staff_user)
        response = self.client.get(reverse('submit_task'))

        self.assertEqual(response.status_code, 200)
        # Preview areas
        self.assertContains(response, 'id="image_preview_area"')
        self.assertContains(response, 'id="upload_image_preview"')
        self.assertContains(response, 'id="selected_image_preview"')
        # Hidden fields
        self.assertContains(response, 'id="selected_image"')
        self.assertContains(response, 'id="clear_image_flag"')
        # Sections
        self.assertContains(response, 'id="upload-section"')
        self.assertContains(response, 'id="gallery-section"')

    def test_edit_mode_displays_gallery_image_preview(self, mock_destroy, mock_upload):
        """Edit form should show preview of gallery image"""
        self.login_as(self.user)
        self.task_with_gallery.image = self.gallery_image1.image
        self.task_with_gallery.save()

        response = self.client.get(edit_url(self.task_with_gallery))

        self.assertEqual(response.status_code, 200)
        self.assertIn('current_image_id', response.context)
        # The view should find the gallery image by matching task.image to SampleImage.image
        self.assertEqual(response.context['current_image_id'], self.gallery_image1.id)
        self.assertContains(response, f'data-current-image-id="{self.gallery_image1.id}"')

    def test_edit_mode_displays_uploaded_image_preview(self, mock_destroy, mock_upload):
        """Edit form should show preview of uploaded image (non-gallery)"""
        # In production this would be a Cloudinary path from an upload
        self.task_with_upload.image = 'samples/test_image.png'
        self.task_with_upload.save()

        self.login_as(self.user)
        response = self.client.get(edit_url(self.task_with_upload))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context.get('current_image_id'))
        self.assertContains(response, 'data-current-image-url')

    def test_gallery_image_selection_via_form_submission(self, mock_destroy, mock_upload):
        """Submitting form with gallery image should associate it with task"""
        self.login_as(self.staff_user)

        self.client.post(reverse('submit_task'), data=submit_data(
            sha256='c' * 64,
            download_link='https://bazaar.abuse.ch/sample/test3/',
            description='Test with gallery image',
            image_id=self.gallery_image1.id,
        ), follow=True)

        task = AnalysisTask.objects.get(sha256='c' * 64)
        # task.image is a CloudinaryResource; compare the string values
        self.assertEqual(str(task.image), str(self.gallery_image1.image))

    def test_image_upload_via_form_submission(self, mock_destroy, mock_upload):
        """Submitting form with uploaded image should save it"""
        mock_upload.return_value = UPLOAD_RESULT
        self.login_as(self.staff_user)

        self.client.post(reverse('submit_task'), data=submit_data(
            sha256='d' * 64,
            download_link='https://bazaar.abuse.ch/sample/test4/',
            description='Test with uploaded image',
            image_upload=create_test_image(width=512, height=512),
        ), follow=True)

        task = AnalysisTask.objects.get(sha256='d' * 64)
        self.assertIsNotNone(task.image)

    def test_clear_image_flag_removes_image(self, mock_destroy, mock_upload):
        """Setting clear_image flag should remove image from task"""
        self.login_as(self.user)
        task = self.task_with_gallery
        task.image = 'sample_images/test.jpg'
        task.save()
        task.refresh_from_db()
        self.assertIsNotNone(task.image)

        self.client.post(edit_url(task), data=edit_data(task, clear_image='true'), follow=True)

        task.refresh_from_db()
        self.assertIsNone(task.image)

    def test_replace_gallery_image_with_upload(self, mock_destroy, mock_upload):
        """Can replace gallery image with uploaded image"""
        mock_upload.return_value = UPLOAD_RESULT
        self.login_as(self.user)
        task = self.task_with_gallery
        task.image = self.gallery_image1.image
        task.save()
        task.refresh_from_db()

        self.client.post(
            edit_url(task),
            data=edit_data(task, image_upload=create_test_image(width=512, height=512)),
            follow=True,
        )

        task.refresh_from_db()
        # Should now have the uploaded image, not the gallery image
        self.assertIsNotNone(task.image)
        if hasattr(task.image, 'id'):
            self.assertNotEqual(task.image.id, self.gallery_image1.id)

    def test_replace_upload_with_gallery_image(self, mock_destroy, mock_upload):
        """Can replace uploaded image with gallery image"""
        self.login_as(self.user)
        task = self.task_with_upload
        task.image = 'samples/test_image.png'
        task.save()

        self.client.post(edit_url(task), data=edit_data(task, image_id=self.gallery_image2.id), follow=True)

        task.refresh_from_db()
        self.gallery_image2.refresh_from_db()
        self.assertEqual(task.image.public_id, self.gallery_image2.image.public_id)


@patch('cloudinary.uploader.upload')
@patch('cloudinary.uploader.destroy')
class ImageValidationTestCase(SampleTestCase):
    """Test image dimension validation"""

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = make_staff()

    def setUp(self):
        self.login_as(self.staff_user)

    def assert_task_created_with_image(self, response, sha256):
        """The task exists and has an image; otherwise fail with the form errors"""
        task = AnalysisTask.objects.filter(sha256=sha256).first()
        if task is None:
            if response.context and 'form' in response.context:
                self.fail(f"Form validation failed: {response.context['form'].errors}")
            self.fail("Task was not created and no form errors found")
        self.assertIsNotNone(task.image)

    def test_image_minimum_size_validation(self, mock_destroy, mock_upload):
        """Images smaller than 125x125 should be rejected"""
        response = self.client.post(reverse('submit_task'), data=submit_data(
            sha256='e' * 64,
            download_link='https://bazaar.abuse.ch/sample/test5/',
            description='Test',
            image_upload=create_test_image(width=100, height=100),
        ))

        self.assertContains(response, 'Minimum size is 125x125 pixels', status_code=200)

    def test_image_maximum_size_validation(self, mock_destroy, mock_upload):
        """Images larger than 1024x1024 should be rejected"""
        response = self.client.post(reverse('submit_task'), data=submit_data(
            sha256='f' * 64,
            download_link='https://bazaar.abuse.ch/sample/test6/',
            description='Test',
            image_upload=create_test_image(width=2000, height=2000),
        ))

        self.assertContains(response, 'Maximum size is 1024x1024 pixels', status_code=200)

    def test_valid_image_size_accepted(self, mock_destroy, mock_upload):
        """Images within 125-1024 range should be accepted"""
        mock_upload.return_value = UPLOAD_RESULT
        sha256 = 'a1b2c3d4' * 8

        response = self.client.post(reverse('submit_task'), data=submit_data(
            sha256=sha256,
            download_link='https://bazaar.abuse.ch/sample/test7/',
            description='Test',
            image_upload=create_test_image(width=512, height=512),
        ), follow=True)

        self.assert_task_created_with_image(response, sha256)

    def test_non_square_image_handling(self, mock_destroy, mock_upload):
        """Non-square images should still be accepted (will be cropped)"""
        mock_upload.return_value = UPLOAD_RESULT
        sha256 = 'b1c2d3e4' * 8

        response = self.client.post(reverse('submit_task'), data=submit_data(
            sha256=sha256,
            download_link='https://bazaar.abuse.ch/sample/test8/',
            description='Test',
            image_upload=create_test_image(width=512, height=300),
        ), follow=True)

        self.assert_task_created_with_image(response, sha256)


class ImagePreviewJavaScriptTestCase(SampleTestCase):
    """Test JavaScript functionality for image preview (template checks)"""

    @classmethod
    def setUpTestData(cls):
        cls.staff_user = make_staff()

    def setUp(self):
        self.login_as(self.staff_user)

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
        task = make_task(author=self.staff_user)

        response = self.client.get(edit_url(task))

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
        task = make_task(author=self.staff_user)

        response = self.client.get(edit_url(task))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'onclick="confirmDelete()"')
