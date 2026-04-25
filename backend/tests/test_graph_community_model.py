"""Unit tests for the GraphCommunity SQLModel."""

import uuid

from src.models.graph_community import GraphCommunity


class TestGraphCommunityModel:
    def test_can_instantiate_with_required_fields(self):
        ws_id = uuid.uuid4()
        gc = GraphCommunity(
            workspace_id=ws_id,
            community_id=1,
            label="Auth & Sessions",
            summary="Cluster owns session and JWT logic.",
            member_count=12,
            person_count=4,
            ticket_count=8,
            top_member_names=["@alice", "@bob"],
        )
        assert gc.workspace_id == ws_id
        assert gc.community_id == 1
        assert gc.label == "Auth & Sessions"
        assert gc.member_count == 12
        assert gc.top_member_names == ["@alice", "@bob"]

    def test_label_and_summary_optional(self):
        gc = GraphCommunity(
            workspace_id=uuid.uuid4(),
            community_id=2,
            label=None,
            summary=None,
            member_count=3,
            person_count=2,
            ticket_count=1,
            top_member_names=[],
        )
        assert gc.label is None
        assert gc.summary is None

    def test_table_name_is_graph_communities(self):
        assert GraphCommunity.__tablename__ == "graph_communities"
