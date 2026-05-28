# Ingest Phase 7a — HWP 5.x 텍스트 추출 라이브러리 리서치

> **목적**: 한국어 HWP 5.x 파일을 RAG 파이프라인으로 인입하기 위한
> Python 라이브러리 선정. **코드 변경 없음** — 실측 + 분석 + 권고만.
>
> **테스트 파일**: 고용노동부 2026 표준 취업규칙
> (`backend/chat/tests/ingest/fixtures/special/standard_employment_rules_2026.hwp`,
> 277KB, HWP 버전 `0x00010105` = 5.1.0.5, zlib 압축, 비밀번호 없음)

---

## 1. 후보 4종 + 보너스 2종

원래 평가 대상은 4종 (`pyhwp`, `hwp5txt`, `olefile + custom`, LibreOffice headless).
리서치 도중 **`libhwp`** (Rust+PyO3) 와 **`hwp-extract`** (Volexity) 가 발견돼서
같이 측정함.

| 라이브러리 | 라이선스 | 최신 릴리스 | Python 지원 | 실측 결과 |
|---|---|---|---|---|
| **pyhwp** (`hwp5txt`) | **AGPLv3+** | 0.1b15 (2020-05) | 2.7~3.8 명시 (3.11 동작) | ✅ 본문 추출 OK, 표 `<표>` 로 손실 |
| `olefile` + custom 파서 | (BSD) | - | 전체 | ⚠ 가능하지만 HWP 5.0 spec 기반 200+ LOC 필요 |
| LibreOffice `--headless` | MPL2 | 25.x | OS 의존 | ❌ 로컬 미설치, H2Orestart 확장 필요 |
| `hwp-extract` (Volexity) | BSD | 0.1.0 (2024-11) | 3.9~3.12 | ❌ **본문 추출 불가** — 메타/임베디드 파일 전용 (위협 인텔용) |
| `libhwp` (Rust) | Apache-2.0 | 0.2.0 (2022-11) | 3.7~3.11 | ❌ **Rust 패닉** — 실제 파일에서 크래시 |

> `hwp5txt` 는 `pyhwp` 가 설치하는 CLI 도구임 (별도 패키지 아님). 후보 1·2 는
> 사실상 같은 라이브러리.

---

## 2. 라이브러리별 실측 결과

### 2.1 pyhwp (`hwp5txt`)

**설치**
```bash
pip install --pre pyhwp
pip install six   # ⚠ pyhwp 0.1b15 의 setup.py 가 six 를 누락 — 수동 설치 필요
```

`six` 누락은 5년간 방치된 명백한 bit-rot 신호. 첫 실행 시:

```
ModuleNotFoundError: No module named 'six'
  File ".../hwp5/dataio.py", line 30, in <module>
    from six import with_metaclass
```

**추출 결과**

```
$ time hwp5txt standard_employment_rules_2026.hwp > out.txt
real    0m1.34s
out.txt: 12,738 bytes
```

본문 (제목, 일반 단락) 한글 100% 정확:

```
표 준 취 업 규 칙
2026. 2.
<표>
고용노동부
...
[별첨]
별도의 직장 내 괴롭힘 예방‧대응규정을 제정하는 경우(표준안)
취업규칙으로 간단하게 직장 내 괴롭힘 행위를 규율하는 방법 이외에 별도의 규정을 두어 규율할 수 있으며,
...
```

**치명적 한계: 표 내용이 `<표>` 플레이스홀더로만 출력됨**

취업규칙·사규 같은 문서는 *조문이 표 안에 들어 있는 경우가 매우 많다*.
12,738 byte 추출 결과 안에 `<표>` 가 수십 번 등장 — 즉 핵심 조항 상당수가 누락.
277KB 원본에서 12.7KB 만 텍스트로 나온 것은 표 누락 영향이 크다.

그림(`<그림>`) 도 마찬가지로 플레이스홀더.

### 2.2 olefile + custom 파서

**파일 구조 확인** (이건 30줄로 됨):

