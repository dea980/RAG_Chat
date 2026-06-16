# Design System — Triple Chat

> 모든 시각적·UI 결정은 이 파일을 단일 출처(single source of truth)로 한다.
> 이 시스템은 Streamlit 챗 화면, 프로젝트 포트폴리오/소개 페이지, 미래 Next.js 프론트엔드 — **세 표면에 공용으로 적용**된다.

## Product Context
- **What this is**: 사내 RAG Q&A 시스템. 영업·지원팀이 제품 스펙·가격을 자연어로 물으면 출처와 함께 답변.
- **Who it's for**: 비개발 사내 사용자(영업·지원). 부트캠프 프로젝트 컨텍스트에서는 채용 평가자.
- **Space/industry**: 내부 도구·생산성·B2B SaaS. 레퍼런스 톤: Linear / Plain / Raycast / Vercel.
- **Project type**: 챗 웹앱(Streamlit → Next.js 마이그레이션 전제) + 마케팅/포트폴리오 페이지.
- **Memorable thing**: “이건 진짜 사내에서 쓰는 도구다” — 진지함. 출처 추적 가능성이 시그니쳐.

## Aesthetic Direction
- **Direction**: Quiet Utilitarian — Linear의 폴리쉬와 Raycast의 모노 밀도 사이.
- **Decoration level**: minimal — 타이포그래피와 hairline dot-grid만. **그라디언트·일러스트·글로우 금지**.
- **Mood**: 조용하고 확신있고 차가워. 답변을 화려하게 포장하지 않는다.
- **Reference sites**: linear.app · plain.com · raycast.com · vercel.com

## Typography
- **Display·Body**: **Pretendard Variable** (`pretendard-variable-dynamic-subset` CDN). 한국어 퍼스트 산스, 영문도 강함. Inter 대체 — “한국어 타이포그래피를 아는 사람” 시그니쳐.
- **Body fallback**: `-apple-system, BlinkMacSystemFont, sans-serif`.
- **Data·Mono·Labels·Code**: **Geist Mono** (Google Fonts). `font-feature-settings: 'tnum' 1` 의무.
- **로드 전략**:
  - Pretendard: `<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">`
  - Geist Mono: `https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600&display=swap`
- **Scale** (px): `12 / 14 / 16(body) / 20 / 24 / 32 / 48 / 64`
- **Weights**: 400(default), 500(emphasis·labels), 600(headings).
- **Letter-spacing**: 헤딩 `-0.01em ~ -0.025em`, 본문 0, 모노 small-caps 라벨 `+0.08em`.
- **Line-height**: 본문 1.5, 헤딩 1.05~1.3.

## Color
- **Approach**: restrained · dark-first · 단일 액센트.
- **Dark (primary)**:
  - Background `#0A0B0D`
  - Surface `#131418`
  - Surface 2 / code BG `#16171B`
  - Border `#25262B` (hi: `#34353B`)
  - Text primary (paperwhite) `#F3F2EE`
  - Text muted `#8B8B93`
  - Text dim `#5C5D63`
  - **Accent · molten amber `#E89B3C`** — **citation chip 전용**, 액티브 상태, primary CTA. 다른 곳 사용 금지.
  - Accent bg `rgba(232,155,60,0.08)` / border `rgba(232,155,60,0.35)`
- **Light**:
  - Background `#F7F6F2` / Surface `#FFFFFF` / Surface 2 `#F0EFEA`
  - Border `#DCDBD4` (hi `#C2C1BA`)
  - Text `#1A1B1F` / muted `#6B6C72`
  - Accent `#B8771F` (다크보다 한 단계 진한 앨버)
- **Semantic** (채도 의도적으로 낮춤 — 네온 금지):
  - success `#4F9D7A` · warning `#D9A441` · error `#C24A4A` · info `#6B8AB8`
- **Dark mode strategy**: 다크가 primary. 라이트는 surface 재설계(채도 10–20% 감소), 같은 토큰 이름 유지.

## Spacing
- **Base unit**: 4px.
- **Density**: comfortable — 마케팅/포트폴리오는 generous, 챗 UI는 tighter.
- **Scale**: `xs(4) sm(8) md(12) lg(16) xl(24) 2xl(32) 3xl(48) 4xl(64) 5xl(96)`.

