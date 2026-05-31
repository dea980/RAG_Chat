# Galaxy B2B 도입 핸드북 (제안서 인용용)

수집일: 2026-05-29
대상 독자: B2B 영업 / 보안·구매 담당
적용 페르소나: P2 (B2B 영업, audience_tier=b2b)
범위: Samsung Knox 호환, 공개 보안 인증, 공개 SKU 및 액세서리 정책, Samsung Care+ for Business

> 본 문서는 samsungknox.com, docs.samsungknox.com, 그리고 공개된 인증 데이터베이스에서 수집한
> **공개 정보**만을 인용합니다. 기업 견적 단가, 임대 계약 조건, 매장 KPI는 수집·기재하지 않습니다.
> 모든 인용은 하단의 출처 목록과 행별 Source URL을 기준으로 합니다.

---

## 1. Samsung Knox 개요

Samsung Knox는 Samsung Galaxy 디바이스에 내장된 하드웨어·소프트웨어 통합 보안·관리 플랫폼입니다.
크게 세 갈래로 나누어 이해할 수 있습니다.

| 갈래 | 대표 제품 | 한 줄 설명 |
| :--- | :--- | :--- |
| 디바이스 관리(EMM/UEM) | Knox Suite, Knox Manage, Knox Platform for Enterprise | 단말 등록, 정책 배포, 앱·OS 라이프사이클 관리 |
| 디바이스 보안 | Knox Vault, Trusted Boot, Realtime Kernel Protection | 격리된 보안 서브시스템 + 부팅·런타임 무결성 |
| 비즈니스 서비스 | Samsung Care+ for Business, Knox Configure, Knox E-FOTA | 사고 보상, 매스 프로비저닝, OS 강제 배포 |

핵심 키워드:
- **Knox Vault**: Galaxy S21 세대부터 도입된 격리형 보안 서브시스템. 주 프로세서와 독립된 자체 CPU·메모리·NVRAM·암호엔진을 가지며, 컴포넌트는 **BSI PP0084 기준 Common Criteria EAL4+ 이상**으로 평가됨. 보호 대상은 비밀번호·PIN·생체데이터·블록체인 키·디바이스 신원키(SAK) 등.
- **Knox Suite**: Base(무료) / Essentials / Enterprise 의 3-티어 플랜. Galaxy 구매에 Base는 무료 포함. Essentials는 SMB, Enterprise는 대기업·복합 디바이스 군 대상.
- **Knox E-FOTA**: 사내 앱 호환성을 검증한 특정 OS 버전을 강제 배포·고정. Knox 3.0 + Android 11 이상 디바이스 지원.

---

## 2. 모델별 Knox 호환 매트릭스 (요약)

전체 표는 `curated/b2b/knox_compatibility.csv` 참조. ✓ / ✗ / N/A 표기.

| 모델 | Knox Manage | Knox Vault | Knox Configure | Knox E-FOTA | Samsung DeX | IT Admin Portal |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Galaxy S25 / S25+ / S25 Ultra | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Galaxy Z Fold6 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Galaxy Tab S10 Ultra / S10+ | ✓ | N/A | ✓ | ✓ | ✓ | ✓ |
| Galaxy Tab S9 FE | ✓ | N/A | ✓ | ✓ | ✓ | ✓ |
| Galaxy A55 / A35 | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |

해설:
- S25 시리즈와 Z Fold6는 플래그십·임원용 시나리오에 적합. Knox Vault·DeX·관리 도구 모두 ✓.
- Tab S10 Ultra/S10+ 는 Samsung Knox 페이지에서 "defense-grade Knox protection" 으로 마케팅되나, **Knox Vault 보유 여부는 samsungknox.com에서 명시적으로 확인되지 않아 N/A** 로 기재. 견적서·제안서에는 "Knox 플랫폼 지원" 정도로 보수적 표현 권장.
- Tab S9 FE 는 동일한 사유로 Knox Vault 항목 N/A. 단 Knox Suite, Configure, E-FOTA, DeX는 Tab S 패밀리 공통으로 지원.
- A55 / A35 는 2024년 출시 시 **A시리즈 최초로 Knox Vault를 탑재**했음을 Samsung Newsroom 공식 발표에서 명시. **Samsung DeX는 미지원** (플래그십·Tab 한정 기능).

