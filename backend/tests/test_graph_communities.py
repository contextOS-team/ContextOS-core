"""Unit tests for the graph_communities service."""

import uuid
from unittest.mock import MagicMock

import networkx as nx
import pytest

from src.services.graph_communities import (
    EDGE_WEIGHTS,
    BRIDGE_DAMPENER,
    build_louvain_graph,
)


def _node(node_id: uuid.UUID, entity_type: str):
    n = MagicMock()
    n.id = node_id
    n.entity_type = entity_type
    return n


def _edge(src: uuid.UUID, tgt: uuid.UUID, rel: str):
    e = MagicMock()
    e.source_node_id = src
    e.target_node_id = tgt
    e.relationship_type = rel
    return e


class TestBuildLouvainGraphDirectEdges:
    def test_empty_inputs_produce_empty_graph(self):
        g = build_louvain_graph(person_ticket_nodes=[], direct_edges=[], bridges=[])
        assert isinstance(g, nx.Graph)
        assert g.number_of_nodes() == 0
        assert g.number_of_edges() == 0

    def test_adds_person_and_ticket_nodes(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[
                _node(p_id, "Person"),
                _node(t_id, "Ticket"),
            ],
            direct_edges=[],
            bridges=[],
        )
        assert set(g.nodes) == {p_id, t_id}
        assert g.number_of_edges() == 0

    def test_assigned_to_edge_uses_weight_3(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[_edge(p_id, t_id, "assigned_to")],
            bridges=[],
        )
        assert g[p_id][t_id]["weight"] == EDGE_WEIGHTS["assigned_to"]
        assert EDGE_WEIGHTS["assigned_to"] == 3.0

    def test_multiple_edges_same_pair_sum_weights(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[
                _edge(p_id, t_id, "assigned_to"),
                _edge(p_id, t_id, "mentions"),
            ],
            bridges=[],
        )
        # 3.0 (assigned_to) + 0.5 (mentions) = 3.5
        assert g[p_id][t_id]["weight"] == pytest.approx(3.5)

    def test_same_as_edges_skipped(self):
        p1, p2 = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p1, "Person"), _node(p2, "Person")],
            direct_edges=[_edge(p1, p2, "same_as")],
            bridges=[],
        )
        assert not g.has_edge(p1, p2)

    def test_unknown_relationship_type_uses_default_weight_1(self):
        p_id, t_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[_edge(p_id, t_id, "implements")],
            bridges=[],
        )
        assert g[p_id][t_id]["weight"] == 1.0
