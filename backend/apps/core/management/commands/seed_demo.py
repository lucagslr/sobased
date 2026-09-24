"""`manage.py seed_demo`: a demo dataset to discover Faiblegraine (SPEC §19).

Three users (demo: owner of two workspaces with every feature exercised:
three artists with albums, singles, clips and concerts, the association's
admin, a school with courses, exams and a bachelor thesis;
ana: commenter of the whole association workspace with a view on the money;
helder: guest of one sub-project), projects on four levels, tasks in every
state, meetings, contacts, bookkeeping, generated files (PNG, WAV, PDF, MP4)
and share links. Only the demo users and the workspaces they own are ever
removed: running it again on a real instance never touches real data.

    manage.py seed_demo                      # fresh demo data, no passwords
    manage.py seed_demo --password S3cret!   # demo accounts you can log into
    manage.py seed_demo --sessions           # dev: prints ready-made sessions
    manage.py seed_demo --remove             # remove the demo data only
"""

import io
import math
import struct
import subprocess
import tempfile
import wave
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    HASH_SESSION_KEY,
    SESSION_KEY,
    get_user_model,
)
from django.contrib.sessions.backends.cached_db import SessionStore
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.activity import services as activity_services
from apps.contacts.models import Contact, ProjectContact
from apps.core import crypto
from apps.events import services as event_services
from apps.events.models import Event
from apps.files import services as file_services
from apps.files.models import Asset, AssetComment
from apps.finance.models import BudgetLine, Category, RecurringExpense, Transaction
from apps.notifications import services as notification_services
from apps.projects.models import Membership, Project
from apps.sharing import services as share_services
from apps.sharing.models import ShareLink, ShareLinkItem
from apps.tasks.models import ChecklistItem, Task, TaskComment
from apps.workspaces.models import Workspace

DEMO_USERS = ["demo", "ana", "helder"]
DEMO_WORKSPACES = ["Démo · 100SATIONS", "Démo · École HEG"]

User = get_user_model()


def remove_demo_data() -> None:
    """Workspaces owned by the demo users, then the users themselves."""
    users = User.objects.filter(username__in=DEMO_USERS)
    Workspace.objects.filter(created_by__in=users, name__in=DEMO_WORKSPACES).delete()
    users.delete()


