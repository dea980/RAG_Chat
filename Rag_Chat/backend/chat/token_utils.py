"""Token counting helpers for model/language comparison.

OpenAI-compatible profiles use `tiktoken` encodings where available. Gemini,
Claude, and Qwen rows are intentionally labelled as estimates because their
production tokenizers differ from OpenAI's encodings.
"""
from __future__ import annotations

import os
from functools import lru_cache
from math import ceil
from typing import Any

try:
    import tiktoken
except ImportError:  # pragma: no cover - dependency should be installed
    tiktoken = None  # type: ignore


EXACT_PROFILES = [
    {
        "id": "openai_o200k",
        "label": "GPT-4o / o-series",
        "encoding": "o200k_base",
        "note": "OpenAI o200k_base tokenizer.",
    },
    {
        "id": "openai_cl100k",
        "label": "GPT-4 / GPT-3.5 / text-embedding-3",
        "encoding": "cl100k_base",
        "note": "OpenAI cl100k_base tokenizer.",
    },
    {
        "id": "openai_p50k",
        "label": "Legacy code models",
        "encoding": "p50k_base",
        "note": "OpenAI p50k_base tokenizer.",
    },
]


ESTIMATE_PROFILES = [
    {
        "id": "gemini_estimate",
        "label": "Gemini estimate",
        "basis": "openai_o200k",
        "multiplier": 1.05,
        "note": "Approximation based on OpenAI o200k token count.",
    },
    {
        "id": "claude_estimate",
        "label": "Claude estimate",
        "basis": "openai_cl100k",
        "multiplier": 1.00,
        "note": "Approximation based on OpenAI cl100k token count.",
    },
    {
        "id": "qwen_estimate",
        "label": "Qwen estimate",
        "basis": "openai_cl100k",
        "multiplier": 1.08,
        "note": "Approximation based on OpenAI cl100k token count.",
    },
    {
        "id": "gpt_oss_estimate",
        "label": "gpt-oss estimate",
        "basis": "openai_o200k",
        "multiplier": 1.00,
        "note": "gpt-oss uses o200k_harmony (same base vocab as o200k_base, "
                "+ harmony chat format). Estimate via o200k_base token count.",
    },
]


LANGUAGE_SAMPLES = [
    {
        "language": "Korean",
        "text": "갤럭시 S25 울트라의 카메라 사양과 가격을 요약해 주세요.",
    },
    {
        "language": "English",
        "text": "Summarize the camera specifications and price of the Galaxy S25 Ultra.",
    },
    {
        "language": "Japanese",
        "text": "Galaxy S25 Ultra のカメラ仕様と価格を要約してください。",
    },
    {
        "language": "Chinese",
        "text": "请总结 Galaxy S25 Ultra 的相机规格和价格。",
    },
    {
        "language": "Code",
        "text": "def price_with_tax(price: float) -> float:\n    return round(price * 1.1, 2)",
    },
    {
        "language": "Mixed",
        "text": "S25 Ultra 512GB 모델의 price와 camera specs를 비교해줘.",
    },
]


# --- Test sets for systematic comparison --------------------------------------
# Category "parallel": same semantic content across 6 languages — best for
# isolating language effects on tokens/char ratio.
# Category "content_type": 6 different content formats (prose/code/json/...) —
# best for showing where each tokenizer is weak.

