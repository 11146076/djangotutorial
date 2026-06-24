from django.test import TestCase
from django.urls import reverse


class AuthTemplateTests(TestCase):
    def test_login_page_renders_google_login_link(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "使用 Google 登入")
        self.assertContains(response, "/oauth/google/login/")

    def test_register_page_renders_google_login_link(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "使用 Google 帳號繼續")
        self.assertContains(response, "/oauth/google/login/")
