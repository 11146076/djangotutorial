from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from posts.models import Category, Follow, Like, Notification, Post, PostComment, SearchLog, Tag
from posts.notifications import notify_followers_new_post, notify_post_commented, notify_post_liked
from posts.recommendations import build_post_suggestions, extract_bold_terms, get_today_meal_recommendations

User = get_user_model()


class TodayMealRecommendationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="foodie",
            email="foodie@example.com",
            password="test-pass",
        )
        self.author = User.objects.create_user(
            username="chef",
            email="chef@example.com",
            password="test-pass",
        )
        self.other_author = User.objects.create_user(
            username="snackboss",
            email="snackboss@example.com",
            password="test-pass",
        )
        self.noodle_category = Category.objects.create(name="麵食")
        self.dessert_category = Category.objects.create(name="甜點")
        self.spicy_tag = Tag.objects.create(name="微辣")
        self.sweet_tag = Tag.objects.create(name="甜食")

    def _post(self, *, title, author=None, category=None, tags=(), visibility=Post.VISIBILITY_PUBLIC, likes=0):
        post = Post.objects.create(
            author=author or self.author,
            category=category,
            title=title,
            content=f"<p>{title}</p>",
            visibility=visibility,
            like_count=likes,
        )
        if tags:
            post.tags.add(*tags)
        return post

    def test_recommendations_prioritize_user_interaction_preferences(self):
        seed = self._post(title="牛肉拉麵紀錄", category=self.noodle_category, tags=[self.spicy_tag])
        matching = self._post(title="今日豚骨拉麵", category=self.noodle_category, tags=[self.spicy_tag])
        unrelated_popular = self._post(
            title="超人氣甜甜圈",
            author=self.other_author,
            category=self.dessert_category,
            tags=[self.sweet_tag],
            likes=50,
        )
        Like.objects.create(user=self.user, post=seed)
        SearchLog.objects.create(user=self.user, keyword="拉麵")

        recommendations = get_today_meal_recommendations(self.user, limit=3)

        self.assertGreaterEqual(len(recommendations), 2)
        self.assertEqual(recommendations[0].post.category, self.noodle_category)
        self.assertIn(recommendations[0].post, {seed, matching})
        self.assertTrue(recommendations[0].reason)
        self.assertIn(unrelated_popular, [rec.post for rec in recommendations])

    def test_recommendations_fall_back_to_public_posts_for_new_users(self):
        public_post = self._post(title="清爽雞肉飯", category=self.noodle_category)
        own_post = self._post(title="自己的晚餐", author=self.user, category=self.noodle_category)
        private_post = self._post(
            title="私密宵夜",
            category=self.dessert_category,
            visibility=Post.VISIBILITY_PRIVATE,
        )

        recommendations = get_today_meal_recommendations(self.user, limit=3)
        recommended_posts = [rec.post for rec in recommendations]

        self.assertIn(public_post, recommended_posts)
        self.assertNotIn(own_post, recommended_posts)
        self.assertNotIn(private_post, recommended_posts)

    def test_feed_shows_today_meal_recommendations_for_authenticated_homepage(self):
        recommended = self._post(title="今天適合吃雞肉飯", category=self.noodle_category)

        self.client.force_login(self.user)
        response = self.client.get(reverse("posts:feed"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "今天吃什麼？")
        self.assertContains(response, recommended.title)

    def test_recommendations_backfill_when_only_own_posts_exist(self):
        own_a = self._post(title="我的早餐", author=self.user, category=self.noodle_category)
        own_b = self._post(title="我的午餐", author=self.user, category=self.noodle_category, likes=3)

        recommendations = get_today_meal_recommendations(self.user, limit=3)

        self.assertGreaterEqual(len(recommendations), 2)
        self.assertIn(own_b, [rec.post for rec in recommendations])


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
