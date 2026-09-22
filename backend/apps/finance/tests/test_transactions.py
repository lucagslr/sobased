"""Transactions: finance rights, validation, receipts, statuses, filters."""

from decimal import Decimal

import pytest

from apps.accounts.tests.factories import UserFactory
from apps.contacts.models import Contact, ProjectContact
from apps.events.models import Event
from apps.finance.models import Transaction
from apps.projects.tests.factories import grant
from apps.tasks.tests.conftest import day

from .conftest import client_for, days, make_transaction, pdf_upload, png_upload

pytestmark = pytest.mark.django_db


def create(client, project, category, **fields):
    payload = {
        "project": project.pk,
        "kind": "expense",
        "amount": "120.50",
        "date": days(0).isoformat(),
        "category": category.pk,
        "label": "Location du studio",
    }
    return client.post("/api/transactions/", {**payload, **fields}, format="json")


def labels(response):
    return sorted(item["label"] for item in response.data["results"])


# --- Rights: the finance flags on top of the role -------------------------------------


def test_money_does_not_exist_without_can_view_finance(tree, categories, blind_editor):
    item = make_transaction(tree["A"], categories["Studio"])
    client = client_for(blind_editor)

    assert client.get("/api/transactions/").data["count"] == 0
    assert client.get(f"/api/transactions/{item.pk}/").status_code == 404
    assert create(client, tree["A"], categories["Studio"]).status_code == 404
    assert client.get("/api/finance/summary/").data["count"] == 0
    assert client.get(f"/api/finance/budget/?project={tree['A'].pk}").status_code == 404


def test_view_only_finance_reads_but_never_writes(tree, categories, finance_viewer):
    item = make_transaction(tree["A"], categories["Studio"])
    client = client_for(finance_viewer)

    assert client.get(f"/api/transactions/{item.pk}/").status_code == 200
    assert client.get("/api/transactions/").data["count"] == 1
    assert create(client, tree["A"], categories["Studio"]).status_code == 403
    assert (
        client.patch(
            f"/api/transactions/{item.pk}/", {"label": "x"}, format="json"
        ).status_code
        == 403
    )
    assert client.delete(f"/api/transactions/{item.pk}/").status_code == 403
    assert client.post(f"/api/transactions/{item.pk}/mark-paid/").status_code == 403


def test_treasurer_of_the_root_sees_the_whole_branch_only(
    tree, categories, treasurer_api
):
    make_transaction(tree["A1x"], categories["Studio"], label="deep")
    make_transaction(tree["B"], categories["Studio"], label="b")
    z_categories = tree.other_workspace.categories.first()
    make_transaction(tree["Z"], z_categories, label="hidden")
    make_transaction(tree["R2"], categories["Studio"], label="r2-hidden")

    assert labels(treasurer_api.get("/api/transactions/")) == ["b", "deep"]


def test_admins_get_finance_by_default_and_guests_of_a_branch_stay_in_it(
    tree, categories
):
    admin = UserFactory(username="admin")
    grant(admin, tree.workspace, "admin", can_view_finance=True, can_edit_finance=True)
    guest = UserFactory(username="guest")
    grant(guest, tree["A1"], "editor", can_view_finance=True, can_edit_finance=True)
    make_transaction(tree["A1x"], categories["Studio"], label="mine")
    make_transaction(tree["B"], categories["Studio"], label="not-mine")

    assert labels(client_for(admin).get("/api/transactions/")) == ["mine", "not-mine"]
    assert labels(client_for(guest).get("/api/transactions/")) == ["mine"]


# --- Creation and validation ----------------------------------------------------------


def test_create_with_defaults(tree, categories, treasurer_api, treasurer):
    response = create(treasurer_api, tree["A"], categories["Studio"])

    assert response.status_code == 201
    data = response.data
    assert data["amount"] == "120.50"
    assert data["payment_status"] == "paid"
    assert data["has_receipt"] is False and data["receipt_url"] is None
    assert data["needs_receipt"] is True  # an expense without a receipt
    assert data["display_status"] == "needs_receipt"
    assert data["payer"] is None and data["is_to_reimburse"] is False
    assert data["created_by"]["username"] == "treasurer"
    assert data["category_name"] == "Studio" and data["project_name"] == "A"