TEST_SETS = [
    {
        "id": "parallel_greeting",
        "category": "parallel",
        "label": "A1. 인사말 (parallel · 6언어)",
        "description": (
            "같은 인사를 6언어로. 짧은 발화에서 한국어/일본어 부풀림이 가장 잘 드러난다."
        ),
        "samples": [
            {"language": "Korean", "text": "안녕하세요, 영업팀입니다. 무엇을 도와드릴까요?"},
            {"language": "English", "text": "Hello, this is the sales team. How can I help you?"},
            {"language": "Japanese", "text": "こんにちは、営業チームです。何かお手伝いできますか?"},
            {"language": "Chinese", "text": "您好，这里是销售团队。我能为您做什么？"},
            {"language": "Spanish", "text": "Hola, somos del equipo de ventas. ¿En qué podemos ayudarle?"},
            {"language": "German", "text": "Hallo, hier ist das Vertriebsteam. Wie können wir Ihnen helfen?"},
        ],
    },
    {
        "id": "parallel_rag_question",
        "category": "parallel",
        "label": "A2. RAG 질문 (parallel · 6언어)",
        "description": (
            "전형적 사내 RAG 질문 — 제품 스펙 / 가격 / 색상. 운영 비용 추정용 reference."
        ),
        "samples": [
            {
                "language": "Korean",
                "text": (
                    "갤럭시 S25 Ultra 512GB 모델의 카메라 사양, 가격, 색상 옵션을 "
                    "영업 자료용으로 한 문단으로 정리해 주세요."
                ),
            },
            {
                "language": "English",
                "text": (
                    "Summarize the camera specifications, price, and color options of the "
                    "Galaxy S25 Ultra 512GB model in one paragraph for sales material."
                ),
            },
            {
                "language": "Japanese",
                "text": (
                    "Galaxy S25 Ultra 512GB モデルのカメラ仕様、価格、カラーオプションを"
                    "営業資料用に1段落で要約してください。"
                ),
            },
            {
                "language": "Chinese",
                "text": (
                    "请将三星 Galaxy S25 Ultra 512GB 型号的相机规格、价格和颜色选项"
                    "整理为一段销售资料。"
                ),
            },
            {
                "language": "Spanish",
                "text": (
                    "Resuma en un párrafo las especificaciones de cámara, el precio y "
                    "las opciones de color del Galaxy S25 Ultra de 512 GB para material de ventas."
                ),
            },
            {
                "language": "German",
                "text": (
                    "Fassen Sie die Kameraspezifikationen, den Preis und die Farboptionen "
                    "des Galaxy S25 Ultra 512 GB für Verkaufsunterlagen in einem Absatz zusammen."
                ),
            },
        ],
    },
    {
        "id": "parallel_long_prose",
        "category": "parallel",
        "label": "A3. 긴 문단 (parallel · 6언어)",
        "description": (
            "200~300자 분석성 문단. 긴 context 운영비용 비교 reference — chunk_size 산정 근거."
        ),
        "samples": [
            {
                "language": "Korean",
                "text": (
                    "최근 6개월간 사내 RAG 챗봇 사용 로그를 분석한 결과, 영업팀이 가장 자주 "
                    "질문한 주제는 제품 스펙 비교와 가격 안내였다. 답변 정확도는 90%를 넘었지만, "
                    "출처 인용이 누락된 사례가 7%였고 이는 신뢰도 하락의 주요 원인으로 지목되었다."
                ),
            },
            {
                "language": "English",
                "text": (
                    "An analysis of internal RAG chatbot usage logs over the past six months "
                    "showed that the sales team most frequently asked about product "
                    "specification comparisons and pricing guidance. Response accuracy exceeded "
                    "90%, but missing source citations were observed in 7% of cases and "
                    "identified as the primary cause of declining trust."
                ),
            },
            {
                "language": "Japanese",
                "text": (
                    "過去6か月間の社内 RAG チャットボットの利用ログを分析した結果、"
                    "営業チームが最も頻繁に質問したテーマは製品仕様の比較と価格案内であった。"
                    "回答精度は90%を超えたが、出典引用が欠落した事例が7%あり、"
                    "これは信頼性低下の主な原因として指摘された。"
                ),
            },
            {
                "language": "Chinese",
                "text": (
                    "对过去六个月内部 RAG 聊天机器人使用日志的分析显示，"
                    "销售团队最常询问的话题是产品规格比较和价格指引。"
                    "回答准确率超过 90%，但有 7% 的案例缺少来源引用，"
                    "这被认为是信任度下降的主要原因。"
                ),
            },
            {
                "language": "Spanish",
                "text": (
                    "Un análisis de los registros de uso del chatbot RAG interno de los últimos "
                    "seis meses mostró que el equipo de ventas preguntó con mayor frecuencia "
                    "sobre comparaciones de especificaciones de productos y orientación de precios. "
                    "La precisión de las respuestas superó el 90%, pero se observó la falta de "
                    "citas de fuente en el 7% de los casos y se identificó como la causa principal "
                    "de la disminución de la confianza."
                ),
            },
            {
                "language": "German",
                "text": (
                    "Eine Analyse der Nutzungsprotokolle des internen RAG-Chatbots der letzten "
                    "sechs Monate ergab, dass das Vertriebsteam am häufigsten Fragen zu "
                    "Produktspezifikationsvergleichen und Preisangaben stellte. Die "
                    "Antwortgenauigkeit lag über 90 %, in 7 % der Fälle fehlten jedoch "
                    "Quellenangaben, was als Hauptursache für den Vertrauensverlust identifiziert wurde."
                ),
            },
        ],
    },
    {
        "id": "parallel_tech_spec",
        "category": "parallel",
        "label": "A4. 기술 스펙 (parallel · 6언어)",
        "description": (
            "bullet 스타일 스펙 list. 숫자·단위·구두점이 많아 token 패턴이 prose와 다르다."
        ),
        "samples": [
            {
                "language": "Korean",
                "text": (
                    "디스플레이: 6.9인치 QHD+ AMOLED, 120Hz. 프로세서: Snapdragon 8 Gen 4. "
                    "RAM: 12GB. 저장: 256/512GB/1TB. 카메라: 200MP 광각 + 50MP 잠망경 망원. "
                    "배터리: 5000mAh. 무게: 218g."
                ),
            },
            {
                "language": "English",
                "text": (
                    "Display: 6.9-inch QHD+ AMOLED, 120Hz. Processor: Snapdragon 8 Gen 4. "
                    "RAM: 12GB. Storage: 256/512GB/1TB. Camera: 200MP wide + 50MP periscope "
                    "telephoto. Battery: 5000mAh. Weight: 218g."
                ),
            },
            {
                "language": "Japanese",
                "text": (
                    "ディスプレイ: 6.9インチ QHD+ AMOLED、120Hz。プロセッサ: Snapdragon 8 Gen 4。"
                    "RAM: 12GB。ストレージ: 256/512GB/1TB。カメラ: 200MP 広角 + 50MP "
                    "ペリスコープ望遠。バッテリー: 5000mAh。重量: 218g。"
                ),
            },
            {
                "language": "Chinese",
                "text": (
                    "屏幕：6.9 英寸 QHD+ AMOLED，120Hz。处理器：Snapdragon 8 Gen 4。"
                    "运行内存：12GB。存储：256/512GB/1TB。摄像头：200MP 广角 + 50MP "
                    "潜望长焦。电池：5000mAh。重量：218 克。"
                ),
            },
            {
                "language": "Spanish",
                "text": (
                    "Pantalla: AMOLED QHD+ de 6,9 pulgadas, 120 Hz. Procesador: Snapdragon 8 Gen 4. "
                    "RAM: 12 GB. Almacenamiento: 256/512 GB/1 TB. Cámara: 200 MP gran angular + "
                    "50 MP teleobjetivo periscópico. Batería: 5000 mAh. Peso: 218 g."
                ),
            },
            {
                "language": "German",
                "text": (
                    "Display: 6,9 Zoll QHD+ AMOLED, 120 Hz. Prozessor: Snapdragon 8 Gen 4. "
                    "RAM: 12 GB. Speicher: 256/512 GB/1 TB. Kamera: 200 MP Weitwinkel + "
                    "50 MP Periskop-Tele. Akku: 5000 mAh. Gewicht: 218 g."
                ),
            },
        ],
    },
    {
        "id": "parallel_conversational",
        "category": "parallel",
        "label": "A5. 구어체 대화 (parallel · 6언어)",
        "description": (
            "캐주얼 말투 / slang. formal text 와 token 분포가 다르다."
        ),
        "samples": [
            {
                "language": "Korean",
                "text": (
                    "야, 그 신제품 카메라 진짜 좋더라. 어제 매장 가서 직접 찍어봤는데 "
                    "야간 모드가 미쳤어. 너도 한번 가서 봐."
                ),
            },
            {
                "language": "English",
                "text": (
                    "Hey, that new camera is really good. I went to the store yesterday and "
                    "tried it myself — the night mode is insane. You should go check it out too."
                ),
            },
            {
                "language": "Japanese",
                "text": (
                    "ねえ、あの新製品のカメラ本当にいいよ。昨日店に行って自分で撮ってみたんだけど、"
                    "夜景モードがやばい。君も一度見に行ってみて。"
                ),
            },
            {
                "language": "Chinese",
                "text": (
                    "喂，那款新产品的相机真的不错。我昨天去店里亲自试了一下，夜景模式太厉害了。"
                    "你也去看看吧。"
                ),
            },
            {
                "language": "Spanish",
                "text": (
                    "Oye, esa cámara del nuevo producto es genial. Ayer fui a la tienda y la "
                    "probé yo mismo — el modo nocturno es una locura. Tú también deberías ir a verla."
                ),
            },
            {
                "language": "German",
                "text": (
                    "Hey, die Kamera des neuen Produkts ist wirklich klasse. Ich war gestern "
                    "im Laden und habe sie selbst ausprobiert — der Nachtmodus ist verrückt. "
                    "Du solltest sie auch mal ansehen."
                ),
            },
        ],
    },
    # --- Content type sets (B): different formats, mostly Korean+ASCII ---
    {
        "id": "content_prose",
        "category": "content_type",
        "label": "B1. Plain prose (한국어 문단)",
        "description": "일반 산문. content type 비교의 baseline.",
        "samples": [
            {
                "language": "Prose",
                "text": (
                    "프로젝트 트리플 챗은 사내 영업·지원팀이 제품 스펙을 자연어로 묻고 "
                    "출처와 함께 답변받는 RAG Q&A 시스템이다. 5개 모델 프로바이더를 "
                    "환경변수만으로 스왑할 수 있게 설계했고, 한국어 문서를 우선 지원한다."
                ),
            },
        ],
    },
    {
        "id": "content_code",
        "category": "content_type",
        "label": "B2. Code (Python)",
        "description": (
            "들여쓰기·기호 많은 코드. p50k 가 강했던 영역. cl100k/o200k 와 격차 확인."
        ),
        "samples": [
            {
                "language": "Code",
                "text": (
                    "def chunk_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:\n"
                    "    chunks = []\n"
                    "    for i in range(0, len(text), size - overlap):\n"
                    "        chunks.append(text[i:i + size])\n"
                    "    return chunks\n\n"
                    "if __name__ == '__main__':\n"
                    "    print(chunk_text('hello world', size=5, overlap=1))"
                ),
            },
        ],
    },
    {
        "id": "content_json",
        "category": "content_type",
        "label": "B3. JSON (structured)",
        "description": (
            "괄호·따옴표·콜론 빈도 높은 구조화 텍스트. tool/function call payload 대표."
        ),
        "samples": [
            {
                "language": "JSON",
                "text": (
                    '{"product": "Galaxy S25 Ultra", "storage_options": [256, 512, 1024], '
                    '"price_krw": 1599000, "colors": ["Titanium Black", "Titanium Gray", '
                    '"Titanium Silver", "Titanium Yellow"], "release_date": "2025-02-07", '
                    '"specs": {"display": "6.9 QHD+ AMOLED", "ram_gb": 12, "battery_mah": 5000}}'
                ),
            },
        ],
    },
    {
        "id": "content_markdown",
        "category": "content_type",
        "label": "B4. Markdown (mixed)",
        "description": (
            "헤더·리스트·테이블·code fence 혼합. RAG 컨텍스트에 자주 들어오는 형식."
        ),
        "samples": [
            {
                "language": "Markdown",
                "text": (
                    "# 제품 비교\n\n"
                    "## 카메라\n"
                    "- S25 Ultra: 200MP + 50MP periscope\n"
                    "- iPhone 16 Pro Max: 48MP\n\n"
                    "## 가격\n"
                    "| Model | KRW | USD |\n"
                    "|---|---|---|\n"
                    "| S25 Ultra 512GB | 1,599,000 | 1,199.99 |\n\n"
                    "```python\n"
                    "ratio = 1599000 / 1199.99\n"
                    "```"
                ),
            },
        ],
    },
    {
        "id": "content_numbers",
        "category": "content_type",
        "label": "B5. 숫자·수식 heavy",
        "description": (
            "숫자·통계·구두점이 많은 분석 텍스트. number splitting 차이가 드러난다."
        ),
        "samples": [
            {
                "language": "Numbers",
                "text": (
                    "총 매출 12,345,678원, 전년 동기 대비 +18.4%. "
                    "평균 객단가 24,567원 → 28,910원 (Δ +17.7%). "
                    "마진율 0.234 → 0.256. 신뢰구간 95% CI: [0.241, 0.271]. p < 0.001."
                ),
            },
        ],
    },
    {
        "id": "content_emoji_url",
        "category": "content_type",
        "label": "B6. Emoji·URL·hashtag",
        "description": (
            "이모지·URL·해시태그 혼합. SNS·마케팅 텍스트 대표. tokenizer 가 가장 비싸게 처리하는 영역."
        ),
        "samples": [
            {
                "language": "Mixed",
                "text": (
                    "🎉 신제품 출시! 자세한 정보는 https://example.com/products/s25-ultra "
                    "또는 https://shop.example.com/s25?ref=internal#specs 에서 확인하세요. "
                    "문의: support@example.com 📧 #갤럭시 #S25Ultra ✨"
                ),
            },
        ],
    },
]


