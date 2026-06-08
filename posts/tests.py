from django.test import TestCase

from posts.models import Tag
from posts.recommendations import build_post_suggestions, extract_bold_terms


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
