import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import digest


SAMPLE_ITEMS = [
    {
        "title": "Agent workflow benchmark",
        "link": "https://example.com/agent",
        "source": "Example AI",
        "category": "agent",
        "summary": "A benchmark compares agent workflows on realistic browser tasks.",
        "published": "2026-06-29 00:00 UTC",
    },
    {
        "title": "New inference chip",
        "link": "https://example.com/chip",
        "source": "Example Labs",
        "category": "industry",
        "summary": "A chip vendor announced lower-cost inference hardware.",
        "published": "2026-06-29 01:00 UTC",
    },
]


class FakeOpenAI:
    calls = []

    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self.create)
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        choice = types.SimpleNamespace(
            message=types.SimpleNamespace(content="LLM digest"), finish_reason="stop"
        )
        return types.SimpleNamespace(choices=[choice])


class DigestSummaryTests(unittest.TestCase):
    def setUp(self):
        FakeOpenAI.calls = []

    def test_ai_summarize_requests_category_and_per_item_takeaways_in_one_call(self):
        fake_openai_module = types.SimpleNamespace(OpenAI=FakeOpenAI)

        with patch.dict(sys.modules, {"openai": fake_openai_module}):
            with patch.dict(
                os.environ,
                {
                    "GOOGLE_API_KEY": "test-key",
                    "LLM_MODEL": "gemini-test",
                    "VERTEXAI_PROXY_URL": "",
                    "VERTEXAI_PROXY_KEY": "",
                },
                clear=False,
            ):
                result = digest.ai_summarize(SAMPLE_ITEMS)

        self.assertEqual(result, "LLM digest")
        self.assertEqual(len(FakeOpenAI.calls), 1)

        prompt = FakeOpenAI.calls[0]["messages"][0]["content"]
        self.assertIn("分类解读", prompt)
        self.assertIn("逐条新闻要点", prompt)
        self.assertIn("每条新闻", prompt)
        self.assertIn("Google AI Studio 免费额度", prompt)
        self.assertIn("只通过本次请求完成", prompt)

    def test_fallback_summary_includes_per_item_takeaway_from_rss_summary(self):
        cat_labels = {
            "research": "研究前沿",
            "agent": "智能体",
            "industry": "行业动态",
            "product": "产品技术",
        }
        by_cat = {
            "agent": [SAMPLE_ITEMS[0]],
            "industry": [SAMPLE_ITEMS[1]],
        }

        result = digest._fallback_summary(SAMPLE_ITEMS, by_cat, cat_labels, "zh")

        self.assertIn("## 智能体", result)
        self.assertIn("[Agent workflow benchmark](https://example.com/agent)", result)
        self.assertIn("重点：A benchmark compares agent workflows", result)
        self.assertIn("## 行业动态", result)
        self.assertIn("[New inference chip](https://example.com/chip)", result)
        self.assertIn("重点：A chip vendor announced lower-cost inference hardware.", result)


if __name__ == "__main__":
    unittest.main()
