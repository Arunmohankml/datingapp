import json
from io import BytesIO
from datetime import datetime, timedelta
from unittest.mock import patch

from PIL import Image
from django.db import connection
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from .models import Community, CommunityMember, CommunityMessage, CommunityMute, CommunityReadStatus, Confession, ConfessionComment, ConfessionRateLimit, Conversation, DailyMatchAction, DailyQuestion, FCMToken, KnotComment, KnotPost, KnotPreference, KnotReport, KnotVote, MatchRequest, Message, Option, Profile, Question, QuestionOption, UserAnswer


class QuizQuestionPriorityTests(TestCase):
    def setUp(self):
        Question.objects.all().delete()
        self.user = User.objects.create_user('quiz-priority-user', password='testpass123')
        Profile.objects.create(user=self.user, name='Quiz User', gender='male')
        self.client.force_login(self.user)

        self.original_questions = self._questions('Original', 10, is_priority=False)
        self.priority_questions = self._questions('Imported', 10, is_priority=True)

    @staticmethod
    def _questions(prefix, count, *, is_priority):
        questions = []
        for index in range(count):
            question = Question.objects.create(
                text=f'{prefix} question {index}',
                is_priority=is_priority,
            )
            Option.objects.create(question=question, text='First option')
            Option.objects.create(question=question, text='Second option')
            questions.append(question)
        return questions

    def test_new_user_batch_mixes_imported_and_original_questions(self):
        response = self.client.get('/api/quiz/batch/')

        self.assertEqual(response.status_code, 200)
        question_ids = [question['id'] for question in response.json()['questions']]
        self.assertEqual(question_ids[:5], [question.id for question in self.priority_questions[:5]])
        self.assertEqual(question_ids[5:], [question.id for question in self.original_questions[:5]])

    def test_answered_questions_are_not_returned(self):
        answered = self.priority_questions[0]
        UserAnswer.objects.create(
            user=self.user,
            question=answered,
            option=answered.options.first(),
        )

        response = self.client.get('/api/quiz/batch/')
        question_ids = [question['id'] for question in response.json()['questions']]

        self.assertNotIn(answered.id, question_ids)
        self.assertEqual(len(question_ids), 10)

    def test_established_user_keeps_original_question_order(self):
        answered_history = self._questions('Answered history', 50, is_priority=False)
        UserAnswer.objects.bulk_create([
            UserAnswer(
                user=self.user,
                question=question,
                option=question.options.first(),
            )
            for question in answered_history
        ])

        response = self.client.get('/api/quiz/batch/')
        question_ids = [question['id'] for question in response.json()['questions']]

        self.assertEqual(question_ids, [question.id for question in self.original_questions])

    def test_pre_rollout_user_with_few_answers_keeps_original_order(self):
        self.user.date_joined = timezone.make_aware(datetime(2026, 7, 15))
        self.user.save(update_fields=['date_joined'])

        response = self.client.get('/api/quiz/batch/')
        question_ids = [question['id'] for question in response.json()['questions']]

        self.assertEqual(question_ids, [question.id for question in self.original_questions])


class TestDatabaseSafetyTests(TestCase):
    def test_test_runner_uses_sqlite_not_supabase(self):
        self.assertEqual(connection.vendor, 'sqlite')


class ConfessionReplyNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('confession-owner', password='testpass123')
        self.commenter = User.objects.create_user('confession-commenter', password='testpass123')
        Profile.objects.create(user=self.owner, name='Confession Owner')
        Profile.objects.create(user=self.commenter, name='Helpful Student')
        self.confession = Confession.objects.create(
            user=self.owner,
            content='Is anyone else feeling this way?',
            poster_fingerprint='owner-device',
        )

    @patch('home.views.broadcast_event')
    @patch('home.views.send_push_to_user')
    def test_reply_notifies_confession_owner_with_push_and_foreground_toast(self, push, broadcast):
        self.client.force_login(self.commenter)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f'/confessions/{self.confession.id}/comment/',
                {
                    'content': 'You are definitely not alone.',
                    'is_anonymous': 'true',
                    'fingerprint': 'commenter-device',
                },
            )

        self.assertEqual(response.status_code, 302)
        comment = ConfessionComment.objects.get(confession=self.confession)
        expected_url = f'/confessions/{self.confession.id}/#comment-{comment.id}'
        push.assert_called_once_with(
            self.owner,
            'New reply to your confession',
            'Someone anonymously replied: You are definitely not alone.',
            expected_url,
        )
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.args[0], f'chat_{self.owner.id}')
        self.assertEqual(broadcast.call_args.args[1], 'confession_activity')
        self.assertEqual(broadcast.call_args.args[2]['comment_id'], comment.id)

    @patch('home.views.broadcast_event')
    @patch('home.views.send_push_to_user')
    def test_owner_comment_does_not_notify_owner(self, push, broadcast):
        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f'/confessions/{self.confession.id}/comment/',
                {
                    'content': 'Adding some context.',
                    'is_anonymous': 'true',
                    'fingerprint': 'owner-device',
                },
            )

        self.assertEqual(response.status_code, 302)
        push.assert_not_called()
        broadcast.assert_not_called()

    def test_base_page_listens_for_foreground_confession_activity(self):
        self.client.force_login(self.owner)

        response = self.client.get(f'/confessions/{self.confession.id}/')

        self.assertContains(response, "userChannel.bind('confession_activity'")


