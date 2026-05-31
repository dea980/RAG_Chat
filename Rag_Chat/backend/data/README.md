# `backend/data/` — RAG 코퍼스 + 평가 + 외부 benchmark

운영자가 코드 없이 namespace·tier 별로 데이터를 교체·확장 가능.
internal namespace 는 이 repo 에 절대 들어오지 않는다.

## 디렉토리 구조

```
data/
├── README.md                ← 이 파일
│
├── corpus/                  ← **RAG 인덱싱 대상.** namespace = audience tier.
│   ├── public/              ← 공개 스펙, USD 가격 (모두 가능)
│   ├── retail/              ← 자급제, 셀링 포인트, 색상별 출시일 (모두 가능)
│   ├── b2b/                 ← Knox 호환, 보안 인증 (P2 + P3)
│   ├── competitive/         ← iPhone/Pixel/Xiaomi 스펙 (P3 만)
│   ├── carrier/             ← 통신사 출고가, 결합 (P1 + P3 + P4)
│   └── internal/            ← **인덱싱 SKIP. gitignored.** [README](corpus/internal/README.md)
│
├── eval/                    ← QA dataset (retrieval 측정)
├── external/                ← 외부 benchmark (KorSTS, KorNLI)
├── samples/                 ← 기존 fixture (test 호환)
└── embedding_eval/          ← curated pair (intrinsic eval)
```

### namespace = audience tier 매핑

| 경로 prefix | audience_tier | 인덱싱 | 접근 가능 페르소나 |
|---|---|---|---|
| `corpus/public/` | public | ✓ | 모두 (P1~P4) |
| `corpus/retail/` | retail | ✓ | 모두 |
| `corpus/b2b/` | b2b | ✓ | P2 B2B + P3 본사 |
| `corpus/competitive/` | competitive | ✓ | P3 본사 만 |
| `corpus/carrier/` | carrier | ✓ | P1 매장 + P3 본사 + P4 외판 |
| `corpus/internal/` | internal_only | **✗ skip** | **누구도 챗봇으로는 못 봄** |
| `samples/` | public (호환) | ✓ | 모두 |

### 안전 원칙

1. **internal/ 는 .gitignore 로 commit 차단** + `build_vectors` 가 경로 보고 skip.
2. RAG 인덱싱 = `corpus/` + `samples/` 만.
3. 모든 chunk 에 `audience_tier` metadata 자동 부여 (`infer_tier()` from 경로).
4. Retrieval 시 `filter(audience_tier IN persona_allowed_tiers)` 적용.

### 관련 문서

- [페르소나 × 보안 통합 설계](../docs/learning/2026-05-29-persona-security-design.md)
- [페르소나 분석](../docs/learning/2026-05-29-sales-persona-analysis.md)
- [IR 개선 plan](../docs/learning/2026-05-29-ir-improvement-plan.md)
- 인덱싱 entry: `chat/management/commands/build_vectors.py`
- ACL filter: `chat/pipeline/modules.py`

---

## 외부 benchmark (이전 README 내용)

아래는 KorSTS, KorNLI, embedding_eval pair 가이드 — 기존 그대로 유지.

| 디렉토리 | 용도 | 비고 |
|---|---|---|
| `KorSTS/` | 한국어 Semantic Textual Similarity 벤치마크 | 0~5 점수 라벨 |
| `KorNLI/` | 한국어 Natural Language Inference 벤치마크 | entailment / neutral / contradiction |
| `embedding_eval/` | 자체 큐레이션 평가 쌍 (도메인 특화) | YAML, positive / negative / hard_negative |
| `samples/` | ingest 파이프라인 검증용 샘플 문서 | 별도 [README](samples/README.md) |

## 1. KorSTS — Korean Semantic Textual Similarity