## Layout
- **Approach**: grid-disciplined (앱·마케팅 모두).
- **Grid**: 마케팅/포트폴리오 12-col, 챗 single-pane + 좌측 220px 고정 rail.
- **Max content width**: 1180px.
- **Border radius**: 카드 6px / 칩 4px / 입력 6px / 디바이더 0. **bubble-radius(>12px) 금지**.
- **Shadow**: **zero shadow** 원칙. 깊이는 border와 surface tier로만 표현.

## Motion
- **Approach**: minimal-functional.
- **Easing**: enter `ease-out` / exit `ease-in` / move `ease-in-out`.
- **Duration**: micro 80ms · short 150ms · medium 250ms.
- **Allowed**: hover 색 전이(150ms), 상태 전환, **챗 스트리밍 응답 단어단위 fade-in 80ms (시그니쳐)**.
- **Forbidden**: scroll-driven, parallax, decorative entrance.

## Signature Patterns (Triple Chat 고유)
1. **Citation Ribbon (R1, R2 적용)** — assistant 메시지 아래 `border-top: dashed var(--border)` 한 줄 뒤에, **횡렬로 정렬된 amber-tinted citation chip** 행. 각 chip: `src.csv:row42 · score 0.94`. 호버 시 chunk preview tooltip. 다른 챗 UI가 출처를 푸터에 숨길 때 **Triple Chat은 답변과 출처를 같은 시야에 둔다**.
2. **Mono small-caps section labels** — `SESSIONS`, `KNOWLEDGE`, `ADMIN` 같은 그룹 헤더는 Geist Mono 10–11px, `letter-spacing: 0.08~0.1em`, `text-transform: uppercase`, `color: muted`.
3. **Tabular-nums everywhere data lives** — 메트릭, 로그, 점수, latency, recall. 헤딩이 아닌 데이터는 무조건 Geist Mono.
4. **Top status bar** — 모델명·retrieval 모드·latency를 `MODEL · openrouter/... | RERANK · bge-v2-m3 | LATENCY · 812ms` 형식으로 mono 11px 표시. 사용자에게 “이 답변이 어떻게 만들어졌는가”를 항상 보여준다.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-28 | 초기 design system 생성 | `/design-consultation`으로 도출. Linear/Plain/Raycast/Vercel 시각 리서치 기반. 3개 표면 공용 토큰. |
| 2026-05-28 | Pretendard 채택(Inter 거부) | 한국어 본문 품질·서비스 정체성. Inter는 한글 fallback 처리되어 컨텍스트 무시. |
| 2026-05-28 | 액센트 = 몰튼 앨버 `#E89B3C` | 카테고리 컨벤션(시안/보라/그린) 회피. 도서관·아카이브·감사 신뢰의 톤. |
| 2026-05-28 | Citation ribbon을 first-class로 | Triple Chat의 핵심 가치(traceability)는 시각화되어야 한다. 푸터는 거짓말. |
| 2026-05-28 | Dark mode primary | Linear/Raycast 컨벤션. 개발자·내부 도구 신호. 라이트는 surface 재설계로 별도 제공. |

## Files
- **Live mockup** (repo-tracked, single source of preview): `Rag_Chat/docs/design/preview.html` — 모든 토큰·시그니쳐 컴포넌트·챗 화면 시각화. 브라우저로 열면 dark/light 토글 가능.
- **Runtime tokens** (실사용 CSS): `Rag_Chat/frontend/static/tokens.css` — Streamlit `st.markdown` 주입 / 미래 Next.js `globals.css` import.
- Origin snapshot (gstack /design-consultation 출력, archival): `~/.gstack/projects/dea980-RAG_Chat/designs/design-system-20260528/preview.html` · `approved.json`
- **Figma 파일** (보류): https://www.figma.com/design/heohJ2l9TiIuNuypacOTxp — 빈 캔버스 3페이지(Tokens·Typography·Components)만 생성됨. Starter 플랜 MCP 호출 한도로 변수·컴포넌트 빌드 중단. 디자이너 합류 또는 유료 업그레이드 시 재개.
