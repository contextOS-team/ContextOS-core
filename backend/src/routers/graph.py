"""Graph explorer API endpoint.

Exposes a ticket's graph neighborhood as structured JSON (nodes + edges),
enabling frontend visualization and external tool consumption.
"""

from fastapi import APIRouter
from pydantic import BaseModel as PydanticBaseModel


class GraphNodeResponse(PydanticBaseModel):
    """A single node in the graph neighborhood."""

    id: str
    entity_type: str
    name: str
    depth: int
    properties: dict


class GraphEdgeResponse(PydanticBaseModel):
    """A single edge in the graph neighborhood."""

    source: str
    target: str
    relationship_type: str
    properties: dict


class GraphNeighborhoodResponse(PydanticBaseModel):
    """Full graph neighborhood response for a ticket."""

    ticket_identifier: str
    depth: int
    node_count: int
    edge_count: int
    truncated: bool
    total_available: int | None = None
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]


router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/{ticket_identifier}")
async def get_graph_neighborhood(ticket_identifier: str) -> dict:
    """Get the graph neighborhood for a ticket. (stub -- not yet implemented)"""
    raise NotImplementedError
