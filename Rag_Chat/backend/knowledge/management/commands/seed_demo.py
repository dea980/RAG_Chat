"""Seed demo data — sales-team beta 용 부서/제품/담당자/금지어.

영업팀이 챗봇과 Django Admin 검수 페이지를 즉시 시연할 수 있도록 한 번에
필요한 모든 데이터를 idempotent 하게 생성한다.

실행:
    docker compose exec backend python manage.py seed_demo
또는 (덮어쓰기):
    docker compose exec backend python manage.py seed_demo --reset
"""
from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import Department, Contact, Product
from moderation.models import ForbiddenWord


DEPARTMENTS = [
    {"name": "영업팀",       "description": "B2B/B2C 영업, 견적, 가격 응대"},
    {"name": "고객지원팀",   "description": "사용자 문의, RMA, AS"},
    {"name": "기술지원팀",   "description": "엔지니어링 escalation, on-site"},
    {"name": "제품기획팀",   "description": "라인업 로드맵, spec 결정"},
    {"name": "마케팅팀",     "description": "캠페인, 가격 포지셔닝"},
]

# (이름, 직책, 부서, primary)
CONTACTS = [
    ("김영업", "팀장",   "영업팀",     True),
    ("이세일", "선임",   "영업팀",     False),
    ("박지원", "팀장",   "고객지원팀", True),
    ("최성웅", "엔지니어","기술지원팀", True),
    ("정혜원", "팀장",   "제품기획팀", True),
    ("강민호", "선임",   "제품기획팀", False),
    ("윤마케팅", "팀장", "마케팅팀",   True),
    ("한도현", "엔지니어","기술지원팀", False),
]

# (name, category, description, department, primary_contact name, specs)
PRODUCTS = [
    ("Galaxy S25 Phantom Black 256GB", Product.Category.PRODUCT,
     "기본 라인업, 256GB, 12GB RAM, 108MP 메인 카메라",
     "영업팀", "김영업",
     {"color": "Phantom Black", "storage": "256GB", "ram": "12GB", "price_usd": 1199.99, "battery": "5000mAh"}),
    ("Galaxy S25 Silver 256GB", Product.Category.PRODUCT,
     "기본 라인업, 실버, 256GB",
     "영업팀", "이세일",
     {"color": "Silver", "storage": "256GB", "ram": "12GB", "price_usd": 1199.99}),
    ("Galaxy S25 Navy Blue 512GB", Product.Category.PRODUCT,
     "기본 라인업, 네이비 블루, 512GB, 16GB RAM",
     "영업팀", "이세일",
     {"color": "Navy Blue", "storage": "512GB", "ram": "16GB", "price_usd": 1299.99}),
    ("Galaxy S25 Plus Phantom Black 256GB", Product.Category.PRODUCT,
     "Plus 라인업, 6.9\" 디스플레이, 5500mAh",
     "영업팀", "김영업",
     {"color": "Phantom Black", "storage": "256GB", "ram": "12GB", "price_usd": 1399.99}),
    ("Galaxy S25 Plus Silver 512GB", Product.Category.PRODUCT,
     "Plus 라인업, 실버, 512GB",
     "영업팀", "이세일",
     {"color": "Silver", "storage": "512GB", "ram": "16GB", "price_usd": 1499.99}),
    ("Galaxy S25 Ultra Phantom Black 512GB", Product.Category.PRODUCT,
     "Ultra 라인업, 7.0\" 디스플레이, 200MP 카메라, 6000mAh",
     "영업팀", "김영업",
     {"color": "Phantom Black", "storage": "512GB", "ram": "16GB", "price_usd": 1599.99}),
    ("Galaxy S25 Ultra Silver 1TB", Product.Category.PRODUCT,
     "Ultra 라인업, 실버, 1TB 최상위 모델",
     "영업팀", "김영업",
     {"color": "Silver", "storage": "1TB", "ram": "16GB", "price_usd": 1799.99}),
    ("프리미엄 케어 서비스", Product.Category.SERVICE,
     "사고 보상 + 화면 수리 무제한",
     "고객지원팀", "박지원",
     {"price_krw_per_year": 120000}),
]

