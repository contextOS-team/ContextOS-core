"""End-to-end tests for the graph pipeline.

Covers ticket validation, provider detection, identifier parsing,
cluster deduplication, integration filtering, extractor registry,
fingerprint determinism, identity resolution, and lens response structure.

All tests use mocked database sessions (same pattern as conftest.py)
to verify pipeline logic without a real database.
"""

import hashlib
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.graph_extractor import (
    ExtractedEntity,
    MentionExtractor,
    TicketRefExtractor,
    run_extractors,
)
from src.services.graph_ops import compute_fingerprint

from tests.conftest import TEST_WORKSPACE_ID, TEST_USER_ID, TEST_EMAIL


# ============================================================
# Helpers (same style as test_graph_lens_api.py)
# ============================================================

WS_ID = uuid.UUID(TEST_WORKSPACE_ID)


def _mock_membership() -> MagicMock:
    mock = MagicMock()
    mock.scalar_one_or_none.return_value = TEST_WORKSPACE_ID
    return mock


def _mock_provider_query(providers: list[str]) -> MagicMock:
    integrations = []
    for p in providers:
        i = MagicMock()
        i.provider = p
        i.status = "connected"
        integrations.append(i)
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = integrations
    return mock


def _mock_ticket_validation(identifiers: list[str]) -> MagicMock:
    mock = MagicMock()
    mock.__iter__ = lambda self: iter([(i,) for i in identifiers])
    return mock


def _mock_fingerprint_nodes(ident_to_id: dict[str, uuid.UUID]) -> MagicMock:
    nodes = []
    for ident, node_id in ident_to_id.items():
        n = MagicMock()
        n.id = node_id
        n.fingerprint = compute_fingerprint("Ticket", ident)
        n.name = ident
        n.properties = {"identifier": ident}
        n.entity_type = "Ticket"
        nodes.append(n)
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = nodes
    return mock


def _make_traverse_row(
    node_id: uuid.UUID,
    entity_type: str,
    name: str,
    depth: int,
    properties: dict | None = None,
    edge_relationship_type: str | None = None,
) -> tuple:
    return (
        node_id,
        entity_type,
        name,
        properties or {},
        edge_relationship_type,
        depth,
        [str(node_id)],
    )


def _mock_traverse(rows: list[tuple]) -> MagicMock:
    mock = MagicMock()
    mock.fetchall.return_value = rows
    return mock


def _make_bulk_traverse_row(
    start_node_id: uuid.UUID,
    node_id: uuid.UUID,
    entity_type: str,
    name: str,
    depth: int,
    properties: dict | None = None,
    edge_relationship_type: str | None = None,
) -> tuple:
    """Row for the bulk unnest+LATERAL traverse query.

    src/routers/graph.py: the SELECT prefixes each traverse_graph row with
    ``t.start_id::text`` and the code does ``start_id = row[0]`` then
    ``traversal_row = row[1:]`` -- so mocked rows need the originating
    ticket node id (str) prepended to the 7-col traverse tuple.
    """
    return (
        str(start_node_id),
        node_id,
        entity_type,
        name,
        properties or {},
        edge_relationship_type,
        depth,
        [str(node_id)],
    )


def _stmt_signature(stmt) -> str:
    """(entity name : selected-column count) | "TEXT" for raw text()."""
    from tests.conftest import _stmt_entity_name

    name = _stmt_entity_name(stmt)
    if name is None:
        return "TEXT"
    try:
        ncols = len(stmt.column_descriptions)
    except Exception:
        ncols = 0
    return f"{name}:{ncols}"


