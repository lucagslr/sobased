"""The daily digest: who gets it when, what it says, nothing when empty."""

from datetime import UTC, date, datetime, time, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from apps.accounts.tests.factories import UserFactory
from apps.events.models import Event
from apps.finance.models import Category, Kind, Transaction
from apps.notifications import digest
from apps.projects.tests.factories import Tree, grant
from apps.tasks.tests.conftest import TaskFactory, day

pytestmark = pytest.mark.django_db


@pytest.fixture
def tree(db):
    return Tree()


@pytest.fixture
def luca(tree):
    user = UserFactory(
        username="luca",
        timezone="Europe/Zurich",
        daily_digest_time=time(8, 0),
        email_verified_at=timezone.now(),
    )
    grant(user, tree["R"], "editor", can_view_finance=True, can_edit_finance=True)
    return user


def zurich(hour: int, minute: int = 0, on: date | None = None) -> datetime:
    """A UTC instant that is `hour:minute` in Zurich (CEST in September)."""
    on = on or date(2026, 9, 23)
    return datetime(on.year, on.month, on.day, hour - 2, minute, tzinfo=UTC)


def test_due_when_local_hour_passed_and_not_sent_today(luca):
    assert not digest.due_now(luca, zurich(7, 45))
    assert digest.due_now(luca, zurich(8, 5))
    luca.last_digest_sent_on = date(2026, 9, 23)
    assert not digest.due_now(luca, zurich(9, 0))
    assert digest.due_now(luca, zurich(8, 0, on=date(2026, 9, 24)))
    luca.daily_digest_enabled = False
    assert not digest.due_now(luca, zurich(9, 0, on=date(2026, 9, 24)))
    luca.daily_digest_enabled = True
    luca.email_verified_at = None
    assert not digest.due_now(luca, zurich(9, 0, on=date(2026, 9, 24)))


def test_nothing_to_say_sends_nothing_but_stamps_the_day(luca):
    assert digest.send(luca) is False
    assert mail.outbox == []
    luca.refresh_from_db()
    assert luca.last_digest_sent_on == timezone.localdate()


def test_sections(luca, tree):
    late = TaskFactory(project=tree["A"], title="En retard", due_at=day(-2), priority=5)
    late.assignees.add(luca)
    todays = TaskFactory(project=tree["A"], title="Ce matin", due_at=day(0))
    todays.assignees.add(luca)
    other = TaskFactory(project=tree["A"], title="Pas à moi", due_at=day(0))
    other.assignees.add(UserFactory(username="other"))
    TaskFactory(project=tree["B"], title="À valider", status="to_validate")
    Event.objects.create(
        project=tree["A"],
        title="Réunion label",
        # Ongoing right now: "today's meetings" are those not finished yet, so a
        # fixed hour would make the test depend on the time of day it runs.
        start=timezone.now() - timedelta(minutes=5),
        end=timezone.now() + timedelta(hours=1),
        created_by=luca,
    )
    if not tree.workspace.categories.exists():
        Category.create_defaults(tree.workspace)
    category = tree.workspace.categories.first()
    Transaction.objects.create(
        project=tree["A"],
        category=category,
        kind=Kind.EXPENSE,
        amount="120.00",
        date=timezone.localdate() + timedelta(days=3),
        label="Loyer studio",
        payment_status="to_pay",
    )
    Transaction.objects.create(
        project=tree["A"],
        category=category,
        kind=Kind.EXPENSE,
        amount="45.50",
        date=timezone.localdate() - timedelta(days=10),
        label="Câbles",
        payment_status="paid",
    )
    built = digest.build(luca)
    assert built is not None
    sections = built["sections"]
    assert [t["title"] for t in sections["overdue"]] == ["En retard"]
    assert [t["title"] for t in sections["today"]] == ["Ce matin"]
    assert [e["title"] for e in sections["meetings"]] == ["Réunion label"]
    assert [i["title"] for i in sections["to_validate"]] == ["À valider"]
    assert [t["title"] for t in sections["to_pay"]] == ["Loyer studio"]
    assert {t["title"] for t in sections["missing_receipts"]} == {
        "Loyer studio",
        "Câbles",
    }

    assert digest.send(luca) is True
    [message] = mail.outbox
    assert message.to == [luca.email]
    assert "résumé" in message.subject
    assert "En retard" in message.body and "Loyer studio" in message.body
    html = message.alternatives[0][0]
    assert (
        "Justificatifs manquants" in html
        and f"/projets/{tree['A'].pk}/taches?tache=" in html
    )


def test_money_sections_need_the_finance_flag(tree):
    blind = UserFactory(username="blind", email_verified_at=timezone.now())
    grant(blind, tree["R"], "editor")
    if not tree.workspace.categories.exists():
        Category.create_defaults(tree.workspace)
    Transaction.objects.create(
        project=tree["A"],
        category=tree.workspace.categories.first(),
        kind=Kind.EXPENSE,
        amount="10.00",
        date=timezone.localdate(),
        label="Secret",
        payment_status="to_pay",
    )
    late = TaskFactory(project=tree["A"], title="Retard", due_at=day(-1))
    late.assignees.add(blind)
    built = digest.build(blind)
    assert (
        built["sections"]["to_pay"] == []
        and built["sections"]["missing_receipts"] == []
    )
    assert [t["title"] for t in built["sections"]["overdue"]] == ["Retard"]


def test_send_due_digests_picks_the_right_users(luca, tree):
    late = TaskFactory(project=tree["A"], title="Retard", due_at=day(-1))
    late.assignees.add(luca)
    early_bird = UserFactory(
        username="early",
        timezone="Europe/Zurich",
        daily_digest_time=time(6, 0),
        email_verified_at=timezone.now(),
        last_digest_sent_on=date(2026, 9, 23),
    )
    grant(early_bird, tree["A"], "editor")
    assert digest.send_due_digests(zurich(8, 30)) == 1  # luca only: early got it
    assert [m.to for m in mail.outbox] == [[luca.email]]
    assert digest.send_due_digests(zurich(8, 45)) == 0  # not twice
