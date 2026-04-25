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


class TestBuildLouvainGraphBridgeProjection:
    def test_single_bridge_emits_person_to_ticket_edge(self):
        p_id, t_id, b_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[],
            bridges=[
                (b_id, [(p_id, "authored_by")], [(t_id, "references")]),
            ],
        )
        assert g.has_edge(p_id, t_id)
        # 0.5 dampener * min(2.5, 0.5) = 0.5 * 0.5 = 0.25
        assert g[p_id][t_id]["weight"] == pytest.approx(0.25)

    def test_bridge_with_multiple_persons_and_tickets_emits_cartesian_product(self):
        p1, p2, t1, t2, b_id = (uuid.uuid4() for _ in range(5))
        g = build_louvain_graph(
            person_ticket_nodes=[
                _node(p1, "Person"),
                _node(p2, "Person"),
                _node(t1, "Ticket"),
                _node(t2, "Ticket"),
            ],
            direct_edges=[],
            bridges=[
                (
                    b_id,
                    [(p1, "authored_by"), (p2, "discussed_in")],
                    [(t1, "references"), (t2, "references")],
                ),
            ],
        )
        assert g.number_of_edges() == 4
        # p1->t1: 0.5 * min(2.5, 0.5) = 0.25
        assert g[p1][t1]["weight"] == pytest.approx(0.25)
        # p2->t2: 0.5 * min(1.5, 0.5) = 0.25
        assert g[p2][t2]["weight"] == pytest.approx(0.25)

    def test_direct_and_bridge_edges_sum(self):
        p_id, t_id, b_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person"), _node(t_id, "Ticket")],
            direct_edges=[_edge(p_id, t_id, "assigned_to")],
            bridges=[(b_id, [(p_id, "authored_by")], [(t_id, "references")])],
        )
        # direct 3.0 + bridge 0.25 = 3.25
        assert g[p_id][t_id]["weight"] == pytest.approx(3.25)

    def test_bridge_with_no_tickets_emits_no_edges(self):
        p_id, b_id = uuid.uuid4(), uuid.uuid4()
        g = build_louvain_graph(
            person_ticket_nodes=[_node(p_id, "Person")],
            direct_edges=[],
            bridges=[(b_id, [(p_id, "authored_by")], [])],
        )
        assert g.number_of_edges() == 0


from src.services.graph_communities import partition_communities


class TestPartitionCommunities:
    def _make_two_clusters(self):
        # Two tightly connected triangles, weakly bridged.
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        d, e, f = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        g = nx.Graph()
        for n in (a, b, c, d, e, f):
            g.add_node(n)
        for u, v in [(a, b), (b, c), (a, c)]:
            g.add_edge(u, v, weight=10.0)
        for u, v in [(d, e), (e, f), (d, f)]:
            g.add_edge(u, v, weight=10.0)
        g.add_edge(c, d, weight=0.1)  # weak bridge
        return g, {a, b, c}, {d, e, f}

    def test_partitions_two_clear_clusters(self):
        g, cluster1, cluster2 = self._make_two_clusters()
        communities = partition_communities(g)
        assert len(communities) == 2
        cluster_sets = [set(c) for c in communities]
        assert cluster1 in cluster_sets
        assert cluster2 in cluster_sets

    def test_filters_communities_below_min_size(self):
        # 3-node clique + 2-node pair: only the 3-clique survives.
        a, b, c, d, e = (uuid.uuid4() for _ in range(5))
        g = nx.Graph()
        for u, v in [(a, b), (b, c), (a, c)]:
            g.add_edge(u, v, weight=10.0)
        g.add_edge(d, e, weight=10.0)
        communities = partition_communities(g)
        assert len(communities) == 1
        assert set(communities[0]) == {a, b, c}

    def test_empty_graph_returns_empty_list(self):
        assert partition_communities(nx.Graph()) == []

    def test_deterministic_with_same_seed(self):
        g, _, _ = self._make_two_clusters()
        c1 = partition_communities(g)
        c2 = partition_communities(g)
        assert [set(c) for c in c1] == [set(c) for c in c2]


