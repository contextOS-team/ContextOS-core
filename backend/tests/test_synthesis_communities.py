"""Unit tests for community section rendering in synthesis prompt."""

from src.services.linking import CommunityContext
from src.services.synthesis import _format_team_context_section


def _ctx(community_id: int, label: str = "Auth", summary: str = "Owns auth.",
         reason: str = "assignee_primary") -> CommunityContext:
    return CommunityContext(
        community_id=community_id,
        label=label,
        summary=summary,
        person_count=2,
        ticket_count=3,
        member_count=5,
        top_member_names=["@alice", "@bob"],
        relevance_reason=reason,
    )


class TestTeamContextSection:
    def test_empty_communities_returns_empty_string(self):
        assert _format_team_context_section([]) == ""

    def test_single_community_renders_label_and_summary(self):
        out = _format_team_context_section([_ctx(1)])
        assert "Team & Feature Context" in out
        assert "Auth" in out
        assert "Owns auth." in out

    def test_multiple_communities_separated(self):
        out = _format_team_context_section([
            _ctx(1, label="Auth", summary="Owns auth."),
            _ctx(2, label="Billing", summary="Owns billing.", reason="retrieved_member"),
        ])
        assert "Auth" in out
        assert "Billing" in out
        assert out.count("members") >= 2

    def test_skips_communities_with_null_summary(self):
        # Defensive — _select_communities should already drop these, but
        # _format must also be safe.
        ctx = _ctx(1)
        ctx.summary = None
        assert _format_team_context_section([ctx]) == ""

    def test_relevance_reason_present_in_output(self):
        out = _format_team_context_section([_ctx(1, reason="assignee_primary")])
        assert "assignee_primary" in out or "primary" in out.lower()

    def test_top_members_rendered(self):
        out = _format_team_context_section([_ctx(1)])
        assert "@alice" in out