class ConfessionPostingCooldownTests(TestCase):
    def test_confession_allows_one_post_every_five_minutes(self):
        payload = {
            'content': 'A first unique campus confession',
            'is_anonymous': 'true',
            'fingerprint': 'five-minute-device',
        }
        first = self.client.post('/confessions/create/', payload)

        payload['content'] = 'A second different campus confession'
        blocked = self.client.post('/confessions/create/', payload)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(blocked.status_code, 302)
        self.assertEqual(Confession.objects.filter(poster_fingerprint='five-minute-device').count(), 1)
        warning_messages = [str(message) for message in get_messages(blocked.wsgi_request)]
        self.assertTrue(any('5 minute(s)' in message for message in warning_messages))

        ConfessionRateLimit.objects.filter(identifier='five-minute-device').update(
            submitted_at=timezone.now() - timedelta(minutes=5, seconds=1)
        )
        payload['content'] = 'A third unique confession after cooldown'
        allowed = self.client.post('/confessions/create/', payload)

        self.assertEqual(allowed.status_code, 302)
        self.assertEqual(Confession.objects.filter(poster_fingerprint='five-minute-device').count(), 2)


class EgressRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('egress-user', password='testpass123')
        self.partner = User.objects.create_user('egress-partner', password='testpass123')
        Profile.objects.create(user=self.user, name='Egress User')
        Profile.objects.create(user=self.partner, name='Egress Partner')
        self.client.force_login(self.user)

    def test_community_poll_is_incremental_without_per_message_community_queries(self):
        community = Community.objects.create(name='Egress Test', slug='egress-test')
        CommunityMember.objects.create(user=self.user, community=community)
        first = CommunityMessage.objects.create(community=community, sender=self.partner, text='old')
        latest = CommunityMessage.objects.create(community=community, sender=self.partner, text='new')

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f'/api/community/{community.slug}/messages/?after={first.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([message['id'] for message in response.json()['messages']], [latest.id])
        repeated_community_fetches = [
            query['sql'] for query in queries.captured_queries
            if 'FROM "home_community"' in query['sql'] and '"home_community"."id" =' in query['sql']
        ]
        self.assertEqual(repeated_community_fetches, [])

    def test_direct_chat_poll_only_returns_messages_after_cursor(self):
        MatchRequest.objects.create(sender=self.user, receiver=self.partner, status='accepted')
        first = Message.objects.create(sender=self.partner, receiver=self.user, text='old')
        latest = Message.objects.create(sender=self.partner, receiver=self.user, text='new')

        response = self.client.get(f'/api/chat/{self.partner.id}/?after={first.id}')

        self.assertEqual(response.status_code, 200)
        self.assertEqual([message['id'] for message in response.json()['messages']], [latest.id])

    def test_wall_page_and_api_are_blocked_without_database_queries(self):
        anonymous_client = Client()

        with self.assertNumQueries(0):
            page = anonymous_client.get('/wall/')
            api_get = anonymous_client.get('/api/wall/')
            api_post = anonymous_client.post('/api/wall/', data='{}', content_type='application/json')
            api_delete = anonymous_client.delete('/api/wall/', data='{}', content_type='application/json')

        self.assertEqual(page.status_code, 410)
        self.assertEqual(api_get.status_code, 410)
        self.assertEqual(api_post.status_code, 410)
        self.assertEqual(api_delete.status_code, 410)


class CommunityMembershipTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('community-user', password='testpass123')
        self.sender = User.objects.create_user('community-sender', password='testpass123')
        self.muted = User.objects.create_user('community-muted', password='testpass123')
        self.outsider = User.objects.create_user('community-outsider', password='testpass123')
        for user in (self.user, self.sender, self.muted, self.outsider):
            Profile.objects.create(user=user, name=user.username.replace('-', ' ').title())
        self.community = Community.objects.create(name='Campus Circle', slug='campus-circle')
        self.client.force_login(self.user)

    def test_non_member_chat_and_poll_are_blocked_before_message_queries(self):
        CommunityMessage.objects.create(community=self.community, sender=self.sender, text='private message')

        with CaptureQueriesContext(connection) as page_queries:
            page = self.client.get(f'/community/{self.community.slug}/')
        with CaptureQueriesContext(connection) as api_queries:
            api = self.client.get(f'/api/community/{self.community.slug}/messages/')
        post = self.client.post(
            f'/community/{self.community.slug}/',
            data=json.dumps({'text': 'not allowed'}),
            content_type='application/json',
        )

        self.assertEqual(page.status_code, 302)
        self.assertEqual(api.status_code, 403)
        self.assertEqual(post.status_code, 403)
        self.assertFalse(CommunityMessage.objects.filter(sender=self.user).exists())
        for queries in (page_queries, api_queries):
            message_queries = [q['sql'] for q in queries.captured_queries if 'home_communitymessage' in q['sql'].lower()]
            self.assertEqual(message_queries, [])

    def test_join_creates_membership_read_marker_and_system_message(self):
        response = self.client.post(f'/api/community/{self.community.slug}/join/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['created'])
        self.assertTrue(CommunityMember.objects.filter(user=self.user, community=self.community).exists())
        self.assertTrue(CommunityReadStatus.objects.filter(user=self.user, community=self.community).exists())
        event = CommunityMessage.objects.get(community=self.community, sender=self.user)
        self.assertEqual(event.kind, CommunityMessage.KIND_JOIN)
        self.assertEqual(response.json()['member_count'], 1)

        chat = self.client.get(f'/community/{self.community.slug}/')
        self.assertEqual(chat.status_code, 200)
        self.assertContains(chat, 'Community User')
        self.assertContains(chat, 'joined')
        self.assertContains(chat, '1 member · tap for info')

    def test_chat_list_join_supplies_a_valid_csrf_token(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)

        page = browser.get('/chats/')
        csrf_cookie = browser.cookies.get('csrftoken')
        response = browser.post(
            f'/api/community/{self.community.slug}/join/',
            HTTP_X_CSRFTOKEN=csrf_cookie.value if csrf_cookie else '',
        )

        self.assertEqual(page.status_code, 200)
        self.assertIsNotNone(csrf_cookie)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_mute_requires_membership_and_leave_removes_private_state(self):
        blocked = self.client.post(f'/api/community/{self.community.slug}/toggle-mute/')
        self.assertEqual(blocked.status_code, 403)

        CommunityMember.objects.create(user=self.user, community=self.community)
        CommunityReadStatus.objects.create(user=self.user, community=self.community)
        muted = self.client.post(f'/api/community/{self.community.slug}/toggle-mute/')
        self.assertEqual(muted.status_code, 200)
        self.assertTrue(muted.json()['is_muted'])

        left = self.client.post(f'/api/community/{self.community.slug}/leave/')
        self.assertEqual(left.status_code, 200)
        self.assertFalse(CommunityMember.objects.filter(user=self.user, community=self.community).exists())
        self.assertFalse(CommunityMute.objects.filter(user=self.user, community=self.community).exists())
        self.assertFalse(CommunityReadStatus.objects.filter(user=self.user, community=self.community).exists())
        self.assertEqual(
            CommunityMessage.objects.filter(sender=self.user).latest('id').kind,
            CommunityMessage.KIND_LEAVE,
        )

    def test_group_info_is_member_only_and_lists_members(self):
        blocked = self.client.get(f'/community/{self.community.slug}/info/')
        self.assertEqual(blocked.status_code, 302)

        CommunityMember.objects.create(user=self.user, community=self.community)
        CommunityMember.objects.create(user=self.sender, community=self.community)
        sender_profile = self.sender.profile
        sender_profile.campus = 'SRM Ramapuram (RMP)'
        sender_profile.course = 'B.Tech'
        sender_profile.save(update_fields=['campus', 'course'])
        allowed = self.client.get(f'/community/{self.community.slug}/info/')
        self.assertEqual(allowed.status_code, 200)
        self.assertContains(allowed, 'Community Sender')
        self.assertContains(allowed, 'SRM BTech student')
        self.assertContains(allowed, 'Mute notifications')

    def test_anonymous_group_info_hides_member_identities(self):
        self.community.is_anonymous = True
        self.community.save(update_fields=['is_anonymous'])
        CommunityMember.objects.create(user=self.user, community=self.community)
        CommunityMember.objects.create(user=self.sender, community=self.community)

        response = self.client.get(f'/community/{self.community.slug}/info/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['members'], [])
        self.assertNotContains(response, 'Community Sender')
        self.assertNotContains(response, f'/profile/{self.sender.id}/')
        self.assertNotContains(response, 'Members —')

    @patch('home.views.messaging.send_each_for_multicast')
    @patch('home.views.get_firebase_app')
    def test_message_push_only_targets_joined_unmuted_members(self, firebase_app, send_multicast):
        CommunityMember.objects.bulk_create([
            CommunityMember(user=self.user, community=self.community),
            CommunityMember(user=self.sender, community=self.community),
            CommunityMember(user=self.muted, community=self.community),
        ])
        CommunityMute.objects.create(user=self.muted, community=self.community, is_muted=True)
        FCMToken.objects.create(user=self.user, token='recipient-token')
        FCMToken.objects.create(user=self.sender, token='sender-token')
        FCMToken.objects.create(user=self.muted, token='muted-token')
        FCMToken.objects.create(user=self.outsider, token='outsider-token')

        response = self.client.post(
            f'/community/{self.community.slug}/',
            data=json.dumps({'text': 'Hello members'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        firebase_app.assert_called_once()
        send_multicast.assert_called_once()
        self.assertEqual(send_multicast.call_args.args[0].tokens, ['sender-token'])

    def test_refresh_groups_consecutive_messages_from_same_sender(self):
        CommunityMember.objects.bulk_create([
            CommunityMember(user=self.user, community=self.community),
            CommunityMember(user=self.sender, community=self.community),
        ])
        CommunityMessage.objects.create(
            community=self.community,
            sender=self.sender,
            text='First consecutive message',
        )
        CommunityMessage.objects.create(
            community=self.community,
            sender=self.sender,
            text='Second consecutive message',
        )

        response = self.client.get(f'/community/{self.community.slug}/')

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        rendered_chat = html.split('<div class="chat-messages" id="chat-box">', 1)[1].split(
            '<div class="chat-input-area">', 1
        )[0]
        self.assertEqual(rendered_chat.count('class="message-group received'), 1)
        self.assertEqual(rendered_chat.count('class="msg-avatar"'), 1)
        self.assertEqual(rendered_chat.count('class="msg-name-in-bubble"'), 1)
        self.assertEqual(rendered_chat.count('class="message received first"'), 1)
        self.assertEqual(rendered_chat.count('class="message received last"'), 1)
        self.assertNotIn('class="message received solo"', rendered_chat)

    def test_system_event_breaks_consecutive_message_group(self):
        CommunityMember.objects.bulk_create([
            CommunityMember(user=self.user, community=self.community),
            CommunityMember(user=self.sender, community=self.community),
        ])
        CommunityMessage.objects.create(
            community=self.community,
            sender=self.sender,
            text='Message before event',
        )
        CommunityMessage.objects.create(
            community=self.community,
            sender=self.user,
            kind=CommunityMessage.KIND_JOIN,
        )
        CommunityMessage.objects.create(
            community=self.community,
            sender=self.sender,
            text='Message after event',
        )

        response = self.client.get(f'/community/{self.community.slug}/')
        html = response.content.decode()
        rendered_chat = html.split('<div class="chat-messages" id="chat-box">', 1)[1].split(
            '<div class="chat-input-area">', 1
        )[0]

        self.assertEqual(rendered_chat.count('class="message-group received'), 2)
        self.assertEqual(rendered_chat.count('class="system-message"'), 1)

    def test_unjoined_communities_do_not_contribute_unread_queries_or_counts(self):
        joined = Community.objects.create(name='Joined', slug='joined')
        CommunityMember.objects.create(user=self.user, community=joined)
        CommunityMessage.objects.create(community=joined, sender=self.sender, text='visible')
        CommunityMessage.objects.create(community=self.community, sender=self.sender, text='must not count')

        response = self.client.get('/api/communities/list/')
        payload = response.json()
        by_slug = {item['slug']: item for item in payload['communities']}

        self.assertEqual(response.status_code, 200)
        self.assertEqual(by_slug['joined']['unread_count'], 1)
        self.assertEqual(by_slug['campus-circle']['unread_count'], 0)
        self.assertEqual(payload['total_unread'], 1)

    def test_joined_communities_are_first_and_knotspot_is_seeded(self):
        joined = Community.objects.create(name='Joined Last Alphabetically', slug='joined-last')
        CommunityMember.objects.create(user=self.user, community=joined)

        response = self.client.get('/api/communities/list/')
        communities = response.json()['communities']

        self.assertEqual(response.status_code, 200)
        self.assertEqual(communities[0]['slug'], joined.slug)
        self.assertTrue(communities[0]['is_member'])
        self.assertIn('knotspot', [community['slug'] for community in communities])

        page = self.client.get('/community/')
        page_communities = page.context['communities']
        self.assertEqual(page_communities[0].slug, joined.slug)
        self.assertTrue(page_communities[0].is_member)


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

    def test_user_delete_comment_with_replies_soft_deletes_placeholder(self):
        comment = KnotComment.objects.create(post=self.post, user=self.owner, content='Owner parent')
        reply = KnotComment.objects.create(post=self.post, user=self.other, parent=comment, content='Visible reply')
        self.client.force_login(self.owner)

        response = self._post_json(f'/api/knots/comments/{comment.id}/delete/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['data']['soft_deleted'])
        comment.refresh_from_db()
        self.assertTrue(comment.is_deleted)
        self.assertEqual(comment.content, '')
        self.assertTrue(KnotComment.objects.filter(id=reply.id, parent=comment).exists())

    def test_admin_can_hard_delete_comment_and_all_replies_with_force(self):
        comment = KnotComment.objects.create(post=self.post, user=self.other, content='Remove whole thread')
        child = KnotComment.objects.create(post=self.post, user=self.owner, parent=comment, content='Child reply')
        grandchild = KnotComment.objects.create(post=self.post, user=self.other, parent=child, content='Nested reply')
        self.client.force_login(self.admin)

        response = self._post_json(f'/api/knots/comments/{comment.id}/delete/', {'force': True})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['data']['hard_deleted'])
        self.assertFalse(KnotComment.objects.filter(id__in=[comment.id, child.id, grandchild.id]).exists())

    def test_non_admin_cannot_force_delete_comment_thread(self):
        comment = KnotComment.objects.create(post=self.post, user=self.owner, content='Protected parent')
        reply = KnotComment.objects.create(post=self.post, user=self.other, parent=comment, content='Protected reply')
        self.client.force_login(self.owner)

        response = self._post_json(f'/api/knots/comments/{comment.id}/delete/', {'force': True})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(KnotComment.objects.filter(id__in=[comment.id, reply.id]).exists())

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

    def test_public_can_read_knots_feed_but_actions_prompt_login(self):
        response = self.client.get('/knots/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Library hours')
        self.assertContains(response, 'id="knotLoginPrompt"')
        self.assertContains(response, 'viewerAuthenticated = false')
        self.assertContains(response, 'data-action="require-login"', html=False)
        self.assertContains(response, 'You can read Knots publicly')
        self.assertContains(response, 'content="index, follow"', html=False)

    def test_public_can_read_knot_detail_and_replies(self):
        root = KnotComment.objects.create(post=self.post, user=self.other, content='Public parent')
        reply = KnotComment.objects.create(post=self.post, user=self.owner, parent=root, content='Public reply')

        detail = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')
        replies = self.client.get(f'/api/knots/comments/{root.id}/replies/')

        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Public parent')
        self.assertContains(detail, 'Log in to comment on this Knot')
        self.assertEqual(replies.status_code, 200)
        self.assertEqual(replies.json()['data'][0]['id'], reply.id)
        self.assertFalse(replies.json()['data'][0]['can_report'])

    def test_admin_sees_anonymous_knot_author_email_only_for_moderation(self):
        self.post.is_anonymous = True
        self.post.save(update_fields=['is_anonymous'])

        self.client.force_login(self.admin)
        admin_response = self.client.get('/knots/')

        self.assertContains(admin_response, 'Anonymous')
        self.assertContains(admin_response, 'class="knot-admin-email"', html=False)
        self.assertContains(admin_response, self.owner.email)

        self.client.force_login(self.other)
        user_response = self.client.get('/knots/')
        self.assertContains(user_response, 'Anonymous')
        self.assertNotContains(user_response, 'class="knot-admin-email"', html=False)
        self.assertNotContains(user_response, self.owner.email)

    def test_knot_report_uses_custom_reason_sheet_instead_of_browser_confirm(self):
        self.client.force_login(self.other)

        response = self.client.get('/knots/')

        self.assertContains(response, 'id="reportSheet"')
        self.assertContains(response, 'id="knotReportForm"')
        self.assertContains(response, 'value="harassment"')
        self.assertContains(response, 'value="unsafe"')
        self.assertContains(response, 'value="misinformation"')
        self.assertContains(response, 'id="reportDetails"')
        self.assertContains(response, 'data-action="report-post"', html=False)
        self.assertContains(response, 'openReportSheet(card)')
        self.assertContains(response, "details:normalizePlainInput(details?details.value:'')", html=False)
        self.assertNotContains(response, "confirm('Report this Knot", html=False)

    def test_knots_feed_has_one_time_rules_dialog(self):
        self.client.force_login(self.owner)

        response = self.client.get('/knots/')

        self.assertContains(response, 'id="knotRulesDialog"')
        self.assertContains(response, 'Knots community rules')
        self.assertContains(response, 'No vulgar words, NSFW content, harassment or character defamation.')
        self.assertContains(response, 'No spam, self-promotion or malicious links.')
        self.assertContains(response, 'More → Feedback')
        self.assertContains(response, 'knotspot.knots.rulesAccepted.v1')
        self.assertContains(response, "localStorage.setItem(knotRulesStorageKey, '1')")
        self.assertContains(response, 'data-action="agree-rules"', html=False)

    def test_knot_report_stores_selected_reason_and_custom_details(self):
        self.client.force_login(self.other)

        response = self._post_json(f'/api/knots/{self.post.id}/report/', {
            'reason': 'harassment',
            'details': 'Targeting a student by name',
        })

        self.assertEqual(response.status_code, 201)
        report = KnotReport.objects.get(post=self.post, reporter=self.other)
        self.assertEqual(report.reason, 'harassment')
        self.assertEqual(report.details, 'Targeting a student by name')

    def test_knots_seo_login_and_about_copy_are_present(self):
        login_response = self.client.get('/login/')
        about_response = self.client.get('/about/')
        seo_response = self.client.get('/knots-campus-discussions/')
        sitemap_response = self.client.get('/sitemap.xml')

        self.assertContains(login_response, 'Knots Campus Threads')
        self.assertContains(login_response, 'href="/knots/"', html=False)
        self.assertContains(about_response, 'KnotSpot was founded, owned, and developed by')
        self.assertContains(about_response, 'who is the developer of KnotSpot')
        self.assertContains(about_response, 'Knots Campus Threads')
        self.assertContains(seo_response, 'Knots Campus Discussion Threads')
        self.assertContains(seo_response, 'Public Reading, Login-Only Participation')
        self.assertContains(seo_response, 'CollectionPage')
        self.assertContains(login_response, 'href="/knots/"', html=False)
        self.assertContains(about_response, 'href="/knots/"', html=False)
        self.assertContains(sitemap_response, 'https://knotspot.online/knots/')
        self.assertContains(sitemap_response, 'https://knotspot.online/knots-campus-discussions/')

    def test_knot_list_excerpt_decodes_html_entities_for_readable_google_safe_text(self):
        KnotPost.objects.create(
            user=self.owner,
            title='Freshers in SRM Ramapuram',
            content='<p>Hey guys I&#x27;m anuhiya, I&#x27;m a fresher in cse IOT. Let&#x27;s all meet.</p>',
            college='SRM',
            campus='Vadapalani Campus',
            is_anonymous=True,
        )

        response = self.client.get('/knots/')

        rendered = response.content.decode()
        self.assertIn("I'm anuhiya", rendered.replace('&#x27;', "'"))
        self.assertIn("Let's all meet", rendered.replace('&#x27;', "'"))
        self.assertNotContains(response, 'I&amp;#x27;m', html=False)
        self.assertNotContains(response, 'Let&amp;#x27;s', html=False)
        self.assertNotContains(response, 'DiscussionForumPosting')
        self.assertContains(response, 'ItemList')

    def test_qotd_shows_author_profile_hook_and_suggestion_privacy_note(self):
        question = DailyQuestion.objects.create(
            question_text='What do you do after class?',
            created_by=self.other,
            is_admin_question=False,
            date=timezone.now().date(),
            is_active=True,
        )
        QuestionOption.objects.create(question=question, text='Library', order=0)
        QuestionOption.objects.create(question=question, text='Room', order=1)
        Profile.objects.filter(user=self.owner).update(age=20, gender='male', native_place='Chennai')
        self.client.force_login(self.owner)
        session = self.client.session
        session['skipped_verification'] = True
        session.save()

        response = self.client.get('/')
        api_response = self.client.get('/api/question-of-the-day/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'function qotdTriggerMarkup(question)')
        self.assertContains(response, 'class="qotd-trigger-author"')
        self.assertContains(response, '.qotd-widget.expanded .qotd-trigger-question')
        self.assertContains(response, 'white-space: normal')
        self.assertNotContains(response, 'var profileAttr = questioner.type', html=False)
        self.assertNotContains(response, 'qotd-trigger-author" + profileAttr', html=False)
        self.assertContains(response, "avatarEl.dataset.qotdProfileUrl = '/profile/' + encodeURIComponent(q.questioner.id) + '/'", html=False)
        self.assertContains(response, 'window.location.href = profileTarget.dataset.qotdProfileUrl')
        self.assertNotContains(response, 'id="qotdAuthorSlot"')
        self.assertNotContains(response, 'id="qotdQuestionText"')
        self.assertContains(response, 'Your profile will be visible to others if your question is selected.')
        data = api_response.json()['question']['questioner']
        self.assertEqual(data['type'], 'user')
        self.assertEqual(data['id'], self.other.id)
        self.assertEqual(data['name'], self.other.profile.name)

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

    def test_create_allows_one_knot_every_five_minutes(self):
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
        self.assertIn('one Knot every 5 minutes', blocked.json()['error'])
        self.assertFalse(KnotPost.objects.filter(title='Second Knot').exists())

        KnotPost.objects.filter(id=recent.id).update(
            created_at=timezone.now() - timedelta(minutes=5, seconds=1)
        )
        allowed = self._post_json('/knots/create/', {
            'title': 'After Cooldown',
            'content': 'This one is allowed now.',
            'college': '',
            'campus': '',
        })

        self.assertEqual(allowed.status_code, 201)

    def test_feed_paginates_twelve_knots_per_page(self):
        KnotPost.objects.bulk_create([
            KnotPost(
                user=self.owner,
                title=f'Paginated Knot {index:02d}',
                content=f'Pagination body {index}',
                college='SRM',
                campus='SRM Kattankulathur (KTR)',
            )
            for index in range(24)
        ])
        self.client.force_login(self.owner)

        first_page = self.client.get('/knots/?page=1&sort=newest&filters=1')
        second_page = self.client.get('/knots/?page=2&sort=newest&filters=1')
        third_page = self.client.get('/knots/?page=3&sort=newest&filters=1')

        self.assertEqual(len(first_page.context['posts']), 12)
        self.assertEqual(len(second_page.context['posts']), 12)
        self.assertEqual(len(third_page.context['posts']), 1)
        self.assertTrue(first_page.context['posts'].has_next())
        self.assertTrue(second_page.context['posts'].has_previous())
        self.assertContains(first_page, 'Load more')
        first_ids = {post.id for post in first_page.context['posts']}
        second_ids = {post.id for post in second_page.context['posts']}
        self.assertFalse(first_ids & second_ids)

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

    @patch('home.views.send_push_to_user')
    @patch('home.knot_views.broadcast_event')
    def test_knot_comment_notifies_post_owner_with_push_and_in_app_toast(self, broadcast, push):
        self.client.force_login(self.other)

        with self.captureOnCommitCallbacks(execute=True):
            response = self._post_json(f'/api/knots/{self.post.id}/comments/', {
                'content': 'Can confirm the library is open.',
            })

        self.assertEqual(response.status_code, 201)
        comment = KnotComment.objects.get(content='Can confirm the library is open.')
        push.assert_called_once()
        self.assertEqual(push.call_args.args[0], self.owner)
        self.assertEqual(push.call_args.args[1], 'New comment on your Knot')
        self.assertEqual(push.call_args.args[3], f'/knots/{self.post.id}/{self.post.slug}/#comment-{comment.id}')
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.args[0], f'chat_{self.owner.id}')
        self.assertEqual(broadcast.call_args.args[1], 'knot_activity')
        self.assertEqual(broadcast.call_args.args[2]['kind'], 'knot_comment')
        self.assertEqual(broadcast.call_args.args[2]['comment_id'], comment.id)

    @patch('home.views.send_push_to_user')
    @patch('home.knot_views.broadcast_event')
    def test_knot_reply_notifies_parent_comment_owner_even_for_reply_chains(self, broadcast, push):
        parent = KnotComment.objects.create(post=self.post, user=self.other, content='Parent question')
        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self._post_json(f'/api/knots/{self.post.id}/comments/', {
                'content': 'Replying to parent',
                'parent_id': parent.id,
            })

        self.assertEqual(response.status_code, 201)
        reply = KnotComment.objects.get(content='Replying to parent')
        push.assert_called_once()
        self.assertEqual(push.call_args.args[0], self.other)
        self.assertEqual(push.call_args.args[1], 'New reply to your comment')
        broadcast.assert_called_once()
        self.assertEqual(broadcast.call_args.args[0], f'chat_{self.other.id}')
        self.assertEqual(broadcast.call_args.args[2]['kind'], 'knot_reply')
        self.assertEqual(broadcast.call_args.args[2]['comment_id'], reply.id)

    @patch('home.views.send_push_to_user')
    @patch('home.knot_views.broadcast_event')
    def test_knot_comment_does_not_notify_self(self, broadcast, push):
        self.client.force_login(self.owner)

        with self.captureOnCommitCallbacks(execute=True):
            response = self._post_json(f'/api/knots/{self.post.id}/comments/', {
                'content': 'Commenting on my own Knot',
            })

        self.assertEqual(response.status_code, 201)
        push.assert_not_called()
        broadcast.assert_not_called()

    def test_global_browser_listener_shows_in_app_knot_activity_toast(self):
        self.client.force_login(self.owner)
        response = self.client.get('/knots/')

        self.assertContains(response, "userChannel.bind('knot_activity'")
        self.assertContains(response, "showGlobalToast(`${title}${body}`, url);", html=False)

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
        self.assertFalse(data[0]['can_admin_delete'])

        self.client.force_login(self.admin)
        admin_response = self.client.get(f'/api/knots/comments/{root.id}/replies/')
        self.assertTrue(admin_response.json()['data'][0]['can_admin_delete'])

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

    def test_admin_comment_menu_has_separate_hard_delete_action(self):
        KnotComment.objects.create(post=self.post, user=self.other, content='Moderate this comment')
        self.client.force_login(self.admin)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertContains(response, 'data-action="delete-comment"', html=False)
        self.assertContains(response, 'data-action="admin-delete-comment"', html=False)
        self.assertContains(response, '>Admin delete</button>', html=False)
        self.assertContains(response, "var adminDelete = item.can_admin_delete", html=False)
        self.assertContains(response, "body:JSON.stringify({force:true})", html=False)
        self.assertContains(response, "toast('Comment thread deleted')", html=False)

    def test_admin_can_hard_delete_soft_deleted_placeholder_from_menu(self):
        KnotComment.objects.create(post=self.post, user=self.other, content='', is_deleted=True)
        self.client.force_login(self.admin)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertContains(response, 'Comment deleted')
        self.assertContains(response, 'data-action="admin-delete-comment"', html=False)

    def test_comment_menu_can_open_above_sticky_comment_bar(self):
        KnotComment.objects.create(post=self.post, user=self.other, content='Only comment')
        self.client.force_login(self.owner)

        response = self.client.get(f'/knots/{self.post.id}/{self.post.slug}/')

        self.assertContains(response, '.comments-panel { margin-top: 12px; border: 0; border-radius: 24px; background: #fff; overflow: visible;')
        self.assertContains(response, '.knot-menu.open-up')
        self.assertContains(response, 'function placeMenu(menu, button)')
        self.assertContains(response, "menu.classList.add('open-up');")
        self.assertContains(response, '#commentList > .comment.menu-open { z-index: 60; }')
        self.assertContains(response, "commentItem.classList.toggle('menu-open', open);")

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