def seed(out, password: str = "", sessions: bool = False) -> None:

    User = get_user_model()

    def make_user(username, first, last):
        user = User.objects.create(
            username=username,
            email=f"{username}@example.org",
            first_name=first,
            last_name=last,
            email_verified_at=timezone.now(),
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        if sessions:  # dev only: a ready-made session for browser checks
            session = SessionStore()
            session[SESSION_KEY] = str(user.pk)
            session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
            session[HASH_SESSION_KEY] = user.get_session_auth_hash()
            session.save()
            out(f"SESSION {username} {session.session_key}")
        return user

    demo = make_user("demo", "Demo", "Test")
    ana = make_user("ana", "Ana", "Costa")
    helder = make_user("helder", "Helder", "S")

    today = date.today()
    asso = Workspace.objects.create(
        name=DEMO_WORKSPACES[0], color="#FDE68A", created_by=demo
    )
    asso.create_defaults()
    Membership.objects.create(user=demo, workspace=asso, role="owner")
    heg = Workspace.objects.create(
        name=DEMO_WORKSPACES[1], color="#BAE6FD", created_by=demo
    )
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
    project(
        asso, "Visuels / cover", "Visuel", album, color="#BBF7D0", status="to_validate"
    )
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

    # Ana: commenter of the whole association, allowed to SEE the money (SPEC §18:
    # three users with different roles). Helder: guest of ONE sub-project only
    # -> sees SHORTY7G and MARCHIOLY as shells.
    Membership.objects.create(
        user=ana,
        workspace=asso,
        role="commenter",
        can_view_finance=True,
        invited_by=demo,
    )
    Membership.objects.create(user=helder, project=clip, role="editor", invited_by=demo)
    out("PROJECT_IDS", shorty.pk, album.pk, clip.pk)

    # --- Tasks (phase 3+): something in every dashboard widget --------------------

    def all_day(offset):
        day = today + timedelta(days=offset)
        return datetime(day.year, day.month, day.day, tzinfo=UTC)

    def task(project_, title, due=None, **fields):
        fields.setdefault("due_at", all_day(due) if due is not None else None)
        created = Task.objects.create(
            project=project_, title=title, created_by=demo, **fields
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

    # --- Phase 5: spans (Gantt), a timed task (calendar), every kanban column ----
    tournage = task(
        clip, "Tournage du clip", due=6, start_at=all_day(4), status="in_progress"
    )
    tournage.blocked_by.add(late)
    montage.start_at = all_day(7)
    montage.save()
    montage.blocked_by.add(tournage)
    etalonnage = task(clip, "Etalonnage", due=13, start_at=all_day(11))
    etalonnage.blocked_by.add(montage)
    task(clip, "Reperages", due=-10, start_at=all_day(-14), status="done")
    task(clip, "Casting figurants", due=-6, status="cancelled")
    task(clip, "<b>Titre piege</b> <img src=x onerror=alert(1)>", due=3)
    noon = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)
    task(
        album,
        "Appel avec le distributeur",
        all_day=False,
        start_at=noon + timedelta(days=1),
        due_at=noon + timedelta(days=1, hours=1),
    )
    out("TASKS", Task.objects.count())

    # --- Phase 6: contacts and events (RDV) ----------------------------------------

    def contact(workspace, last_name, **fields):
        return Contact.objects.create(
            workspace=workspace, last_name=last_name, created_by=demo, **fields
        )

    realisateur = contact(
        asso,
        "Morel",
        first_name="Sam",
        job="Realisateur",
        email="sam@example.org",
        phone="+41 79 000 00 00",
        instagram="sam.cuts",
    )
    booker = contact(
        asso, "Duarte", first_name="Ana", job="Programmatrice", organization="L'Usine"
    )
    contact(
        asso,
        "",
        organization="Studio Les Forges",
        job="Studio",
        website="https://example.org",
    )
    contact(
        heg, "Muller", first_name="Prof", job="Enseignant", email="prof@example.org"
    )
    ProjectContact.objects.create(
        project=clip, contact=realisateur, role_label="Realisateur du clip"
    )
    ProjectContact.objects.create(project=shorty, contact=booker, role_label="Booking")

    def event(project_, title, start_offset, hour=None, days=0, **fields):
        if hour is None:
            start = all_day(start_offset)
            end = all_day(start_offset + days)
            fields.setdefault("all_day", True)
        else:
            start = noon.replace(hour=hour) + timedelta(days=start_offset)
            end = start + timedelta(hours=1)
        created = Event.objects.create(
            project=project_,
            title=title,
            start=start,
            end=end,
            created_by=demo,
            **fields,
        )
        created.participants.add(demo)
        return created

    brief = event(
        clip,
        "Brief avec le realisateur",
        -2,
        hour=10,
        location="Studio Les Forges",
        report="Brief fait. Tournage confirme sur deux jours.",
        decisions=["Deux jours de tournage", "Budget figurants : 400 CHF"],
    )
    brief.contacts.add(realisateur)
    brief.participants.add(helder)
    tournage_event = event(
        clip, "Tournage", 4, days=2, type="shooting", location="Vieille ville"
    )
    tournage_event.contacts.add(realisateur)
    event(album, "Ecoute du master", 1, hour=15, type="studio", location="Studio")
    event(
        shorty, "Date live L'Usine", 21, type="live", location="L'Usine"
    ).contacts.add(booker)
    event(ecole, "Examen BPMN", 12, hour=8, type="exam", location="HEG, salle 3")
    event(album, "Release party", 45, type="release_party")
    # A recurring meeting (SPEC §18): weekly, materialised 90 days ahead.
    weekly = event(shorty, "Point hebdo SHORTY7G", 1, hour=18, location="Studio")
    weekly.participants.add(ana, helder)
    event_services.start_series(weekly, "FREQ=WEEKLY;BYDAY=MO", demo.timezone)
    montage.source_event = brief
    montage.save(update_fields=["source_event"])
    out("EVENTS", Event.objects.count(), "CONTACTS", Contact.objects.count())

    # --- Phase 7: bookkeeping (demo has both finance flags as owner) ----------------

    def cat(workspace, name):
        return Category.objects.get(workspace=workspace, name=name)

    def tx(
        project_, label, amount, days_ago=0, kind="expense", category="Autre", **fields
    ):
        return Transaction.objects.create(
            project=project_,
            kind=kind,
            amount=Decimal(str(amount)),
            date=today - timedelta(days=days_ago),
            category=cat(project_.workspace, category),
            label=label,
            created_by=demo,
            **fields,
        )

    tx(
        shorty,
        "Subvention Ville de Geneve",
        5000,
        40,
        kind="income",
        category="Subvention",
    )
    tx(
        album,
        "Studio Les Forges : 2 jours",
        800,
        12,
        category="Studio",
        vendor="Les Forges",
    )
    tx(
        clip,
        "Location camera",
        350,
        5,
        category="Location",
        paid_by_user=demo,
        to_reimburse=True,
    )
    tx(
        clip,
        "Train Geneve - Lausanne",
        46.40,
        3,
        category="Transport",
        paid_by_user=helder,
        to_reimburse=True,
    )
    tx(
        album,
        "Adobe Creative Cloud",
        59.90,
        1,
        category="Logiciel",
        payment_status="to_pay",
    )
    tx(
        admin,
        "Assurance RC asso",
        420,
        8,
        category="Frais admin",
        payment_status="to_pay",
    )
    tx(shorty, "Cachet date live", 600, 20, category="Cachet", contact=booker)
    tx(ecole, "Manuel BPMN", 89, 2, category="Matériel")
    BudgetLine.objects.create(
        project=album, category=cat(asso, "Studio"), kind="expense", amount=1500
    )
    BudgetLine.objects.create(
        project=clip, category=cat(asso, "Location"), kind="expense", amount=500
    )
    BudgetLine.objects.create(
        project=clip, category=cat(asso, "Transport"), kind="expense", amount=100
    )
    BudgetLine.objects.create(
        project=shorty, category=cat(asso, "Subvention"), kind="income", amount=8000
    )
    RecurringExpense.objects.create(
        project=admin,
        label="Studio One",
        amount=Decimal("19.90"),
        category=cat(asso, "Logiciel"),
        vendor="PreSonus",
        frequency="monthly",
        day=5,
        start_date=today - timedelta(days=90),
        created_by=demo,
    )
    out("TRANSACTIONS", Transaction.objects.count())

    # --- Phase 8: files with real (generated) content ------------------------------
    # Small files built here: a cover (PNG), a mix (WAV sine), a dossier (PDF with
    # two pages), a clip (MP4 made by ffmpeg). Processing runs through Celery
    # after the commit; comments are anchored by kind.

    def png_bytes(color, size=(1200, 1200), text=""):
        image = Image.new("RGB", size, color)
        draw = ImageDraw.Draw(image)
        draw.rectangle((100, 100, 500, 500), fill="#1c1917")
        draw.ellipse((700, 700, 1100, 1100), fill="#fef3c7")
        draw.text((120, 1050), text, fill="#1c1917")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def wav_bytes(seconds=12, rate=22050):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(rate)
            frames = bytearray()
            for i in range(int(rate * seconds)):
                t = i / rate
                envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 0.25 * t)
                value = int(
                    9000 * envelope * math.sin(2 * math.pi * (220 + 110 * int(t)) * t)
                )
                frames += struct.pack("<h", value)
            handle.writeframes(bytes(frames))
        return buffer.getvalue()

    def pdf_bytes():
        pages = []
        for index, title in enumerate(
            ["Dossier de presse", "Fiche technique"], start=1
        ):
            content = f"BT /F1 36 Tf 72 720 Td ({title}) Tj ET".encode()
            pages.append(content)
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
        kids = []
        for content in pages:
            page_id = len(objects) + 1
            font_id = len(pages) * 2 + 3
            objects.append(
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]"
                f" /Contents {page_id + 1} 0 R"
                f" /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
            )
            objects.append(
                b"<< /Length "
                + str(len(content)).encode()
                + b" >>\nstream\n"
                + content
                + b"\nendstream"
            )
            kids.append(f"{page_id} 0 R")
        objects[1] = (
            f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>".encode()
        )
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        out = io.BytesIO()
        out.write(b"%PDF-1.4\n")
        offsets = []
        for number, body in enumerate(objects, start=1):
            offsets.append(out.tell())
            out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
        xref = out.tell()
        out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
        for offset in offsets:
            out.write(f"{offset:010d} 00000 n \n".encode())
        trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        out.write(f"{trailer}startxref\n{xref}\n%%EOF\n".encode())
        return out.getvalue()

    def mp4_bytes():
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "clip.mp4"
            subprocess.run(
                [
                    "ffmpeg",
                    "-v",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=size=640x360:rate=25:duration=6",
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=330:duration=6",
                    "-shortest",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    "-y",
                    str(target),
                ],
                check=True,
                capture_output=True,
            )
            return target.read_bytes()

    def asset(
        project_, name, filename, content, author, label="", status="draft", **fields
    ):
        created = Asset.objects.create(
            project=project_, name=name, created_by=author, **fields
        )
        upload = SimpleUploadedFile(filename, content)
        with db_transaction.atomic():
            version = file_services.add_version(created, upload, author, label=label)
        if status != "draft":
            file_services.change_status(created, status, author)
        created.refresh_from_db()
        return created, version

    visuels = Project.objects.get(name="Visuels / cover", workspace=asso)
    cover, cover_v1 = asset(
        visuels,
        "Cover MARCHIOLY",
        "cover_v1.png",
        png_bytes("#fbcfe8", text="v1"),
        demo,
        "esquisse",
    )
    cover_v2 = file_services.add_version(
        cover,
        SimpleUploadedFile("cover_v2.png", png_bytes("#bbf7d0", text="v2")),
        demo,
        label="cover finale",
        note="Logo remonté, fond vert.",
    )
    file_services.change_status(
        cover, "to_validate", demo, note="Prête pour validation"
    )
    AssetComment.objects.create(
        version=cover_v2,
        author=helder,
        body="Le logo est encore un peu bas, non ?",
        rect_x=8,
        rect_y=8,
        rect_w=34,
        rect_h=34,
    )
    general = AssetComment.objects.create(
        version=cover_v2, author=demo, body="Le vert marche mieux que le rose."
    )
    AssetComment.objects.create(
        version=cover_v2, author=helder, body="Validé pour moi.", parent=general
    )

    mix, mix_v1 = asset(
        album, "Mix titre 3", "mix_titre3.wav", wav_bytes(), demo, "mix 1"
    )
    AssetComment.objects.create(
        version=mix_v1, author=demo, body="Basse trop forte ici.", timestamp_ms=3200
    )
    AssetComment.objects.create(
        version=mix_v1,
        author=demo,
        body="Couper la réverb sur la voix.",
        timestamp_ms=8900,
        resolved_at=timezone.now(),
        resolved_by=demo,
    )

    dossier, dossier_v1 = asset(
        shorty,
        "Dossier de presse",
        "dossier_presse.pdf",
        pdf_bytes(),
        demo,
        status="approved",
    )
    AssetComment.objects.create(
        version=dossier_v1, author=demo, body="Manque le logo du label.", page=2
    )

    try:
        clip_asset, _ = asset(
            clip, "Clip teaser", "teaser.mp4", mp4_bytes(), demo, "montage 1"
        )
    except Exception as exc:  # noqa: BLE001 - ffmpeg missing: the rest still helps
        out("NO_VIDEO", exc)

    asset(admin, "Statuts de l'association", "statuts.txt", b"Statuts...\n", demo)
    out(
        "ASSETS",
        Asset.objects.count(),
        "cover",
        cover.pk,
        "mix",
        mix.pk,
        "dossier",
        dossier.pk,
    )

    # --- Phase 9: share links ---------------------------------------------------------

    def share(project_, title, target_type, author, **fields):
        token = share_services.new_token()
        link = ShareLink(
            project=project_,
            title=title,
            target_type=target_type,
            token_hash=share_services.token_hash(token),
            token_encrypted=crypto.encrypt(token),
            created_by=author,
            **fields,
        )
        link.save()
        out("SHARE", title, f"{token}")
        return link

    share(
        album,
        "Écoute privée · Mix titre 3",
        "asset",
        demo,
        asset=mix,
        recipient_label="Radio X",
    )
    locked = share(
        visuels, "Cover pour la presse", "asset", demo, asset=cover, allow_download=True
    )
    share_services.set_password(locked, "presse2026")
    locked.save(update_fields=["password_hash"])
    share(  # revoked: shows the 410 page
        shorty,
        "Ancien dossier",
        "asset",
        demo,
        asset=dossier,
        expires_at=timezone.now(),
    )
    mixed = share(
        shorty, "Sélection SHORTY7G", "playlist", demo, recipient_label="Usine"
    )
    for position, item in enumerate([mix, cover, dossier]):
        ShareLinkItem.objects.create(share_link=mixed, asset=item, position=position)
    out("SHARE_LINKS", ShareLink.objects.count())

    # --- More life (24.09.2026): two more artists with concerts, school work,
    # notifications and a journal, so that every screen has something to show.
    memosa = project(asso, "MEMOSA", "Artiste", color="#FCA5A5", status="in_progress")
    Membership.objects.create(user=demo, project=memosa, role="owner")
    ep = project(
        asso,
        "EP « Nuit blanche »",
        "Album",
        memosa,
        color="#FDBA74",
        status="in_progress",
        start_date=today - timedelta(days=90),
        end_date=today - timedelta(days=5),  # overdue: the end-date modal
    )
    project(
        asso,
        "Clip « Nuit blanche »",
        "Clip",
        ep,
        color="#C4B5FD",
        status="planned",
        start_date=today + timedelta(days=20),
        end_date=today + timedelta(days=35),
    )
    docks = project(
        asso,
        "Concert Les Docks",
        "Date live",
        memosa,
        color="#F9A8D4",
        status="in_progress",
        start_date=today + timedelta(days=12),
        end_date=today + timedelta(days=12),
    )
    project(
        asso,
        "Tournée printemps 2027",
        "Date live",
        memosa,
        color="#A5B4FC",
        status="idea",
        start_date=today + timedelta(days=180),
        end_date=today + timedelta(days=200),
    )
    lea = project(asso, "LÉA K", "Artiste", color="#99F6E4", status="in_progress")
    Membership.objects.create(user=demo, project=lea, role="owner")
    rivage = project(
        asso,
        "Single « Rivage »",
        "Single",
        lea,
        color="#5EEAD4",
        status="done",
        start_date=today - timedelta(days=80),
        end_date=today - timedelta(days=20),
    )
    antigel = project(
        asso,
        "Festival Antigel",
        "Date live",
        lea,
        color="#FDE68A",
        status="planned",
        start_date=today + timedelta(days=40),
        end_date=today + timedelta(days=40),
    )
    comm = project(
        asso,
        "Communication Rivage",
        "Communication",
        lea,
        color="#BFDBFE",
        status="in_progress",
    )
    bachelor = project(
        heg,
        "Travail de bachelor",
        "Travail de bachelor",
        color="#DDD6FE",
        status="in_progress",
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=120),
    )
    rendu = project(
        heg,
        "Rendu intermédiaire",
        "Rendu",
        bachelor,
        color="#C7D2FE",
        start_date=today + timedelta(days=14),
        end_date=today + timedelta(days=14),
    )
    secu = project(
        heg, "63-31 Sécurité", "Cours", color="#FBCFE8", status="in_progress"
    )
    project(
        heg,
        "Examen 63-31",
        "Examen",
        secu,
        color="#FECDD3",
        start_date=today + timedelta(days=25),
        end_date=today + timedelta(days=25),
    )

    # Tasks: late, today, this week, later, without date, done, in every column.
    task(docks, "Envoyer le rider technique aux Docks", due=-2, priority=5)
    task(rivage, "Relancer la SUISA pour « Rivage »", due=-6, priority=3)
    task(ep, "Payer l'acompte du studio", due=-1, priority=4)
    task(antigel, "Appeler le booker d'Antigel", due=0, priority=4)
    teaser = task(
        comm, "Poster le teaser « Rivage »", due=0, priority=3, status="in_progress"
    )
    task(memosa, "Préparer la répétition de ce soir", due=0, priority=2)
    stems = task(ep, "Envoyer les stems au mixeur", due=1, priority=4)
    stems.assignees.add(ana)
    setlist = task(docks, "Valider la setlist", due=4, status="to_validate")
    for position, (title, done) in enumerate(
        [
            ("Intro", True),
            ("Nuit blanche", True),
            ("Rappel : Rivage (feat. LÉA K)", False),
        ]
    ):
        ChecklistItem.objects.create(
            task=setlist, title=title, done=done, position=position
        )
    task(comm, "Commander les affiches", due=5, status="to_validate", priority=3)
    task(admin, "Déposer le dossier Pro Helvetia", due=30, priority=5)
    task(secu, "Réviser le chapitre 4", due=0, priority=2)
    task(rendu, "Rendre le rapport intermédiaire", due=14, priority=5)
    done_task = task(docks, "Réserver la salle de répétition", due=-8, status="done")
    done_task.completed_at = timezone.now() - timedelta(days=9)
    done_task.save(update_fields=["completed_at"])
    task(ep, "Choisir l'ordre des titres", status="in_progress")
    task(lea, "Mettre à jour la bio")
    task(
        bachelor, "Lire les trois articles de référence", due=9, priority=3
    ).assignees.add(ana)

    # Meetings and concerts: today, soon, past, and a weekly class.
    point = event(
        memosa, "Point label MEMOSA", 0, hour=15, location="Bureau 100SATIONS"
    )
    point.participants.add(ana)
    event(memosa, "Répétition MEMOSA", 0, hour=19, location="Salle Les Forges")
    concert = event(
        docks,
        "Concert Les Docks",
        12,
        hour=20,
        type="live",
        location="Les Docks, Lausanne",
    )
    event(
        antigel,
        "Festival Antigel : scène Le Groove",
        40,
        hour=21,
        type="live",
        location="Genève",
    )
    event(rivage, "Sortie du single « Rivage »", -20, type="release")
    event(
        rendu,
        "Soutenance intermédiaire",
        14,
        hour=10,
        type="defense",
        location="HEG, salle 1",
    )
    cours = event(secu, "Cours 63-31", 2, hour=8, type="class", location="HEG, salle 4")
    event_services.start_series(cours, "FREQ=WEEKLY;BYDAY=TU", demo.timezone)

    julie = contact(
        asso,
        "Roth",
        first_name="Julie",
        job="Programmatrice",
        organization="Les Docks",
        email="julie@example.org",
    )
    ProjectContact.objects.create(project=docks, contact=julie, role_label="Booking")
    concert.contacts.add(julie)
    karim = contact(
        asso, "Benali", first_name="Karim", job="Manager", phone="+41 78 000 00 00"
    )
    ProjectContact.objects.create(project=lea, contact=karim, role_label="Management")
    contact(asso, "", organization="Antigel", job="Festival", email="prog@example.org")

    # Money on the new projects: a fee to come, an advance, a missing receipt.
    tx(docks, "Cachet Les Docks", 1200, days_ago=-12, kind="income", category="Cachet")
    tx(
        docks,
        "Transport backline",
        180,
        days_ago=2,
        category="Transport",
        payment_status="paid",
        paid_by_user=ana,
        to_reimburse=True,
    )
    tx(
        memosa,
        "Location salle de répétition",
        300,
        days_ago=4,
        category="Location",
        payment_status="paid",
    )
    tx(
        rivage,
        "Distribution digitale",
        45,
        days_ago=25,
        category="Streaming",
        payment_status="paid",
    )
    tx(ep, "Studio Les Forges · 3 jours", 1800, days_ago=1, category="Studio")
    tx(comm, "Impression affiches", 240, days_ago=-5, category="Communication")
    BudgetLine.objects.create(
        project=ep, category=cat(asso, "Studio"), kind="expense", amount=Decimal("2500")
    )
    BudgetLine.objects.create(
        project=docks,
        category=cat(asso, "Cachet"),
        kind="income",
        amount=Decimal("1200"),
    )

    cover_ep, _ = asset(
        ep,
        "Cover EP Nuit blanche",
        "cover-ep.png",
        png_bytes("#0f172a", text="NUIT BLANCHE"),
        demo,
        "v1",
        status="to_validate",
    )
    asset(
        memosa,
        "Répétition · Nuit blanche (live)",
        "repet.wav",
        wav_bytes(8),
        demo,
        "prise 2",
    )

    # Notifications for demo: assigned by Ana, mentioned, a file validated, a
    # link opened. Then a few journal entries spread over the last days.
    notification_services.task_assigned(stems, [demo], ana)
    mention = TaskComment.objects.create(
        task=setlist, author=ana, body="@demo la setlist est prête, tu valides ?"
    )
    notification_services.mentioned(mention, [demo], ana)
    file_services.change_status(
        cover_ep, "approved", ana, note="Validée pour l'impression"
    )
    opened = share(
        ep,
        "Cover EP pour le label",
        "asset",
        demo,
        asset=cover_ep,
        recipient_label="Label",
    )
    opened.notify_on_open = True
    opened.first_opened_at = timezone.now() - timedelta(hours=3)
    opened.save(update_fields=["notify_on_open", "first_opened_at"])
    notification_services.share_link_opened(opened)

    journal = [
        (demo, activity_services.Verb.CREATED, ep, "project", {}, 12),
        (demo, activity_services.Verb.CREATED, concert, "event", {}, 10),
        (
            ana,
            activity_services.Verb.UPDATED,
            docks,
            "project",
            {"end_date": [None, str(docks.end_date)]},
            6,
        ),
        (
            ana,
            activity_services.Verb.STATUS_CHANGED,
            teaser,
            "task",
            {"status": ["todo", "in_progress"]},
            2,
        ),
        (demo, activity_services.Verb.SHARED, opened, "share_link", {}, 1),
        (
            ana,
            activity_services.Verb.STATUS_CHANGED,
            cover_ep,
            "asset",
            {"status": ["to_validate", "approved"]},
            0,
        ),
    ]
    for actor, verb, target, target_type, changes, days_ago in journal:
        entry = activity_services.log(
            actor, verb, target, target_type=target_type, changes=changes
        )
        entry.__class__.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago, minutes=days_ago * 7)
        )
    activity_services.log(
        demo,
        activity_services.Verb.ACCESS_CHANGED,
        target_type="membership",
        target_id=helder.pk,
        label=helder.display_name,
        project=clip,
        changes={"role": [None, "Éditeur"]},
    )
    out(
        "MORE",
        "projects",
        Project.objects.count(),
        "tasks",
        Task.objects.count(),
        "events",
        Event.objects.count(),
    )


class Command(BaseCommand):
    help = "Crée (ou remplace) le jeu de données de démonstration."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password", default="", help="Mot de passe des comptes démo"
        )
        parser.add_argument(
            "--sessions", action="store_true", help="Dev : imprime des sessions prêtes"
        )
        parser.add_argument("--remove", action="store_true", help="Supprime la démo")

    def handle(self, *args, **options):
        remove_demo_data()
        if options["remove"]:
            self.stdout.write("Données de démonstration supprimées.")
            return
        seed(
            lambda *parts: self.stdout.write(" ".join(str(p) for p in parts)),
            password=options["password"],
            sessions=options["sessions"],
        )
        self.stdout.write(
            self.style.SUCCESS("Démo prête : comptes demo, ana et helder.")
        )
