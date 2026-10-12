"""Admin — get_search_results surchargé en full-text (jamais icontains)."""

from django.contrib import admin
from django.db.models import Case, IntegerField, Value, When
from django.utils.html import format_html

from .models import Cart, CartItem, Category, Order, OrderItem, Product, clean_search_query, score_text_search

SEUIL_STOCK_BAS = 20


class StockBasFilter(admin.SimpleListFilter):
    """Filtre : produits à réassortir (stock < 20)."""

    title = "stock bas"
    parameter_name = "stock_bas"

    def lookups(self, request, model_admin):
        return (
            ("oui", f"Stock < {SEUIL_STOCK_BAS} (à réassortir)"),
            ("non", f"Stock ≥ {SEUIL_STOCK_BAS}"),
        )

    def queryset(self, request, queryset):
        if self.value() == "oui":
            return queryset.filter(stock__lt=SEUIL_STOCK_BAS)
        if self.value() == "non":
            return queryset.filter(stock__gte=SEUIL_STOCK_BAS)
        return queryset


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "alerte_stock", "is_active", "created_at")
    list_filter = ("category", "is_active", "unit", StockBasFilter)
    list_editable = ("price", "stock")
    prepopulated_fields = {"slug": ("name",)}
    # search_fields volontairement vide : on utilise SearchVector ci-dessous
    search_fields = ()

    def get_queryset(self, request):
        """Annote le flag stock bas SANS trier : l'annotation doit exister
        avant que get_ordering() ne trie dessus (le super() trierait trop tôt)."""
        return self.model._default_manager.get_queryset().annotate(
            _stock_bas=Case(
                When(stock__lt=SEUIL_STOCK_BAS, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )

    def get_ordering(self, request):
        """Stocks bas (< 20) affichés en premier (la ChangeList réapplique
        l'ordre par défaut, d'où cette méthode plutôt que order_by seul)."""
        return ["-_stock_bas", "-created_at"]

    @admin.display(description="Alerte stock", ordering="_stock_bas")
    def alerte_stock(self, obj):
        if obj.stock < SEUIL_STOCK_BAS:
            return format_html(
                '<strong style="color:#dc2626;">Attention — stock bas ({}) !</strong>',
                obj.stock,
            )
        return format_html('<span style="color:#059669;">OK</span>')

    def get_search_results(self, request, queryset, search_term):
        if not search_term:
            return queryset, False
        search_term = clean_search_query(search_term)
        if not search_term:
            return queryset, False
        return score_text_search(queryset, search_term), False


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "count", "total", "updated_at")
    inlines = [CartItemInline]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("uuid", "email", "status", "payment_method", "total", "created_at")
    list_filter = ("status", "payment_method", "created_at")
    inlines = [OrderItemInline]
