"""DEV ONLY: throwaway data to check the interface by hand.

Creates two users WITHOUT usable passwords (demo: owner, helder: guest of one
sub-project) and prints a session key for each. From the backend/ directory:

    docker compose exec -T backend python manage.py shell < scripts/dev_scenario.py

Replaced by `manage.py seed_demo` in phase 14. Never run on a real instance.
"""

from datetime import date, timedelta

from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
    get_user_model,
)
from django.contrib.sessions.backends.cached_db import SessionStore
from django.utils import timezone

from apps.projects.models import Membership, Project
from apps.workspaces.models import Workspace

User = get_user_model()
User.objects.filter(username__in=["demo", "helder"]).delete()
Workspace.objects.filter(name__in=["100SATIONS", "École HEG"]).delete()


def make_user(username, first, last):
    user = User.objects.create(
        username=username,
        email=f"{username}@example.org",
        first_name=first,
        last_name=last,
        email_verified_at=timezone.now(),
    )
    user.set_unusable_password()
    user.save()
    session = SessionStore()
    session[SESSION_KEY] = str(user.pk)
    session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    session[HASH_SESSION_KEY] = user.get_session_auth_hash()
    session.save()
    print(f"SESSION {username} {session.session_key}")
    return user


demo = make_user("demo", "Demo", "Test")
helder = make_user("helder", "Helder", "S")

today = date.today()
asso = Workspace.objects.create(name="100SATIONS", color="#FDE68A", created_by=demo)
asso.create_defaults()
Membership.objects.create(user=demo, workspace=asso, role="owner")
heg = Workspace.objects.create(name="École HEG", color="#BAE6FD", created_by=demo)
heg.create_defaults()
Membership.objects.create(user=demo, workspace=heg, role="owner")


def kind(workspace, name):
    return workspace.project_types.get(name=name)


def project(workspace, name, type_name, parent=None, **fields):
    return Project.objects.create(
        workspace=workspace,
        parent=parent,
        name=name,
        type=kind(workspace, type_name),
        created_by=demo,
        **fields,
    )


shorty = project(asso, "SHORTY7G", "Artiste", color="#FECACA", status="in_progress")
Membership.objects.create(user=demo, project=shorty, role="owner")
album = project(
    asso,
    "MARCHIOLY",
    "Album",
    shorty,
    color="#FED7AA",
    status="in_progress",
    start_date=today - timedelta(days=60),
    end_date=today - timedelta(days=3),
)
project(
    asso,
    "Release",
    "Release",
    album,
    color="#FDE68A",
    start_date=today + timedelta(days=30),
)
clip = project(
    asso, "Clip « Titre 1 »", "Clip", album, color="#DDD6FE", status="in_progress"
)
project(asso, "Tournage", "Tournage", clip, color="#C7D2FE", status="done")
project(asso, "Visuels / cover", "Visuel", album, color="#BBF7D0", status="to_validate")
project(asso, "Feat avec X", "Feat", shorty, color="#BAE6FD", status="idea")
project(
    asso,
    "Date live 12.10",
    "Date live",
    shorty,
    color="#FBCFE8",
    start_date=today + timedelta(days=21),
    end_date=today + timedelta(days=21),
)
admin = project(
    asso, "100SATIONS Admin", "Administratif", color="#E7E5E4", status="in_progress"
)
project(asso, "Demande de fonds 2026", "Demande de fonds", admin, color="#D9F99D")
ecole = project(heg, "62-52 BPMN", "Cours", color="#BAE6FD", status="in_progress")
project(heg, "TP 3", "TP", ecole, color="#BFDBFE")

# Helder: guest of ONE sub-project only -> sees SHORTY7G and MARCHIOLY as shells.
Membership.objects.create(user=helder, project=clip, role="editor", invited_by=demo)
print("PROJECT_IDS", shorty.pk, album.pk, clip.pk)

# --- Tasks (phase 3+): something in every dashboard widget --------------------
from datetime import UTC, datetime  # noqa: E402

from apps.tasks.models import ChecklistItem, Task  # noqa: E402


def all_day(offset):
    day = today + timedelta(days=offset)
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def task(project_, title, due=None, **fields):
    created = Task.objects.create(
        project=project_,
        title=title,
        due_at=all_day(due) if due is not None else None,
        created_by=demo,
        **fields,
    )
    created.assignees.add(demo)
    return created


late = task(clip, "Envoyer le brief au realisateur", due=-3, priority=5)
late.assignees.add(helder)
task(album, "Valider le mix du titre 3", due=-1, priority=4)
task(clip, "Confirmer le lieu de tournage", due=0, priority=4)
task(ecole, "Rendre le TP 3", due=0, priority=3)
task(album, "Reserver le studio", due=2)
task(admin, "Completer la demande de fonds", due=6, priority=5)
task(album, "Pochette : choisir la typo", due=5, status="to_validate")
montage = task(clip, "Monter le clip", due=10)
montage.blocked_by.add(late)
ChecklistItem.objects.create(task=montage, title="Recuperer les rushs", pinned=True)
ChecklistItem.objects.create(task=montage, title="Valider la musique", pinned=True)
ChecklistItem.objects.create(task=montage, title="Exporter en 9:16")
print("TASKS", Task.objects.count())
