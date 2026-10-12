"""Remplit le catalogue Fruits & Légumes du marché. Idempotent (re-jouable).

Usage : pipenv run python manage.py seed_products
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from store.models import Category, Product

CATALOG = {
    "Fruits": [
        {"name": "Pomme Golden", "price": "12.50", "unit": "kg", "stock": 94,
         "description": "Pomme Golden douce et croquante du Moyen Atlas. Parfaite à croquer ou en tarte.",
         "tags": ["pomme", "fruit", "doux", "croquante"], "attributes": {"origine": "Maroc", "calibre": "gros"}},
        {"name": "Banane", "price": "14.00", "unit": "kg", "stock": 46,
         "description": "Banane importée riche en potassium. Énergie naturelle pour le sport et le goûter.",
         "tags": ["banane", "fruit", "potassium", "énergie"], "attributes": {"origine": "Import", "maturité": "à point"}},
        {"name": "Orange Navel", "price": "9.00", "unit": "kg", "stock": 120,
         "description": "Orange Navel juteuse du Souss, gorgée de vitamine C. Idéale en jus du matin.",
         "tags": ["orange", "fruit", "jus", "vitamine C"], "attributes": {"origine": "Maroc", "saison": "hiver"}},
        {"name": "Clémentine", "price": "11.00", "unit": "kg", "stock": 85,
         "description": "Clémentine facile à éplucher, douce et parfumée. Le fruit préféré des enfants.",
         "tags": ["clémentine", "fruit", "doux", "enfant"], "attributes": {"origine": "Maroc", "sans pépins": True}},
        {"name": "Citron", "price": "7.00", "unit": "kg", "stock": 70,
         "description": "Citron jaune bien juteux pour assaisonner poissons, salades et jus détox.",
         "tags": ["citron", "fruit", "jus", "assaisonnement"], "attributes": {"origine": "Maroc"}},
        {"name": "Fraise", "price": "22.00", "unit": "kg", "stock": 40,
         "description": "Fraise gariguette sucrée et parfumée de Loukkos. À déguster nature ou en dessert.",
         "tags": ["fraise", "fruit", "sucré", "dessert"], "attributes": {"origine": "Maroc", "fragile": True}},
        {"name": "Raisin blanc", "price": "18.00", "unit": "kg", "stock": 55,
         "description": "Raisin blanc muscat, grains croquants et sucrés. Parfait pour les plateaux de fruits.",
         "tags": ["raisin", "fruit", "sucré"], "attributes": {"origine": "Maroc", "sans pépins": False}},
        {"name": "Pastèque", "price": "4.50", "unit": "kg", "stock": 30,
         "description": "Pastèque d'été ultra rafraîchissante, chair rouge et sucrée. La star des pique-niques.",
         "tags": ["pastèque", "fruit", "été", "rafraîchissant"], "attributes": {"origine": "Maroc", "saison": "été"}},
        {"name": "Melon", "price": "12.00", "unit": "piece", "stock": 25,
         "description": "Melon charentais parfumé à chair orange. Servi frais en entrée avec du jambon.",
         "tags": ["melon", "fruit", "été"], "attributes": {"origine": "Maroc", "pièce": "≈1,2 kg"}},
        {"name": "Pêche", "price": "16.00", "unit": "kg", "stock": 50,
         "description": "Pêche jaune fondante et juteuse. Délicieuse en salade de fruits ou en compote.",
         "tags": ["pêche", "fruit", "juteux", "été"], "attributes": {"origine": "Maroc", "saison": "été"}},
        {"name": "Abricot", "price": "20.00", "unit": "kg", "stock": 38,
         "description": "Abricot doux et velouté, riche en bêta-carotène. Excellent en confiture maison.",
         "tags": ["abricot", "fruit", "confiture"], "attributes": {"origine": "Maroc", "saison": "été"}},
        {"name": "Grenade", "price": "13.00", "unit": "kg", "stock": 42,
         "description": "Grenade aux grains rubis acidulés, pleine d'antioxydants. Superbe en jus et salades.",
         "tags": ["grenade", "fruit", "jus", "antioxydant"], "attributes": {"origine": "Maroc", "saison": "automne"}},
        {"name": "Dattes Deglet Nour", "price": "28.00", "old_price": "34.00", "unit": "kg", "stock": 60,
         "description": "Dattes Deglet Nour fondantes, récoltées à maturité. L'accompagnement du thé et du Ramadan.",
         "tags": ["datte", "fruit", "sucré", "ramadan"], "attributes": {"origine": "Tunisie", "qualité": "extra"}},
        {"name": "Figue", "price": "24.00", "old_price": "29.00", "unit": "kg", "stock": 22,
         "description": "Figue noire sucrée et délicate, à manger mûre. Sublime avec du fromage de chèvre.",
         "tags": ["figue", "fruit", "sucré"], "attributes": {"origine": "Maroc", "fragile": True}},
    ],
    "Légumes": [
        {"name": "Tomate", "price": "8.00", "unit": "kg", "stock": 35,
         "description": "Tomate ronde charnue pour salades, sauces et tajines. Mûrie au soleil du Souss.",
         "tags": ["tomate", "légume", "salade", "sauce"], "attributes": {"origine": "Maroc", "variété": "ronde"}},
        {"name": "Pomme de terre", "price": "6.00", "unit": "kg", "stock": 200,
         "description": "Pomme de terre polyvalente pour frites, purées et tajines. Chair ferme qui tient à la cuisson.",
         "tags": ["pomme de terre", "légume", "frites"], "attributes": {"origine": "Maroc", "chair": "ferme"}},
        {"name": "Oignon", "price": "5.50", "unit": "kg", "stock": 150,
         "description": "Oignon jaune, la base de toutes les cuissons : tajines, sauces et salades.",
         "tags": ["oignon", "légume", "cuisson"], "attributes": {"origine": "Maroc", "conservation": "longue"}},
        {"name": "Carotte", "price": "6.50", "unit": "kg", "stock": 110,
         "description": "Carotte croquante et sucrée, riche en vitamine A. Crue en salade ou cuite en soupe.",
         "tags": ["carotte", "légume", "soupe", "salade"], "attributes": {"origine": "Maroc"}},
        {"name": "Poivron", "price": "10.00", "unit": "kg", "stock": 65,
         "description": "Poivron tricolore croquant et doux : salades, farcis et chakchouka.",
         "tags": ["poivron", "légume", "salade"], "attributes": {"origine": "Maroc", "couleurs": "rouge/vert/jaune"}},
        {"name": "Courgette", "price": "8.50", "unit": "kg", "stock": 75,
         "description": "Courgette tendre pour gratins, soupes et tajines. Se cuisine de mille façons.",
         "tags": ["courgette", "légume", "gratin"], "attributes": {"origine": "Maroc"}},
        {"name": "Aubergine", "price": "9.00", "unit": "kg", "stock": 58,
         "description": "Aubergine fondante pour zaalouk, grillades et moussaka. Chair douce sans amertume.",
         "tags": ["aubergine", "légume", "zaalouk", "grillade"], "attributes": {"origine": "Maroc"}},
        {"name": "Concombre", "price": "7.50", "unit": "kg", "stock": 80,
         "description": "Concombre frais et croquant pour salades d'été et tzatziki maison.",
         "tags": ["concombre", "légume", "salade", "été"], "attributes": {"origine": "Maroc"}},
        {"name": "Salade verte", "price": "5.00", "unit": "piece", "stock": 45,
         "description": "Laitue verte croquante du jour, cueillie le matin. La base de vos salades.",
         "tags": ["salade", "légume", "vert", "frais"], "attributes": {"origine": "Maroc", "cueillette": "jour"}},
        {"name": "Chou-fleur", "price": "9.50", "unit": "piece", "stock": 32,
         "description": "Chou-fleur blanc et compact : gratin, couscous aux légumes ou beignets.",
         "tags": ["chou-fleur", "légume", "gratin"], "attributes": {"origine": "Maroc"}},
        {"name": "Haricot vert", "price": "14.00", "old_price": "17.00", "unit": "kg", "stock": 48,
         "description": "Haricot vert fin et tendre, à la vapeur avec un filet d'huile d'olive.",
         "tags": ["haricot", "légume", "vapeur"], "attributes": {"origine": "Maroc", "calibre": "fin"}},
        {"name": "Petit pois", "price": "13.00", "unit": "kg", "stock": 36,
         "description": "Petit pois sucré à écosser, pour tajines, couscous et salades composées.",
         "tags": ["petit pois", "légume", "tajine"], "attributes": {"origine": "Maroc"}},
        {"name": "Betterave", "price": "7.00", "unit": "kg", "stock": 52,
         "description": "Betterave rouge sucrée pour salades colorées et jus vitaminés.",
         "tags": ["betterave", "légume", "salade", "jus"], "attributes": {"origine": "Maroc"}},
        {"name": "Ail", "price": "18.00", "unit": "kg", "stock": 90,
         "description": "Ail blanc parfumé, indispensable en cuisine méditerranéenne et pour la santé.",
         "tags": ["ail", "légume", "assaisonnement"], "attributes": {"origine": "Maroc", "conservation": "longue"}},
        {"name": "Menthe fraîche", "price": "3.00", "unit": "pack", "stock": 60,
         "description": "Botte de menthe fraîche pour le thé à la menthe et les salades. Cueillie du jour.",
         "tags": ["menthe", "herbe", "thé", "frais"], "attributes": {"origine": "Maroc", "botte": "fraîche"}},
    ],
}


class Command(BaseCommand):
    help = "Remplit le catalogue Fruits & Légumes (idempotent)."

    def handle(self, *args, **options):
        created_cats = created_prods = updated_prods = 0
        with transaction.atomic():
            for cat_name, items in CATALOG.items():
                cat, cat_created = Category.objects.get_or_create(
                    name=cat_name,
                    defaults={"slug": slugify(cat_name), "description": f"{cat_name} frais du marché.", "is_active": True},
                )
                if cat_created:
                    created_cats += 1
                for item in items:
                    slug = slugify(item["name"])
                    defaults = {
                        "name": item["name"],
                        "category": cat,
                        "price": item["price"],
                        "unit": item["unit"],
                        "stock": item["stock"],
                        "description": item["description"],
                        "tags": item["tags"],
                        "attributes": item["attributes"],
                        "is_active": True,
                    }
                    if item.get("old_price"):
                        defaults["old_price"] = item["old_price"]
                    _, prod_created = Product.objects.update_or_create(slug=slug, defaults=defaults)
                    if prod_created:
                        created_prods += 1
                    else:
                        updated_prods += 1
        self.stdout.write(self.style.SUCCESS(
            f"Catégories créées : {created_cats} | Produits créés : {created_prods} | mis à jour : {updated_prods} "
            f"| total : {Product.objects.count()}"
        ))
