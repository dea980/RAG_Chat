"""Ingest layer — RAG 파이프라인의 1단계 (데이터 수집·정규화).

청킹/임베딩/검색 앞단에서 다양한 포맷(CSV, PDF, HWP ...)을
공통 표현(RawDoc) 으로 변환한다. 자세한 설계는
backend/docs/ingest_layer.md 참고.
"""