from unittest.mock import AsyncMock as _AsyncMock

import json as _json

from src.services.graph_communities import generate_community_summary


class TestGenerateCommunitySummary:
    @pytest.mark.asyncio
    async def test_returns_label_and_summary_on_valid_response(self):
        llm = _AsyncMock()
        llm.generate.return_value = MagicMock(text=_json.dumps({
            "label": "Auth & Sessions",
            "summary": "This cluster owns session and JWT logic.",
        }))
        result = await generate_community_summary(
            llm_client=llm,
            person_descriptions=["@alice (assignee on 12 tickets)"],
            ticket_descriptions=["ENG-456: Add JWT refresh flow"],
        )
        assert result == {
            "label": "Auth & Sessions",
            "summary": "This cluster owns session and JWT logic.",
        }

    @pytest.mark.asyncio
    async def test_returns_none_label_summary_on_llm_failure(self):
        llm = _AsyncMock()
        llm.generate.side_effect = RuntimeError("upstream timeout")
        result = await generate_community_summary(
            llm_client=llm,
            person_descriptions=["@alice"],
            ticket_descriptions=["ENG-1"],
        )
        assert result == {"label": None, "summary": None}

    @pytest.mark.asyncio
    async def test_returns_none_label_summary_on_invalid_json(self):
        llm = _AsyncMock()
        llm.generate.return_value = MagicMock(text="not json at all")
        result = await generate_community_summary(
            llm_client=llm,
            person_descriptions=[],
            ticket_descriptions=[],
        )
        assert result == {"label": None, "summary": None}

    @pytest.mark.asyncio
    async def test_passes_temperature_to_llm(self):
        llm = _AsyncMock()
        llm.generate.return_value = MagicMock(text=_json.dumps({"label": "X", "summary": "Y"}))
        await generate_community_summary(
            llm_client=llm,
            person_descriptions=["@x"],
            ticket_descriptions=["E-1"],
        )
        kwargs = llm.generate.call_args.kwargs
        # The implementation may pass temperature as a named arg or in a config dict.
        # Check at least one of these is present and equals 0.3.
        flat = kwargs.get("temperature")
        nested = (kwargs.get("config") or {}).get("temperature") if "config" in kwargs else None
        assert flat == 0.3 or nested == 0.3


from src.services.graph_communities import (
    CommunityMeta,
    persist_communities,
)


class TestPersistCommunities:
    @pytest.fixture
    def session(self):
        sess = MagicMock()
        sess.execute = _AsyncMock()
        sess.add = MagicMock()
        sess.flush = _AsyncMock()
        sess.begin = MagicMock()
        # Make session.begin() usable as `async with session.begin()`
        sess.begin.return_value.__aenter__ = _AsyncMock(return_value=None)
        sess.begin.return_value.__aexit__ = _AsyncMock(return_value=None)
        return sess

    @pytest.mark.asyncio
    async def test_clears_previous_snapshot_then_writes_new(self, session):
        ws_id = uuid.uuid4()
        node_a = uuid.uuid4()
        node_b = uuid.uuid4()
        meta = {
            1: CommunityMeta(
                community_id=1,
                label="Auth",
                summary="...",
                member_count=2,
                person_count=1,
                ticket_count=1,
                top_member_names=["@alice", "ENG-1"],
            ),
        }
        assignments = {node_a: 1, node_b: 1}

        await persist_communities(session, ws_id, assignments, meta)

        # session.execute called for: DELETE communities, UPDATE clear nodes,
        # plus per-node update and per-community add.
        assert session.execute.await_count >= 2
        assert session.add.call_count == 1  # one GraphCommunity row

    @pytest.mark.asyncio
    async def test_empty_inputs_still_clear_previous(self, session):
        ws_id = uuid.uuid4()
        await persist_communities(session, ws_id, {}, {})
        # Even with empty assignments, we must still wipe the previous snapshot.
        assert session.execute.await_count >= 2
        assert session.add.call_count == 0
