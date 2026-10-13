"""Extensions PostgreSQL requises par la recherche (étaient dans sql/01_init.sql).

pg_trgm + unaccent sont des extensions « trusted » : installables par le
rôle applicatif, y compris sur les bases de test recréées à chaque run.
"""

from django.contrib.postgres.operations import TrigramExtension, UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0005_permissions_fr"),
    ]

    operations = [
        TrigramExtension(),
        UnaccentExtension(),
    ]
