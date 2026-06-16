"""Lightweight search API — sales-team lookups that should NOT go through the LLM.

For "누가 이 제품 담당이야?" type questions we want a deterministic, audited
answer from the DB instead of an LLM-paraphrased one.
"""
from django.db.models import Q
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contact, Department, Product


class ProductSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        category = request.query_params.get("category", "").strip().upper()
        qs = Product.objects.filter(is_active=True).select_related("department", "primary_contact")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if category:
            qs = qs.filter(category=category)
        results = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "description": p.description,
                "department": p.department.name,
                "primary_contact": {
                    "name": p.primary_contact.name,
                    "email": p.primary_contact.email,
                    "phone": p.primary_contact.phone,
                } if p.primary_contact else None,
                "specs": p.specs,
            }
            for p in qs[:50]
        ]
        return Response({"count": len(results), "results": results})


class ContactSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        dept = request.query_params.get("department", "").strip()
        qs = Contact.objects.select_related("department")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(title__icontains=q) | Q(email__icontains=q))
        if dept:
            qs = qs.filter(department__name__icontains=dept)
        results = [
            {
                "id": c.id,
                "name": c.name,
                "title": c.title,
                "email": c.email,
                "phone": c.phone,
                "department": c.department.name,
                "is_primary": c.is_primary,
            }
            for c in qs[:50]
        ]
        return Response({"count": len(results), "results": results})


class DepartmentListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        results = [
            {
                "id": d.id,
                "name": d.name,
                "description": d.description,
                "parent": d.parent.name if d.parent else None,
                "member_count": d.members.count(),
                "product_count": d.products.filter(is_active=True).count(),
            }
            for d in Department.objects.all()
        ]
        return Response({"count": len(results), "results": results})
