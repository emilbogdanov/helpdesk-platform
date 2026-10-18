from uuid import uuid4

from helpdesk.application.actor import Actor
from helpdesk.application.ports import Clock, UnitOfWork
from helpdesk.application.tickets.access import load_visible_ticket
from helpdesk.domain.ids import CommentId, TicketId
from helpdesk.domain.tickets.comment import Comment, CommentBody, Visibility


class CommentService:
    def __init__(self, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def add_comment(
        self,
        actor: Actor,
        ticket_id: TicketId,
        *,
        body: CommentBody,
        visibility: Visibility,
    ) -> Comment:
        async with self._uow as uow:
            ticket = await load_visible_ticket(uow.tickets, actor, ticket_id)
            comment = ticket.add_comment(
                comment_id=CommentId(uuid4()),
                author_id=actor.user_id,
                author_role=actor.role,
                body=body,
                visibility=visibility,
                at=self._clock.now(),
            )
            await uow.comments.add(comment)
            # The ticket changed too: updated_at always, and status when the requester replies.
            await uow.tickets.update(ticket)
            await uow.audit.record(actor.user_id, ticket.pull_events())
            await uow.commit()
        return comment

    async def list_comments(self, actor: Actor, ticket_id: TicketId) -> list[Comment]:
        async with self._uow as uow:
            await load_visible_ticket(uow.tickets, actor, ticket_id)
            return await uow.comments.list_for_ticket(
                ticket_id, include_internal=actor.role.is_staff
            )
