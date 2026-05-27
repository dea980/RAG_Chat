from django.test import SimpleTestCase


class TokenUtilsTestCase(SimpleTestCase):
    def test_analyze_text_returns_counts_for_exact_and_estimated_profiles(self):
        from chat.token_utils import analyze_text

        result = analyze_text("안녕하세요. Galaxy S25 price is 1199.99 USD.")

        self.assertEqual(result["characters"], 39)
        self.assertGreater(result["bytes"], result["characters"])

        profiles = {row["id"]: row for row in result["profiles"]}
        self.assertIn("openai_o200k", profiles)
        self.assertIn("openai_cl100k", profiles)
        self.assertIn("gemini_estimate", profiles)

        self.assertGreater(profiles["openai_o200k"]["tokens"], 0)
        self.assertIn(profiles["openai_o200k"]["method"], {"exact", "fallback"})
        self.assertEqual(profiles["gemini_estimate"]["method"], "estimate")

    def test_language_samples_include_korean_english_and_code(self):
        from chat.token_utils import language_sample_comparison

        result = language_sample_comparison()
        languages = {row["language"] for row in result}

        self.assertTrue({"Korean", "English", "Code"}.issubset(languages))
        self.assertTrue(all(row["profiles"] for row in result))
