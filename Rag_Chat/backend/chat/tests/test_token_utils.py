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

    def test_list_test_sets_returns_parallel_and_content_type_entries(self):
        from chat.token_utils import list_test_sets

        result = list_test_sets()
        ids = {row["id"] for row in result}
        categories = {row["category"] for row in result}

        self.assertIn("parallel_greeting", ids)
        self.assertIn("content_code", ids)
        self.assertEqual(categories, {"parallel", "content_type"})
        self.assertTrue(all(row["sample_count"] >= 1 for row in result))

    def test_test_set_comparison_analyzes_each_sample(self):
        from chat.token_utils import test_set_comparison

        result = test_set_comparison("parallel_rag_question")

        self.assertEqual(result["id"], "parallel_rag_question")
        self.assertEqual(result["category"], "parallel")
        self.assertEqual(len(result["samples"]), 6)
        first = result["samples"][0]
        self.assertIn("profiles", first)
        self.assertGreater(len(first["profiles"]), 0)

    def test_test_set_comparison_raises_on_unknown_id(self):
        from chat.token_utils import test_set_comparison

        with self.assertRaises(ValueError):
            test_set_comparison("does_not_exist")
