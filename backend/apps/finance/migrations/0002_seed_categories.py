"""Workspaces created before the finance app get the default categories too."""

from django.db import migrations

DEFAULT_CATEGORIES = [
    "Studio",
    "Logiciel",
    "Matériel",
    "Transport",
    "Communication",
    "Graphisme",
    "Tournage",
    "Location",
    "Frais admin",
    "Cachet",
    "Billetterie",
    "Subvention",
    "Streaming",
    "Merch",
    "Autre",
]


def seed(apps, schema_editor):
    Workspace = apps.get_model("workspaces", "Workspace")
    Category = apps.get_model("finance", "Category")
    for workspace in Workspace.objects.filter(categories__isnull=True).distinct():
        Category.objects.bulk_create(
            Category(workspace=workspace, name=name, position=index)
            for index, name in enumerate(DEFAULT_CATEGORIES)
        )


class Migration(migrations.Migration):
    dependencies = [("finance", "0001_initial"), ("workspaces", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
