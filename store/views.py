"""Vues boutique : liste + recherche full-text + filtres + pagination + panier HTMX."""

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Case, ExpressionWrapper, F, FloatField, Value, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .cart import get_cart
from .models import Category, Product


def product_list(request):
    """Liste + recherche live (HTMX) + filtres + pagination. Rendu Django uniquement."""
    q = request.GET.get("q", "").strip()
    cat_slug = request.GET.get("category", "")
    min_price = request.GET.get("min_price", "")
    max_price = request.GET.get("max_price", "")
    in_stock = request.GET.get("in_stock", "")
    on_sale = request.GET.get("on_sale", "")
    sort = request.GET.get("sort", "newest")
    if sort not in ("newest", "price_asc", "price_desc", "name", "name_desc", "promo"):
        sort = "newest"

    qs = Product.objects.search(q) if q else Product.objects.active()
    qs = qs.select_related("category")

    if cat_slug:
        qs = qs.filter(category__slug=cat_slug)
    if min_price:
        try:
            qs = qs.filter(price__gte=min_price)
        except ValueError:
            pass
    if max_price:
        try:
            qs = qs.filter(price__lte=max_price)
        except ValueError:
            pass
    if in_stock == "on":
        qs = qs.filter(stock__gt=0)
    if on_sale == "on":
        qs = qs.filter(old_price__isnull=False, old_price__gt=F("price"))

    # Tri serveur (le full-text garde son rang par défaut en mode "newest")
    if sort == "price_asc":
        qs = qs.order_by("price", "-created_at")
    elif sort == "price_desc":
        qs = qs.order_by("-price", "-created_at")
    elif sort == "name":
        qs = qs.order_by("name")
    elif sort == "name_desc":
        qs = qs.order_by("-name")
    elif sort == "promo":
        discount = Case(
            When(
                old_price__isnull=False,
                old_price__gt=F("price"),
                then=ExpressionWrapper(
                    (F("old_price") - F("price")) / F("old_price"),
                    output_field=FloatField(),
                ),
            ),
            default=Value(0.0),
            output_field=FloatField(),
        )
        qs = qs.annotate(_discount=discount).order_by("-_discount", "-created_at")
    elif not q:
        # Prix filtré sans tri explicite : min → croissant, max seul → décroissant.
        # Le menu garde le tri réel : au refresh on revient à Nouveautés.
        if min_price:
            qs = qs.order_by("price", "-created_at")
        elif max_price:
            qs = qs.order_by("-price", "-created_at")
        else:
            qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 12)
    page = paginator.get_page(request.GET.get("page", 1))

    # Quantités déjà au panier → badge "X au panier" par carte (100% Python)
    try:
        cart = get_cart(request)
        qty_map = dict(cart.lines.values_list("product_id", "quantity"))
    except Exception:
        qty_map = {}
    for p in page.object_list:
        p.cart_qty = qty_map.get(p.pk, 0)

    ctx = {
        "page": page,
        "categories": Category.objects.filter(is_active=True),
        "q": q,
        "cat_slug": cat_slug,
        "min_price": min_price,
        "max_price": max_price,
        "in_stock": in_stock,
        "on_sale": on_sale,
        "sort": sort,
        "total_count": paginator.count,
        "has_filters": bool(q or cat_slug or min_price or max_price or in_stock or on_sale),
    }
    # Fragment HTMX préfixé "_" pour recherche live / pagination / filtres
    if request.htmx:
        return render(request, "store/partials/_product_grid.html", ctx)
    return render(request, "store/product_list.html", ctx)


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related("category"), slug=slug)
    return render(request, "store/product_detail.html", {"product": product})


def cart_detail(request):
    cart = get_cart(request)
    return render(request, "store/cart_detail.html", {"cart": cart})


def _cart_ctx(cart, product):
    """Contexte fragment : pastille header (OOB) + badge carte (OOB)."""
    line = cart.lines.filter(product=product).first()
    return {"cart": cart, "updated_slug": product.slug, "updated_qty": line.quantity if line else 0}


@require_POST
def _cart_add(request, slug):
    """Fragment HTMX : ajoute 1 unité, renvoie pastille + lignes."""
    cart = get_cart(request)
    product = get_object_or_404(Product, slug=slug)
    try:
        cart.add_product(product, 1)
    except ValueError as e:
        messages.error(request, str(e))
    if request.htmx:
        resp = render(request, "store/partials/_cart_lines.html", _cart_ctx(cart, product))
        resp["HX-Trigger"] = "cart-updated"
        return resp
    return redirect("store:cart_detail")