# (word, category, severity, direction)
FORBIDDEN_WORDS = [
    # MASK — PII
    ("주민등록번호", "PII",       "MASK",    "BOTH"),
    ("주민번호",     "PII",       "MASK",    "BOTH"),
    ("신용카드",     "PII",       "MASK",    "BOTH"),
    ("고객번호",     "PII",       "MASK",    "INBOUND"),
    # WARNING — 경쟁사 / 마케팅 민감
    ("애플",         "경쟁사",    "WARNING", "BOTH"),
    ("아이폰",       "경쟁사",    "WARNING", "BOTH"),
    ("화웨이",       "경쟁사",    "WARNING", "BOTH"),
    ("샤오미",       "경쟁사",    "WARNING", "BOTH"),
    # BLOCK — 내부 기밀
    ("프로젝트 X",   "코드네임",  "BLOCK",   "BOTH"),
    ("인수합병",     "M&A",       "BLOCK",   "BOTH"),
    ("미공개",       "기밀",      "BLOCK",   "BOTH"),
    ("내부전용",     "기밀",      "BLOCK",   "BOTH"),
    # OUTBOUND only — LLM이 잘못 노출하면 안 되는 키워드
    ("내부 가격표", "기밀",       "BLOCK",   "OUTBOUND"),
    ("원가",         "기밀",      "WARNING", "OUTBOUND"),
    ("마진율",       "기밀",      "BLOCK",   "OUTBOUND"),
]


class Command(BaseCommand):
    help = "Seed demo data for the sales-team beta (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Wipe existing seed-managed rows before re-creating.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            self.stdout.write(self.style.WARNING("Resetting seed data..."))
            ForbiddenWord.objects.all().delete()
            Product.objects.all().delete()
            Contact.objects.all().delete()
            Department.objects.all().delete()

        with transaction.atomic():
            dept_by_name = {}
            for d in DEPARTMENTS:
                obj, created = Department.objects.update_or_create(
                    name=d["name"], defaults={"description": d["description"]},
                )
                dept_by_name[d["name"]] = obj
                self._log("Department", obj.name, created)

            contact_by_name = {}
            for name, title, dept_name, is_primary in CONTACTS:
                obj, created = Contact.objects.update_or_create(
                    name=name, department=dept_by_name[dept_name],
                    defaults={
                        "title": title, "email": f"{name}@example.com",
                        "phone": "010-0000-0000", "is_primary": is_primary,
                    },
                )
                contact_by_name[name] = obj
                self._log("Contact", obj.name, created)

            for name, category, desc, dept_name, contact_name, specs in PRODUCTS:
                obj, created = Product.objects.update_or_create(
                    name=name,
                    defaults={
                        "category": category, "description": desc,
                        "department": dept_by_name[dept_name],
                        "primary_contact": contact_by_name.get(contact_name),
                        "specs": specs, "is_active": True,
                    },
                )
                self._log("Product", obj.name, created)

            for word, category, severity, direction in FORBIDDEN_WORDS:
                obj, created = ForbiddenWord.objects.update_or_create(
                    word=word,
                    defaults={
                        "category": category, "severity": severity,
                        "direction": direction, "is_active": True,
                        "mask_replacement": "[REDACTED]",
                    },
                )
                self._log("ForbiddenWord", obj.word, created)

        self.stdout.write(self.style.SUCCESS(
            f"Done. {Department.objects.count()} depts · "
            f"{Contact.objects.count()} contacts · "
            f"{Product.objects.count()} products · "
            f"{ForbiddenWord.objects.count()} forbidden words."
        ))

    def _log(self, kind, name, created):
        verb = self.style.SUCCESS("created") if created else self.style.NOTICE("updated")
        self.stdout.write(f"  {verb} {kind}: {name}")
