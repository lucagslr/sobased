"""Existing workspaces get the new default types and the family of the old
ones (24.09.2026: project types in two levels). Custom types keep their name
and land in "Autre", after the defaults."""

from django.db import migrations


def forwards(apps, schema_editor):
    from apps.workspaces.models import DEFAULT_PROJECT_TYPES

    Workspace = apps.get_model("workspaces", "Workspace")
    ProjectType = apps.get_model("workspaces", "ProjectType")
    for workspace in Workspace.objects.all():
        existing = {t.name.lower(): t for t in ProjectType.objects.filter(workspace=workspace)}
        seen = set()
        for position, (category, name) in enumerate(DEFAULT_PROJECT_TYPES):
            seen.add(name.lower())
            current = existing.get(name.lower())
            if current is None:
                ProjectType.objects.create(
                    workspace=workspace, name=name, category=category, position=position
                )
            else:
                current.category = category
                current.position = position
                current.save(update_fields=["category", "position"])
        offset = len(DEFAULT_PROJECT_TYPES)
        for key, custom in sorted(existing.items(), key=lambda item: item[1].position):
            if key not in seen:
                custom.position = offset + custom.position
                custom.save(update_fields=["position"])


class Migration(migrations.Migration):
    dependencies = [("workspaces", "0002_projecttype_category")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