def test_an_income_never_needs_a_receipt_nor_reimbursement(
    tree, categories, treasurer_api
):
    response = create(
        treasurer_api,
        tree["A"],
        categories["Subvention"],
        kind="income",
        amount="5000",
        to_reimburse=True,
        paid_by_username="treasurer",
    )

    assert response.status_code == 201
    assert response.data["needs_receipt"] is False
    assert response.data["to_reimburse"] is False and response.data["payer"] is None
    assert response.data["display_status"] == "ok"


@pytest.mark.parametrize(
    "fields",
    [
        {"amount": "0"},
        {"amount": "-5"},
        {"amount": "abc"},
        {"kind": "loan"},
        {"label": ""},
        {"date": "hier"},
    ],
)
def test_invalid_fields(tree, categories, treasurer_api, fields):
    assert (
        create(treasurer_api, tree["A"], categories["Studio"], **fields).status_code
        == 400
    )


def test_category_must_belong_to_the_workspace(tree, categories, treasurer_api):
    foreign = tree.other_workspace.categories.first()

    response = create(treasurer_api, tree["A"], foreign)

    assert response.status_code == 400 and "category" in response.data


def test_amount_has_two_decimals_at_most(tree, categories, treasurer_api):
    # Half a cent does not exist: the client rounds before sending.
    response = create(treasurer_api, tree["A"], categories["Studio"], amount="10.005")
    exact = create(treasurer_api, tree["A"], categories["Studio"], amount="10.5")

    assert response.status_code == 400 and "amount" in response.data
    assert exact.status_code == 201
    assert Transaction.objects.get(pk=exact.data["id"]).amount == Decimal("10.50")


def test_a_transaction_never_changes_project(tree, categories, treasurer_api):
    item = make_transaction(tree["A"], categories["Studio"])

    treasurer_api.patch(
        f"/api/transactions/{item.pk}/", {"project": tree["B"].pk}, format="json"
    )

    item.refresh_from_db()
    assert item.project == tree["A"]


def test_contact_and_event_links(tree, categories, treasurer_api):
    contact = Contact.objects.create(workspace=tree.workspace, last_name="Studio")
    ProjectContact.objects.create(project=tree["A"], contact=contact)
    hidden = Contact.objects.create(workspace=tree.workspace, last_name="Hidden")
    event = Event.objects.create(
        project=tree["A"], title="Session", start=day(0), end=day(0), all_day=True
    )
    elsewhere = Event.objects.create(
        project=tree["Z"], title="Z", start=day(0), end=day(0), all_day=True
    )

    ok = create(
        treasurer_api,
        tree["A"],
        categories["Studio"],
        contact=contact.pk,
        event=event.pk,
    )
    bad_contact = create(
        treasurer_api, tree["A"], categories["Studio"], contact=hidden.pk
    )
    bad_event = create(
        treasurer_api, tree["A"], categories["Studio"], event=elsewhere.pk
    )

    assert ok.status_code == 201
    assert ok.data["contact_name"] == "Studio" and ok.data["event_title"] == "Session"
    assert bad_contact.status_code == 400 and bad_event.status_code == 400


# --- Receipts -------------------------------------------------------------------------


def test_receipt_uploaded_with_the_form(tree, categories, treasurer_api):
    response = treasurer_api.post(
        "/api/transactions/",
        {
            "project": tree["A"].pk,
            "kind": "expense",
            "amount": "42.00",
            "date": days(0).isoformat(),
            "category": categories["Studio"].pk,
            "label": "Câbles",
            "receipt": png_upload("ticket migros.png"),
        },
        format="multipart",
    )

    assert response.status_code == 201
    data = response.data
    assert data["has_receipt"] is True and data["needs_receipt"] is False
    assert data["receipt_name"] == "ticket migros.png"
    assert data["receipt_content_type"] == "image/png"
    assert data["receipt_url"] == f"/api/transactions/{data['id']}/receipt/"
    assert data["display_status"] == "ok"
    stored = Transaction.objects.get(pk=data["id"])
    # Random storage name: nothing of the original name in the path.
    assert "migros" not in stored.receipt.name and stored.receipt.name.endswith(".png")


