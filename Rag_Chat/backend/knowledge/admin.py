from django.contrib import admin

from .models import Contact, Department, Product


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "created_at")
    search_fields = ("name", "description")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("name", "title", "department", "email", "is_primary")
    list_filter = ("department", "is_primary")
    search_fields = ("name", "email", "title")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "department", "primary_contact", "is_active")
    list_filter = ("category", "department", "is_active")
    search_fields = ("name", "description")
    autocomplete_fields = ("department", "primary_contact")