```python
import olefile, struct
f = olefile.OleFileIO(path)
for s in f.listdir(): print('/'.join(s))
# HwpSummaryInformation, BodyText/Section0..3, DocInfo, FileHeader,
# DocOptions/_LinkDoc, PrvImage, PrvText, Scripts/*

hdr = f.openstream('FileHeader').read()
flags = struct.unpack('<I', hdr[36:40])[0]
# 0x00000001 → compressed=True, password=False, distributable=False
```

**본문 파싱 시도** — Section0 을 zlib 로 풀고 record stream 을 순회:

```
Compressed 2126 → Decompressed 5796 bytes
PARA_TEXT records: 0   ← tag id 추측 잘못해서 0건
```

당장 실패한 게 정확히 이 접근의 비용을 증명한다. HWP 5.0 binary spec 의
record tag 값(`HWPTAG_BEGIN` = 0x10, `PARA_TEXT` = BEGIN+66, 제어문자 16 bytes
별도 처리, 등) 을 정확히 구현하려면 한컴 공식 스펙(~ 200 페이지) 을 읽고
**최소 300~500 LOC + 검증 fixture 5종 이상**이 필요. 표 셀까지 복원하면 +200 LOC.

→ pyhwp 가 이미 5년 동안 해 둔 일을 다시 하는 셈.

### 2.3 LibreOffice `soffice --headless`

**로컬 상태** — `which soffice` 미설치. 도입 시 필요:

- `brew install --cask libreoffice` (~ 600MB)
- **H2Orestart 확장** 별도 설치 (HWP/HWPX 임포트 필터, 한컴이 아닌 커뮤니티 산출물)
- Dockerfile 에 `libreoffice` 패키지 추가 (~ 1GB Docker image 증가)

**실측 못함**. 일반론:

- 장점: 표/그림 포함 풀 렌더링 가능 (PDF 변환 거치면), 표 셀 텍스트 보존 가능성 ↑
- 단점: subprocess 호출, 동시성 제약 (LO 인스턴스 1개당 1파일), 인덱싱 한 번에
  Section 4개짜리 277KB 파일이 2~5초 (pyhwp 1.3s 대비 ~3배)
- H2Orestart 변환 품질은 케이스별 편차 큼. 한국 정부 문서에서 보고된 이슈:
  레이아웃 깨짐, 표 셀 병합 손실, 폰트 fallback 등

서버 배포 환경 (현재 docker-compose 백엔드 ~ 작은 컨테이너) 에 600MB+ 의존성
추가는 **HWP 1개 포맷 때문에 치르기 큰 비용**.

### 2.4 hwp-extract (Volexity)

```bash
$ hwp-extract --help
Volexity HWPExtractor | Extract metadata and/or files from HWP files
options:
  --extract-meta     If set, extracts metadata from .hwp file
  --extract-files    If set, extracts files from .hwp file
```

본문 텍스트 추출 옵션이 **없음**. 위협 인텔 회사가 HWP 안에 숨겨진 악성 객체를
끄집어내려고 만든 도구. 우리 용도와 무관.

### 2.5 libhwp (Rust + PyO3) — 보너스 평가

스펙상 가장 매력적이었음 (Apache-2.0, Rust 속도, table.cells API):

```python
hwp = HWPReader(path)
paragraphs = list(hwp.find_all('paragraph'))
tables = list(hwp.find_all('table'))
```

**실측 결과 — 첫 실행에서 Rust 패닉**:

```
thread '<unnamed>' panicked at 'called `Option::unwrap()` on a None value',
  crates/hwp/src/hwp/doc_info/style.rs:43:89
pyo3_runtime.PanicException
```

DocInfo 의 style record 파싱에서 `Option` unwrap 실패. 2022 년 11월 이후 릴리스
없음 → 한컴의 새 HWP 변종에 대응 못함. 패닉 캐치도 안 됨 (PyO3 가 PanicException
던지긴 하지만, 라이브러리 내부 상태가 어떻게 됐는지 보장 없음).

**결론**: 외관 좋음, 실전 불가. *real fixture 로 검증한 가치가 여기서 정확히 드러남.*