def _signature_router(handlers: dict[str, list]):
    """session.execute side-effect routed by statement signature.

    Same rationale as test_graph_lens_api._LensRouter: the lens path now
    runs ONE bulk traverse query plus a trailing _inject_user_decisions()
    pass. Returns a plain async closure so AsyncMock auto-awaits it.
    """
    queues = {k: list(v) for k, v in handlers.items()}

    def _empty():
        m = MagicMock()
        m.scalars.return_value.all.return_value = []
        m.scalar_one_or_none.return_value = None
        m.scalar_one.return_value = 0
        m.fetchall.return_value = []
        m.__iter__ = lambda self: iter([])
        return m

    async def _execute(stmt, *args, **kwargs):
        queue = queues.get(_stmt_signature(stmt))
        if not queue:
            return _empty()
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return _execute


def _mock_source_type_lookup(
    id_to_info: dict[str, tuple[str | None, str, str]],
) -> MagicMock:
    mock = MagicMock()
    mock.__iter__ = lambda self: iter(
        [(uuid.UUID(nid), src, etype, name) for nid, (src, etype, name) in id_to_info.items()]
    )
    return mock


def _mock_edge(
    source_node_id: uuid.UUID,
    target_node_id: uuid.UUID,
    relationship_type: str = "mentions",
) -> MagicMock:
    edge = MagicMock()
    edge.source_node_id = source_node_id
    edge.target_node_id = target_node_id
    edge.relationship_type = relationship_type
    edge.properties = {}
    return edge


def _mock_edge_result(edges: list[MagicMock]) -> MagicMock:
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = edges
    return mock


def _mock_empty_result() -> MagicMock:
    mock = MagicMock()
    mock.scalars.return_value.all.return_value = []
    mock.__iter__ = lambda self: iter([])
    return mock


def _make_graph_node(
    node_id: uuid.UUID,
    entity_type: str,
    name: str,
    source_type: str | None = None,
    properties: dict | None = None,
) -> MagicMock:
    """Create a mock GraphNode."""
    n = MagicMock()
    n.id = node_id
    n.entity_type = entity_type
    n.name = name
    n.source_type = source_type
    n.properties = properties or {}
    n.deleted_at = None
    n.fingerprint = compute_fingerprint(entity_type, properties.get("identifier", name) if properties else name)
    return n


# Stable test IDs
TICKET_A = uuid.uuid4()
TICKET_B = uuid.uuid4()
TICKET_FAKE = uuid.uuid4()
PERSON_NODE = uuid.uuid4()
NOTION_NODE = uuid.uuid4()
SLACK_NODE = uuid.uuid4()


# ============================================================
# 1. test_workspace_graph_filters_phantom_tickets
# ============================================================


