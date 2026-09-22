from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.projects.models import Project
from apps.workspaces.models import Tag, Workspace

from .models import Contact, ProjectContact


class ContactLinkSerializer(serializers.Serializer):
    """A project the contact is linked to (only projects I can open)."""

    id = serializers.IntegerField(help_text="Id of the link, for PATCH / DELETE")
    project = serializers.IntegerField()
    project_name = serializers.CharField()
    project_color = serializers.CharField()
    role_label = serializers.CharField()


class ContactSerializer(serializers.ModelSerializer):
    workspace = serializers.PrimaryKeyRelatedField(
        queryset=Workspace.objects.all(), required=False
    )
    # Write-only shortcut: create the contact AND link it to this project.
    # It is how a guest of a project (not a member of the workspace) adds one.
    project = serializers.PrimaryKeyRelatedField(
        queryset=Project.objects.all(), required=False, write_only=True
    )
    role_label = serializers.CharField(
        required=False, allow_blank=True, write_only=True, max_length=80
    )
    tags = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(), many=True, required=False
    )
    display_name = serializers.CharField(read_only=True)
    links = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            "id",
            "workspace",
            "project",
            "role_label",
            "first_name",
            "last_name",
            "display_name",
            "organization",
            "job",
            "email",
            "phone",
            "instagram",
            "website",
            "notes",
            "tags",
            "links",
            "can_edit",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    @extend_schema_field(ContactLinkSerializer(many=True))
    def get_links(self, contact) -> list[dict]:
        visible = set(self.context["access_map"].project_ids())
        return [
            {
                "id": link.pk,
                "project": link.project_id,
                "project_name": link.project.name,
                "project_color": link.project.color,
                "role_label": link.role_label,
            }
            for link in contact.project_links.all()
            if link.project_id in visible
        ]

    def get_can_edit(self, contact) -> bool:
        return self.context["can_edit"](contact)

    def validate_instagram(self, value):
        return value.strip().lstrip("@")

    def validate(self, attrs):
        if self.instance is not None:
            # A contact never changes workspace; links have their own endpoint.
            for key in ("workspace", "project", "role_label"):
                attrs.pop(key, None)
            workspace = self.instance.workspace
        else:
            project = attrs.get("project")
            if project is not None:
                attrs["workspace"] = project.workspace
            elif attrs.get("workspace") is None:
                raise serializers.ValidationError(
                    {"workspace": "Indique l'espace (ou le projet)."}
                )
            workspace = attrs["workspace"]

        def current(field):
            return attrs.get(field, getattr(self.instance, field, ""))

        if not any(
            current(f).strip() for f in ("first_name", "last_name", "organization")
        ):
            raise serializers.ValidationError(
                {"last_name": "Indique au moins un nom ou une organisation."}
            )
        for tag in attrs.get("tags", []):
            if tag.workspace_id != workspace.pk:
                raise serializers.ValidationError(
                    {"tags": "Ce tag n'est pas de cet espace."}
                )
        return attrs


class ProjectContactSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    contact = serializers.PrimaryKeyRelatedField(queryset=Contact.objects.all())
    contact_detail = serializers.SerializerMethodField()

    class Meta:
        model = ProjectContact
        fields = ["id", "project", "contact", "contact_detail", "role_label"]
        read_only_fields = ["id"]

    @extend_schema_field(ContactSerializer)
    def get_contact_detail(self, link) -> dict:
        return ContactSerializer(link.contact, context=self.context).data

    def validate(self, attrs):
        if self.instance is not None:
            attrs.pop("project", None)
            attrs.pop("contact", None)
            return attrs
        project, contact = attrs["project"], attrs["contact"]
        # The contact must be one I can see, and of the project's workspace.
        if (
            contact.workspace_id != project.workspace_id
            or not Contact.objects.for_user(self.context["request"])
            .filter(pk=contact.pk)
            .exists()
        ):
            raise serializers.ValidationError({"contact": "Contact introuvable."})
        if ProjectContact.objects.filter(project=project, contact=contact).exists():
            raise serializers.ValidationError(
                {"contact": "Ce contact est déjà lié à ce projet."}
            )
        return attrs