def test_receipt_endpoint_serves_replaces_and_removes(tree, categories, treasurer_api):
    item = make_transaction(tree["A"], categories["Studio"])
    url = f"/api/transactions/{item.pk}/receipt/"

    assert treasurer_api.get(url).status_code == 404  # none yet
    put = treasurer_api.put(url, {"receipt": pdf_upload()}, format="multipart")
    assert put.status_code == 200
    assert put.data["receipt_content_type"] == "application/pdf"
    served = treasurer_api.get(url)
    assert served.status_code == 200
    assert served["Content-Type"] == "application/pdf"
    assert "facture.pdf" in served["Content-Disposition"]
    assert served["Cache-Control"] == "private, no-store"
    removed = treasurer_api.delete(url)
    assert removed.status_code == 200 and removed.data["needs_receipt"] is True
    assert treasurer_api.get(url).status_code == 404


def test_receipt_content_is_checked_not_its_name(tree, categories, treasurer_api):
    item = make_transaction(tree["A"], categories["Studio"])
    url = f"/api/transactions/{item.pk}/receipt/"
    from django.core.files.uploadedfile import SimpleUploadedFile

    fake = SimpleUploadedFile("ticket.png", b"<script>alert(1)</script>", "image/png")
    exe = SimpleUploadedFile("facture.pdf", b"MZ\x90\x00 not a pdf", "application/pdf")

    assert (
        treasurer_api.put(url, {"receipt": fake}, format="multipart").status_code == 400
    )
    assert (
        treasurer_api.put(url, {"receipt": exe}, format="multipart").status_code == 400
    )
    assert treasurer_api.put(url, {}, format="multipart").status_code == 400


def test_receipt_rights(tree, categories, treasurer_api, finance_viewer, blind_editor):
    item = make_transaction(tree["A"], categories["Studio"])
    treasurer_api.put(
        f"/api/transactions/{item.pk}/receipt/",
        {"receipt": png_upload()},
        format="multipart",
    )
    url = f"/api/transactions/{item.pk}/receipt/"

    viewer = client_for(finance_viewer)
    assert viewer.get(url).status_code == 200  # may look
    assert viewer.delete(url).status_code == 403  # may not touch
    assert client_for(blind_editor).get(url).status_code == 404


def test_deleting_a_transaction_removes_its_file(tree, categories, treasurer_api):
    item = make_transaction(tree["A"], categories["Studio"])
    treasurer_api.put(
        f"/api/transactions/{item.pk}/receipt/",
        {"receipt": png_upload()},
        format="multipart",
    )
    item.refresh_from_db()
    storage, name = item.receipt.storage, item.receipt.name
    assert storage.exists(name)

    assert treasurer_api.delete(f"/api/transactions/{item.pk}/").status_code == 204
    assert not storage.exists(name)


def test_deleting_a_project_removes_the_receipt_files_too(
    tree, categories, treasurer_api
):
    item = make_transaction(tree["A1x"], categories["Studio"])
    treasurer_api.put(
        f"/api/transactions/{item.pk}/receipt/",
        {"receipt": png_upload()},
        format="multipart",
    )
    item.refresh_from_db()
    storage, name = item.receipt.storage, item.receipt.name

    tree["A1"].delete()  # cascades to A1x and its transactions

    assert not Transaction.objects.filter(pk=item.pk).exists()
    assert not storage.exists(name)


# --- Statuses and advances ------------------------------------------------------------


def test_display_status_priority(tree, categories, treasurer_api):
    to_pay = make_transaction(
        tree["A"], categories["Studio"], payment_status="to_pay", to_reimburse=True
    )
    advance = make_transaction(
        tree["A"], categories["Studio"], to_reimburse=True, label="advance"
    )
    treasurer_api.put(
        f"/api/transactions/{advance.pk}/receipt/",
        {"receipt": png_upload()},
        format="multipart",
    )
    unjustified_advance = make_transaction(
        tree["A"], categories["Studio"], to_reimburse=True, label="both"
    )

    def get(item):
        return treasurer_api.get(f"/api/transactions/{item.pk}/").data

    assert get(to_pay)["display_status"] == "to_pay"
    assert get(advance)["display_status"] == "to_reimburse"
    assert get(unjustified_advance)["display_status"] == "needs_receipt"