@lru_cache(maxsize=8)
def _encoding_for(name: str):
    if tiktoken is None:
        return None
    if os.getenv("TOKENLAB_ENABLE_TIKTOKEN", "0") != "1":
        return None
    try:
        return tiktoken.get_encoding(name)
    except Exception:
        # Some encodings (notably o200k_base) may not be cached locally and
        # tiktoken attempts a network fetch. Token Lab must remain offline-safe.
        return None


def _fallback_token_count(text: str) -> int:
    """Coarse fallback when tiktoken is unavailable."""
    if not text:
        return 0
    return max(1, ceil(len(text.encode("utf-8")) / 4))


def _exact_count(text: str, encoding_name: str) -> tuple[int, str]:
    encoding = _encoding_for(encoding_name)
    if encoding is None:
        return _fallback_token_count(text), "fallback"
    return len(encoding.encode(text)), "exact"


def _ratio(tokens: int, characters: int) -> float:
    if characters == 0:
        return 0.0
    return round(tokens / characters, 3)


def analyze_text(text: str) -> dict[str, Any]:
    """Return token counts across supported model profiles."""
    characters = len(text)
    byte_count = len(text.encode("utf-8"))

    profiles: list[dict[str, Any]] = []
    exact_counts: dict[str, int] = {}
    for profile in EXACT_PROFILES:
        tokens, method = _exact_count(text, profile["encoding"])
        exact_counts[profile["id"]] = tokens
        profiles.append({
            "id": profile["id"],
            "label": profile["label"],
            "method": method,
            "tokenizer": profile["encoding"],
            "tokens": tokens,
            "tokens_per_character": _ratio(tokens, characters),
            "note": profile["note"],
        })

    for profile in ESTIMATE_PROFILES:
        basis_count = exact_counts.get(profile["basis"], _fallback_token_count(text))
        tokens = int(round(basis_count * profile["multiplier"]))
        if text and tokens == 0:
            tokens = 1
        profiles.append({
            "id": profile["id"],
            "label": profile["label"],
            "method": "estimate",
            "tokenizer": profile["basis"],
            "tokens": tokens,
            "tokens_per_character": _ratio(tokens, characters),
            "note": profile["note"],
        })

    reference_tokens = exact_counts.get("openai_cl100k", _fallback_token_count(text))
    chunk_targets = [250, 500, 1000, 2000]
    chunk_recommendations = [
        {
            "target_tokens": target,
            "estimated_chunks": ceil(reference_tokens / target) if reference_tokens else 0,
        }
        for target in chunk_targets
    ]

    return {
        "text_preview": text[:160],
        "characters": characters,
        "bytes": byte_count,
        "profiles": profiles,
        "reference_profile": "openai_cl100k",
        "reference_tokens": reference_tokens,
        "chunk_recommendations": chunk_recommendations,
    }


