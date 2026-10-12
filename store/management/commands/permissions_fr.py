"""Renomme TOUTES les permissions Django en français (rejouable).

Usage : pipenv run python manage.py permissions_fr
"""

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand

ACTION_FR = {
    "add": "Peut ajouter",
    "change": "Peut modifier",
    "delete": "Peut supprimer",
    "view": "Peut voir",
}

# Modèles hors boutique (noms français forcés)
MODEL_FR = {
    ("admin", "logentry"): "entrée de journal",
    ("auth", "group"): "groupe",
    ("auth", "permission"): "permission",
    ("auth", "user"): "utilisateur",
    ("contenttypes", "contenttype"): "type de contenu",
    ("sessions", "session"): "session",
}


def nom_francais(content_type):
    """Nom français singulier du modèle (verbose_name ou table forcée)."""
    forced = MODEL_FR.get((content_type.app_label, content_type.model))
    if forced:
        return forced
    try:
        model = apps.get_model(content_type.app_label, content_type.model)
    except LookupError:
        return None
    return str(model._meta.verbose_name)


def franciser_permissions():
    """Renomme les permissions 'Can ...' en 'Peut ...'. Retourne (total, renommées)."""
    total = renommees = 0
    for perm in Permission.objects.select_related("content_type"):
        total += 1
        action, _, _reste = perm.codename.partition("_")
        if action not in ACTION_FR:
            continue
        nom = nom_francais(perm.content_type)
        if not nom:
            continue
        nouveau = f"{ACTION_FR[action]} {nom}"
        if perm.name != nouveau:
            perm.name = nouveau
            perm.save(update_fields=["name"])
            renommees += 1
    return total, renommees


class Command(BaseCommand):
    help = "Renomme toutes les permissions Django en français."

    def handle(self, *args, **options):
        total, renommees = franciser_permissions()
        self.stdout.write(self.style.SUCCESS(f"Permissions : {total} | renommées en français : {renommees}"))
