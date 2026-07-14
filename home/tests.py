import json
from io import BytesIO
from datetime import timedelta
from unittest.mock import patch

from PIL import Image
from django.db import connection
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Conversation, DailyMatchAction, KnotComment, KnotPost, KnotPreference, KnotVote, MatchRequest, Profile


class TestDatabaseSafetyTests(TestCase):
    def test_test_runner_uses_sqlite_not_supabase(self):
        self.assertEqual(connection.vendor, 'sqlite')


@override_settings(ADMIN_EMAILS=['admin@knotspot.test'])
class KnotsFeatureTests(TestCase):
    def setUp(self):
        self.owner = self._user('owner', 'owner@knotspot.test', 'KTR')
        self.other = self._user('other', 'other@knotspot.test', 'VLR')
        self.admin = self._user('admin', 'admin@knotspot.test', 'ACB')
        self.post = KnotPost.objects.create(
            user=self.owner, title='Library hours', content='Does anyone know the weekend hours?',
            category='question', college='SRM', campus='SRM Kattankulathur (KTR)',
        )
        KnotPost.objects.filter(id=self.post.id).update(created_at=timezone.now() - timedelta(hours=2))
        self.post.refresh_from_db()

    @staticmethod
    def _user(username, email, campus):
        user = User.objects.create_user(username=username, email=email, password='testpass123')
        Profile.objects.create(user=user, name=username.title(), campus=campus)
        return user

    def _post_json(self, url, data=None):
        return self.client.post(url, data=json.dumps(data or {}), content_type='application/json')

    def test_create_sanitizes_html_and_uses_profile_campus(self):
        self.client.force_login(self.other)
        response = self._post_json('/knots/create/', {
            'title': '<b>Study group</b>', 'content': '<script>alert(1)</script> Join us',
            'link': 'https://example.com/group', 'category': 'discussion',
        })
        self.assertEqual(response.status_code, 201)
        created = KnotPost.objects.get(id=response.json()['data']['id'])
        self.assertEqual(created.title, 'Study group')
        self.assertNotIn('<script>', created.content)
        self.assertEqual(created.college, 'VIT')
        self.assertEqual(created.campus, 'VIT Vellore (VLR)')

    def test_non_owner_cannot_edit_or_delete_post(self):
        self.client.force_login(self.other)
        edit = self._post_json(f'/knots/{self.post.id}/edit/', {
            'title': 'Changed', 'content': 'Changed by someone else', 'category': '', 'link': '',
        })
        delete = self._post_json(f'/api/knots/{self.post.id}/delete/')
        self.assertEqual(edit.status_code, 403)
        self.assertEqual(delete.status_code, 403)
        self.assertTrue(KnotPost.objects.filter(id=self.post.id).exists())

    def test_admin_can_edit_any_post(self):
        self.client.force_login(self.admin)
        response = self._post_json(f'/knots/{self.post.id}/edit/', {
            'title': 'Updated by moderation', 'content': 'Clarified campus information.',
            'category': 'information', 'link': '',
        })
        self.assertEqual(response.status_code, 200)
        self.post.refresh_from_db()
        self.assertEqual(self.post.title, 'Updated by moderation')

    def test_admin_can_delete_any_post(self):
        self.client.force_login(self.admin)
        response = self._post_json(f'/api/knots/{self.post.id}/delete/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(KnotPost.objects.filter(id=self.post.id).exists())

    def test_admin_can_edit_and_soft_delete_comment_with_replies(self):
        comment = KnotComment.objects.create(post=self.post, user=self.other, content='Original text')
        reply = KnotComment.objects.create(post=self.post, user=self.owner, parent=comment, content='Keep this reply')
        self.client.force_login(self.admin)
        edit = self._post_json(f'/api/knots/comments/{comment.id}/edit/', {'content': 'Moderator correction'})
        delete = self._post_json(f'/api/knots/comments/{comment.id}/delete/')
        self.assertEqual(edit.status_code, 200)
        self.assertEqual(delete.status_code, 200)
        self.assertTrue(delete.json()['data']['soft_deleted'])
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)
        self.assertEqual(comment.content, '')
        self.assertTrue(KnotComment.objects.filter(id=reply.id, parent=comment).exists())

    def test_non_owner_cannot_edit_or_delete_comment(self):
        comment = KnotComment.objects.create(post=self.post, user=self.owner, content='Owner comment')
        self.client.force_login(self.other)
        edit = self._post_json(f'/api/knots/comments/{comment.id}/edit/', {'content': 'Hijacked'})
        delete = self._post_json(f'/api/knots/comments/{comment.id}/delete/')
        self.assertEqual(edit.status_code, 403)
        self.assertEqual(delete.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.content, 'Owner comment')

    def test_vote_toggle_allows_only_one_vote_per_user(self):
        self.client.force_login(self.other)
        first = self._post_json(f'/api/knots/{self.post.id}/vote/')
        second = self._post_json(f'/api/knots/{self.post.id}/vote/')
        self.assertTrue(first.json()['data']['active'])
        self.assertFalse(second.json()['data']['active'])
        self.assertEqual(KnotVote.objects.filter(post=self.post, user=self.other).count(), 0)

    def test_feed_persists_sort_and_multiselect_filters(self):
        self.client.force_login(self.owner)
        response = self.client.get('/knots/', {
            'filters': '1', 'sort': 'hot', 'colleges': ['SRM', 'VIT'], 'campuses': ['KTR', 'VLR'],
        })
        self.assertEqual(response.status_code, 200)
        preference = KnotPreference.objects.get(user=self.owner)
        self.assertEqual(preference.sort, 'hot')
        self.assertEqual(preference.colleges, ['SRM', 'VIT'])
        self.assertEqual(preference.campuses, ['KTR', 'VLR'])

    def test_feed_renders_scoped_styles_compact_toolbar_and_location(self):
        self.client.force_login(self.owner)
        response = self.client.get('/knots/')
        self.assertContains(response, '<style id="knots-styles">', html=False)
        self.assertContains(response, 'Reddit-style campus threads')
        self.assertContains(response, '>Sort<', html=False)
        self.assertContains(response, '>Filter<', html=False)
        self.assertContains(response, '>SRM KTR<', html=False)
        self.assertContains(response, 'class="knots-header-icon"', html=False)
        self.assertNotContains(response, 'aria-label="Back to More"', html=False)
        self.assertNotContains(response, '<span class="material-symbols-outlined">arrow_back</span>', html=False)
        self.assertContains(response, 'html::-webkit-scrollbar,', html=False)
        self.assertContains(response, 'scrollbar-width: none;', html=False)
        self.assertContains(response, 'data-action="copy-post-text"', html=False)
        self.assertContains(response, '>Copy text</button>', html=False)
        self.assertContains(response, "font-family: 'Plus Jakarta Sans', -apple-system", html=False)
        self.assertContains(response, '.knot-content {')
        self.assertContains(response, 'font-size: 14.5px;')
        self.assertContains(response, '.knot-card h2 {')
        self.assertContains(response, 'font-size: 18.5px;')
        self.assertNotContains(
            response,
            '<span class="knot-campus-chip">SRM Kattankulathur (KTR)</span>',
            html=False,
        )

    def test_bottom_nav_has_knots_tab_active_on_knots_feed(self):
        self.client.force_login(self.owner)

        response = self.client.get('/knots/')

        self.assertContains(response, 'href="/knots/" class="nav-link active"', html=False)
        self.assertContains(response, '>Knots<', html=False)
        self.assertNotContains(response, 'href="/more/" class="nav-link active"', html=False)

    def test_knot_author_avatar_and_name_open_profile_when_not_anonymous(self):
        self.client.force_login(self.owner)

        response = self.client.get('/knots/')

        profile_url = f'/profile/{self.owner.id}/'
        self.assertContains(response, f'data-profile-url="{profile_url}"')
        self.assertContains(response, 'knot-profile-click')

        self.post.is_anonymous = True
        self.post.save(update_fields=['is_anonymous'])
        anonymous = self.client.get('/knots/')
        self.assertNotContains(anonymous, f'data-profile-url="{profile_url}"')

    def test_feed_hides_total_badge_and_filter_controls_can_bubble(self):
        self.client.force_login(self.owner)

        response = self.client.get('/knots/')

        self.assertNotContains(response, 'class="knots-header-badge"')
        self.assertNotContains(response, 'onclick="event.stopPropagation()"')

    def test_create_form_only_labels_campuses_by_code(self):
        self.client.force_login(self.owner)
        response = self.client.get('/knots/create/')
        self.assertContains(response, 'data-org="SRM"')
        self.assertContains(response, 'data-org="SRM">KTR</button>', html=False)
        self.assertNotContains(response, '>KTR â€” SRM Kattankulathur', html=False)

    def test_create_rejects_campus_from_a_different_college(self):
        self.client.force_login(self.owner)
        response = self._post_json('/knots/create/', {
            'title': 'Wrong campus', 'content': 'This should not be accepted.',
            'college': 'SRM', 'campus': 'VIT Vellore (VLR)',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('selected college', response.json()['error'])
        self.assertFalse(KnotPost.objects.filter(title='Wrong campus').exists())

    def test_create_rejects_overlong_title(self):
        self.client.force_login(self.owner)
        response = self._post_json('/knots/create/', {
            'title': 'x' * 181,
            'content': 'Valid body',
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('180 characters', response.json()['error'])

    def test_create_page_uses_compact_rich_composer_without_header_or_nav(self):
        self.client.force_login(self.owner)

        response = self.client.get('/knots/create/')

        self.assertNotContains(response, '<header')
        self.assertNotContains(response, '<nav>')
        self.assertContains(response, 'class="knot-composer-topbar"')
        self.assertContains(response, 'id="knotCollege" name="college" type="hidden"')
        self.assertContains(response, 'id="knotCampus" name="campus" type="hidden"')
        self.assertContains(response, 'data-custom-select data-target="knotCollege"')
        self.assertContains(response, 'data-custom-select data-target="knotCampus"')
        self.assertNotContains(response, '<select id="knotCollege"')
        self.assertNotContains(response, '<select id="knotCampus"')
        self.assertNotContains(response, 'knot-native-hidden')
        self.assertContains(response, 'id="knotRichEditor"')
        self.assertContains(response, 'data-placeholder="Body"')
        self.assertContains(response, 'data-format="bold"')
        self.assertContains(response, 'data-format="italic"')
        self.assertContains(response, 'data-format="insertUnorderedList"')
        self.assertContains(response, 'data-format="formatBlock"')
        self.assertContains(response, "function wrapSelectedRange(tagName, className)")
        self.assertContains(response, "if (format === 'bold') return wrapSelectedRange('strong');")
        self.assertContains(response, "if (format === 'italic') return wrapSelectedRange('em');")
        self.assertContains(response, "if (format === 'formatBlock') return wrapSelectedRange('span', 'knot-inline-heading');")
        self.assertContains(response, "if (format === 'insertUnorderedList') return bulletSelectedRange();")
        self.assertNotContains(response, 'document.execCommand(button.dataset.format', html=False)
        self.assertContains(response, 'id="knotImageInput"')
        self.assertContains(response, 'var maxKnotImages = 4;')
        self.assertContains(response, 'Max 4 images per Knot')
        self.assertContains(response, 'id="knotLinkDialog"')
        self.assertContains(response, 'class="knot-anon-toggle"')
        self.assertContains(response, 'Anonymous')
        self.assertNotContains(response, "prompt('Paste a link")

    def test_create_page_hides_rich_editor_focus_outline(self):
        self.client.force_login(self.owner)
        response = self.client.get('/knots/create/')
        self.assertContains(response, '.knot-rich-editor:focus,')
        self.assertContains(response, '.knot-rich-editor:focus-visible { outline: 0; }')

    def test_edit_page_uses_same_rich_composer_controls_as_create(self):
        self.post.content = (
            '<p>Existing text</p>'
            '<img src="https://res.cloudinary.com/demo/image/upload/edit.webp" alt="Edit image">'
        )
        self.post.link = 'https://example.com/edit'
        self.post.is_anonymous = True
        self.post.save(update_fields=['content', 'link', 'is_anonymous'])
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/edit/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<header')
        self.assertNotContains(response, '<nav>')
        self.assertContains(response, 'class="knot-composer-topbar"')
        self.assertContains(response, 'data-custom-select data-target="knotCollege"')
        self.assertContains(response, 'data-custom-select data-target="knotCampus"')
        self.assertContains(response, 'id="knotCollege" name="college" type="hidden"')
        self.assertContains(response, 'id="knotCampus" name="campus" type="hidden"')
        self.assertNotContains(response, '<select id="knotCollege"')
        self.assertNotContains(response, '<select id="knotCampus"')
        self.assertContains(response, 'id="knotRichEditor"')
        self.assertContains(response, 'data-placeholder="Body"')
        self.assertContains(response, 'Existing text')
        self.assertContains(response, 'edit.webp')
        self.assertContains(response, 'value="https://example.com/edit"')
        self.assertContains(response, 'id="knotAnonymous" type="checkbox" checked')
        self.assertContains(response, 'Anonymous')
        self.assertContains(response, '>Save<', html=False)

    def test_create_sanitizes_rich_content_and_keeps_supported_formatting(self):
        self.client.force_login(self.owner)

        response = self._post_json('/knots/create/', {
            'title': 'Formatted Knot',
            'content': 'Formatted words',
            'content_html': (
                '<p><strong>Formatted</strong> <em>words</em>'
                '<script>alert(1)</script>'
                '<img src="https://res.cloudinary.com/demo/image/upload/sample.webp" onerror="alert(2)"></p>'
            ),
            'college': '',
            'campus': '',
        })

        self.assertEqual(response.status_code, 201)
        post = KnotPost.objects.get(title='Formatted Knot')
        self.assertIn('<strong>Formatted</strong>', post.content)
        self.assertIn('<em>words</em>', post.content)
        self.assertIn('res.cloudinary.com', post.content)
        self.assertNotIn('<script', post.content)
        self.assertNotIn('onerror', post.content)
        detail = self.client.get(f'/knots/{post.id}/{post.slug}/')
        self.assertContains(detail, '<strong>Formatted</strong>', html=False)

    def test_create_sanitizes_inline_heading_span(self):
        self.client.force_login(self.owner)

        response = self._post_json('/knots/create/', {
            'title': 'Inline heading',
            'content': 'Only selected words should be bigger',
            'content_html': '<p>Only <span class="knot-inline-heading bad">selected words</span> should be bigger</p>',
            'college': '',
            'campus': '',
        })

        self.assertEqual(response.status_code, 201)
        post = KnotPost.objects.get(title='Inline heading')
        self.assertIn('<span class="knot-inline-heading">selected words</span>', post.content)
        self.assertNotIn(' bad', post.content)

    def test_create_rejects_more_than_four_images(self):
        self.client.force_login(self.owner)
        images = ''.join(
            f'<img src="https://res.cloudinary.com/demo/image/upload/knot-{index}.webp" alt="Image {index}">'
            for index in range(5)
        )

        response = self._post_json('/knots/create/', {
            'title': 'Too many images',
            'content': 'This knot has too many images',
            'content_html': f'<p>This knot has too many images</p>{images}',
            'college': '',
            'campus': '',
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('up to 4 images', response.json()['error'])
        self.assertFalse(KnotPost.objects.filter(title='Too many images').exists())

    def test_create_allows_only_one_knot_per_hour(self):
        recent = KnotPost.objects.create(
            user=self.other,
            title='Recent Knot',
            content='Posted recently.',
            college='VIT',
            campus='VIT Vellore (VLR)',
        )
        self.client.force_login(self.other)

        blocked = self._post_json('/knots/create/', {
            'title': 'Second Knot',
            'content': 'Trying again too soon.',
            'college': '',
            'campus': '',
        })

        self.assertEqual(blocked.status_code, 429)
        self.assertIn('one Knot per hour', blocked.json()['error'])
        self.assertFalse(KnotPost.objects.filter(title='Second Knot').exists())

        KnotPost.objects.filter(id=recent.id).update(created_at=timezone.now() - timedelta(hours=1, minutes=1))
        allowed = self._post_json('/knots/create/', {
            'title': 'After Cooldown',
            'content': 'This one is allowed now.',
            'college': '',
            'campus': '',
        })

        self.assertEqual(allowed.status_code, 201)

    def test_rich_content_caps_blank_lines_and_repeated_spaces(self):
        self.client.force_login(self.owner)

        response = self._post_json('/knots/create/', {
            'title': 'Normal spacing',
            'content': 'First Second words',
            'content_html': '<div>First</div><br><br><br><br><div>Second     words</div>\n\n\n\n',
            'college': '',
            'campus': '',
        })

        self.assertEqual(response.status_code, 201)
        post = KnotPost.objects.get(title='Normal spacing')
        self.assertNotIn('<br><br><br>', post.content)
        self.assertNotIn('Second     words', post.content)
        self.assertNotIn('\n\n\n', post.content)
        self.assertIn('Second words', post.content)

    def test_comment_text_is_limited_and_collapses_blank_lines(self):
        self.client.force_login(self.other)
        response = self._post_json(f'/api/knots/{self.post.id}/comments/', {
            'content': 'First\n\n\n\nSecond     line',
        })
        self.assertEqual(response.status_code, 201)
        comment = KnotComment.objects.get(id=response.json()['data']['id'])
        self.assertEqual(comment.content, 'First\n\nSecond line')

        too_long = self._post_json(f'/api/knots/{self.post.id}/comments/', {'content': 'x' * 1201})
        self.assertEqual(too_long.status_code, 400)
        self.assertIn('1200 characters', too_long.json()['error'])

    @patch('home.knot_views.upload_to_cloudinary', return_value='https://res.cloudinary.com/demo/image/upload/knot.webp')
    def test_authenticated_user_can_upload_valid_knot_image(self, upload):
        self.client.force_login(self.owner)
        image_bytes = BytesIO()
        Image.new('RGB', (12, 12), color='blue').save(image_bytes, format='PNG')
        image = SimpleUploadedFile('knot.png', image_bytes.getvalue(), content_type='image/png')

        response = self.client.post('/api/knots/images/', {'image': image})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['data']['url'], upload.return_value)
        upload.assert_called_once()
        self.assertFalse(upload.call_args.kwargs['optimize'])

    @patch('home.knot_views.upload_to_cloudinary', return_value='https://res.cloudinary.com/demo/image/upload/optimized.webp')
    def test_knot_image_upload_compresses_normal_images_before_cloudinary(self, upload):
        self.client.force_login(self.owner)
        image_bytes = BytesIO()
        image = Image.effect_noise((1600, 1100), 42).convert('RGB')
        image.save(image_bytes, format='JPEG', quality=95)
        original_size = image_bytes.tell()
        image_file = SimpleUploadedFile('large-knot.jpg', image_bytes.getvalue(), content_type='image/jpeg')

        response = self.client.post('/api/knots/images/', {'image': image_file})

        self.assertEqual(response.status_code, 201)
        optimized_file = upload.call_args.args[0]
        optimized_file.seek(0, 2)
        optimized_size = optimized_file.tell()
        optimized_file.seek(0)
        self.assertLess(optimized_size, original_size)
        self.assertLessEqual(optimized_size, 150 * 1024)
        self.assertEqual(Image.open(optimized_file).format, 'WEBP')
        self.assertFalse(upload.call_args.kwargs['optimize'])

    @patch('home.knot_views.upload_to_cloudinary')
    def test_knot_image_upload_rejects_non_image(self, upload):
        self.client.force_login(self.owner)
        fake = SimpleUploadedFile('not-image.txt', b'not an image', content_type='text/plain')

        response = self.client.post('/api/knots/images/', {'image': fake})

        self.assertEqual(response.status_code, 400)
        upload.assert_not_called()

    def test_replies_endpoint_returns_only_direct_children(self):
        root = KnotComment.objects.create(post=self.post, user=self.owner, content='Root')
        child = KnotComment.objects.create(post=self.post, user=self.other, parent=root, content='Child')
        KnotComment.objects.create(post=self.post, user=self.owner, parent=child, content='Grandchild')
        self.client.force_login(self.owner)
        response = self.client.get(f'/api/knots/comments/{root.id}/replies/')
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual([item['id'] for item in data], [child.id])
        self.assertEqual(data[0]['reply_count'], 1)
        self.assertEqual(data[0]['profile_url'], f'/profile/{self.other.id}/')

    def test_comment_author_avatar_and_name_link_to_profile(self):
        KnotComment.objects.create(post=self.post, user=self.other, content='Profile tap')
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        profile_url = f'/profile/{self.other.id}/'
        self.assertContains(response, f'href="{profile_url}"')
        self.assertContains(response, 'class="knot-profile-link knot-avatar-link"')
        self.assertContains(response, 'class="knot-profile-link knot-author-name"')

    def test_comment_and_dynamic_reply_menus_can_copy_text(self):
        comment = KnotComment.objects.create(post=self.post, user=self.other, content='Copy this comment')
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertContains(response, 'data-action="copy-comment-text"', html=False)
        self.assertContains(response, "var copy = item.is_deleted ? '' : '<button type=\"button\" data-action=\"copy-comment-text\"", html=False)
        self.assertContains(response, "copyText(commentCopyText(comment), 'Comment text copied');", html=False)
        self.assertContains(response, 'Copy this comment')

    def test_detail_has_no_bottom_nav_and_uses_one_discussion_container(self):
        root = KnotComment.objects.create(post=self.post, user=self.other, content='Top level comment')
        KnotComment.objects.create(post=self.post, user=self.owner, parent=root, content='Hidden child reply')
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<nav>')
        self.assertContains(response, 'class="knot-discussion-card"')
        self.assertContains(response, 'Top level comment')
        self.assertNotContains(response, 'Hidden child reply')
        self.assertContains(response, 'View 1 reply')
        self.assertContains(response, '.knots-detail-shell .knots-body-inner { padding-right: 0; padding-left: 0; }')
        self.assertContains(response, '#commentList { display: grid; gap: 6px;')
        self.assertContains(response, '.knot-author > .knot-chips-row')

    def test_thread_page_also_has_no_bottom_nav(self):
        root = KnotComment.objects.create(post=self.post, user=self.other, content='Thread root')
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/replies/{root.id}/')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<nav>')

    def test_bottom_nav_is_only_on_knots_list_not_create_page(self):
        self.client.force_login(self.owner)
        feed = self.client.get('/knots/')
        create = self.client.get('/knots/create/')

        self.assertContains(feed, '<nav>')
        self.assertNotContains(create, '<nav>')

    def test_posting_reply_does_not_force_reply_tree_open(self):
        self.client.force_login(self.owner)
        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')
        self.assertNotContains(response, "children.classList.add('open')")

    def test_comment_metadata_and_actions_use_compact_layout(self):
        comment = KnotComment.objects.create(post=self.post, user=self.other, content='Compact comment')
        KnotComment.objects.filter(id=comment.id).update(
            created_at=timezone.now() - timedelta(hours=1, minutes=3)
        )
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertContains(response, 'class="comment-author-line"')
        self.assertContains(response, '1h 3m ago')
        self.assertContains(response, '.comment .knot-author-copy { transform: translateY(-5px); }')
        self.assertContains(response, '.comment-body { margin: -13px 0 0 48px; color: #344054; font-size: 14px;')
        self.assertContains(response, '#commentList > .comment { margin: 0; padding: 10px 16px 14px;')
        self.assertContains(response, '.comment-actions { gap: 2px; margin: 8px 0 0 44px;')
        self.assertNotContains(response, 'VIT VLR ·')
        self.assertContains(response, 'aria-label="Reply to Other"')
        self.assertNotContains(response, '>Reply</button>', html=False)

    def test_knot_images_open_in_a_dismissible_viewer_and_surfaces_are_borderless(self):
        self.post.content = (
            '<p>Campus photo</p>'
            '<img src="https://res.cloudinary.com/demo/image/upload/campus.webp" alt="Campus">'
        )
        self.post.save(update_fields=['content'])
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertContains(response, "event.target.closest('.knot-rich-content img')")
        self.assertContains(response, "id = 'knotImageLightbox'")
        self.assertContains(response, '.knot-image-lightbox.open')
        self.assertContains(response, '.comment-body { margin: -13px 0 0 48px; color: #344054; font-size: 14px;')
        self.assertContains(response, '--knot-shadow-soft:')
        self.assertContains(response, '.knot-card {')
        self.assertContains(response, 'border: 0;')

    def test_feed_uses_plain_ellipsized_excerpt_and_hides_rich_images(self):
        self.post.content = (
            '<p>Long paragraph ' + ('word ' * 90) + '</p>'
            '<img src="https://res.cloudinary.com/demo/image/upload/feed.webp" alt="Feed image">'
        )
        self.post.save(update_fields=['content'])
        self.client.force_login(self.owner)

        response = self.client.get('/knots/')

        self.assertContains(response, 'class="knot-content knot-list-excerpt"')
        self.assertNotContains(response, 'feed.webp')
        self.assertContains(response, '.knot-list-excerpt')
        self.assertContains(response, '-webkit-line-clamp: 4;')

    def test_discussion_sections_are_edge_to_edge_and_action_controls_are_outlined(self):
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertContains(response, '.knot-discussion-card > .knot-card {')
        self.assertContains(response, 'border-radius: 0;')
        self.assertContains(response, '#commentList > .comment { margin: 0;')
        self.assertContains(response, 'border: 1px solid #edf0f5;')
        self.assertContains(response, 'box-shadow: none;')
        self.assertContains(response, '<span class="material-symbols-outlined">star</span>')
        self.assertNotContains(response, '<span class="material-symbols-outlined">arrow_upward</span>')

    def test_view_replies_is_in_the_comment_action_row(self):
        comment = KnotComment.objects.create(post=self.post, user=self.other, content='Parent comment')
        KnotComment.objects.create(post=self.post, user=self.owner, parent=comment, content='Child reply')
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')
        html = response.content.decode()
        action_row_start = html.index('<div class="comment-actions">')
        action_row_end = html.index('</div>', action_row_start)

        self.assertIn('class="view-replies"', html[action_row_start:action_row_end])


class DailyMatchActionLimitTests(TestCase):
    def _actor(self, username, gender):
        user = User.objects.create(username=username, email=f'{username}@test.local')
        Profile.objects.create(
            user=user, name=username, gender=gender, campus='KTR', age=20,
            native_place='Chennai', is_discoverable=True,
        )
        return user

    @staticmethod
    def _candidate(index):
        return User.objects.create(username=f'candidate-{index}', email=f'candidate-{index}@test.local')

    def test_male_profile_is_blocked_after_eight_skip_or_connect_actions(self):
        actor = self._actor('male-actor', 'male')
        candidates = [self._candidate(i) for i in range(10)]
        for candidate in candidates[:8]:
            MatchRequest.objects.create(sender=actor, receiver=candidate, status='skipped')
            DailyMatchAction.objects.create(user=actor, target=candidate, action='skip')
        self.client.force_login(actor)

        connect = self.client.post(
            f'/match/send/{candidates[8].id}/', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        skip = self.client.post(
            f'/match/skip/{candidates[9].id}/', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(connect.status_code, 429)
        self.assertEqual(skip.status_code, 429)
        self.assertEqual(connect.json()['code'], 'daily_limit_reached')
        self.assertEqual(connect.json()['limit'], 8)
        self.assertEqual(MatchRequest.objects.filter(sender=actor).count(), 8)
        limit_page = self.client.get('/match/')
        self.assertContains(limit_page, 'Daily match limit reached')
        self.assertContains(limit_page, 'all 8 Skip/Connect actions')

    @patch('home.views.send_push_to_user')
    @patch('home.views.broadcast_event')
    def test_female_profile_gets_thirteen_actions_and_fourteenth_is_blocked(self, broadcast, push):
        actor = self._actor('female-actor', 'female')
        candidates = [self._candidate(i + 20) for i in range(14)]
        for candidate in candidates[:12]:
            MatchRequest.objects.create(sender=actor, receiver=candidate, status='skipped')
            DailyMatchAction.objects.create(user=actor, target=candidate, action='skip')
        self.client.force_login(actor)

        thirteenth = self.client.post(
            f'/match/send/{candidates[12].id}/', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        fourteenth = self.client.post(
            f'/match/send/{candidates[13].id}/', HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(thirteenth.status_code, 200)
        self.assertEqual(thirteenth.json()['daily_remaining'], 0)
        self.assertEqual(fourteenth.status_code, 429)
        self.assertEqual(fourteenth.json()['limit'], 13)
        self.assertEqual(MatchRequest.objects.filter(sender=actor).count(), 13)
        self.assertEqual(DailyMatchAction.objects.filter(user=actor).count(), 13)


@override_settings(ADMIN_EMAILS=['admin-profile@test.local'])
class AdminProfileModerationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create(username='profile-admin', email='admin-profile@test.local')
        Profile.objects.create(user=self.admin, name='Admin', gender='male', campus='KTR')
        self.target = User.objects.create(username='target-user', email='target@test.local')
        self.target_profile = Profile.objects.create(
            user=self.target, name='Target', gender='female', campus='VLR',
            profile_pic='https://example.com/meme.jpg', is_discoverable=True,
        )
        self.other = User.objects.create(username='not-admin', email='other@test.local')
        Profile.objects.create(user=self.other, name='Other', gender='male', campus='KTR')

    def test_admin_can_remove_profile_photo_and_matching_is_disabled(self):
        self.client.force_login(self.admin)
        edit_page = self.client.get(f'/master/profile/edit/{self.target.id}/')
        self.assertContains(edit_page, 'Message user')
        self.assertContains(edit_page, 'Remove photo')
        response = self.client.post(
            f'/master/profile/edit/{self.target.id}/', {'remove_profile_pic': '1'}
        )
        self.assertEqual(response.status_code, 302)
        self.target_profile.refresh_from_db()
        self.assertEqual(self.target_profile.profile_pic, '')
        self.assertFalse(self.target_profile.is_discoverable)

    def test_admin_can_start_direct_chat_from_profile_editor(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            f'/master/profile/edit/{self.target.id}/', {'start_admin_chat': '1'}
        )
        self.assertRedirects(response, f'/chat/{self.target.id}/', fetch_redirect_response=False)
        self.assertTrue(Conversation.objects.filter(
            user1_id=min(self.admin.id, self.target.id),
            user2_id=max(self.admin.id, self.target.id),
            source='admin',
        ).exists())

    def test_non_admin_cannot_use_profile_moderation_actions(self):
        self.client.force_login(self.other)
        response = self.client.post(
            f'/master/profile/edit/{self.target.id}/', {'remove_profile_pic': '1'}
        )
        self.assertEqual(response.status_code, 403)
        self.target_profile.refresh_from_db()
        self.assertTrue(self.target_profile.profile_pic)