@require_POST
def _cart_set(request, slug):
    cart = get_cart(request)
    product = get_object_or_404(Product, slug=slug)
    try:
        cart.set_quantity(product, int(request.POST.get("qty", 1)))
    except ValueError as e:
        messages.error(request, str(e))
    return render(request, "store/partials/_cart_lines.html", _cart_ctx(cart, product))


@require_POST
def _cart_minus(request, slug):
    """Fragment HTMX : retire 1 unité (supprime la ligne à 0)."""
    cart = get_cart(request)
    product = get_object_or_404(Product, slug=slug)
    line = cart.lines.filter(product=product).first()
    if line:
        try:
            cart.set_quantity(product, line.quantity - 1)
        except ValueError as e:
            messages.error(request, str(e))
    return render(request, "store/partials/_cart_lines.html", _cart_ctx(cart, product))


@require_POST
def _cart_remove(request, slug):
    """Fragment HTMX : retire la ligne complète (✕)."""
    cart = get_cart(request)
    product = get_object_or_404(Product, slug=slug)
    cart.lines.filter(product=product).delete()
    return render(request, "store/partials/_cart_lines.html", _cart_ctx(cart, product))


def _merge_session_cart_to_user(request, user):
    """Transfère le panier anonyme vers le compte. À appeler AVANT auth_login
    (la connexion fait pivoter la clé de session)."""
    from .models import Cart

    key = request.session.session_key
    if not key:
        return
    try:
        anon = Cart.objects.get(session_key=key, user__isnull=True)
    except Cart.DoesNotExist:
        return
    user_cart, _ = Cart.objects.get_or_create(user=user)
    if anon.pk == user_cart.pk:
        return
    for line in anon.lines.select_related("product"):
        try:
            user_cart.add_product(line.product, line.quantity)
        except ValueError:
            continue
    anon.delete()


def login_view(request):
    """Connexion par email + mot de passe (panier anonyme conservé)."""
    from .forms import EmailLoginForm

    if request.method == "POST":
        form = EmailLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            _merge_session_cart_to_user(request, user)
            auth_login(request, user)
            return redirect("store:product_list")
    else:
        form = EmailLoginForm()
    return render(request, "store/login.html", {"form": form})


def signup_view(request):
    """Création de compte client + connexion auto + panier conservé."""
    from .forms import SignupForm

    if request.user.is_authenticated:
        return redirect("store:product_list")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            _merge_session_cart_to_user(request, user)
            auth_login(request, user, backend="store.backends.EmailBackend")
            messages.success(request, f"Bienvenue {user.username} ! Compte créé.")
            return redirect("store:product_list")
    else:
        form = SignupForm()
    return render(request, "store/signup.html", {"form": form})


def logout_view(request):
    auth_logout(request)
    return redirect("store:product_list")


def checkout_view(request):
    """Checkout classique (POST → Order.create_from_cart, 100% Python).

    Comptes staff (équipe/vendeurs) : gestion uniquement, commande interdite.
    """
    from .forms import CheckoutForm
    from .models import Order

    if request.user.is_staff:
        messages.error(request, "Compte équipe : la commande est réservée aux clients.")
        return redirect("store:cart_detail")
    cart = get_cart(request)
    if cart.count == 0:
        messages.info(request, "Panier vide.")
        return redirect("store:cart_detail")
    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order = Order.create_from_cart(cart, **form.to_order_kwargs())
            except ValueError as e:
                messages.error(request, str(e))
                return redirect("store:cart_detail")
            return redirect("store:order_success", uuid=order.uuid)
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {"email": request.user.email}
        form = CheckoutForm(initial=initial)
    return render(request, "store/checkout.html", {"form": form, "cart": cart})


def order_success(request, uuid):
    from .models import Order

    order = get_object_or_404(Order, uuid=uuid)
    return render(request, "store/order_success.html", {"order": order})


@login_required
def order_list(request):
    """Historique des commandes du client connecté."""
    from .models import Order

    orders = (
        Order.objects.filter(user=request.user)
        .prefetch_related("items__product")
        .order_by("-created_at")
    )
    return render(request, "store/order_list.html", {"orders": orders})


def _ping(request):
    return HttpResponse("ok")
