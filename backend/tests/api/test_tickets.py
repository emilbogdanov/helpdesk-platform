import pytest
from httpx import AsyncClient

from helpdesk.domain.tickets.status import TicketStatus
from tests.api.conftest import Headers
from tests.unit.application.fakes import FakeUnitOfWork
from tests.unit.domain.tickets.builders import (
    MILA,
    REQUESTER,
    STEFAN,
    TICKET_ID,
    open_ticket,
    ticket_in,
)

NEW_TICKET = {
    "subject": "Two-factor codes arrive after they expire",
    "description": "SMS codes take about 90 seconds to arrive; the login form rejects them.",
    "priority": "high",
}


async def seed(uow: FakeUnitOfWork, status: TicketStatus | None = None) -> None:
    ticket = open_ticket() if status is None else ticket_in(status)
    await uow.tickets.add(ticket, idempotency_key=None)


class TestOpenTicket:
    async def test_customer_opens_a_ticket(self, client: AsyncClient, as_customer: Headers) -> None:
        response = await client.post("/tickets", json=NEW_TICKET, headers=as_customer)

        assert response.status_code == 201
        body = response.json()
        assert body["requester_id"] == str(REQUESTER)
        assert body["status"] == "open"
        assert body["priority"] == "high"
        assert body["assignee_id"] is None

    async def test_priority_defaults_to_normal(
        self, client: AsyncClient, as_customer: Headers
    ) -> None:
        body = {key: value for key, value in NEW_TICKET.items() if key != "priority"}

        response = await client.post("/tickets", json=body, headers=as_customer)

        assert response.json()["priority"] == "normal"

    async def test_retry_with_the_same_idempotency_key_returns_the_same_ticket(
        self, client: AsyncClient, as_customer: Headers
    ) -> None:
        headers = as_customer | {"Idempotency-Key": "c0ffee-2fa-retry"}

        first = await client.post("/tickets", json=NEW_TICKET, headers=headers)
        retry = await client.post("/tickets", json=NEW_TICKET, headers=headers)

        assert retry.status_code == 201
        assert retry.json() == first.json()

    async def test_idempotency_key_reused_for_another_ticket_is_rejected(
        self, client: AsyncClient, as_customer: Headers
    ) -> None:
        headers = as_customer | {"Idempotency-Key": "c0ffee-2fa-retry"}
        await client.post("/tickets", json=NEW_TICKET, headers=headers)

        response = await client.post(
            "/tickets", json=NEW_TICKET | {"priority": "low"}, headers=headers
        )

        assert response.status_code == 422
        assert response.json()["code"] == "idempotency_key_reused"

    async def test_oversized_idempotency_key_is_rejected(
        self, client: AsyncClient, as_customer: Headers
    ) -> None:
        headers = as_customer | {"Idempotency-Key": "k" * 256}

        response = await client.post("/tickets", json=NEW_TICKET, headers=headers)

        assert response.status_code == 422

    async def test_multiline_subject_is_rejected(
        self, client: AsyncClient, as_customer: Headers
    ) -> None:
        body = NEW_TICKET | {"subject": "Two-factor\ncodes"}

        response = await client.post("/tickets", json=body, headers=as_customer)

        assert response.status_code == 422
        assert response.json()["detail"] == "subject must be a single line"


class TestReadTicket:
    async def test_requester_reads_their_ticket(
        self, client: AsyncClient, as_customer: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow)

        response = await client.get(f"/tickets/{TICKET_ID}", headers=as_customer)

        assert response.status_code == 200
        assert response.json()["subject"] == "Invoice PDF shows last month's VAT rate"

    async def test_other_customers_get_404(
        self, client: AsyncClient, as_other_customer: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow)

        response = await client.get(f"/tickets/{TICKET_ID}", headers=as_other_customer)

        assert response.status_code == 404
        assert response.json()["code"] == "ticket_not_found"

    async def test_malformed_id_is_a_validation_error(
        self, client: AsyncClient, as_agent: Headers
    ) -> None:
        response = await client.get("/tickets/not-a-uuid", headers=as_agent)

        assert response.status_code == 422


