from django.urls import path

from . import views

app_name = "store"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("produit/<slug:slug>/", views.product_detail, name="product_detail"),
    path("panier/", views.cart_detail, name="cart_detail"),
    path("commande/", views.checkout_view, name="checkout"),
    path("commande/<uuid:uuid>/succes/", views.order_success, name="order_success"),
    # Fragments HTMX préfixés "_"
    path("_panier/ajouter/<slug:slug>/", views._cart_add, name="_cart_add"),
    path("_panier/quantite/<slug:slug>/", views._cart_set, name="_cart_set"),
    path("_panier/moins/<slug:slug>/", views._cart_minus, name="_cart_minus"),
    path("_panier/retirer/<slug:slug>/", views._cart_remove, name="_cart_remove"),
    path("login/", views.login_view, name="login"),
    path("inscription/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
]
