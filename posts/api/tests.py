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

    def test_openapi_schema_documents_ai_chat_endpoint(self):
        response = self.client.get(reverse("schema"))
        content = response.content.decode()

        self.assertIn("/api/v1/ai-chat/", content)
        self.assertIn("AI 美食助理對話", content)