---

## 3. 비교 매트릭스

| 항목 | pyhwp | olefile+custom | LibreOffice | libhwp |
|---|---|---|---|---|
| 설치 난이도 | 중 (six 수동) | 낮 | **높** (600MB+) | 낮 |
| 한국어 정확도 | **본문 100%** | 미측정 | 미측정 | N/A (크래시) |
| 표 셀 추출 | **❌ `<표>` 만** | 직접 구현 시 가능 | 가능 (변환 품질 케바케) | (의도는 됨) |
| 그림/캡션 | ❌ `<그림>` | 직접 | 가능 | N/A |
| 의존성 무게 | cryptography + lxml + olefile + six | olefile 단독 | LO 풀 설치 | none (Rust 바이너리 휠) |
| 라이선스 | **AGPLv3+** ⚠ | (직접 작성) | MPL2 | Apache-2.0 |
| 마지막 릴리스 | 2020-05 | - | 활발 | 2022-11 |
| 처리 속도 (277KB) | 1.3s | - | ~2-5s (예상) | 즉시 크래시 |
| Python 3.11/3.12 호환 | 동작 (수동 수정 후) | 항상 | 외부 프로세스 | 3.11 OK, 3.12 미보장 |

### AGPLv3 주의

pyhwp 는 AGPLv3+. RAG_Chat 의 라이선스 정책에 따라 영향이 다름:

- **본 프로젝트 내부 사용 / 학습 / 개인 RAG 서버**: 문제 없음
- **백엔드를 SaaS 로 외부 사용자에게 노출**: AGPL §13 의 "network use" 조항
  → 백엔드 전체 소스 공개 의무 발생 가능
- **상용 배포 / 라이브러리 형태로 묶어서 재배포**: AGPL 전염성 검토 필요

현재 RAG_Chat 의 위치 (단일 사용자 학습용 도커 compose) 에서는 실용적 문제 없음.
**단, 향후 외부 노출 시 재평가 필수** — 이 결정을 라이센스 노트로 남겨야 함.

---

## 4. 권고

### 4.1 1차 선택: **pyhwp** (`hwp5txt` CLI 또는 Python API)

채택 이유:

1. **유일하게 실제 파일에서 동작** — libhwp 는 크래시, hwp-extract 는 본문
   추출 안 함, LibreOffice 는 인프라 부담, custom 은 비용 큼.
2. **한국어 본문 정확도 100%** — 표/그림 외의 본문은 그대로 나옴.
   취업규칙 [별첨] 같이 표 밖 단락이 본문 분량의 상당 부분을 차지하므로
   "전혀 못 쓴다" 가 아니라 "완벽하진 않다" 가 정확한 평가.
3. **설치 비용 낮음** — Python 의존성 4개, OS 패키지 불필요.
4. **속도** — 277KB / 1.3s, RAG 인덱싱 워크로드에 충분.

**채택 시 필수 처리**:

- `requirements.txt` 에 `pyhwp` 와 `six` 를 함께 명시 (`six` 누락이 첫 실행
  실패 원인)
- 표 내용 손실을 메타데이터로 표기 — 청크에 `"has_tables": true, "table_count": N` 같은
  필드 추가하면 retrieval 시 "이 응답은 표 내용을 못 봤을 수 있다" 표시 가능
- AGPLv3 사실을 LICENSE 노트나 docs/legal 에 기록

**예상 코드 형태** (Phase 7a 본 구현 단계에서):

```python
# backend/chat/ingest/loaders/text/hwp.py 같은 위치
@register
class HwpLoader:
    extensions = (".hwp",)
    source_type = "hwp"

    def load(self, path):
        from hwp5.hwp5txt import TextTransform  # lazy import
        from hwp5.xmlmodel import Hwp5File
        h = Hwp5File(str(path))
        text = TextTransform.transform_hwp5_to_text(h)
        yield RawDoc(content=text, source_file=path, source_type="hwp", ...)
```

