from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from apps.accounts.permissions import IsAdminRole

from .filters import ProductFilter
from .models import Product
from .serializers import ProductSerializer


@extend_schema_view(
    list=extend_schema(summary="List products (search & price filters)"),
    retrieve=extend_schema(summary="Product detail"),
)
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_class = ProductFilter
    search_fields = ("name",)
    ordering_fields = ("price", "created_at", "name")

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAuthenticated(), IsAdminRole()]
        return [permissions.AllowAny()]
