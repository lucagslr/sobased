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
