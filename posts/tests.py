from django.contrib.auth import get_user_model
from django.test import TestCase

from posts.models import Category, Collection, Post, SearchLog, Tag
from posts.recommendations import (
    build_post_suggestions,
    extract_bold_terms,
    get_personalized_recommendations,
)

User = get_user_model()


class RecommendationHelperTests(TestCase):
    def test_extract_bold_terms(self):
        self.assertEqual(extract_bold_terms("今天試試 **拉麵**，暖胃又飽足。"), ["拉麵"])

    def test_build_post_suggestions_tag_match(self):
        tag = Tag.objects.create(name="拉麵")
        suggestions = build_post_suggestions("推薦你吃 **拉麵**，湯頭濃郁。")
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["type"], "tag")
        self.assertEqual(suggestions[0]["id"], tag.id)
        self.assertEqual(suggestions[0]["name"], "拉麵")

    def test_build_post_suggestions_search_fallback(self):
        suggestions = build_post_suggestions("來碗 **滷肉飯** 吧。")
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["type"], "search")
        self.assertEqual(suggestions[0]["query"], "滷肉飯")


class PersonalizedRecommendationTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            username="viewer", email="viewer@test.com", password="pass12345"
        )
        self.author = User.objects.create_user(
            username="chef", email="chef@test.com", password="pass12345"
        )
        self.ramen_tag = Tag.objects.create(name="拉麵")
        self.category = Category.objects.create(name="日式")
        self.collected_post = Post.objects.create(
            author=self.author,
            title="深夜拉麵",
            content="湯頭濃郁",
            category=self.category,
        )
        self.collected_post.tags.add(self.ramen_tag)
        self.recommended_post = Post.objects.create(
            author=self.author,
            title="豚骨拉麵推薦",
            content="好吃",
            category=self.category,
        )
        self.recommended_post.tags.add(self.ramen_tag)
        self.other_post = Post.objects.create(
            author=self.author,
            title="無關貼文",
            content="甜點",
        )

    def test_recommend_from_collection_tags(self):
        Collection.objects.create(user=self.viewer, post=self.collected_post)
        items, meta = get_personalized_recommendations(self.viewer, limit=5)
        self.assertEqual(meta["strategy"], "personalized")
        post_ids = [item.post.id for item in items]
        self.assertIn(self.recommended_post.id, post_ids)
        self.assertNotIn(self.collected_post.id, post_ids)

    def test_recommend_from_search_logs(self):
        SearchLog.objects.create(user=self.viewer, keyword="拉麵")
        items, meta = get_personalized_recommendations(self.viewer, limit=5)
        self.assertEqual(meta["strategy"], "personalized")
        post_ids = [item.post.id for item in items]
        self.assertIn(self.recommended_post.id, post_ids)

    def test_popular_fallback_without_signals(self):
        items, meta = get_personalized_recommendations(self.viewer, limit=3)
        self.assertEqual(meta["strategy"], "popular")
        self.assertTrue(items)


class NotificationServiceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.author = User.objects.create_user(username="author", email="author@example.com", password="pw")
        self.actor = User.objects.create_user(username="actor", email="actor@example.com", password="pw")
        self.follower = User.objects.create_user(username="follower", email="follower@example.com", password="pw")
        self.post = Post.objects.create(author=self.author, title="拉麵", content="好吃")

    def test_like_creates_notification_for_post_author(self):
        like = Like.objects.create(user=self.actor, post=self.post)

        notify_post_liked(like)

        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.author)
        self.assertEqual(notification.actor, self.actor)
        self.assertEqual(notification.notification_type, Notification.TYPE_POST_LIKED)
        self.assertEqual(notification.post, self.post)

    def test_self_like_does_not_create_notification(self):
        like = Like.objects.create(user=self.author, post=self.post)

        notify_post_liked(like)

        self.assertFalse(Notification.objects.exists())

    def test_comment_notifies_post_author(self):
        comment = PostComment.objects.create(post=self.post, author=self.actor, content="看起來很好吃")

        notify_post_commented(comment)

        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.author)
        self.assertEqual(notification.notification_type, Notification.TYPE_POST_COMMENTED)
        self.assertEqual(notification.comment, comment)

    def test_reply_notifies_parent_author(self):
        parent = PostComment.objects.create(post=self.post, author=self.follower, content="想吃")
        reply = PostComment.objects.create(post=self.post, author=self.actor, parent=parent, content="一起去")

        notify_post_commented(reply)

        recipients = set(Notification.objects.values_list("recipient__username", flat=True))
        self.assertEqual(recipients, {"author", "follower"})
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.follower,
                notification_type=Notification.TYPE_COMMENT_REPLIED,
                comment=reply,
            ).exists()
        )

    def test_public_post_notifies_followers(self):
        Follow.objects.create(follower=self.follower, following=self.author)

        created = notify_followers_new_post(self.post)

        self.assertEqual(created, 1)
        notification = Notification.objects.get()
        self.assertEqual(notification.recipient, self.follower)
        self.assertEqual(notification.actor, self.author)
        self.assertEqual(notification.notification_type, Notification.TYPE_FOLLOWING_POSTED)

    def test_private_post_does_not_notify_followers(self):
        Follow.objects.create(follower=self.follower, following=self.author)
        private_post = Post.objects.create(
            author=self.author,
            title="私密",
            content="自己看",
            visibility=Post.VISIBILITY_PRIVATE,
        )

        created = notify_followers_new_post(private_post)

        self.assertEqual(created, 0)
        self.assertFalse(Notification.objects.exists())
