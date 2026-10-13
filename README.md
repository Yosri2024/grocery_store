# Grocery Store — Fruits & légumes frais du marché

Fruits & légumes frais du marché : catalogue, recherche instantanée
(nom + hashtags, full-text PostgreSQL + trigramme), panier HTMX, commandes
avec décompte de stock, comptes clients, mode nuit, admin FR avec alertes stock.

## Stack

Python 3.14 · Django 5 · **PostgreSQL 16 uniquement** (jamais SQLite) ·
Tailwind CDN · HTMX (serveur) · Alpine.js (UI locale) · WhiteNoise · Gunicorn.
Aucun npm, aucun framework JS.

## Installation (from scratch)

```bash
git clone https://github.com/Yosri2024/grocery_store.git
cd grocery_store
pipenv install             # ou : pip install -r requirements.txt

cp .env.example .env       # ajuster SECRET_KEY / DATABASE_URL si besoin

# PostgreSQL 16 : rôle + base + extensions (superuser postgres)
psql -U postgres -f sql/01_init.sql

pipenv run python manage.py migrate
pipenv run python manage.py seed_products     # 29 fruits & légumes
pipenv run python manage.py fetch_photos      # photos libres (Wikimedia)
pipenv run python manage.py permissions_fr    # permissions 100% FR (auto via migrate)
pipenv run python manage.py createsuperuser   # compte admin
pipenv run python manage.py runserver         # http://127.0.0.1:8000
```

## Rôles

| Qui | Accès |
|---|---|
| Client (compte `/inscription/`) | Catalogue, panier, commandes |
| Vendeur (groupe `Vendeur` + statut staff) | Admin limité : produits, commandes, catégories. **Commande interdite** |
| Admin (superuser) | Tout |

## Commandes utiles

```bash
pipenv run python manage.py seed_products              # catalogue (idempotent)
pipenv run python manage.py fetch_photos [slug] [--force]
pipenv run python manage.py permissions_fr             # tout renommer en FR
pipenv run python manage.py test                       # 18 tests (base de test dédiée)
```

## Mise en production (checklist)

```bash
# 1. Variables : recopier le bloc PROD de .env.example dans .env
#    SECRET_KEY fort (50+ caractères), DEBUG=False, domaine réel en
#    ALLOWED_HOSTS + CSRF_TRUSTED_ORIGINS (https). Sans SECRET_KEY de
#    production, Django refuse de démarrer (garde-fou intégré).

# 2. Base + données
psql -U postgres -f sql/01_init.sql
pipenv run python manage.py migrate
pipenv run python manage.py createsuperuser

# 3. Statiques + lancement (derrière Nginx/HTTPS)
pipenv run python manage.py collectstatic --noinput
pipenv run gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3

# 4. Sauvegarde régulière
pg_dump -U grocery_user -h 127.0.0.1 grocery_db > backup-$(date +%F).dump
```

Dès `DEBUG=False` : redirection HTTPS, cookies sécurisés et HSTS activés
automatiquement. Ne jamais exposer `runserver` ni le `.env` sur Internet.
