"""Modèles grocery store — 100% PostgreSQL, logique métier 100% Python.

Types avancés exigés :
- UUIDField : Product.uuid (pk), Order.uuid
- ArrayField : Product.tags (nécessite django.contrib.postgres)
- JSONField : Product.attributes, Order.shipping_address
- SearchVector : recherche full-text (jamais icontains), voir ProductQuerySet.search()
"""

import unicodedata
import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramWordSimilarity,
)
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CharField, F, Func, Q, Value
from django.db.models.functions import Greatest
from django.urls import reverse
from django.utils.text import slugify


def product_text_vector():
    """Vecteur full-text partagé (nom + hashtags + description). 100% PostgreSQL.

    Pondération : nom (A) > tags ArrayField (B) > description (C).
    Les tags sont concaténés via array_to_string puis vectorisés.
    """
    tags_text = Func(F("tags"), Value(" "), function="array_to_string", output_field=CharField())
    return (
        SearchVector("name", weight="A", config="french")
        + SearchVector(tags_text, weight="B", config="french")
        + SearchVector("description", weight="C", config="french")
    )


def clean_search_query(query):
    """Nettoie la saisie : retire les '#' (ex. '#jus' → 'jus'). 100% Python."""
    return " ".join(w.lstrip("#") for w in (query or "").split())


def fold_query(query):
    """Minuscules sans accents, miroir Python de unaccent() SQL. 100% Python."""
    norm = unicodedata.normalize("NFD", query or "")
    return "".join(c for c in norm if unicodedata.category(c) != "Mn").lower()


def score_text_search(qs, query):
    """Full-text (mots entiers) + similarité de mots (frappe partielle).

    - rank : SearchRank nom(A) > tags(B) > description(C), config french.
    - sim : WORD_SIMILARITY(requête, colonne) — la requête DOIT être le
      premier argument pour bien scorer le partiel ("pom" → "pomme" ≈ 0.75).
      Colonnes nom/tags passées à unaccent(), requête normalisée en Python.
      La description est exclue du partiel (trop de petits mots français).
    Un résultat passe si rank >= 0.05 OU sim > seuil (0.3 si 1-2 lettres,
    0.6 sinon : les requêtes courtes matchent large, les longues exigent
    un vrai préfixe). 100% PostgreSQL.
    """
    tags_text = Func(F("tags"), Value(" "), function="array_to_string", output_field=CharField())
    folded = fold_query(query)
    threshold = 0.6 if len(folded) >= 3 else 0.3
    return (
        qs.annotate(
            rank=SearchRank(product_text_vector(), SearchQuery(query, config="french")),
            sim=Greatest(
                TrigramWordSimilarity(Value(folded), Func(F("name"), function="unaccent")),
                TrigramWordSimilarity(Value(folded), Func(tags_text, function="unaccent")),
            ),
        )
        .filter(Q(rank__gte=0.05) | Q(sim__gt=threshold))
        .order_by("-rank", "-sim", "-created_at")
    )


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("store:product_list") + f"?category={self.slug}"


class ProductQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def in_stock(self):
        return self.active().filter(stock__gt=0)

    def search(self, query):
        """Full-text + trigramme PostgreSQL uniquement. Jamais icontains.

        Cherche dans le nom ET les hashtags (tags) ET la description,
        dès le premier caractère tapé ("lé" trouve déjà les légumes).
        Pondération : nom (A) > tags (B) > description (C), puis similarité.
        """
        query = clean_search_query(query)
        if not query:
            return self.active().order_by("-created_at")
        return score_text_search(self.active(), query)


