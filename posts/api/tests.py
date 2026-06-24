from django.test import Client, SimpleTestCase
from django.urls import reverse


class ApiSchemaTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_openapi_schema_endpoint_returns_yaml(self):
        response = self.client.get(reverse("schema"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("openapi:", response.content.decode().lower())

    def test_swagger_ui_url_is_registered(self):
        self.assertEqual(reverse("swagger-ui"), "/api/docs/")
        self.assertEqual(reverse("redoc"), "/api/redoc/")

    def test_openapi_schema_documents_core_endpoints(self):
        response = self.client.get(reverse("schema"))
        content = response.content.decode()

        endpoints = [
            "/api/v1/ai-chat/",
            "/api/v1/posts/",
            "/api/v1/comments/",
            "/api/v1/notifications/",
            "/api/v1/collections/",
            "/api/v1/categories/",
            "/api/v1/tags/",
            "/api/v1/users/",
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, content)
