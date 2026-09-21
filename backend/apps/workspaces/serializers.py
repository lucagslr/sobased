from rest_framework import serializers

from apps.accounts.serializers import PublicUserSerializer

from .models import ProjectType, Tag, Workspace


class WorkspaceSerializer(serializers.ModelSerializer):
    """Full view of a workspace, for its members."""

    my_role = serializers.SerializerMethodField()
    is_shell = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()

    class Meta:
        model = Workspace
        fields = ["id", "name", "color", "my_role", "is_shell", "owner", "created_at"]
        read_only_fields = ["id", "created_at"]

    def _access(self, workspace):
        return self.context["access_map"].for_workspace(workspace.pk)

    def get_my_role(self, workspace) -> str | None:
        role = self._access(workspace).role
        return role.stored if role else None

    def get_is_shell(self, workspace) -> bool:
        return self._access(workspace).is_shell

    def get_owner(self, workspace) -> dict | None:
        # A shell member learns nothing about the people of the workspace.
        if self._access(workspace).is_shell:
            return None
        owner = workspace.owner
        return PublicUserSerializer(owner).data if owner else None


class ProjectTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectType
        fields = ["id", "workspace", "name", "position"]

    def validate(self, attrs):
        workspace = attrs.get("workspace") or self.instance.workspace
        name = attrs.get("name", getattr(self.instance, "name", ""))
        clash = ProjectType.objects.filter(workspace=workspace, name__iexact=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
            attrs.pop("workspace", None)  # a type never changes workspace
        if clash.exists():
            raise serializers.ValidationError({"name": "Ce type existe déjà."})
        return attrs


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "workspace", "name", "color"]

    def validate(self, attrs):
        workspace = attrs.get("workspace") or self.instance.workspace
        name = attrs.get("name", getattr(self.instance, "name", ""))
        clash = Tag.objects.filter(workspace=workspace, name__iexact=name)
        if self.instance:
            clash = clash.exclude(pk=self.instance.pk)
            attrs.pop("workspace", None)  # a tag never changes workspace
        if clash.exists():
            raise serializers.ValidationError({"name": "Ce tag existe déjà."})
        return attrs