def test_workspace_graph_filters_phantom_tickets(
    client,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Phantom ticket nodes (e.g. 'SHA-256' from text extraction) are filtered
    when they don't exist in the linear_tickets table."""

    real_ticket = _make_graph_node(TICKET_A, "Ticket", "CON-50", "linear_ticket", {"identifier": "CON-50"})
    fake_ticket = _make_graph_node(TICKET_FAKE, "Ticket", "SHA-256", None, {"identifier": "SHA-256"})
    person = _make_graph_node(PERSON_NODE, "Person", "Alice", None, {})

    mock_session.execute.side_effect = [
        _mock_membership(),  # auth: workspace membership lookup
        # _get_connected_providers
        _mock_provider_query(["linear"]),
        # Step 1: ALL workspace nodes
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[real_ticket, fake_ticket, person])))),
        # _validate_ticket_identifiers for Linear (only CON-50 is real)
        _mock_ticket_validation(["CON-50"]),
        # Step 2: ALL workspace edges
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
            _mock_edge(TICKET_A, PERSON_NODE, "mentions"),
            _mock_edge(TICKET_FAKE, PERSON_NODE, "references"),
        ])))),
    ]

    response = client.get("/api/graph/", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    node_names = {n["name"] for n in data["nodes"]}
    # Real ticket should be present
    assert "CON-50" in node_names
    # Phantom ticket should be filtered out
    assert "SHA-256" not in node_names


# ============================================================
# 2. test_workspace_graph_validates_jira_tickets
# ============================================================


def test_workspace_graph_validates_jira_tickets(
    client,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """When only Jira is connected, ticket validation should query jira_issues
    (not linear_tickets) and return real Jira tickets."""

    jira_ticket = _make_graph_node(TICKET_A, "Ticket", "PROJ-42", "jira_issue", {"identifier": "PROJ-42"})
    fake_ticket = _make_graph_node(TICKET_FAKE, "Ticket", "FAKE-99", None, {"identifier": "FAKE-99"})

    mock_session.execute.side_effect = [
        _mock_membership(),  # auth: workspace membership lookup
        # _get_connected_providers -> only Jira
        _mock_provider_query(["jira"]),
        # Step 1: ALL workspace nodes
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[jira_ticket, fake_ticket])))),
        # _validate_ticket_identifiers for Jira (only PROJ-42 is real)
        _mock_ticket_validation(["PROJ-42"]),
        # Step 2: ALL workspace edges
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
    ]

    response = client.get("/api/graph/", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    node_names = {n["name"] for n in data["nodes"]}
    # Jira ticket should survive validation
    assert "PROJ-42" in node_names
    # Fake ticket should be filtered even with Jira provider
    assert "FAKE-99" not in node_names


# ============================================================
# 3. test_ticket_identifier_parsing
# ============================================================


class TestTicketIdentifierParsing:
    """Test the 'CON-50: Some title' -> 'CON-50' parsing used in graph.py."""

    def test_colon_separated_title(self):
        """'CON-50: Some title' should parse to 'CON-50'."""
        name = "CON-50: Fix login bug"
        parsed = name.split(":")[0].strip()
        assert parsed == "CON-50"

    def test_plain_identifier(self):
        """'CON-50' with no colon should parse to 'CON-50'."""
        name = "CON-50"
        parsed = name.split(":")[0].strip()
        assert parsed == "CON-50"

    def test_identifier_with_spaces(self):
        """' CON-50 : title' should strip and parse correctly."""
        name = " CON-50 : Something"
        parsed = name.split(":")[0].strip()
        assert parsed == "CON-50"

    def test_empty_name(self):
        """Empty name should parse to empty string."""
        name = ""
        parsed = name.split(":")[0].strip()
        assert parsed == ""

    def test_name_with_multiple_colons(self):
        """'CON-50: fix: edge case' should parse to 'CON-50'."""
        name = "CON-50: fix: edge case"
        parsed = name.split(":")[0].strip()
        assert parsed == "CON-50"

    def test_extractor_identifier_consistency(self):
        """TicketRefExtractor output should match the parsing format."""
        extractor = TicketRefExtractor()
        entities = extractor.extract("See CON-50 for details", "slack_message")
        assert len(entities) == 1
        # The extractor sets name = identifier (no title)
        name = entities[0].name
        parsed = name.split(":")[0].strip()
        assert parsed == "CON-50"
        assert parsed == entities[0].external_id


# ============================================================
# 4. test_build_ticket_clusters_deduplicates_nodes
# ============================================================


def test_build_ticket_clusters_deduplicates_nodes(
    client,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """When two ticket clusters share a Person node, the shared node should
    appear only once in all_nodes (deduplicated)."""

    # Signature-routed (not order-based): _build_ticket_clusters now does
    # ONE bulk traverse_graph query (start_ids=[CON-1 node, CON-2 node])
    # and the my-work endpoint appends a _inject_user_decisions() pass --
    # the router serves an inert empty result for that (unregistered)
    # IdentityMapping query so it can't raise.
    mock_session.execute.side_effect = _signature_router({
        "WorkspaceMember:1": [_mock_membership()],
        "WorkspaceIntegration:1": [_mock_provider_query(["linear"])],
        "LinearTicket:1": [_mock_ticket_validation(["CON-1", "CON-2"])],
        "GraphNode:1": [_mock_fingerprint_nodes({"CON-1": TICKET_A, "CON-2": TICKET_B})],
        "TEXT": [_mock_traverse([
            _make_bulk_traverse_row(TICKET_A, TICKET_A, "Ticket", "CON-1", 0),
            _make_bulk_traverse_row(TICKET_A, PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
            _make_bulk_traverse_row(TICKET_B, TICKET_B, "Ticket", "CON-2", 0),
            _make_bulk_traverse_row(TICKET_B, PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
        ])],
        "GraphNode:4": [_mock_source_type_lookup({
            str(TICKET_A): ("linear_ticket", "Ticket", "CON-1"),
            str(TICKET_B): ("linear_ticket", "Ticket", "CON-2"),
            str(PERSON_NODE): (None, "Person", "Alice"),
        })],
        "GraphEdge:1": [
            _mock_edge_result([_mock_edge(TICKET_A, PERSON_NODE, "mentions")]),
            _mock_edge_result([_mock_edge(TICKET_B, PERSON_NODE, "mentions")]),
        ],
    })

    # LinearGraphQLClient + get_valid_access_token are bound into
    # src.routers.graph at import time -> patch there.
    with patch("src.routers.graph.get_valid_access_token", new_callable=AsyncMock, return_value="t"), \
         patch("src.routers.graph.LinearGraphQLClient") as mock_cls:
        mock_linear = AsyncMock()
        mock_linear.query.return_value = {
            "data": {"viewer": {"assignedIssues": {"nodes": [
                {"identifier": "CON-1"},
                {"identifier": "CON-2"},
            ]}}}
        }
        mock_linear.close = AsyncMock()
        mock_cls.return_value = mock_linear

        response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()

    # Two clusters, each with their ticket + shared person
    assert len(data["clusters"]) == 2
    assert len(data["clusters"][0]["nodes"]) == 2
    assert len(data["clusters"][1]["nodes"]) == 2

    # all_nodes should have 3 unique nodes: TICKET_A, TICKET_B, PERSON
    all_node_ids = [n["id"] for n in data["all_nodes"]]
    assert len(all_node_ids) == len(set(all_node_ids)), "all_nodes should be deduplicated"
    assert len(all_node_ids) == 3


# ============================================================
# 5. test_provider_detection_prefers_linear
# ============================================================


class TestProviderDetection:
    """Tests for _detect_provider logic."""

    def test_linear_only(self):
        from src.routers.graph import _detect_provider
        assert _detect_provider({"linear"}) == "linear"

    def test_jira_only(self):
        from src.routers.graph import _detect_provider
        assert _detect_provider({"jira"}) == "jira"

    def test_both_prefers_linear(self):
        """When both Linear and Jira are connected, Linear wins."""
        from src.routers.graph import _detect_provider
        result = _detect_provider({"linear", "jira"})
        assert result == "linear", "Linear should be preferred over Jira when both are connected"

    def test_neither(self):
        from src.routers.graph import _detect_provider
        assert _detect_provider(set()) is None

    def test_unrelated_providers_ignored(self):
        from src.routers.graph import _detect_provider
        assert _detect_provider({"slack", "github", "notion"}) is None

    def test_jira_with_unrelated(self):
        from src.routers.graph import _detect_provider
        assert _detect_provider({"jira", "slack", "github"}) == "jira"


# ============================================================
# 6. test_disconnected_integration_nodes_filtered
# ============================================================


def test_disconnected_integration_nodes_filtered(
    client,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """Nodes from a disconnected integration (Notion) should be filtered
    from the workspace graph when Notion is not connected."""

    linear_ticket = _make_graph_node(
        TICKET_A, "Ticket", "CON-1", "linear_ticket", {"identifier": "CON-1"}
    )
    notion_page = _make_graph_node(
        NOTION_NODE, "NotionPage", "Design Doc", "notion_page", {}
    )

    mock_session.execute.side_effect = [
        _mock_membership(),  # auth: workspace membership lookup
        # _get_connected_providers -> Linear only, no Notion
        _mock_provider_query(["linear"]),
        # Step 1: ALL workspace nodes
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(
            return_value=[linear_ticket, notion_page]
        )))),
        # _validate_ticket_identifiers for Linear
        _mock_ticket_validation(["CON-1"]),
        # Step 2: ALL workspace edges
        MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(
            return_value=[_mock_edge(TICKET_A, NOTION_NODE, "references")]
        )))),
    ]

    response = client.get("/api/graph/", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()
    node_types = {n["entity_type"] for n in data["nodes"]}
    # Notion page should be filtered out
    assert "NotionPage" not in node_types
    # Linear ticket should remain
    assert "Ticket" in node_types


# ============================================================
# 7. test_graph_extractor_skips_person_entities
# ============================================================


class TestExtractorSkipsPerson:
    """Verify that MentionExtractor is not registered by default,
    so Person entities are NOT created during extraction."""

    def test_mention_extractor_not_registered(self):
        """MentionExtractor should NOT be in the global registry."""
        from src.services import graph_extractor
        extractor_types = [type(e).__name__ for e in graph_extractor._EXTRACTORS]
        assert "MentionExtractor" not in extractor_types, (
            "MentionExtractor should be unregistered -- Person entities "
            "should only come from roster-based identity resolution"
        )

    def test_run_extractors_no_person_entities(self):
        """run_extractors on content with @mentions should NOT produce Person entities."""
        entities = run_extractors(
            "Hey <@U12345ABC> please check @alice on ENG-123", "slack_message"
        )
        person_entities = [e for e in entities if e.entity_type == "Person"]
        assert len(person_entities) == 0, (
            "Person entities should not be produced by the default extractor registry"
        )

    def test_mention_extractor_still_works_in_isolation(self):
        """MentionExtractor itself works correctly -- it's just not registered."""
        extractor = MentionExtractor()
        entities = extractor.extract("<@U12345ABC> and @alice", "slack_message")
        assert len(entities) == 2
        assert all(e.entity_type == "Person" for e in entities)


# ============================================================
# 8. test_fingerprint_determinism
# ============================================================


class TestFingerprintDeterminism:
    """Verify compute_fingerprint is deterministic and collision-resistant."""

    def test_same_inputs_same_output(self):
        fp1 = compute_fingerprint("Ticket", "CON-50")
        fp2 = compute_fingerprint("Ticket", "CON-50")
        assert fp1 == fp2

    def test_different_inputs_different_output(self):
        fp1 = compute_fingerprint("Ticket", "CON-50")
        fp2 = compute_fingerprint("Ticket", "CON-51")
        assert fp1 != fp2

    def test_different_types_different_output(self):
        fp1 = compute_fingerprint("Ticket", "CON-50")
        fp2 = compute_fingerprint("Person", "CON-50")
        assert fp1 != fp2

    def test_matches_expected_sha256(self):
        expected = hashlib.sha256("Ticket:CON-50".encode()).hexdigest()
        actual = compute_fingerprint("Ticket", "CON-50")
        assert actual == expected

    def test_format_is_64_char_hex(self):
        fp = compute_fingerprint("Ticket", "CON-50")
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)

    def test_canonical_person_fingerprint(self):
        """Canonical person fingerprints use 'Person:canonical:{uuid}' format."""
        cid = uuid.uuid4()
        fp = compute_fingerprint("Person", f"canonical:{cid}")
        expected = hashlib.sha256(f"Person:canonical:{cid}".encode()).hexdigest()
        assert fp == expected

    def test_stable_across_calls(self):
        """100 calls with the same inputs all produce the same result."""
        reference = compute_fingerprint("Ticket", "ENG-999")
        for _ in range(100):
            assert compute_fingerprint("Ticket", "ENG-999") == reference


