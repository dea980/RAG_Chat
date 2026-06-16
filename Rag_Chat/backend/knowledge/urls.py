from django.urls import path

from .views import ContactSearchView, DepartmentListView, ProductSearchView

urlpatterns = [
    path("products/", ProductSearchView.as_view(), name="knowledge-products"),
    path("contacts/", ContactSearchView.as_view(), name="knowledge-contacts"),
    path("departments/", DepartmentListView.as_view(), name="knowledge-departments"),
]