---

## 3. 보안 인증 매트릭스

전체 표는 `curated/b2b/security_certifications.csv` 참조.

**플랫폼 차원의 공통 인증** (모델 단위가 아니라 Knox 플랫폼·암호 모듈 단위):

| 인증 체계 | 항목 | 비고 |
| :--- | :--- | :--- |
| FIPS 140-3 (NIST/CCCS) | Samsung SCrypto v2.7 — Interim Validation Cert #4792 | 암호모듈 단위 |
| FIPS 140-3 (NIST/CCCS) | Samsung SKC v2.3 — Interim Validation Cert #4764 | 암호모듈 단위 |
| FIPS 140-2 | Samsung Kernel Cryptographic Module v2.2 (#4097), Flash Memory Protector v3.0.1 (#4092), BoringSSL v1.5 (#3900) 등 | 다수 모듈 |
| Common Criteria (NIAP MDFPP) | Samsung Galaxy Devices on Android 16 (Fall), Android 15 (Spring), Android 14 (Fall/Spring) | 연 2회 갱신 |
| Common Criteria (Knox Vault) | BSI PP0084 EAL4+ 이상 | Galaxy S21 이후 |
| DISA STIG | Samsung Android 16 STIG, Android 15 BYOAD STIG, Android OS 15 with Knox 3.x STIG | 미국 국방부 운용 |
| DISA UC APL | Galaxy Z Fold6 5G, Galaxy Z Flip6 5G, Galaxy S24 FE, Galaxy S23 Ultra/Plus/Std 등 (S25 미등재) | 미국 국방통신망 적격품 |
| CSfC Components List | Galaxy S23 Ultra, S22 Ultra, S21 Ultra 등 (S25 미등재) | NSA CSfC 적격품 |

**국가별 정부·국방 인증**:

| 국가 | 인증 | 대상 모델 |
| :--- | :--- | :--- |
| 독일 BSI | VS-NfD (Knox Native Solution 3.10, 운용허가 BSI-VSA-10875) | Galaxy 스마트폰·태블릿 + SecuSmart SecuSUITE |
| 스페인 CCN | STIC Qualified Products (Android 15) | S Series (**S25, S25+, S25 Ultra**, S24/S23/S22/S21 패밀리), Z Fold3~6, A36/A56/A53, Tab S Series (S10 FE/FE+, S9/S9+/S9 Ultra, S8 패밀리), Tab Active 5 / 4 Pro |
| 폴란드 ABW | Cryptographic Protection Certificate | **Galaxy S25 with Knox Android 15 (2025)**, S21/S23/S24 with Knox Android 14 (2025) |
| 폴란드 DKWOC | Cryptographic Protection Certificate | Galaxy S23, S24 with Knox (2025) |
| 영국 NCSC | End User Device Security Guidance | Knox 2.x 기반 |
| 호주 | Security Configuration Guide MDFPP | Knox 3.9+ / Android 13.0+ |
| 네덜란드 AIVD | RESTRICTED 등급 (Tiger/R 4.1 + Knox 3.6) | Sectra + Samsung 솔루션 |
| 카자흐스탄 STRK | Workspace as cryptographic software | Knox Workspace |

**한국 (KCMVP)**:
- KCMVP는 KISA·국정원이 운영하는 **암호모듈** 검증 제도이며, Samsung의 SCrypto / SKC 모듈은 FIPS 140-3 Interim 인증을 보유하지만 **KCMVP 인증 목록에서 Galaxy 단말 또는 Knox 암호모듈의 공개 등록은 본 수집 시점(2026-05-29)에 확인되지 않았습니다.** 표에는 모두 N/A 로 기재.
- 추후 확인이 필요한 경우 KISA 암호모듈검증 자료실(`https://seed.kisa.or.kr/kisa/kcmvp/reference.do`)에서 갱신본 확인 후 업데이트하는 절차를 권장.

신뢰도 평가:
- **High**: FIPS 140-3 Interim, CC NIAP, BSI VS-NfD, CCN STIC, DISA STIG/UC APL — Samsung Knox 공식 인증 페이지에 모델·문서 번호와 함께 게재됨.
- **Medium**: Knox Vault EAL4+ 표기 — Samsung 공식 문서에 "BSI PP0084 EAL4+ 이상" 으로만 명시되고, 모델별 인증서 번호는 미공개. 제안서 인용 시 "Knox Vault 컴포넌트는 BSI PP0084 EAL4+ 이상으로 평가" 로 인용 권장.
- **Low / N/A**: KCMVP — 공개 검색 결과로는 Galaxy 단말 매핑이 확인되지 않음. 영업 단계에서 한국 공공·금융 고객이 요구할 경우 Samsung Korea Business 채널에 직접 문의 필요.

---

## 4. Knox 라이선스 SKU (공개 단가 제외)

출처: `docs.samsungknox.com/admin/fundamentals/knox-licenses/`

| 플랜 | 포함 서비스 | 비고 |
| :--- | :--- | :--- |
| **Knox Suite - Base Plan** | Knox Mobile Enrollment, Knox Platform for Enterprise | **무료**. Galaxy 단말 구매 시 기본 포함. |
| **Knox Suite - Essentials Plan** | Knox Mobile Enrollment, Knox Manage, Knox Remote Support, Knox Platform for Enterprise | SMB 대상. 리셀러 통해 구매. |
| **Knox Suite - Enterprise Plan** | Mobile Enrollment(Advanced), Knox Manage, Knox E-FOTA, Knox Asset Intelligence, Knox Remote Support, Knox Platform for Enterprise, Knox Capture, Knox Authentication Manager | 대기업 대상. Galaxy Enterprise Edition 단말은 1년 무료 제공. |

**개별 (Standalone) 라이선스** — 위 Suite와 별개로 단품 구매 가능:
- Knox Manage (Paid)
- Knox E-FOTA (Paid)
- Knox Asset Intelligence (Paid)
- Knox Configure (Paid, staggered license)
- Knox Guard (Paid, staggered license)
- Samsung Care+ for Business (Paid, staggered license)
- Knox Platform for Enterprise DualDAR (Paid, device-based)
- Knox E-FOTA On-Premises (Paid, on-prem)

**무료 라이선스**:
- Knox Mobile Enrollment (라이선스 키 불필요)
- Knox Platform for Enterprise (Knox Service Plugin, device-based 무료 라이선스)
- Knox Mobile Enrollment Direct (on-prem 무료)

**시험판 (Trial)**:
- Knox Suite - Enterprise Plan trial: 30대, 90일.
- Knox Configure / Knox Guard 개별 trial: 30대, 3개월.

> 단가는 모두 리셀러 견적이며 공개되지 않습니다. 제안서에는 "리셀러 견적 기준" 으로만 표기 권장.

---

## 5. 기업용 액세서리 정책 (공개 분)

samsungknox.com과 Samsung Business 페이지에는 별매 액세서리(예: Book Cover Keyboard, Insert Tray) 단가·SKU가 명시되지 않습니다. 일반 공개 사실만 정리:

- **Galaxy Tab S 시리즈**: Book Cover Keyboard는 별매 액세서리이며 모델별(Tab S10+, Tab S10 Ultra, Tab S9 FE 등) 전용 규격이 존재.
- **Galaxy XCover / Tab Active**: 러기드 카테고리 전용 Insert Tray·Pogo 충전 도크가 별매.
- **S Pen**: Galaxy S25 Ultra, Z Fold6(별매·기기 외장), Tab S10 시리즈는 기본 동봉 또는 별매(모델별 상이).
- 기업 일괄 구매 시 Knox Configure 의 "Customization" 옵션을 통해 **부트 로고·런처·기본 앱 사전 탑재** 가능.

> 본 절은 단가·재고를 포함하지 않습니다. 구체 SKU는 Samsung Korea Business 영업창구에 문의.

---

## 6. Samsung Care+ for Business

출처: `samsungknox.com/en/samsung-care-plus`, `samsungknox.com/en/samsung-care-plus/supported-locations`

**커버리지**:
- 하드웨어 수리 (Samsung 정품 부품, 공식 서비스센터)
- 소프트웨어 점검·수리
- 배터리 교체
- 연장 보증 (최대 3년, 일부 국가 최대 5년)
- "Accidental Damage from Handling" — 우발적 물리·액체 손상, 전손 보상

**한국 적용**: Supported Locations 페이지의 Asia-Pacific 섹션에 **South Korea** 명시. 따라서 본사 발표 기준 한국 법인 도입 가능. 단 "Availability may vary by region" 단서가 있으므로 실제 SKU와 보상 범위는 Samsung Korea 리셀러를 통해 확인 필요.

**관리 도구**: Knox Admin Portal의 라이선스 메뉴에서 Samsung Care+ for Business 라이선스를 활성화·할당. 디바이스별 개시일·만료일·진행 중 클레임 수가 대시보드에서 가시화됨. 리셀러로부터 자동 갱신됨.

**라이선스 형태**: Staggered License (활성화 기간 + 서비스 기간 구분, 활성화 기간 내 추가 구매 시 서비스 기간 자동 연장).

---

## 7. 4경계 Moderation 관점 메모

- 본 핸드북에 포함된 정보는 모두 공개 정보. 운영 시점에 Triple Chat 의 **B2B 영업 페르소나**에 한정 노출 권장 (audience_tier=b2b).
- 모델별 ✗ 또는 N/A 셀이 다수 존재 — 챗봇 답변 시 "확실하지 않음" 가드레일이 작동해야 함. citation chip 에서 N/A 셀은 `[수정됨·N건]` 처럼 사용자에게 가시화.
- 가격·임대 조건은 본 문서에 포함되지 않음 (수집 금지 항목). 사용자가 단가를 질문하면 "리셀러 문의" 로 라우팅.

---

## 8. 출처 (Sources)

### Samsung Knox (1차)
- https://www.samsungknox.com/en/knox-platform/knox-certifications — Knox 보안 인증 종합
- https://www.samsungknox.com/en/solutions/knox-suite — Knox Suite 플랜 / 기능
- https://www.samsungknox.com/en/solutions/it-solutions/knox-platform-for-enterprise — Knox Platform for Enterprise
- https://www.samsungknox.com/en/solutions/it-solutions/samsung_e-fota — Knox E-FOTA (Knox 3.0 + Android 11+)
- https://www.samsungknox.com/en/samsung-care-plus — Samsung Care+ for Business 커버리지
- https://www.samsungknox.com/en/samsung-care-plus/supported-locations — Care+ 지원 국가 (South Korea 포함)
- https://www.samsungknox.com/en/secured-by-knox — Secured by Knox 마케팅 페이지
- https://www.samsungknox.com/en/knox-platform/supported-devices — (SPA, JS 렌더 전 모델 리스트 비노출)

### Samsung Knox Docs (2차)
- https://docs.samsungknox.com/admin/fundamentals/whitepaper/samsung-knox-mobile-security/system-security/knox-vault/ — Knox Vault 아키텍처·EAL 평가
- https://docs.samsungknox.com/admin/fundamentals/knox-licenses/ — Knox Suite Plan / Standalone 라이선스 분류

### Samsung Newsroom·Business (보조 확인)
- https://news.samsung.com/in/samsung-launches-galaxy-a55-5g-and-galaxy-a35-5g-with-flagship-like-camera-innovations-and-samsung-knox-vault-protection — A55/A35 Knox Vault 최초 탑재
- https://www.samsung.com/ae/support/mobile-devices/knox-security-solutions-in-the-galaxy-tab-s10-series/ — Tab S10 시리즈 Knox 솔루션 안내
- https://www.samsung.com/sec/business/ — Samsung Korea Business 랜딩

### 인증 데이터베이스
- https://www.commoncriteriaportal.org — Common Criteria 인증서 검색
- https://www.niap-ccevs.org/product/PCL.cfm — NIAP Product Compliant List
- https://seed.kisa.or.kr/kisa/kcmvp/reference.do — KISA KCMVP 자료실

### 원본 보관
- `data/raw/samsungknox/20260529_*.html`
- `data/raw/samsung/20260529_*.html`
- 리니지: `data/manifests/lineage.jsonl`
