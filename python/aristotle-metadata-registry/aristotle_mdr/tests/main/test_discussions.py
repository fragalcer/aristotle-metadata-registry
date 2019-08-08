from django.test import TestCase, tag
from django.contrib.auth import get_user_model
from django.urls import reverse
import aristotle_mdr.models as models
import aristotle_mdr.perms as perms
import aristotle_mdr.tests.utils as utils

import logging

logger = logging.getLogger(__name__)


class PostingAndCommentingAtObjectLevel(TestCase):

    def setUp(self):
        self.steward_org = models.StewardOrganisation.objects.create(name="Test SO")
        self.wg1 = models.Workgroup.objects.create(name="Test WG 1", stewardship_organisation=self.steward_org)
        self.wg2 = models.Workgroup.objects.create(name="Test WG 2", stewardship_organisation=self.steward_org)
        self.viewer1 = get_user_model().objects.create_user('vicky@example.com', 'viewer')  # viewer 1 always posts
        self.viewer2 = get_user_model().objects.create_user('viewer2@example.com', 'viewer')
        self.manager = get_user_model().objects.create_user('mandy@example.com', 'manger')
        self.wg1.giveRoleToUser('viewer', self.viewer1)
        self.wg1.giveRoleToUser('viewer', self.viewer2)
        self.wg1.giveRoleToUser('manager', self.manager)

    def test_ViewerCanAlterPost(self):
        post = models.DiscussionPost.objects.create(author=self.viewer1, workgroup=self.wg1, title="test", body="test")
        self.assertTrue(perms.user_can_alter_post(self.viewer1, post))
        self.assertTrue(perms.user_can_alter_post(self.manager, post))
        self.assertFalse(perms.user_can_alter_post(self.viewer2, post))

    def test_ViewerCanAlterComment(self):
        post = models.DiscussionPost.objects.create(author=self.viewer1, workgroup=self.wg1, title="test", body="test")
        comment = models.DiscussionComment.objects.create(author=self.viewer2, post=post, body="test")
        self.assertFalse(perms.user_can_alter_comment(self.viewer1, comment))
        self.assertTrue(perms.user_can_alter_comment(self.manager, comment))
        self.assertTrue(perms.user_can_alter_comment(self.viewer2, comment))

    def test_comment_ordering(self):
        post = models.DiscussionPost.objects.create(author=self.viewer1, workgroup=self.wg1, title="test", body="test")
        comment1 = models.DiscussionComment.objects.create(author=self.viewer2, post=post, body="test1")
        comment2 = models.DiscussionComment.objects.create(author=self.viewer2, post=post, body="test2")
        comment3 = models.DiscussionComment.objects.create(author=self.viewer2, post=post, body="test3")

        post = models.DiscussionPost.objects.get(id=post.id)  # decache

        self.assertTrue(post.comments.all()[0:3], [comment1, comment2, comment3])
        comment1.title = "modified"
        comment1.save()
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertTrue(post.comments.all()[0:3], [comment1, comment2, comment3])
        comment2.title = "modified"
        comment2.save()
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertTrue(post.comments.all()[0:3], [comment1, comment2, comment3])

    def test_post_ordering(self):
        # Check posts ordered by modified
        post1 = models.DiscussionPost.objects.create(author=self.viewer1, workgroup=self.wg1, title="test1",
                                                     body="test")
        post2 = models.DiscussionPost.objects.create(author=self.viewer1, workgroup=self.wg1, title="test2",
                                                     body="test")
        post3 = models.DiscussionPost.objects.create(author=self.viewer1, workgroup=self.wg1, title="test3",
                                                     body="test")

        posts = models.DiscussionPost.objects.all()
        self.assertTrue(posts[0:3], [post3, post2, post1])
        post1.title = "modified"
        post1.save()
        self.assertTrue(posts[0:3], [post1, post3, post2])
        post3.title = "modified"
        post3.save()
        self.assertTrue(posts[0:3], [post3, post1, post2])


