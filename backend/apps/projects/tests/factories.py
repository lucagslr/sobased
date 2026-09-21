"""Factories and the reference tree used by the access-rights tests.

W (workspace)                    W2 (another workspace)
├─ R        depth 1              └─ Z   depth 1
│  ├─ A     depth 2
│  │  ├─ A1   depth 3
│  │  │  └─ A1x depth 4
│  │  └─ A2   depth 3
│  └─ B     depth 2
└─ R2       depth 1
"""

import factory

from apps.accounts.tests.factories import UserFactory
from apps.projects.models import Membership, Project
from apps.workspaces.models import ProjectType, Tag, Workspace


class WorkspaceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Workspace
        skip_postgeneration_save = True

    name = factory.Sequence(lambda n: f"Espace {n}")

    @factory.post_generation
    def with_defaults(self, create, extracted, **kwargs):
        if create:
            ProjectType.objects.create(workspace=self, name="Autre")


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag

    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"tag{n}")


class ProjectFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Project

    workspace = factory.SubFactory(WorkspaceFactory)
    name = factory.Sequence(lambda n: f"Projet {n}")
    type = factory.LazyAttribute(lambda o: o.workspace.project_types.first())


def grant(user, scope, role="viewer", **flags) -> Membership:
    key = "workspace" if isinstance(scope, Workspace) else "project"
    return Membership.objects.create(user=user, role=role, **{key: scope}, **flags)


# Ancestors of each node, written by hand: the tests' oracle must not reuse the
# code under test.
ANCESTORS = {
    "R": [],
    "A": ["R"],
    "A1": ["A", "R"],
    "A1x": ["A1", "A", "R"],
    "A2": ["A", "R"],
    "B": ["R"],
    "R2": [],
    "Z": [],
}
BY_DEPTH = {1: "R", 2: "A", 3: "A1", 4: "A1x"}


class Tree:
    """Builds the reference tree. Nodes are reachable as tree["A1"]."""

    def __init__(self):
        self.workspace = WorkspaceFactory(name="W")
        self.other_workspace = WorkspaceFactory(name="W2")
        self.owner = UserFactory(username="wsowner")
        grant(self.owner, self.workspace, "owner")
        self.nodes: dict[str, Project] = {}
        for name, parents in ANCESTORS.items():
            workspace = self.other_workspace if name == "Z" else self.workspace
            parent = self.nodes[parents[0]] if parents else None
            self.nodes[name] = ProjectFactory(
                workspace=workspace, parent=parent, name=name
            )

    def __getitem__(self, name: str) -> Project:
        return self.nodes[name]

    def name_of(self, project_id: int) -> str:
        return next(name for name, node in self.nodes.items() if node.pk == project_id)