class Product(models.Model):
    UNIT_CHOICES = [
        ("piece", "Pièce"),
        ("kg", "Kg"),
        ("g", "G"),
        ("l", "Litre"),
        ("pack", "Pack"),
    ]

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default="piece")
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="products/%Y/%m/", blank=True, null=True)

    # Types Postgres avancés
    tags = ArrayField(models.CharField(max_length=50), default=list, blank=True)
    attributes = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "produit"
        verbose_name_plural = "produits"
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["price"]),
            GinIndex(fields=["tags"], name="product_tags_gin"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="product_price_gte0"),
            models.CheckConstraint(
                condition=models.Q(old_price__isnull=True) | models.Q(old_price__gte=0),
                name="product_old_price_gte0",
            ),
            models.CheckConstraint(condition=~models.Q(name=""), name="product_name_nonempty"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            i = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("store:product_detail", kwargs={"slug": self.slug})

    # --- Logique métier 100% Python ---
    @property
    def is_in_stock(self):
        return self.stock > 0

    @property
    def discount_pct(self):
        if self.old_price and self.old_price > self.price:
            return round((1 - self.price / self.old_price) * 100)
        return 0

    @property
    def initial(self):
        """Initiale de repli quand aucune image produit. 100% Python."""
        return (self.name[:1] or "?").upper()


class Cart(models.Model):
    """Un panier = user connecté OU session_key anonyme. Jamais les deux vides."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="carts",
    )
    session_key = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "panier"
        verbose_name_plural = "paniers"
        constraints = [
            models.UniqueConstraint(fields=["session_key"], name="unique_session_cart"),
        ]

    def __str__(self):
        owner = self.user.username if self.user else f"session:{self.session_key}"
        return f"Panier {owner}"

    # --- Logique métier ---
    @property
    def items(self):
        return self.lines.select_related("product", "product__category")

    @property
    def count(self):
        return sum(line.quantity for line in self.lines.all())

    @property
    def total(self):
        return sum(line.subtotal for line in self.lines.all())

    def add_product(self, product, qty=1):
        if qty < 1:
            raise ValueError("Quantité >= 1 exigée.")
        if product.stock < qty:
            raise ValueError(f"Stock insuffisant ({product.stock} dispo).")
        line, created = self.lines.get_or_create(product=product, defaults={"quantity": qty})
        if created:
            return line
        new_qty = line.quantity + qty
        if product.stock < new_qty:
            raise ValueError(f"Stock insuffisant ({product.stock} dispo).")
        line.quantity = new_qty
        line.save()
        return line

    def set_quantity(self, product, qty):
        if qty < 0:
            raise ValueError("Quantité négative interdite.")
        if qty == 0:
            self.lines.filter(product=product).delete()
            return None
        if product.stock < qty:
            raise ValueError(f"Stock insuffisant ({product.stock} dispo).")
        line, _ = self.lines.get_or_create(product=product, defaults={"quantity": qty})
        line.quantity = qty
        line.save()
        return line


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="lines")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="cart_lines")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "article du panier"
        verbose_name_plural = "articles du panier"
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="unique_cart_product"),
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="cartitem_qty_gte1"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "En attente"),
        ("paid", "Payée"),
        ("preparing", "En préparation"),
        ("done", "Terminée"),
        ("cancelled", "Annulée"),
    ]
    PAYMENT_CHOICES = [
        ("cash", "Espèces à la livraison"),
        ("card", "Carte bancaire"),
        ("transfer", "Virement bancaire"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="orders",
    )
    email = models.EmailField()
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    # Adresse libre + snapshot — JSONField Postgres
    shipping_address = models.JSONField(default=dict)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="pending")
    payment_method = models.CharField(max_length=12, choices=PAYMENT_CHOICES, default="cash")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "commande"
        verbose_name_plural = "commandes"
        constraints = [
            models.CheckConstraint(condition=models.Q(total__gte=0), name="order_total_gte0"),
        ]

    def __str__(self):
        return f"Commande {self.uuid.hex[:8]} — {self.total} $"

    @classmethod
    def create_from_cart(cls, cart, **customer):
        """Transfère panier -> commande + décrémente stock. 100% Python."""
        if cart.count == 0:
            raise ValueError("Panier vide.")
        order = cls.objects.create(
            user=cart.user,
            total=cart.total,
            **customer,
        )
        for line in cart.items:
            if line.product.stock < line.quantity:
                raise ValueError(f"Rupture : {line.product.name}.")
            OrderItem.objects.create(
                order=order,
                product=line.product,
                product_name=line.product.name,
                price=line.product.price,
                quantity=line.quantity,
            )
            line.product.stock -= line.quantity
            line.product.save(update_fields=["stock"])
        cart.lines.all().delete()
        return order


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=200)  # snapshot si produit renommé
    price = models.DecimalField(max_digits=10, decimal_places=2)  # snapshot prix
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "article de commande"
        verbose_name_plural = "articles de commande"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="orderitem_qty_gte1"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="orderitem_price_gte0"),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"

    @property
    def subtotal(self):
        return self.price * self.quantity
