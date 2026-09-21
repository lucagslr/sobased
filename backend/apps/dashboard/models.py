"""Saved dashboard views (SPEC §15): a named filter + a widget layout, per user.

Example: "Perso", "100SATIONS", "École". A view belongs to one user and is
never shared; what it shows is always re-filtered by that user's rights at
query time, so a saved filter can never reveal a project they lost access to.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel

# Widget keys, in their default order. "overdue" is always first and can never
# be hidden (SPEC §7: late tasks stay on top until someone deals with them).
# The last three light up when their feature exists (phases 6 and 7).
WIDGET_KEYS = [
    "overdue",
    "today",
    "pinned",
    "next7",
    "to_validate",
    "meetings",
    "expenses_to_pay",
    "missing_receipts",
]
PINNED_FIRST = "overdue"
MIN_SIZE, MAX_SIZE = 1, 3  # width in grid columns (decision D3: preset sizes)


def default_layout() -> list[dict]:
    return [
        {
            "key": key,
            "size": 2 if key == PINNED_FIRST else 1,
            "tall": False,
            "hidden": False,
        }
        for key in WIDGET_KEYS
    ]


def normalise_layout(layout) -> list[dict]:
    """Clean a layout coming from the client.

    Unknown keys are dropped, missing widgets are appended with their defaults
    (so a widget added by a later phase shows up in existing views), sizes are
    clamped, and "overdue" is forced first and visible.
    """
    defaults = {item["key"]: item for item in default_layout()}
    seen, cleaned = set(), []
    for item in layout if isinstance(layout, list) else []:
        key = item.get("key") if isinstance(item, dict) else None
        if key not in defaults or key in seen:
            continue
        seen.add(key)
        try:
            size = int(item.get("size", defaults[key]["size"]))
        except (TypeError, ValueError):
            size = defaults[key]["size"]
        cleaned.append(
            {
                "key": key,
                "size": max(MIN_SIZE, min(MAX_SIZE, size)),
                "tall": bool(item.get("tall", False)),
                "hidden": bool(item.get("hidden", False)),
            }
        )
    cleaned += [defaults[key] for key in WIDGET_KEYS if key not in seen]
    first = next(item for item in cleaned if item["key"] == PINNED_FIRST)
    first["hidden"] = False
    cleaned.remove(first)
    return [first, *cleaned]


def default_filters() -> dict:
    return {"workspaces": [], "projects": [], "tags": [], "only_mine": False}


def normalise_filters(filters) -> dict:
    """Keep only what we understand: lists of ids and one boolean."""
    source = filters if isinstance(filters, dict) else {}
    cleaned = default_filters()
    for key in ("workspaces", "projects", "tags"):
        values = source.get(key) or []
        if isinstance(values, list):
            cleaned[key] = sorted({int(v) for v in values if str(v).isdigit()})
    cleaned["only_mine"] = bool(source.get("only_mine", False))
    return cleaned


class DashboardView(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_views",
    )
    name = models.CharField(max_length=60)
    # {"workspaces": [ids], "projects": [ids], "tags": [ids], "only_mine": bool}
    filters = models.JSONField(default=default_filters)
    # [{"key", "size" 1-3, "tall", "hidden"}], in display order.
    layout = models.JSONField(default=default_layout)
    is_default = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=Q(is_default=True),
                name="dashboardview_single_default_per_user",
            )
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.filters = normalise_filters(self.filters)
        self.layout = normalise_layout(self.layout)
        super().save(*args, **kwargs)
