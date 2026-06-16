from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


class TokenEstimateAPIViewTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_post_returns_token_analysis(self):
        text = "한국어와 English mixed prompt."
        response = self.client.post(
            reverse("token-estimate"),
            {"text": text},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["analysis"]["characters"], len(text))
        self.assertGreater(len(response.data["analysis"]["profiles"]), 0)

    def test_post_requires_text(self):
        response = self.client.post(reverse("token-estimate"), {"text": ""}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