→ 실제 API 는 phase 7a 구현 단계에서 확정. 본 리서치는 라이브러리 선정까지.

### 4.2 2차 옵션 (Plan B) — 표 보존이 결정적으로 필요해지면

다음 중 하나로 점진 이행:

- **olefile + custom 파서를 pyhwp 위에 얹기**: pyhwp 의 본문 추출은 유지하고,
  `BodyText/SectionN` 을 직접 풀어 `HWPTAG_TABLE` (BEGIN+87) 셀만 별도 파싱.
  pyhwp 소스가 참고 구현이 됨. 추가 LOC ~ 150~300.
- **HWPX 강제**: 한컴 권장 신 포맷 (XML+ZIP). 사용자가 한컴오피스 보유 시
  업로드 전 변환 요청. 표/그림 완전 보존, XML 파싱은 `lxml` 로 단순. 단,
  정부 문서는 여전히 `.hwp` 가 많음.
- **LibreOffice 변환 서버 분리**: 별도 컨테이너로 LO + H2Orestart 띄우고
  REST 로 `.hwp → .pdf` 만 받기. 그 후 pdf loader 재사용. 인프라 가중 큼.

지금은 1차로 충분. Plan B 들은 실제 표 손실 불만이 사용자에게서 나오면 그때
의사결정.

### 4.3 채택하지 말 것

- ❌ **libhwp**: 실파일 크래시, 3.5년 무릴리스. PyO3 패닉은 try/except 로
  안전하게 잡기 어려움.
- ❌ **hwp-extract**: 용도가 다름.
- ❌ **LibreOffice 단독**: HWP 한 포맷 위한 600MB 의존성은 과함.
- ❌ **olefile + custom 단독**: 5년치 작업 재발명.

---

## 5. 후속 작업 (Phase 7a 구현 단계로 넘기는 것)

| 항목 | 우선 | 비고 |
|---|---|---|
| `backend/requirements.txt` 에 `pyhwp` + `six` 추가 | 높음 | `six` 누락 함정 회피 |
| `loaders/text/hwp.py` 작성 + `text/__init__.py` import 등록 | 높음 | Phase 3 의 패턴 그대로 |
| 표 검출 메타데이터 (`has_tables`, `table_count`) 추가 | 중 | retrieval 정확도 영향 표면화 |
| LICENSE 노트에 AGPLv3 의존성 표기 | 중 | 향후 외부 노출 의사결정용 근거 |
| 본 fixture (`special/standard_employment_rules_2026.hwp`) 로 loader 테스트 추가 | 높음 | 회귀 방지 — 본 문서가 "한 번 검증된 시점" |
| 추가 fixture 1~2종 (사규 외 HWP) | 낮 | 표/그림 손실 영향 범위 파악 |

---

## 6. 안 한 것 (의도적)

- **loader 코드 작성 X** — 본 작업은 리서치 한정.
- **표 셀 복원 PoC X** — 후속 Plan B 영역.
- **LibreOffice 실측 X** — 로컬 미설치, 도입 결정 후 별도 PoC.
- **HWPX (`.hwpx`) 처리 검토 X** — 본 fixture 가 HWP 5.x 라 범위 외. HWPX 가 들어오면
  별도 phase 에서 (간단함: ZIP+XML).

---

## 관련 문서

- [phase7a_hwp.md](phase7a_hwp.md) — 부모 phase doc. 본 리서치 완료 후 구현
  세션이 채워 넣을 통합 노트 자리.
- [phase3_text_loaders.md](phase3_text_loaders.md) — Phase 3 loader 패턴 (이 리서치
  결과는 같은 패턴에 얹힘).
- [phase1_skeleton.md](phase1_skeleton.md) — ingest layer 전체 구조.

---

## 부록 — 실측 환경

- macOS Darwin 25.4.0, Python 3.11.3
- 임시 venv (`/tmp/hwp_research/venv*`), 본 프로젝트 환경 미오염
- 모든 라이브러리는 PyPI 공식 릴리스 (소스 빌드 없음)
- 테스트 파일은 git 추적 fixture (재현 가능)