class WorkgroupMembersCanMakePostsAndComments(utils.LoggedInViewPages, TestCase):
    def setUp(self):
        super().setUp()
        self.viewer2 = get_user_model().objects.create_user('viewer2@example.com', 'viewer')  # not in any workgroup
        self.viewer3 = get_user_model().objects.create_user('viewer3@example.com',
                                                            'viewer')  # not in our "primary testing workgroup" (self.wg1)
        self.wg1.giveRoleToUser('viewer', self.viewer3)
        self.wg2 = models.Workgroup.objects.create(name="Test WG 2", stewardship_organisation=self.steward_org_1)

    def can_the_current_logged_in_user_toggle_post(self):
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")
        self.assertEqual(post.closed, False)

        response = self.client.get(reverse('aristotle:discussionsPostToggle', args=[post.id]))
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[post.id]))
        self.assertEqual(response.status_code, 302)
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertEqual(post.closed, True)

        response = self.client.get(reverse('aristotle:discussionsPostToggle', args=[post.id]))
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[post.id]))
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertEqual(post.closed, False)

    def test_viewer_can_toggle_post(self):
        self.login_viewer()
        self.can_the_current_logged_in_user_toggle_post()

    def test_superuser_can_toggle_post(self):
        self.login_superuser()
        self.can_the_current_logged_in_user_toggle_post()

    def test_manager_can_toggle_post(self):
        self.login_manager()
        self.can_the_current_logged_in_user_toggle_post()

    def test_editor_cannot_toggle_post(self):
        # Standard editors/submitters have no power to close/open posts that aren't their own.
        self.login_editor()
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")
        self.assertEqual(post.closed, False)

        response = self.client.get(reverse('aristotle:discussionsPostToggle', args=[post.id]))
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertEqual(post.closed, False)
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('aristotle:discussionsPostToggle', args=[post.id]))
        self.assertEqual(response.status_code, 403)
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertEqual(post.closed, False)

    def can_the_current_logged_in_user_post(self):
        response = self.client.get(reverse('aristotle:discussionsNew'), )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(reverse('aristotle:discussionsNew'),
                                    {
                                        'title': "New post that will not work",
                                        'body': "I am not a member of this workgroup, so this shouldn't work.",
                                        'workgroup': self.wg2.id
                                    }
                                    )
        self.assertEqual(self.wg2.discussions.count(), 0)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(self.wg1.discussions.count(), 0)
        forbidden_item = models.ObjectClass.objects.create(name="OC2", workgroup=self.wg2)
        response = self.client.post(reverse('aristotle:discussionsNew'),
                                    {
                                        'title': "New post that will not work",
                                        'body': "I am a member of this workgroup but am trying to post about an item that I'm not allowed to see.",
                                        'workgroup': self.wg1.id,
                                        'relatedItems': [forbidden_item.id]
                                    }
                                    )
        # We allow the request to add the forbidden_item to pass, but the item is never attached.
        self.assertEqual(self.wg1.discussions.count(), 1)
        self.assertEqual(self.wg1.discussions.first().relatedItems.count(), 0)
        self.assertEqual(response.status_code, 302)

        response = self.client.post(reverse('aristotle:discussionsNew'),
                                    {
                                        'title': "New post that will work",
                                        'body': "I am a member of this workgroup.",
                                        'workgroup': self.wg1.id
                                    }
                                    )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.wg1.discussions.count(), 2)

    def test_viewer_can_post_in_workgroup(self):
        self.login_viewer()
        self.can_the_current_logged_in_user_post()

    def test_editor_can_post_in_workgroup(self):
        self.login_editor()
        self.can_the_current_logged_in_user_post()

    def can_the_current_logged_in_user_comment(self):
        p1 = models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg1, title="test", body="test")
        p2 = models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg2, title="test", body="test")

        response = self.client.get(reverse('aristotle:discussionsPost', args=[p1.id]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('aristotle:discussionsPost', args=[p2.id]))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(reverse('aristotle:discussionsPostNewComment', args=[p2.id]),
                                    {'body': "I am not a member of this workgroup, so this shouldn't work."}
                                    )
        self.assertEqual(p2.comments.count(), 0)
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse('aristotle:discussionsPostNewComment', args=[p1.id]))
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[p1.id]))

        response = self.client.post(reverse('aristotle:discussionsPostNewComment', args=[p1.id]),
                                    {'body': "I am a member of this workgroup, so I can comment."}
                                    )
        self.assertEqual(p1.comments.count(), 1)
        c = p1.comments.first().id
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[p1.id]) + "#comment_%s" % c)

    def test_viewer_can_comment_in_workgroup(self):
        self.login_viewer()
        self.can_the_current_logged_in_user_comment()

    def test_editor_can_comment_in_workgroup(self):
        self.login_editor()
        self.can_the_current_logged_in_user_comment()

    def can_the_current_logged_in_user_delete_post(self):
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")

        response = self.client.post(reverse('aristotle:discussionsDeletePost', args=[post.id]))
        self.assertRedirects(response, reverse('aristotle:discussionsWorkgroup', args=[self.wg1.id]))
        self.assertEqual(models.DiscussionPost.objects.filter(id=post.id).count(), 0)

    def test_viewer_can_delete_post(self):
        self.login_viewer()
        self.can_the_current_logged_in_user_delete_post()

    def test_superuser_can_delete_post(self):
        self.login_superuser()
        self.can_the_current_logged_in_user_delete_post()

    def test_manager_can_delete_post(self):
        self.login_manager()
        self.can_the_current_logged_in_user_delete_post()

    def test_editor_cannot_delete_post(self):
        # Standard editors/submitters have no power to delete posts that aren't their own.
        self.login_editor()
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")

        response = self.client.get(reverse('aristotle:discussionsDeletePost', args=[post.id]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.DiscussionPost.objects.filter(id=post.id).count(), 1)

    def can_the_current_logged_in_user_edit_post(self):
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")

        response = self.client.get(reverse('aristotle:discussionsEditPost', args=[post.id]))
        self.assertEqual(response.status_code, 200)

        data = {
            'title': 'test',
            'body': 'edit test',
        }

        response = self.client.post(reverse('aristotle:discussionsEditPost', args=[post.id]), data)
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[post.id]))
        self.assertEqual(response.status_code, 302)
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertEqual(post.body, "edit test")

    def test_viewer_can_edit_post(self):
        self.login_viewer()
        self.can_the_current_logged_in_user_edit_post()

    def test_superuser_can_edit_post(self):
        self.login_superuser()
        self.can_the_current_logged_in_user_edit_post()

    def test_manager_can_edit_post(self):
        self.login_manager()
        self.can_the_current_logged_in_user_edit_post()

    def test_editor_cannot_edit_post(self):
        # Standard editors/submitters have no power to edit posts that aren't their own.
        self.login_editor()
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")

        response = self.client.get(reverse('aristotle:discussionsEditPost', args=[post.id]))
        self.assertEqual(response.status_code, 403)

        data = {
            'title': 'test',
            'body': 'edit test',
        }

        response = self.client.post(reverse('aristotle:discussionsEditPost', args=[post.id]), data)
        self.assertEqual(response.status_code, 403)
        post = models.DiscussionPost.objects.get(id=post.id)  # decache
        self.assertEqual(post.body, "test")

    def can_the_current_logged_in_user_delete_comment(self):
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")
        comment = models.DiscussionComment.objects.create(author=self.viewer, post=post, body="test")
        response = self.client.get(reverse('aristotle:discussionsDeleteComment', args=[comment.id]))
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[post.id]))
        self.assertEqual(models.DiscussionComment.objects.filter(id=comment.id).count(), 0)

    def test_viewer_can_delete_comment(self):
        self.login_viewer()
        self.can_the_current_logged_in_user_delete_comment()

    def test_superuser_can_delete_comment(self):
        self.login_superuser()
        self.can_the_current_logged_in_user_delete_comment()

    def test_manager_can_delete_comment(self):
        self.login_manager()
        self.can_the_current_logged_in_user_delete_comment()

    def test_editor_cannot_delete_comment(self):
        # Standard editors/submitters have no power to delete posts that aren't their own.
        self.login_editor()
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")
        comment = models.DiscussionComment.objects.create(author=self.viewer, post=post, body="test")
        response = self.client.get(reverse('aristotle:discussionsDeleteComment', args=[comment.id]))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(models.DiscussionComment.objects.filter(id=comment.id).count(), 1)

    def can_the_current_logged_in_user_edit_comment(self):
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")
        comment = models.DiscussionComment.objects.create(author=self.viewer, post=post, body="test comment")

        response = self.client.get(reverse('aristotle:discussionsEditComment', args=[comment.id]))
        self.assertEqual(response.status_code, 200)

        data = {
            'body': 'edit comment test',
        }

        response = self.client.post(reverse('aristotle:discussionsEditComment', args=[comment.id]), data)
        self.assertRedirects(response,
                             reverse('aristotle:discussionsPost', args=[post.id]) + "#comment_%s" % comment.id)
        self.assertEqual(response.status_code, 302)
        comment = models.DiscussionComment.objects.get(id=comment.id)  # decache
        self.assertEqual(comment.body, "edit comment test")

    def test_viewer_can_edit_comment(self):
        self.login_viewer()
        self.can_the_current_logged_in_user_edit_comment()

    def test_superuser_can_edit_comment(self):
        self.login_superuser()
        self.can_the_current_logged_in_user_edit_comment()

    def test_manager_can_edit_comment(self):
        self.login_manager()
        self.can_the_current_logged_in_user_edit_comment()

    def test_editor_cannot_edit_comment(self):
        # Standard editors/submitters have no power to edit posts that aren't their own.
        self.login_editor()
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")
        comment = models.DiscussionComment.objects.create(author=self.viewer, post=post, body="test comment")

        response = self.client.get(reverse('aristotle:discussionsEditComment', args=[comment.id]))
        self.assertEqual(response.status_code, 403)

        data = {
            'body': 'edit comment test',
        }

        response = self.client.post(reverse('aristotle:discussionsEditComment', args=[comment.id]), data)
        self.assertEqual(response.status_code, 403)
        comment = models.DiscussionComment.objects.get(id=comment.id)  # decache
        self.assertEqual(comment.body, "test comment")

    def test_post_to_workgroup_from_URL(self):
        # If a user posts clicks a link to go to their workgroup's post page let them.
        self.login_viewer()
        response = self.client.get(reverse('aristotle:discussionsNew') + "?workgroup={}".format(self.wg1.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.context['form'].initial['workgroup']), int(self.wg1.id))

        response = self.client.get(reverse('aristotle:discussionsNew') + "?workgroup={}".format(self.wg2.id))
        self.assertRedirects(response, reverse('aristotle:discussionsNew'))

    def test_post_to_workgroup_from_URL_for_item(self):
        # If a user posts clicks a link to go to their workgroup's post page let them.
        self.login_viewer()
        allowed_item = models.ObjectClass.objects.create(name="OC1", workgroup=self.wg1)
        other_allowed_item = models.ObjectClass.objects.create(name="OC2", workgroup=self.wg1)
        forbidden_item = models.ObjectClass.objects.create(name="OC3", workgroup=self.wg2)
        response = self.client.get(
            reverse('aristotle:discussionsNew') + "?workgroup={0}&item={1}".format(self.wg1.id, allowed_item.id))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(int(response.context['form'].initial['workgroup']), int(self.wg1.id))
        related = set([i.id for i in response.context['form'].initial['relatedItems']])
        expected = set([allowed_item.id])
        self.assertEqual(related, expected)
        self.assertTrue(response.status_code, 200)

        response = self.client.get(
            reverse('aristotle:discussionsNew') + "?workgroup={0}&item={1}&item={2}".format(self.wg1.id,
                                                                                            allowed_item.id,
                                                                                            other_allowed_item.id))
        related = set([i.id for i in response.context['form'].initial['relatedItems']])
        expected = set([allowed_item.id, other_allowed_item.id])
        self.assertEqual(related, expected)
        self.assertTrue(response.status_code, 200)

        response = self.client.get(
            reverse('aristotle:discussionsNew') + "?workgroup={0}&item={1}".format(self.wg1.id, forbidden_item.id))
        related = set([i.pk for i in response.context['form'].initial['relatedItems']])
        expected = set([])
        self.assertEqual(related, expected)
        self.assertTrue(response.status_code, 200)

        response = self.client.get(
            reverse('aristotle:discussionsNew') + "?workgroup={0}&item={1}&item={2}".format(self.wg1.id,
                                                                                            forbidden_item.id,
                                                                                            other_allowed_item.id))
        related = set([i.pk for i in response.context['form'].initial['relatedItems']])
        expected = set([other_allowed_item.id])
        self.assertEqual(related, expected)
        self.assertEqual(response.status_code, 200)

    def test_post_to_closed_discussion(self):
        self.login_viewer()

        p1 = models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg1, title="test", body="test")

        response = self.client.get(reverse('aristotle:discussionsPost', args=[p1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(p1.comments.count(), 0)

        response = self.client.get(reverse('aristotle:discussionsPostNewComment', args=[p1.id]))
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[p1.id]))

        response = self.client.post(reverse('aristotle:discussionsPostNewComment', args=[p1.id]),
                                    {'body': "Post is open, so I can comment."}
                                    )
        self.assertEqual(p1.comments.count(), 1)
        c = p1.comments.first().id

        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[p1.id]) + "#comment_%s" % c)

        p1.closed = True
        p1.save()
        response = self.client.post(reverse('aristotle:discussionsPostNewComment', args=[p1.id]),
                                    {'body': "Post is closed, so I can NOT comment."}, follow=True
                                    )

        self.assertEqual(p1.comments.count(), 1)
        self.assertRedirects(response, reverse('aristotle:discussionsPost', args=[p1.id]))

        _messages = list(response.context['messages'])
        self.assertEqual(len(_messages), 1)
        self.assertEqual("This post is closed. Your comment was not added.", _messages[0].message)

    @tag('notify_comment')
    def test_user_is_notified_of_comment_and_is_linked_to_post(self):
        # Create post as editor
        post = models.DiscussionPost.objects.create(
            workgroup=self.wg1,
            title='This item is very good',
            body='Very good',
            author=self.editor
        )

        # Create comment as viewer
        comment = models.DiscussionComment.objects.create(
            body='No it is not good',
            post=post,
            author=self.viewer
        )

        # Get editors notifications
        notifications = self.editor.notifications.unread()
        self.assertEqual(len(notifications), 1)
        noti = notifications[0]

        # Check that notification redirects to post page
        post_page_url = reverse(
            'aristotle:discussionsPost',
            args=[post.id]
        )
        notify_redirect_url = reverse(
            'aristotle:notify_redirect',
            args=[noti.actor_content_type.id, noti.actor_object_id]
        )