# ============================================================
# 9. test_identity_resolution_bulk_efficiency
# ============================================================


class TestIdentityResolutionBulk:
    """Tests for resolve_by_email: bulk grouping and canonical person creation."""

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_same_email_creates_one_canonical(self, mock_session):
        """Two mappings with the same email resolve to one canonical Person."""
        from src.models.identity_mapping import IdentityMapping

        workspace_id = uuid.uuid4()

        mapping1 = MagicMock(spec=IdentityMapping)
        mapping1.id = uuid.uuid4()
        mapping1.workspace_id = workspace_id
        mapping1.email = "alice@example.com"
        mapping1.platform = "slack"
        mapping1.platform_user_id = "U12345"
        mapping1.display_name = "Alice (Slack)"
        mapping1.canonical_person_id = None

        mapping2 = MagicMock(spec=IdentityMapping)
        mapping2.id = uuid.uuid4()
        mapping2.workspace_id = workspace_id
        mapping2.email = "alice@example.com"
        mapping2.platform = "linear"
        mapping2.platform_user_id = "linear-alice-id"
        mapping2.display_name = "Alice (Linear)"
        mapping2.canonical_person_id = None

        # Mock the bulk query to return both mappings
        bulk_result = MagicMock()
        bulk_result.scalars.return_value.all.return_value = [mapping1, mapping2]
        mock_session.execute.return_value = bulk_result

        with patch("src.services.identity_resolution.create_canonical_person", new_callable=AsyncMock) as mock_create, \
             patch("src.services.identity_resolution._create_same_as_edge", new_callable=AsyncMock) as mock_edge:
            canonical_node_id = uuid.uuid4()
            mock_create.return_value = canonical_node_id

            from src.services.identity_resolution import resolve_by_email
            count = await resolve_by_email(mock_session, workspace_id)

        # Should create exactly 1 canonical person (both mappings share email)
        assert count == 1
        mock_create.assert_called_once()
        # Both mappings should get the same canonical_person_id
        assert mapping1.canonical_person_id == canonical_node_id
        assert mapping2.canonical_person_id == canonical_node_id
        # same_as edges created for both mappings
        assert mock_edge.call_count == 2

    @pytest.mark.asyncio
    async def test_different_emails_create_separate_canonicals(self, mock_session):
        """Two mappings with different emails create two canonical Persons."""
        from src.models.identity_mapping import IdentityMapping

        workspace_id = uuid.uuid4()

        mapping1 = MagicMock(spec=IdentityMapping)
        mapping1.id = uuid.uuid4()
        mapping1.workspace_id = workspace_id
        mapping1.email = "alice@example.com"
        mapping1.platform = "slack"
        mapping1.platform_user_id = "U12345"
        mapping1.display_name = "Alice"
        mapping1.canonical_person_id = None

        mapping2 = MagicMock(spec=IdentityMapping)
        mapping2.id = uuid.uuid4()
        mapping2.workspace_id = workspace_id
        mapping2.email = "bob@example.com"
        mapping2.platform = "slack"
        mapping2.platform_user_id = "U99999"
        mapping2.display_name = "Bob"
        mapping2.canonical_person_id = None

        bulk_result = MagicMock()
        bulk_result.scalars.return_value.all.return_value = [mapping1, mapping2]
        mock_session.execute.return_value = bulk_result

        with patch("src.services.identity_resolution.create_canonical_person", new_callable=AsyncMock) as mock_create, \
             patch("src.services.identity_resolution._create_same_as_edge", new_callable=AsyncMock):
            mock_create.side_effect = [uuid.uuid4(), uuid.uuid4()]

            from src.services.identity_resolution import resolve_by_email
            count = await resolve_by_email(mock_session, workspace_id)

        assert count == 2
        assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_existing_canonical_is_reused(self, mock_session):
        """If one mapping already has a canonical_person_id, others in the
        same email group reuse it (no new canonical created)."""
        from src.models.identity_mapping import IdentityMapping

        workspace_id = uuid.uuid4()
        existing_canonical_id = uuid.uuid4()

        mapping1 = MagicMock(spec=IdentityMapping)
        mapping1.id = uuid.uuid4()
        mapping1.workspace_id = workspace_id
        mapping1.email = "alice@example.com"
        mapping1.platform = "slack"
        mapping1.platform_user_id = "U12345"
        mapping1.display_name = "Alice (Slack)"
        mapping1.canonical_person_id = existing_canonical_id

        mapping2 = MagicMock(spec=IdentityMapping)
        mapping2.id = uuid.uuid4()
        mapping2.workspace_id = workspace_id
        mapping2.email = "alice@example.com"
        mapping2.platform = "github"
        mapping2.platform_user_id = "alice-gh"
        mapping2.display_name = "Alice (GitHub)"
        mapping2.canonical_person_id = None

        bulk_result = MagicMock()
        bulk_result.scalars.return_value.all.return_value = [mapping1, mapping2]
        mock_session.execute.return_value = bulk_result

        with patch("src.services.identity_resolution.create_canonical_person", new_callable=AsyncMock) as mock_create, \
             patch("src.services.identity_resolution._create_same_as_edge", new_callable=AsyncMock):

            from src.services.identity_resolution import resolve_by_email
            count = await resolve_by_email(mock_session, workspace_id)

        # No new canonical created (reused existing)
        assert count == 0
        mock_create.assert_not_called()
        # mapping2 should get the existing canonical_person_id
        assert mapping2.canonical_person_id == existing_canonical_id

    @pytest.mark.asyncio
    async def test_empty_mappings_returns_zero(self, mock_session):
        """No mappings with email returns 0."""
        bulk_result = MagicMock()
        bulk_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = bulk_result

        from src.services.identity_resolution import resolve_by_email
        count = await resolve_by_email(mock_session, uuid.uuid4())

        assert count == 0