**출처**: Ham et al. 2020 — [KorNLI and KorSTS: New Benchmark Datasets for Korean
Natural Language Understanding](https://arxiv.org/abs/2004.03289)
**Repo**: <https://github.com/kakaobrain/kor-nlu-datasets>
**License**: CC BY-SA 4.0

### 파일

| 파일 | 줄 수 (헤더 포함) | 용도 |
|---|---:|---|
| `sts-train.tsv` | 5,750 | (기계 번역) 학습 — 임베딩 모델 fine-tune 용 |
| `sts-dev.tsv` | 1,500 | 사람 번역 — **평가 권장** |
| `sts-test.tsv` | 1,379 | 사람 번역 — **최종 평가** |

### 포맷 (TSV)

```
genre	filename	year	id	score	sentence1	sentence2
main-captions	MSRvid	2012test	0001	5.000	비행기가 이륙하고 있다.	비행기가 이륙하고 있다.
main-captions	MSRvid	2012test	0004	3.800	한 남자가 큰 플루트를 연주하고 있다.	남자가 플루트를 연주하고 있다.
```

- `score` ∈ [0.0, 5.0] — 사람 라벨 의미 유사도 (0=무관, 5=동일)
- embedding 평가 시 사용법: 모델의 cosine 값 vs `score` 의 **Pearson / Spearman
  correlation** 측정. 보통 0.7+ = 한국어 STS 합격선.

### 점수 분포 (sts-test.tsv)

| score 정수부 | 쌍 수 |
|---:|---:|
| 0 | 243 |
| 1 | 198 |
| 2 | 265 |
| 3 | 335 |
| 4 | 241 |
| 5 | 97 |

## 2. KorNLI — Korean Natural Language Inference

**출처**: 같은 논문 / 같은 repo / 같은 license.
**Repo**: <https://github.com/kakaobrain/kor-nlu-datasets>

### 파일

| 파일 | 줄 수 | 용도 |
|---|---:|---|
| `xnli.dev.ko.tsv` | 2,491 | XNLI 사람 번역 dev — **평가 권장** |
| `xnli.test.ko.tsv` | 5,011 | XNLI 사람 번역 test |

`multinli.train.ko.tsv` (392K 쌍) / `snli_1.0_train.ko.tsv` (550K 쌍) 는
학습용. 본 RAG 시스템은 embedding 모델 학습이 아닌 *평가* 가 목적이라
포함하지 않음. 필요 시 동일 repo 에서 추가 다운로드.

### 포맷 (TSV)

```
sentence1	sentence2	gold_label
그리고 그가 말했다, "엄마, 저 왔어요."	그는 학교 버스가 그를 내려주자마자 엄마에게 전화를 걸었다.	neutral
그리고 그가 말했다, "엄마, 저 왔어요."	그는 한마디도 하지 않았다.	contradiction
```

- `gold_label` ∈ {entailment, neutral, contradiction}
- embedding 평가 시 사용법:
  - **entailment** → positive (높은 cosine 기대)
  - **contradiction** → hard negative (낮은 cosine 기대)
  - **neutral** → 중간

### 라벨 분포 (xnli.dev.ko.tsv)

| label | 쌍 수 |
|---|---:|
| entailment | 830 |
| neutral | 830 |
| contradiction | 830 |

완전 균형. 모델 편향 측정 깨끗.

## 3. `embedding_eval/curated_pairs.yaml` — 자체 큐레이션 도메인 쌍

KorSTS / KorNLI 는 일반 도메인 (captions, news, multinli). 사내 RAG 가
다루는 **사규 / HR / 재무 / IT** 도메인은 별도 큐레이션 필요.

### 구조

```yaml
version: 1
positive:        # 의미 유사 — 점수 높아야 (목표 > 0.75)
  - {text1: "연차 휴가", text2: "연차 사용", category: hr, tags: [synonym]}
negative:        # 의미 무관 — 점수 낮아야 (목표 < 0.40)
  - {text1: "출장비 정산", text2: "VPN 접속 오류", category_pair: [hr, it]}
hard_negative:   # 어휘 겹치지만 의미 다름 (negation / homonym / antonym)
  - {text1: "휴가 신청 승인", text2: "휴가 신청 거부", tags: [negation]}
```

카테고리: `hr / finance / legal / it / general`
약 60 쌍. 운영자가 YAML 한 줄 추가로 확장.

## 4. 평가 harness (todo)

```bash
# 예정 — 아직 구현 안 됨
python manage.py embedding_eval --dataset korsts-dev
python manage.py embedding_eval --dataset curated
python manage.py embedding_eval --dataset all --models bge-m3,gemini,e5-large
```

출력 예시 (가상):

| model | korsts dev pearson | curated separation | hard_neg mean |
|---|---:|---:|---:|
| gemini | 0.82 | 0.31 | 0.62 |
| bge-m3 | 0.87 | 0.41 | 0.48 |
| e5-large | 0.85 | 0.38 | 0.55 |

해석: bge-m3 가 한국어 의미 유사도 & 하드 케이스 모두 우수.

## 5. License 요약

| 데이터 | License | 상업 사용 |
|---|---|---|
| KorSTS / KorNLI | CC BY-SA 4.0 | ✅ (단, 동일 라이선스 공유) |
| `curated_pairs.yaml` | 프로젝트 라이선스 | 자체 작성 |
| `samples/galaxy_*` | gsmarena 출처 (fair use) | 사내 테스트 한정 |

## 6. 데이터 갱신

- KorSTS / KorNLI 는 v1.0 이후 변경 없음 (2020). 갱신 불필요.
- 추가 데이터셋 후보 (미포함):
  - **KLUE-STS** (`klue/sts`) — STS v1.1, 약 13K 쌍, CC BY-SA 4.0
  - **MIRACL-ko** (multilingual retrieval) — 진짜 retrieval 평가용, ~10GB
  - **Ko-StrategyQA** — Q→passage 매핑

필요 시 같은 패턴으로 추가.

## Sources

- [KorNLI and KorSTS paper (arXiv 2004.03289)](https://arxiv.org/abs/2004.03289)
- [kakaobrain/kor-nlu-datasets](https://github.com/kakaobrain/kor-nlu-datasets)
- [Korpora — KorSTS 문서](https://ko-nlp.github.io/Korpora/ko-docs/corpuslist/korsts.html)
