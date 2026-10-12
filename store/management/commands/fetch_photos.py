"""Télécharge des photos libres (Wikimedia Commons) pour les produits sans image.

Usage :
    pipenv run python manage.py fetch_photos              # remplit les manquantes
    pipenv run python manage.py fetch_photos tomate ail    # sous-ensemble
    pipenv run python manage.py fetch_photos --force       # tout re-télécharger
"""

import json
import os
import time
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand

from store.models import Product

HEADERS = {
    "User-Agent": "GroceryStore/1.0 (dev market; contact: admin@example.com)",
    "Referer": "https://commons.wikimedia.org/",
}

# slug -> (requête Commons, index du bon candidat) — ordre vérifié visuellement.
PHOTOS = {
    "pomme-golden": ("Golden Delicious apples", 2),
    "banane": ("Ripe yellow bananas", 0),
    "orange-navel": ("Navel oranges fruit", 0),
    "clementine": ("Clementine fruits", 2),
    "citron": ("Lemon fruits", 4),
    "fraise": ("Strawberries", 2),
    "raisin-blanc": ("White table grapes", 0),
    "pasteque": ("Watermelon red cut slice", 1),
    "melon": ("Cantaloupe melon fruit", 0),
    "peche": ("Peach fruits", 2),
    "abricot": ("Apricot fruits", 0),
    "grenade": ("Pomegranate fruits", 0),
    "dattes-deglet-nour": ("Deglet Nour dates", 2),
    "figue": ("Ficus carica ripe", 0),
    "tomate": ("Red tomatoes", 0),
    "pomme-de-terre": ("Potato tubers", 5),
    "oignon": ("Onion bulbs", 0),
    "carotte": ("Carrots", 2),
    "poivron": ("Bell peppers", 0),
    "courgette": ("Zucchini", 5),
    "aubergine": ("Eggplants", 0),
    "concombre": ("Cucumbers", 5),
    "salade-verte": ("Green lettuce", 1),
    "chou-fleur": ("Cauliflower", 0),
    "haricot-vert": ("Green beans", 0),
    "petit-pois": ("Green peas", 0),
    "betterave": ("Beetroot", 0),
    "ail": ("Garlic bulbs", 1),
    "menthe-fraiche": ("Fresh mint leaves", 1),
}

MIME_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def api_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def search_candidates(query):
    q = urllib.parse.quote(query + " filetype:bitmap")
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        f"&generator=search&gsrsearch={q}&gsrnamespace=6&gsrlimit=6"
        "&prop=imageinfo&iiprop=url%7Csize%7Cmime&iiurlwidth=800"
    )
    data = api_get(url)
    out = []
    for page in (data.get("query") or {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("mime") not in MIME_EXT or (info.get("width") or 0) < 400:
            continue
        out.append({"title": page.get("title"), "url": info.get("thumburl") or info.get("url"), "mime": info["mime"]})
    return out


def download(url, dest):
    last = None
    for wait in (2, 5, 10):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as fh:
                fh.write(resp.read())
            return
        except Exception as exc:  # noqa: BLE001 — réseau : on réessaie
            last = exc
            time.sleep(wait)
    raise last


class Command(BaseCommand):
    help = "Télécharge les photos produits manquantes (Wikimedia Commons)."

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Slugs à traiter (défaut : tous)")
        parser.add_argument("--force", action="store_true", help="Re-télécharger même si image présente")

    def handle(self, *args, **options):
        os.makedirs(os.path.join(settings.MEDIA_ROOT, "products"), exist_ok=True)
        slugs = options["slugs"] or list(PHOTOS)
        ok = skipped = failed = 0
        for slug in slugs:
            if slug not in PHOTOS:
                self.stderr.write(f"SKIP {slug} : slug inconnu")
                failed += 1
                continue
            try:
                product = Product.objects.get(slug=slug)
            except Product.DoesNotExist:
                self.stderr.write(f"SKIP {slug} : produit introuvable")
                failed += 1
                continue
            if product.image and not options["force"]:
                skipped += 1
                continue
            query, wanted = PHOTOS[slug]
            try:
                cands = search_candidates(query)
                cand = cands[wanted] if len(cands) > wanted else cands[0]
            except (IndexError, Exception) as exc:  # noqa: BLE001
                self.stderr.write(f"FAIL {slug} : recherche ({exc})")
                failed += 1
                continue
            ext = MIME_EXT[cand["mime"]]
            if product.image:
                old = os.path.join(settings.MEDIA_ROOT, str(product.image))
                if os.path.exists(old) and not old.endswith(ext):
                    os.remove(old)
            filename = f"products/{slug}{ext}"
            try:
                download(cand["url"], os.path.join(settings.MEDIA_ROOT, filename))
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"FAIL {slug} : téléchargement ({exc})")
                failed += 1
                continue
            product.image = filename
            product.save(update_fields=["image"])
            self.stdout.write(f"OK {slug} : {cand['title']}")
            ok += 1
            time.sleep(0.5)
        self.stdout.write(self.style.SUCCESS(f"Téléchargées : {ok} | déjà là : {skipped} | échecs : {failed}"))