def test_mark_paid_and_mark_reimbursed(tree, categories, treasurer_api):
    bill = make_transaction(tree["A"], categories["Logiciel"], payment_status="to_pay")
    advance = create(
        treasurer_api,
        tree["A"],
        categories["Transport"],
        paid_by_username="@Treasurer",
        to_reimburse=True,
    ).data

    paid = treasurer_api.post(f"/api/transactions/{bill.pk}/mark-paid/")
    reimbursed = treasurer_api.post(
        f"/api/transactions/{advance['id']}/mark-reimbursed/",
        {"reimbursed_on": days(1).isoformat()},
        format="json",
    )
    not_an_advance = treasurer_api.post(f"/api/transactions/{bill.pk}/mark-reimbursed/")

    assert paid.status_code == 200 and paid.data["payment_status"] == "paid"
    assert advance["payer"]["type"] == "user"
    assert advance["payer"]["username"] == "treasurer"
    assert reimbursed.status_code == 200
    assert reimbursed.data["reimbursed_on"] == days(1).isoformat()
    assert reimbursed.data["is_to_reimburse"] is False
    assert not_an_advance.status_code == 400


def test_payer_is_a_project_member_or_a_visible_contact(
    tree, categories, treasurer_api
):
    outsider = UserFactory(username="outsider")
    contact = Contact.objects.create(workspace=tree.workspace, last_name="Sam")
    ProjectContact.objects.create(project=tree["A"], contact=contact)

    refused = create(
        treasurer_api,
        tree["A"],
        categories["Studio"],
        paid_by_username=outsider.username,
    )
    by_contact = create(
        treasurer_api, tree["A"], categories["Studio"], paid_by_contact=contact.pk
    )

    assert refused.status_code == 400
    assert by_contact.status_code == 201
    assert by_contact.data["payer"]["type"] == "contact"
    assert by_contact.data["payer"]["name"] == "Sam"


def test_reimbursed_on_requires_an_advance(tree, categories, treasurer_api):
    response = create(
        treasurer_api,
        tree["A"],
        categories["Studio"],
        reimbursed_on=days(0).isoformat(),
    )

    assert response.status_code == 400 and "reimbursed_on" in response.data


# --- Filters --------------------------------------------------------------------------


def test_filters(tree, categories, treasurer_api, treasurer):
    make_transaction(tree["A"], categories["Studio"], label="a-old", date=days(-40))
    make_transaction(
        tree["A1"], categories["Logiciel"], label="a1-bill", payment_status="to_pay"
    )
    advance = make_transaction(
        tree["B"],
        categories["Transport"],
        label="b-advance",
        to_reimburse=True,
        paid_by_user=treasurer,
        vendor="CFF",
    )
    treasurer_api.put(
        f"/api/transactions/{advance.pk}/receipt/",
        {"receipt": png_upload()},
        format="multipart",
    )
    make_transaction(
        tree["B"], categories["Subvention"], label="b-grant", kind="income", amount=900
    )

    get = treasurer_api.get
    assert labels(get("/api/transactions/")) == [
        "a-old",
        "a1-bill",
        "b-advance",
        "b-grant",
    ]
    assert labels(get(f"/api/transactions/?project={tree['A'].pk}")) == ["a-old"]
    assert labels(
        get(f"/api/transactions/?project={tree['A'].pk}&include_descendants=true")
    ) == ["a-old", "a1-bill"]
    assert labels(get("/api/transactions/?kind=income")) == ["b-grant"]
    assert labels(get(f"/api/transactions/?category={categories['Logiciel'].pk}")) == [
        "a1-bill"
    ]
    assert labels(get(f"/api/transactions/?date_after={days(-7).isoformat()}")) == [
        "a1-bill",
        "b-advance",
        "b-grant",
    ]
    assert labels(get(f"/api/transactions/?date_before={days(-7).isoformat()}")) == [
        "a-old"
    ]
    assert labels(get("/api/transactions/?payment_status=to_pay")) == ["a1-bill"]
    assert labels(get("/api/transactions/?needs_receipt=true")) == ["a-old", "a1-bill"]
    assert labels(get("/api/transactions/?to_reimburse=true")) == ["b-advance"]
    assert labels(get("/api/transactions/?paid_by=me")) == ["b-advance"]
    assert labels(get("/api/transactions/?search=cff")) == ["b-advance"]
    assert labels(get(f"/api/transactions/?workspace={tree.other_workspace.pk}")) == []
    # Newest first by default.
    assert [t["label"] for t in get("/api/transactions/").data["results"]][
        -1
    ] == "a-old"