# ============================================================
# 10. test_lens_response_structure
# ============================================================


def test_lens_response_structure(
    client,
    valid_auth_header: dict,
    mock_session: AsyncMock,
) -> None:
    """LensGraphResponse has correct structure with deduplicated all_nodes/all_edges."""

    mock_session.execute.side_effect = [
        _mock_membership(),
        _mock_provider_query(["linear"]),
        # _build_ticket_clusters:
        _mock_ticket_validation(["CON-1"]),
        _mock_fingerprint_nodes({"CON-1": TICKET_A}),
        _mock_traverse([
            _make_traverse_row(TICKET_A, "Ticket", "CON-1", 0),
            _make_traverse_row(PERSON_NODE, "Person", "Alice", 1, edge_relationship_type="mentions"),
        ]),
        _mock_source_type_lookup({
            str(TICKET_A): ("linear_ticket", "Ticket", "CON-1"),
            str(PERSON_NODE): (None, "Person", "Alice"),
        }),
        _mock_edge_result([
            _mock_edge(TICKET_A, PERSON_NODE, "mentions"),
        ]),
    ]

    with patch("src.services.linear_oauth.get_valid_access_token", new_callable=AsyncMock, return_value="t"), \
         patch("src.routers.graph.get_valid_access_token", new_callable=AsyncMock, return_value="t"), \
         patch("src.services.linear_graphql.LinearGraphQLClient") as _, \
         patch("src.routers.graph.LinearGraphQLClient") as mock_cls:
        mock_linear = AsyncMock()
        mock_linear.query.return_value = {
            "data": {"viewer": {"assignedIssues": {"nodes": [{"identifier": "CON-1"}]}}}
        }
        mock_linear.close = AsyncMock()
        mock_cls.return_value = mock_linear

        response = client.get("/api/graph/lens/my-work", headers=valid_auth_header)

    assert response.status_code == 200
    data = response.json()

    # Required top-level fields
    assert data["lens"] == "my_work"
    assert isinstance(data["clusters"], list)
    assert isinstance(data["all_nodes"], list)
    assert isinstance(data["all_edges"], list)
    assert isinstance(data["node_count"], int)
    assert isinstance(data["edge_count"], int)
    assert isinstance(data["truncated"], bool)
    # Optional sprint fields present but None for my_work
    assert "sprint_name" in data
    assert "sprint_progress" in data

    # node_count / edge_count match actual lists
    assert data["node_count"] == len(data["all_nodes"])
    assert data["edge_count"] == len(data["all_edges"])

    # all_nodes are deduplicated
    all_node_ids = [n["id"] for n in data["all_nodes"]]
    assert len(all_node_ids) == len(set(all_node_ids))

    # all_edges are deduplicated
    all_edge_keys = [(e["source"], e["target"], e["relationship_type"]) for e in data["all_edges"]]
    assert len(all_edge_keys) == len(set(all_edge_keys))

    # Each cluster has required fields
    for cluster in data["clusters"]:
        assert "ticket_identifier" in cluster
        assert "ticket_node_id" in cluster
        assert "ticket_name" in cluster
        assert isinstance(cluster["nodes"], list)
        assert isinstance(cluster["edges"], list)

    # Each node has required fields
    for node in data["all_nodes"]:
        assert "id" in node
        assert "entity_type" in node
        assert "name" in node
        assert "depth" in node
        assert "properties" in node

    # Each edge has required fields
    for edge in data["all_edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "relationship_type" in edge
        assert "properties" in edge


# ============================================================
# Additional: _validate_ticket_identifiers unit tests
# ============================================================


class TestValidateTicketIdentifiers:
    """Direct tests for the _validate_ticket_identifiers helper."""

    @pytest.mark.asyncio
    async def test_empty_identifiers_returns_empty(self):
        from src.routers.graph import _validate_ticket_identifiers
        session = AsyncMock()
        result = await _validate_ticket_identifiers(session, uuid.uuid4(), set(), "linear")
        assert result == set()
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_linear_provider_queries_linear_tickets(self):
        from src.routers.graph import _validate_ticket_identifiers
        session = AsyncMock()
        session.execute.return_value = _mock_ticket_validation(["CON-1"])
        result = await _validate_ticket_identifiers(session, uuid.uuid4(), {"CON-1", "FAKE-1"}, "linear")
        assert result == {"CON-1"}

    @pytest.mark.asyncio
    async def test_jira_provider_queries_jira_issues(self):
        from src.routers.graph import _validate_ticket_identifiers
        session = AsyncMock()
        session.execute.return_value = _mock_ticket_validation(["PROJ-1"])
        result = await _validate_ticket_identifiers(session, uuid.uuid4(), {"PROJ-1", "FAKE-1"}, "jira")
        assert result == {"PROJ-1"}

    @pytest.mark.asyncio
    async def test_none_provider_defaults_to_linear(self):
        """When provider is None, the function defaults to querying Linear."""
        from src.routers.graph import _validate_ticket_identifiers
        session = AsyncMock()
        session.execute.return_value = _mock_ticket_validation([])
        await _validate_ticket_identifiers(session, uuid.uuid4(), {"X-1"}, None)
        # Should have executed (defaults to Linear path)
        session.execute.assert_called_once()


# ============================================================
# Additional: _allowed_source_types tests
# ============================================================


class TestAllowedSourceTypes:
    """Tests for the _allowed_source_types helper."""

    def test_linear_provider(self):
        from src.routers.graph import _allowed_source_types
        result = _allowed_source_types({"linear"})
        assert "linear_ticket" in result
        assert "linear_comment" in result
        assert "jira_issue" not in result

    def test_multiple_providers(self):
        from src.routers.graph import _allowed_source_types
        result = _allowed_source_types({"linear", "slack", "github"})
        assert "linear_ticket" in result
        assert "slack_message" in result
        assert "github_pr" in result
        assert "notion_page" not in result

    def test_empty_providers(self):
        from src.routers.graph import _allowed_source_types
        result = _allowed_source_types(set())
        assert result == set()

    def test_unknown_provider(self):
        from src.routers.graph import _allowed_source_types
        result = _allowed_source_types({"unknown_provider"})
        assert result == set()
