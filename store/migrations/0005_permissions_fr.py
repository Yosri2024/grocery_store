"""Permissions en français (données). Rejoue store/management/commands/permissions_fr.py."""

from django.db import migrations


def franciser(apps, schema_editor):
    from store.management.commands.permissions_fr import franciser_permissions

    franciser_permissions()


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0004_alter_cart_options_alter_cartitem_options_and_more"),
    ]

    operations = [
        migrations.RunPython(franciser, migrations.RunPython.noop),
    ]