class ViewDiscussionPostPage(utils.LoggedInViewPages, TestCase):
    def setUp(self):
        super().setUp()
        self.viewer2 = get_user_model().objects.create_user('viewer2@example.com', 'viewer')  # not in any workgroup
        self.viewer3 = get_user_model().objects.create_user('viewer3@example.com',
                                                            'viewer')  # not in our "primary testing workgroup" (self.wg1)
        self.wg2.giveRoleToUser('viewer', self.viewer3)

    def test_member_can_see_posts(self):
        self.login_viewer()
        self.wg3 = models.Workgroup.objects.create(name="Test WG 3", stewardship_organisation=self.steward_org_1)
        self.wg3.giveRoleToUser('viewer', self.viewer)

        p1 = models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg1, title="test", body="test")
        p2 = models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg1, title="test", body="test")
        p3 = models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg3, title="test", body="test")

        response = self.client.get(reverse('aristotle:discussionsWorkgroup', args=[self.wg1.id]))
        self.assertEqual(len(response.context['discussions']), 2)

        self.assertTrue(p1 in response.context['discussions'].all())
        self.assertTrue(p2 in response.context['discussions'].all())
        self.assertTrue(p3 not in response.context['discussions'].all())

        response = self.client.get(reverse('aristotle:discussions'))
        self.assertEqual(len(response.context['discussions']), 3)

        self.assertTrue(p1 in response.context['discussions'].all())
        self.assertTrue(p2 in response.context['discussions'].all())
        self.assertTrue(p3 in response.context['discussions'].all())

    def test_nonmember_cannot_see_posts(self):
        self.login_viewer()
        self.wg3 = models.Workgroup.objects.create(name="Test WG 3", stewardship_organisation=self.steward_org_1)

        response = self.client.get(reverse('aristotle:discussionsWorkgroup', args=[self.wg3.id]))
        self.assertEqual(response.status_code, 403)

    def test_viewer_can_see_posts_for_a_workgroup(self):
        self.login_viewer()
        post = models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg1, title="test", body="test")
        models.DiscussionPost.objects.create(author=self.su, workgroup=self.wg2, title="test", body="test")
        response = self.client.get(reverse('aristotle:discussionsWorkgroup', args=[self.wg1.id]))
        self.assertEqual(len(response.context['discussions']), 1)
        self.assertEqual(response.context['discussions'][0], post)

    def test_viewer_can_see_post_in_workgroup(self):
        post = models.DiscussionPost.objects.create(author=self.viewer, workgroup=self.wg1, title="test", body="test")
        models.DiscussionComment.objects.create(author=self.viewer2, post=post, body="test")
        self.login_viewer()
        response = self.client.get(reverse('aristotle:discussionsPost', args=[post.id]))
        self.assertEqual(response.status_code, 200)
        self.wg1.removeRoleFromUser('viewer', self.viewer)
        response = self.client.get(reverse('aristotle:discussionsPost', args=[post.id]))
        self.assertEqual(response.status_code, 403)