class TestWorkflow:
    async def test_agent_works_a_ticket_from_queue_to_resolution(
        self, client: AsyncClient, as_agent: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow)
        url = f"/tickets/{TICKET_ID}"

        taken = await client.post(f"{url}/take", headers=as_agent)
        started = await client.put(
            f"{url}/status", json={"status": "in_progress"}, headers=as_agent
        )
        escalated = await client.put(
            f"{url}/priority", json={"priority": "urgent"}, headers=as_agent
        )
        resolved = await client.put(f"{url}/status", json={"status": "resolved"}, headers=as_agent)

        assert taken.json()["assignee_id"] == str(MILA)
        assert started.json()["status"] == "in_progress"
        assert escalated.json()["priority"] == "urgent"
        assert resolved.json()["status"] == "resolved"
        assert resolved.json()["resolved_at"] is not None

    async def test_admin_assigns_and_unassigns(
        self, client: AsyncClient, as_admin: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow)
        url = f"/tickets/{TICKET_ID}/assignee"

        assigned = await client.put(url, json={"assignee_id": str(STEFAN)}, headers=as_admin)
        released = await client.delete(url, headers=as_admin)

        assert assigned.json()["assignee_id"] == str(STEFAN)
        assert released.json()["assignee_id"] is None

    async def test_assigning_to_a_customer_is_rejected(
        self, client: AsyncClient, as_agent: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow)

        response = await client.put(
            f"/tickets/{TICKET_ID}/assignee", json={"assignee_id": str(REQUESTER)}, headers=as_agent
        )

        assert response.status_code == 422
        assert response.json()["code"] == "invalid_assignee"

    async def test_invalid_transition_conflicts(
        self, client: AsyncClient, as_agent: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, TicketStatus.WAITING_ON_CUSTOMER)

        response = await client.put(
            f"/tickets/{TICKET_ID}/status", json={"status": "closed"}, headers=as_agent
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": "cannot move a ticket from waiting_on_customer to closed",
            "code": "invalid_status_transition",
        }

    async def test_unknown_status_is_a_validation_error(
        self, client: AsyncClient, as_agent: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow)

        response = await client.put(
            f"/tickets/{TICKET_ID}/status", json={"status": "escalated"}, headers=as_agent
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("PUT", "status", {"status": "resolved"}),
            ("PUT", "priority", {"priority": "urgent"}),
            ("PUT", "assignee", {"assignee_id": str(MILA)}),
            ("DELETE", "assignee", None),
            ("POST", "take", None),
        ],
    )
    async def test_customers_cannot_work_tickets(
        self,
        client: AsyncClient,
        as_customer: Headers,
        uow: FakeUnitOfWork,
        method: str,
        path: str,
        body: dict[str, str] | None,
    ) -> None:
        await seed(uow)

        response = await client.request(
            method, f"/tickets/{TICKET_ID}/{path}", json=body, headers=as_customer
        )

        assert response.status_code == 403
        assert response.json()["code"] == "staff_only"


class TestComments:
    async def test_requester_reply_resumes_a_waiting_ticket(
        self, client: AsyncClient, as_customer: Headers, as_agent: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, TicketStatus.WAITING_ON_CUSTOMER)

        reply = await client.post(
            f"/tickets/{TICKET_ID}/comments",
            json={"body": "It still shows 19% after re-downloading."},
            headers=as_customer,
        )
        ticket = await client.get(f"/tickets/{TICKET_ID}", headers=as_agent)

        assert reply.status_code == 201
        assert reply.json()["visibility"] == "public"
        assert ticket.json()["status"] == "in_progress"

    async def test_internal_notes_are_hidden_from_the_requester(
        self, client: AsyncClient, as_customer: Headers, as_agent: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, TicketStatus.IN_PROGRESS)
        url = f"/tickets/{TICKET_ID}/comments"
        await client.post(
            url,
            json={"body": "Billing pushed the VAT change late.", "visibility": "internal"},
            headers=as_agent,
        )
        await client.post(url, json={"body": "We're on it."}, headers=as_agent)

        as_seen_by_customer = await client.get(url, headers=as_customer)
        as_seen_by_agent = await client.get(url, headers=as_agent)

        assert [c["body"] for c in as_seen_by_customer.json()] == ["We're on it."]
        assert len(as_seen_by_agent.json()) == 2

    async def test_customer_cannot_write_internal_notes(
        self, client: AsyncClient, as_customer: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow)

        response = await client.post(
            f"/tickets/{TICKET_ID}/comments",
            json={"body": "Note to self", "visibility": "internal"},
            headers=as_customer,
        )

        assert response.status_code == 403
        assert response.json()["code"] == "internal_note_not_allowed"

    async def test_closed_ticket_takes_no_comments(
        self, client: AsyncClient, as_agent: Headers, uow: FakeUnitOfWork
    ) -> None:
        await seed(uow, TicketStatus.CLOSED)

        response = await client.post(
            f"/tickets/{TICKET_ID}/comments", json={"body": "One more thing"}, headers=as_agent
        )

        assert response.status_code == 409
        assert response.json()["code"] == "ticket_closed"
