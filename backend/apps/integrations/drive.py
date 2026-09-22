"""Drive folders and files of projects (SPEC §11, SPECIFICATIONS §7).

Rule D8: the folder tree of a project belongs to the Google account of
whoever created the root folder (`Project.drive_account`). Sub-folders and
uploads "to the project's Drive" are made server-side with THAT account,
whatever SOBASED user acts (their SOBASED rights are checked first by the
views). Without a connected account, everything else keeps working with
the internal storage.
"""

from __future__ import annotations

from apps.projects.access import Role, effective_access, member_user_ids
from apps.projects.models import Project

from . import google, microsoft
from .google import DriveClient, GoogleError
from .models import DriveLink, OAuthAccount, Provider

SUBFOLDERS = ["Contrats", "Visuels", "Audio", "Vidéo", "Compta", "Documents"]


class DriveUnavailable(Exception):
    """No usable account for this operation: a clear message for the user."""


def google_account(user) -> OAuthAccount | None:
    return OAuthAccount.objects.filter(user=user, provider=Provider.GOOGLE).first()


def drive_account(user) -> OAuthAccount | None:
    """The user's Google account if it may use Drive."""
    account = google_account(user)
    if account and account.usable and account.has_feature("drive"):
        return account
    return None


def folder_owner(project: Project) -> OAuthAccount:
    """The account that owns the project's folder tree (walks up to the root)."""
    disconnected = DriveUnavailable(
        "Le compte Google propriétaire du dossier Drive est déconnecté : "
        "création de dossier et envoi vers Drive désactivés."
    )
    node = project
    while node is not None:
        if node.drive_account_id:
            account = node.drive_account
            if account.usable and account.has_feature("drive"):
                return account
            raise disconnected
        if node.parent_id is None and node.drive_folder_id:
            # A root folder whose account was deleted (SET_NULL).
            raise disconnected
        node = node.parent
    raise DriveUnavailable("Ce projet n'a pas de dossier Drive.")


def file_summary(data: dict) -> dict:
    return {
        "drive_file_id": data.get("id", ""),
        "name": data.get("name", ""),
        "mime_type": data.get("mimeType", ""),
        "icon_url": data.get("iconLink", ""),
        "web_view_url": data.get("webViewLink", ""),
        "thumbnail_url": data.get("thumbnailLink", ""),
        "size_bytes": int(data["size"]) if data.get("size") else None,
    }


def create_folder(project: Project, account: OAuthAccount | None = None) -> dict:
    """The project's folder: under the parent's folder for a sub-project
    (same owner account), at the Drive root with the type sub-folders for a
    root project (owner = `account`, the acting user's).

    Not atomic on purpose: a Google refusal marks the account needs_reauth,
    and that mark must survive the failure of the folder creation."""
    if project.drive_folder_id:
        raise DriveUnavailable("Ce projet a déjà un dossier Drive.")
    if project.parent_id:
        parent = project.parent
        if not parent.drive_folder_id:
            raise DriveUnavailable(
                "Le projet parent n'a pas de dossier Drive : crée-le d'abord."
            )
        owner = folder_owner(parent)
        client = DriveClient(owner)
        folder = client.create_folder(project.name, parent.drive_folder_id)
        project.drive_folder_id = folder["id"]
        project.drive_folder_url = folder.get("webViewLink", "")
        project.save(
            update_fields=["drive_folder_id", "drive_folder_url", "updated_at"]
        )
        return folder
    if account is None:
        raise DriveUnavailable("Connecte Google Drive pour créer le dossier du projet.")
    client = DriveClient(account)
    folder = client.create_folder(project.name)
    for name in SUBFOLDERS:
        client.create_folder(name, folder["id"])
    project.drive_folder_id = folder["id"]
    project.drive_folder_url = folder.get("webViewLink", "")
    project.drive_account = account
    project.save(
        update_fields=[
            "drive_folder_id",
            "drive_folder_url",
            "drive_account",
            "updated_at",
        ]
    )
    if project.drive_share_with_members:
        share_with_members(project)
    return folder


def share_with_members(project: Project) -> int:
    """Members who connected Google get the folder: Viewer → reader,
    Editor and above → writer. Returns how many were shared."""
    root = project
    while root.parent_id:
        root = root.parent
    if not root.drive_folder_id or not root.drive_share_with_members:
        return 0
    owner = folder_owner(root)
    client = DriveClient(owner)
    shared = 0
    accounts = OAuthAccount.objects.filter(
        user_id__in=member_user_ids(root), provider=Provider.GOOGLE
    ).select_related("user")
    for account in accounts:
        if account.pk == owner.pk or not account.account_email:
            continue
        access = effective_access(account.user, root)
        if not access.has(Role.VIEWER):
            continue
        drive_role = "writer" if access.has(Role.EDITOR) else "reader"
        try:
            client.share(root.drive_folder_id, account.account_email, drive_role)
            shared += 1
        except GoogleError:
            continue  # one refusal must not stop the others
    return shared


def upload_to_project(project: Project, upload, actor) -> DriveLink:
    """A file sent from the site to the project's Drive folder, with the
    owner's account; the result is attached as a DriveLink."""
    owner = folder_owner(project)
    if not project.drive_folder_id:
        raise DriveUnavailable("Ce projet n'a pas de dossier Drive.")
    client = DriveClient(owner)
    data = client.upload(
        upload.name or "fichier",
        upload.content_type or "",
        upload,
        project.drive_folder_id,
    )
    return DriveLink.objects.create(
        project=project, added_by=actor, **file_summary(data)
    )


def attach_picked_file(project: Project, file_id: str, actor, task=None) -> DriveLink:
    """A file chosen in the Picker: its metadata is re-read with the user's
    own account (the Picker grants drive.file access to that file)."""
    account = drive_account(actor)
    if account is None:
        raise DriveUnavailable("Connecte Google Drive pour attacher un fichier.")
    data = DriveClient(account).get_file(file_id)
    link, _ = DriveLink.objects.update_or_create(
        project=project,
        task=task,
        drive_file_id=file_id,
        defaults={"added_by": actor, **file_summary(data)},
    )
    return link


def integration_state(user) -> dict:
    """What the front needs to show the Intégrations settings."""
    account = google_account(user)
    ms = OAuthAccount.objects.filter(user=user, provider=Provider.MICROSOFT).first()
    return {
        "google": {
            "enabled": google.enabled(),
            "connected": account is not None,
            "email": account.account_email if account else "",
            "features": account.features if account else [],
            "status": account.status if account else "",
            "picker": bool(
                google.enabled() and account and account.has_feature("drive")
            ),
        },
        "microsoft": {
            "enabled": microsoft.enabled(),
            "connected": ms is not None,
            "email": ms.account_email if ms else "",
            "features": ["calendar"] if ms else [],
            "status": ms.status if ms else "",
            "picker": False,
        },
    }
