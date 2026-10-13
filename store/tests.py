"""Tests automatisés boutique — `pipenv run python manage.py test`.

Couvre : recherche (nom/hashtag/partiel), tri/filtres, panier HTMX,
commande + stock, blocage staff, inscription, login email, mes commandes,
alerte stock bas admin. 100% PostgreSQL (base de test dédiée).
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from store.models import Cart, Category, Order, Product

VALID_CUSTOMER = {
    "email": "client@test.tn",
    "first_name": "Hist",
    "last_name": "Test",
    "street": "Rue test 12345",
    "city": "Tunis",
    "zip_code": "1000",
    "phone": "99 999 999",
    "payment_method": "cash",
}


class BoutiqueTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.fruits = Category.objects.create(name="Fruits")
        cls.legumes = Category.objects.create(name="Légumes")
        cls.pomme = Product.objects.create(
            category=cls.fruits, name="Pomme Golden", price="12.50", unit="kg",
            stock=10, tags=["pomme", "fruit"], description="Pomme douce et croquante",
        )
        cls.banane = Product.objects.create(
            category=cls.fruits, name="Banane", price="14.00", unit="kg",
            stock=5, tags=["banane", "fruit"],
        )
        cls.tomate = Product.objects.create(
            category=cls.legumes, name="Tomate", price="8.00", unit="kg",
            stock=3, tags=["tomate", "tajine"],
        )
        cls.dattes = Product.objects.create(
            category=cls.fruits, name="Dattes", price="28.00", old_price="34.00",
            unit="kg", stock=7, tags=["datte", "sucré"],
        )
        cls.customer = User.objects.create_user("client", "client@test.tn", "S3cure-pass-99")
        cls.staff = User.objects.create_user("vendeur", "vendeur@test.tn", "S3cure-pass-99", is_staff=True)
        cls.boss = User.objects.create_superuser("boss", "boss@test.tn", "S3cure-pass-99")

    # ---------- recherche ----------
    def test_recherche_nom(self):
        body = self.client.get(reverse("store:product_list"), {"q": "pomme"}).content.decode()
        self.assertIn("Pomme Golden", body)
        self.assertNotIn("Banane", body)

    def test_recherche_hashtag(self):
        body = self.client.get(reverse("store:product_list"), {"q": "#tajine"}).content.decode()
        self.assertIn("Tomate", body)
        self.assertNotIn("Banane", body)

    def test_recherche_partielle_chaque_lettre(self):
        body = self.client.get(reverse("store:product_list"), {"q": "tomat"}).content.decode()
        self.assertIn("Tomate", body)
        self.assertNotIn("Banane", body)

    def test_recherche_vide_ou_absurde(self):
        self.assertIn("Pomme Golden", self.client.get(reverse("store:product_list"), {"q": ""}).content.decode())
        body = self.client.get(reverse("store:product_list"), {"q": "xyz123"}).content.decode()
        self.assertIn("Rien pour", body)

    # ---------- tri / filtres ----------
    def _positions(self, body, *names):
        return [body.index(n) for n in names]

    def test_tri_prix_croissant(self):
        body = self.client.get(reverse("store:product_list"), {"sort": "price_asc"}).content.decode()
        self.assertEqual(self._positions(body, "Tomate", "Pomme Golden", "Banane", "Dattes"), sorted(self._positions(body, "Tomate", "Pomme Golden", "Banane", "Dattes")))

    def test_tri_prix_auto_avec_min(self):
        body = self.client.get(reverse("store:product_list"), {"min_price": "5"}).content.decode()
        self.assertEqual(self._positions(body, "Tomate", "Pomme Golden", "Banane"), sorted(self._positions(body, "Tomate", "Pomme Golden", "Banane")))

    def test_filtre_soldes(self):
        body = self.client.get(reverse("store:product_list"), {"on_sale": "on"}).content.decode()
        self.assertIn("Dattes", body)
        self.assertNotIn("Tomate", body)

    def test_filtre_categorie(self):
        body = self.client.get(reverse("store:product_list"), {"category": "legumes"}).content.decode()
        self.assertIn("Tomate", body)
        self.assertNotIn("Pomme Golden", body)

    # ---------- panier ----------
    def _add(self, slug, qty=1):
        return self.client.post(reverse("store:_cart_set", kwargs={"slug": slug}), {"qty": qty})

    def test_panier_ajout_et_limite_stock(self):
        self._add("pomme-golden", 2)
        cart = Cart.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(cart.count, 2)
        # Au-delà du stock (10) : refusé, quantité inchangée
        self._add("pomme-golden", 999)
        self.assertEqual(Cart.objects.get(session_key=self.client.session.session_key).count, 2)

    def test_panier_moins_et_retirer(self):
        self._add("pomme-golden", 2)
        self.client.post(reverse("store:_cart_minus", kwargs={"slug": "pomme-golden"}))
        cart = Cart.objects.get(session_key=self.client.session.session_key)
        self.assertEqual(cart.count, 1)
        self.client.post(reverse("store:_cart_remove", kwargs={"slug": "pomme-golden"}))
        self.assertEqual(Cart.objects.get(session_key=self.client.session.session_key).count, 0)

    # ---------- commande ----------
    def test_commande_decompte_stock(self):
        self._add("pomme-golden", 3)
        resp = self.client.post(reverse("store:checkout"), VALID_CUSTOMER)
        self.assertEqual(resp.status_code, 302)
        self.pomme.refresh_from_db()
        self.assertEqual(self.pomme.stock, 7)
        order = Order.objects.get(email="client@test.tn")
        self.assertEqual(order.items.first().quantity, 3)

    def test_commande_panier_vide_redirige(self):
        resp = self.client.get(reverse("store:checkout"))
        self.assertEqual(resp.status_code, 302)

    def test_commande_telephone_et_cp_formats(self):
        self._add("pomme-golden", 1)
        base = dict(VALID_CUSTOMER)
        for phone in ["123", "999999999", "abcdefgh", "99-999-999"]:
            resp = self.client.post(reverse("store:checkout"), dict(base, phone=phone))
            self.assertEqual(resp.status_code, 200, f"téléphone {phone!r} accepté !")
        resp = self.client.post(reverse("store:checkout"), dict(base, zip_code="AB"))
        self.assertEqual(resp.status_code, 200)
        resp = self.client.post(reverse("store:checkout"), dict(base, phone="25876411", zip_code="2052"))
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.get(email="client@test.tn")
        self.assertEqual(order.shipping_address["phone"], "25876411")

    def test_commande_carte_valide(self):
        self._add("pomme-golden", 1)
        data = dict(VALID_CUSTOMER, payment_method="card",
                    card_number="4242 4242 4242 4242", card_expiry="12/30", card_cvc="123")
        resp = self.client.post(reverse("store:checkout"), data)
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.get(email="client@test.tn")
        self.assertEqual(order.payment_method, "card")
        # Numéro jamais conservé, référence virement vide
        self.assertNotIn("4242", str(order.shipping_address))

    def test_commande_carte_invalide_refusee(self):
        self._add("pomme-golden", 1)
        n = Order.objects.count()
        data = dict(VALID_CUSTOMER, payment_method="card",
                    card_number="1234", card_expiry="13/99", card_cvc="1")
        resp = self.client.post(reverse("store:checkout"), data)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Order.objects.count(), n)
        body = resp.content.decode()
        self.assertIn("field-error", body)

    def test_commande_virement_avec_reference(self):
        self._add("banane", 1)
        data = dict(VALID_CUSTOMER, payment_method="transfer", transfer_ref="VIR-2026-001")
        resp = self.client.post(reverse("store:checkout"), data)
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.get(email="client@test.tn")
        self.assertEqual(order.shipping_address.get("transfer_ref"), "VIR-2026-001")

    def test_checkout_affiche_sections_dynamiques(self):
        self._add("pomme-golden", 1)
        body = self.client.get(reverse("store:checkout")).content.decode()
        self.assertIn("Numéro de carte", body)
        self.assertIn("RIB démo", body)
        self.assertIn("Référence du virement", body)

    def test_commande_interdite_staff(self):
        staff_client = Client()
        staff_client.force_login(self.staff)
        staff_client.post(reverse("store:_cart_set", kwargs={"slug": "pomme-golden"}), {"qty": 1})
        n = Order.objects.count()
        self.assertEqual(staff_client.get(reverse("store:checkout")).status_code, 302)
        self.assertEqual(staff_client.post(reverse("store:checkout"), VALID_CUSTOMER).status_code, 302)
        self.assertEqual(Order.objects.count(), n)

    # ---------- comptes ----------
    def test_inscription_login_email(self):
        resp = self.client.post(reverse("store:signup"), {
            "username": "nouveau", "email": "Nouveau@Test.tn",
            "password1": "S3cure-pass-99", "password2": "S3cure-pass-99",
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username="nouveau")
        self.assertFalse(user.is_staff)
        self.client.logout()
        resp = self.client.post(reverse("store:login"), {"username": "nouveau@test.tn", "password": "S3cure-pass-99"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_inscription_email_duplique_et_mdp_faible_refuses(self):
        resp = self.client.post(reverse("store:signup"), {
            "username": "autre", "email": "CLIENT@test.tn",
            "password1": "S3cure-pass-99", "password2": "S3cure-pass-99",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="autre").exists())
        resp = self.client.post(reverse("store:signup"), {
            "username": "faible", "email": "f@f.tn", "password1": "abc", "password2": "abc",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="faible").exists())

    def test_login_refus(self):
        resp = self.client.post(reverse("store:login"), {"username": "client@test.tn", "password": "faux-xx"})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        resp = self.client.post(reverse("store:login"), {"username": "inconnu@x.tn", "password": "S3cure-pass-99"})
        self.assertNotIn("_auth_user_id", self.client.session)

    # ---------- mes commandes ----------
    def test_mes_commandes(self):
        url = reverse("store:order_list")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)  # anonyme → login
        self.assertIn(reverse("store:login"), resp["Location"])
        user = User.objects.get(username="client")
        self.client.force_login(user)
        self.assertIn("Aucune commande", self.client.get(url).content.decode())
        self._add("pomme-golden", 2)
        self.client.post(reverse("store:checkout"), VALID_CUSTOMER)
        body = self.client.get(url).content.decode()
        self.assertIn("Pomme Golden", body)
        other = User.objects.create_user("autre", "a@a.tn", "S3cure-pass-99")
        self.client.force_login(other)
        self.assertIn("Aucune commande", self.client.get(url).content.decode())

    # ---------- admin ----------
    def test_admin_stock_bas_premier(self):
        self.tomate.stock = 5
        self.tomate.save(update_fields=["stock"])
        admin = Client()
        admin.force_login(self.boss)
        body = admin.get("/admin/store/product/").content.decode()
        self.assertIn("Attention", body)
        self.assertLess(body.index("Tomate"), body.index("Banane"))
