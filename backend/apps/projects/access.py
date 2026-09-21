"""Access rights: THE single place where "who can do what" is decided.

Rules (SPEC §6, SPECIFICATIONS §1):

1. A workspace membership applies to every project of the workspace.
2. A project membership applies to that project and all its descendants.
3. When several memberships apply, the highest role wins, and each finance
   flag is the OR of the applicable ones. A membership lower in the tree never
   reduces a right inherited from above.
4. A user with access to a sub-project only sees its ancestors (and the
   workspace) as SHELLS: name, colour and breadcrumb, nothing else.
5. No applicable membership and no descendant membership: the object does
   not exist for that user (404).

Everything is computed by AccessMap, which resolves the whole set of trees a
user can reach in three queries (volumes are small, SPEC §5).
`effective_access(user, project)` is the single public entry point required
by the spec; the DRF mixin and the queryset filter in permissions.py are built
on the same map, so there is exactly one implementation of the rules above.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

from .models import Membership, Project
from .models import Role as StoredRole


class Role(IntEnum):
    """Roles as comparable ranks: `access.role >= Role.EDITOR`."""

    VIEWER = 10
    COMMENTER = 20
    EDITOR = 30
    ADMIN = 40
    OWNER = 50

    @classmethod
    def from_stored(cls, value: str) -> "Role":
        return _FROM_STORED[value]

    @property
    def stored(self) -> str:
        return _TO_STORED[self]


_FROM_STORED = {
    StoredRole.VIEWER: Role.VIEWER,
    StoredRole.COMMENTER: Role.COMMENTER,
    StoredRole.EDITOR: Role.EDITOR,
    StoredRole.ADMIN: Role.ADMIN,
    StoredRole.OWNER: Role.OWNER,
}
_TO_STORED = {rank: stored for stored, rank in _FROM_STORED.items()}


@dataclass(frozen=True)
class Access:
    """What a user may do on one project (or one workspace)."""

    role: Role | None = None
    can_view_finance: bool = False
    can_edit_finance: bool = False
    is_shell: bool = False

    @property
    def visible(self) -> bool:
        """The object exists for this user (fully, or as a shell)."""
        return self.role is not None or self.is_shell

    def has(self, minimum: Role) -> bool:
        return self.role is not None and self.role >= minimum

    def merged_with(self, other: "Access") -> "Access":
        """Rule 3: highest role, OR of the finance flags."""
        if other.role is None:
            return self
        if self.role is None:
            return Access(other.role, other.can_view_finance, other.can_edit_finance)
        return Access(
            role=max(self.role, other.role),
            can_view_finance=self.can_view_finance or other.can_view_finance,
            can_edit_finance=self.can_edit_finance or other.can_edit_finance,
        )


NO_ACCESS = Access()
SHELL = Access(is_shell=True)


def _from_membership(row: dict) -> Access:
    return Access(
        role=Role.from_stored(row["role"]),
        can_view_finance=row["can_view_finance"],
        can_edit_finance=row["can_edit_finance"],
    )


@dataclass
class AccessMap:
    """Resolved access of one user on every workspace and project they reach."""

    workspaces: dict[int, Access] = field(default_factory=dict)
    projects: dict[int, Access] = field(default_factory=dict)
    # project id -> parent id (None for roots), for the trees loaded here.
    parents: dict[int, int | None] = field(default_factory=dict)
    project_workspace: dict[int, int] = field(default_factory=dict)

    # --- Lookups ------------------------------------------------------------
    def for_project(self, project_id: int) -> Access:
        return self.projects.get(project_id, NO_ACCESS)

    def for_workspace(self, workspace_id: int) -> Access:
        return self.workspaces.get(workspace_id, NO_ACCESS)

    def project_ids(
        self, minimum: Role = Role.VIEWER, *, finance: str = ""
    ) -> list[int]:
        """Projects where the user has at least `minimum`.

        finance="view" / "edit" additionally requires the finance flag.
        Shells are never included: a shell grants no content.
        """
        result = []
        for project_id, access in self.projects.items():
            if not access.has(minimum):
                continue
            if finance == "view" and not access.can_view_finance:
                continue
            if finance == "edit" and not access.can_edit_finance:
                continue
            result.append(project_id)
        return result

    def visible_project_ids(self) -> list[int]:
        """Projects the user can see at all, shells included (navigation)."""
        return [pid for pid, access in self.projects.items() if access.visible]

    def ancestors(self, project_id: int) -> list[int]:
        """[parent, grand-parent, ..., root]. At most 3 entries."""
        chain = []
        current = self.parents.get(project_id)
        while current is not None:
            chain.append(current)
            current = self.parents.get(current)
        return chain

    def descendants(self, project_id: int) -> list[int]:
        children: dict[int | None, list[int]] = {}
        for pid, parent in self.parents.items():
            children.setdefault(parent, []).append(pid)
        result, stack = [], list(children.get(project_id, []))
        while stack:
            current = stack.pop()
            result.append(current)
            stack.extend(children.get(current, []))
        return result


def build_access_map(user) -> AccessMap:
    """Resolve rules 1 to 5 for `user`. Three queries, whatever the tree size."""
    access_map = AccessMap()
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return access_map

    memberships = list(
        Membership.objects.filter(user=user).values(
            "workspace_id", "project_id", "role", "can_view_finance", "can_edit_finance"
        )
    )
    if not memberships:
        return access_map

    workspace_grants: dict[int, Access] = {}
    project_grants: dict[int, Access] = {}
    for row in memberships:
        if row["workspace_id"]:
            workspace_grants[row["workspace_id"]] = _from_membership(row)
        else:
            project_grants[row["project_id"]] = _from_membership(row)

    # Workspaces to load: those joined directly + those of the joined projects.
    workspace_ids = set(workspace_grants)
    if project_grants:
        workspace_ids.update(
            Project.objects.filter(pk__in=project_grants).values_list(
                "workspace_id", flat=True
            )
        )

    # Parents before children, so that inheritance is a single pass.
    nodes = Project.objects.filter(workspace_id__in=workspace_ids).order_by("depth")
    for project_id, parent_id, workspace_id in nodes.values_list(
        "id", "parent_id", "workspace_id"
    ):
        access_map.parents[project_id] = parent_id
        access_map.project_workspace[project_id] = workspace_id
        inherited = (
            access_map.projects[parent_id]  # rule 2
            if parent_id is not None
            else workspace_grants.get(workspace_id, NO_ACCESS)  # rule 1
        )
        own = project_grants.get(project_id, NO_ACCESS)
        access_map.projects[project_id] = inherited.merged_with(own)  # rule 3

    # Rule 4: ancestors of an accessible project, and its workspace, are shells.
    for project_id, access in list(access_map.projects.items()):
        if access.role is None:
            continue
        for ancestor_id in access_map.ancestors(project_id):
            if access_map.projects[ancestor_id].role is None:
                access_map.projects[ancestor_id] = SHELL
        workspace_id = access_map.project_workspace[project_id]
        if workspace_id not in workspace_grants:
            access_map.workspaces[workspace_id] = SHELL

    access_map.workspaces.update(workspace_grants)
    # Rule 5: drop what stayed invisible, so "in the map" means "visible".
    access_map.projects = {
        pid: access for pid, access in access_map.projects.items() if access.visible
    }
    return access_map


_CACHE_ATTR = "_sobased_access_map"


def get_access_map(actor) -> AccessMap:
    """AccessMap for a user, or for a DRF/Django request (cached on it).

    Pass the request whenever there is one: a list endpoint would otherwise
    rebuild the map for every object it checks.
    """
    user = getattr(actor, "user", actor)
    if user is actor:  # a bare user: nothing to cache on
        return build_access_map(user)
    # DRF wraps the Django request; cache on the underlying one so that both
    # wrappers share it.
    holder = getattr(actor, "_request", actor)
    cached = getattr(holder, _CACHE_ATTR, None)
    if cached is None or cached[0] != user.pk:
        cached = (user.pk, build_access_map(user))
        setattr(holder, _CACHE_ATTR, cached)
    return cached[1]


def invalidate_access_map(actor) -> None:
    """Call after changing memberships or the tree within a request."""
    holder = getattr(actor, "_request", actor)
    if hasattr(holder, _CACHE_ATTR):
        delattr(holder, _CACHE_ATTR)


def effective_access(actor, project) -> Access:
    """Role + finance flags of a user (or request) on a project. SPEC §6."""
    project_id = project.pk if hasattr(project, "pk") else int(project)
    return get_access_map(actor).for_project(project_id)


def member_user_ids(project) -> set[int]:
    """Ids of every user with a real role on `project` (direct or inherited).

    The reverse question of effective_access(): used to decide who may be
    assigned a task or mentioned. Same rules 1 and 2: a membership on the
    workspace, on the project, or on any of its ancestors.
    """
    chain = [project.pk]
    parent_id = project.parent_id
    while parent_id is not None:
        chain.append(parent_id)
        parent_id = (
            Project.objects.filter(pk=parent_id)
            .values_list("parent_id", flat=True)
            .first()
        )
    rows = Membership.objects.filter(workspace_id=project.workspace_id).values_list(
        "user_id", flat=True
    ) | Membership.objects.filter(project_id__in=chain).values_list(
        "user_id", flat=True
    )
    return set(rows)


def workspace_access(actor, workspace) -> Access:
    workspace_id = workspace.pk if hasattr(workspace, "pk") else int(workspace)
    return get_access_map(actor).for_workspace(workspace_id)
