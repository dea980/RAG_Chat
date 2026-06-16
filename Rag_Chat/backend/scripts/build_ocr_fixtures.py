"""OCR 테스트용 이미지를 PIL 로 생성.

Phase 5 OCR loader 검증용. 외부 의존성은 Pillow 만.
macOS 시스템 폰트를 사용하므로 다른 OS 에서는 폰트 경로만 바꾸면 된다.

생성 위치: chat/tests/ingest/fixtures/ocr/
- sample_ko.png   : 한국어
- sample_en.png   : 영어
- sample_mixed.png: 한/영 혼합 + 숫자

각 이미지는 OCR loader 가 추출한 텍스트가 ground-truth (이 파일 본문) 와
일정 비율 이상 일치하는지 검증할 때 쓰는 진실표 역할.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FIXTURES = Path(__file__).resolve().parent.parent / "chat" / "tests" / "ingest" / "fixtures" / "ocr"

KO_FONT = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
EN_FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"


def render(text: str, out: Path, font_path: str, font_size: int = 28, padding: int = 40) -> None:
    """텍스트를 흰 배경 검은 글씨 PNG 로 렌더링."""
    font = ImageFont.truetype(font_path, font_size)

    lines = text.strip().split("\n")
    line_heights = []
    max_w = 0
    dummy = Image.new("RGB", (10, 10))
    dctx = ImageDraw.Draw(dummy)
    for line in lines:
        bbox = dctx.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        line_heights.append(h)
        if w > max_w:
            max_w = w

    line_gap = int(font_size * 0.4)
    total_h = sum(line_heights) + line_gap * (len(lines) - 1)
    img = Image.new("RGB", (max_w + padding * 2, total_h + padding * 2), "white")
    draw = ImageDraw.Draw(img)

    y = padding
    for line, h in zip(lines, line_heights):
        draw.text((padding, y), line, fill="black", font=font)
        y += h + line_gap

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    print(f"wrote {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out} ({img.size[0]}x{img.size[1]})")


def main() -> int:
    for path in (KO_FONT, EN_FONT):
        if not Path(path).exists():
            print(f"font not found: {path}", file=sys.stderr)
            return 1

    render(
        "갤럭시 S25 는 2025년 2월 7일 출시되었다.\n"
        "메인 카메라는 50MP 이며 배터리는 4000mAh 이다.\n"
        "시작 가격은 미화 434.95 달러이다.",
        FIXTURES / "sample_ko.png",
        KO_FONT,
    )

    render(
        "Galaxy S25 launched on February 7, 2025.\n"
        "Main camera is 50MP and battery is 4000mAh.\n"
        "Starting price is USD 434.95.",
        FIXTURES / "sample_en.png",
        EN_FONT,
    )

    render(
        "Galaxy S25 Ultra 스펙 요약 / Spec Summary\n"
        "Display: 6.9 inch, 1440 x 3120\n"
        "Camera: 200MP main + 5x periscope\n"
        "배터리: 5000mAh, 45W charging\n"
        "Price: USD 737.93",
        FIXTURES / "sample_mixed.png",
        KO_FONT,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