def language_sample_comparison() -> list[dict[str, Any]]:
    """Return fixed language sample token comparisons."""
    rows = []
    for sample in LANGUAGE_SAMPLES:
        analysis = analyze_text(sample["text"])
        rows.append({
            "language": sample["language"],
            "text": sample["text"],
            "characters": analysis["characters"],
            "bytes": analysis["bytes"],
            "profiles": analysis["profiles"],
        })
    return rows


def list_test_sets() -> list[dict[str, Any]]:
    """Return test set metadata (no token analysis) for UI selectors."""
    return [
        {
            "id": ts["id"],
            "category": ts["category"],
            "label": ts["label"],
            "description": ts["description"],
            "sample_count": len(ts["samples"]),
        }
        for ts in TEST_SETS
    ]


def test_set_comparison(set_id: str) -> dict[str, Any]:
    """Analyze every sample in a test set. Raise ValueError if unknown id."""
    test_set = next((ts for ts in TEST_SETS if ts["id"] == set_id), None)
    if test_set is None:
        raise ValueError(f"unknown test_set id: {set_id}")

    samples = []
    for sample in test_set["samples"]:
        analysis = analyze_text(sample["text"])
        samples.append({
            "language": sample["language"],
            "text": sample["text"],
            "characters": analysis["characters"],
            "bytes": analysis["bytes"],
            "profiles": analysis["profiles"],
        })

    return {
        "id": test_set["id"],
        "category": test_set["category"],
        "label": test_set["label"],
        "description": test_set["description"],
        "samples": samples,
    }
