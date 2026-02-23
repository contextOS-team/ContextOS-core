"""Tickets API routes.

Provides endpoints for listing and retrieving development tickets.
"""

from pydantic import BaseModel
from fastapi import APIRouter

router = APIRouter()


class Ticket(BaseModel):
    """A development ticket."""

    id: str
    title: str
    description: str
    status: str
    assignee: str | None = None
    labels: list[str] = []
    source: str = "linear"


class TicketList(BaseModel):
    """Paginated list of tickets."""

    items: list[Ticket]
    total: int
    offset: int
    limit: int


@router.get("", response_model=TicketList)
async def list_tickets(
    offset: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> TicketList:
    """List tickets with optional filtering.

    Args:
        offset: Pagination offset.
        limit: Maximum number of tickets to return.
        status: Optional status filter.

    Returns:
        A paginated list of tickets.
    """
    # TODO: implement — fetch tickets from Linear API / database
    return TicketList(
        items=[],
        total=0,
        offset=offset,
        limit=limit,
    )


@router.get("/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str) -> Ticket:
    """Retrieve a single ticket by ID.

    Args:
        ticket_id: The unique identifier of the ticket.

    Returns:
        The ticket details.
    """
    # TODO: implement — fetch ticket from Linear API / database
    return Ticket(
        id=ticket_id,
        title="",
        description="",
        status="unknown",
    )
