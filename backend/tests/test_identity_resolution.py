"""Unit tests for identity resolution: email-based deterministic matching.

Tests canonical Person node creation, email-based grouping, mapping lookup,
and inline resolution during graph extraction.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.graph_extractor import ExtractedEntity


# ============================================================
# Test: resolve_by_email groups same-email mappings
# ============================================================


class TestResolveByEmail:
    """Tests for resolve_by_email() email-based deterministic matching."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_same_email_grouped_under_one_canonical(self, mock_session):
        """Two mappings with the same email resolve to one canonical_person_id
        and create a single canonical Person graph node."""
        from src.models.identity_mapping import IdentityMapping

        workspace_id = uuid.uuid4()

        # Two mappings with same email, no canonical yet
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
        mapping2.platform = "github"
        mapping2.platform_user_id = "alice-gh"
        mapping2.display_name = "Alice (GitHub)"
        mapping2.canonical_person_id = None

        # Mock session.execute for the group-by query: returns one group
        mock_group_result = MagicMock()
        mock_group_result.all.return_value = [("alice@example.com",)]

        # Mock for fetching mappings by email
        mock_mappings_result = MagicMock()
        mock_mappings_result.scalars.return_value.all.return_value = [mapping1, mapping2]

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_mappings_result]
        )

        canonical_node_id = uuid.uuid4()

        with patch(
            "src.services.identity_resolution.upsert_node",
            new_callable=AsyncMock,
            return_value=canonical_node_id,
        ) as mock_upsert_node, patch(
            "src.services.identity_resolution.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid.uuid4(),
        ) as mock_upsert_edge, patch(
            "src.services.identity_resolution._create_same_as_edge",
            new_callable=AsyncMock,
        ):
            from src.services.identity_resolution import resolve_by_email

            count = await resolve_by_email(mock_session, workspace_id)

        # One canonical person created
        assert count == 1

        # upsert_node called once for the canonical Person
        mock_upsert_node.assert_called_once()
        call_kwargs = mock_upsert_node.call_args.kwargs
        assert call_kwargs["entity_type"] == "Person"
        assert call_kwargs["properties"]["canonical"] is True

        # Both mappings should have canonical_person_id set
        assert mapping1.canonical_person_id is not None
        assert mapping2.canonical_person_id is not None
        assert mapping1.canonical_person_id == mapping2.canonical_person_id

    @pytest.mark.asyncio
    async def test_different_emails_create_separate_canonicals(self, mock_session):
        """Two different emails create two separate canonical Person nodes."""
        from src.models.identity_mapping import IdentityMapping

        workspace_id = uuid.uuid4()

        mapping_alice = MagicMock(spec=IdentityMapping)
        mapping_alice.id = uuid.uuid4()
        mapping_alice.workspace_id = workspace_id
        mapping_alice.email = "alice@example.com"
        mapping_alice.platform = "slack"
        mapping_alice.platform_user_id = "U12345"
        mapping_alice.display_name = "Alice"
        mapping_alice.canonical_person_id = None

        mapping_bob = MagicMock(spec=IdentityMapping)
        mapping_bob.id = uuid.uuid4()
        mapping_bob.workspace_id = workspace_id
        mapping_bob.email = "bob@example.com"
        mapping_bob.platform = "slack"
        mapping_bob.platform_user_id = "U67890"
        mapping_bob.display_name = "Bob"
        mapping_bob.canonical_person_id = None

        # Two email groups
        mock_group_result = MagicMock()
        mock_group_result.all.return_value = [
            ("alice@example.com",),
            ("bob@example.com",),
        ]

        mock_alice_result = MagicMock()
        mock_alice_result.scalars.return_value.all.return_value = [mapping_alice]

        mock_bob_result = MagicMock()
        mock_bob_result.scalars.return_value.all.return_value = [mapping_bob]

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_alice_result, mock_bob_result]
        )

        node_ids = [uuid.uuid4(), uuid.uuid4()]
        call_count = 0

        async def fake_upsert_node(**kwargs):
            nonlocal call_count
            nid = node_ids[call_count]
            call_count += 1
            return nid

        with patch(
            "src.services.identity_resolution.upsert_node",
            side_effect=fake_upsert_node,
        ), patch(
            "src.services.identity_resolution.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid.uuid4(),
        ), patch(
            "src.services.identity_resolution._create_same_as_edge",
            new_callable=AsyncMock,
        ):
            from src.services.identity_resolution import resolve_by_email

            count = await resolve_by_email(mock_session, workspace_id)

        assert count == 2
        # Each mapping got a different canonical_person_id
        assert mapping_alice.canonical_person_id != mapping_bob.canonical_person_id

    @pytest.mark.asyncio
    async def test_idempotent_no_duplicate_canonicals(self, mock_session):
        """Re-running resolve_by_email does not create duplicate canonical nodes
        when mappings already have canonical_person_id set."""
        from src.models.identity_mapping import IdentityMapping

        workspace_id = uuid.uuid4()
        existing_canonical_id = uuid.uuid4()

        mapping1 = MagicMock(spec=IdentityMapping)
        mapping1.id = uuid.uuid4()
        mapping1.workspace_id = workspace_id
        mapping1.email = "alice@example.com"
        mapping1.platform = "slack"
        mapping1.platform_user_id = "U12345"
        mapping1.display_name = "Alice"
        mapping1.canonical_person_id = existing_canonical_id

        # Group query returns the email
        mock_group_result = MagicMock()
        mock_group_result.all.return_value = [("alice@example.com",)]

        # Fetch mappings -- already has canonical
        mock_mappings_result = MagicMock()
        mock_mappings_result.scalars.return_value.all.return_value = [mapping1]

        mock_session.execute = AsyncMock(
            side_effect=[mock_group_result, mock_mappings_result]
        )

        with patch(
            "src.services.identity_resolution.upsert_node",
            new_callable=AsyncMock,
        ) as mock_upsert_node, patch(
            "src.services.identity_resolution.upsert_edge",
            new_callable=AsyncMock,
        ), patch(
            "src.services.identity_resolution._create_same_as_edge",
            new_callable=AsyncMock,
        ):
            from src.services.identity_resolution import resolve_by_email

            count = await resolve_by_email(mock_session, workspace_id)

        # No new canonical created
        assert count == 0
        mock_upsert_node.assert_not_called()


# ============================================================
# Test: create_canonical_person
# ============================================================


class TestCreateCanonicalPerson:
    """Tests for create_canonical_person()."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_creates_person_node_with_canonical_properties(self, mock_session):
        """create_canonical_person creates a Person node with
        fingerprint=hash('Person:canonical:{UUID}') and properties.canonical=True."""
        workspace_id = uuid.uuid4()
        canonical_id = uuid.uuid4()
        node_id = uuid.uuid4()

        with patch(
            "src.services.identity_resolution.upsert_node",
            new_callable=AsyncMock,
            return_value=node_id,
        ) as mock_upsert:
            from src.services.identity_resolution import create_canonical_person

            result = await create_canonical_person(
                mock_session, workspace_id, canonical_id, "Alice"
            )

        assert result == node_id
        mock_upsert.assert_called_once()
        kwargs = mock_upsert.call_args.kwargs
        assert kwargs["entity_type"] == "Person"
        assert kwargs["external_id"] == f"canonical:{canonical_id}"
        assert kwargs["name"] == "Alice"
        assert kwargs["properties"]["canonical"] is True
        assert kwargs["properties"]["canonical_person_id"] == str(canonical_id)


# ============================================================
# Test: lookup_mapping
# ============================================================


class TestLookupMapping:
    """Tests for lookup_mapping()."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_mapping_when_exists(self, mock_session):
        """lookup_mapping returns the correct mapping for a given
        (workspace_id, platform, platform_user_id)."""
        from src.models.identity_mapping import IdentityMapping

        workspace_id = uuid.uuid4()
        expected_mapping = MagicMock(spec=IdentityMapping)
        expected_mapping.platform = "slack"
        expected_mapping.platform_user_id = "U12345"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = expected_mapping
        mock_session.execute = AsyncMock(return_value=mock_result)

        from src.services.identity_resolution import lookup_mapping

        result = await lookup_mapping(mock_session, workspace_id, "slack", "U12345")

        assert result is expected_mapping
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_no_mapping(self, mock_session):
        """lookup_mapping returns None when no mapping exists."""
        workspace_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        from src.services.identity_resolution import lookup_mapping

        result = await lookup_mapping(mock_session, workspace_id, "slack", "UXXXXX")

        assert result is None


# ============================================================
# Test: resolve_identity_inline (inline hook)
# ============================================================


class TestResolveIdentityInline:
    """Tests for resolve_identity_inline() called during graph extraction."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_creates_same_as_edge_when_mapping_exists(self, mock_session):
        """When a Person entity is extracted and a matching identity_mapping
        exists with a canonical_person_id, a same_as edge is created."""
        workspace_id = uuid.uuid4()
        entity_node_id = uuid.uuid4()
        canonical_node_id = uuid.uuid4()

        entity = ExtractedEntity(
            entity_type="Person",
            external_id="slack:U12345",
            name="Slack user U12345",
            properties={"platform": "slack", "platform_user_id": "U12345"},
            relationship_type="mentions",
        )

        # Mock lookup_mapping to return a mapping with canonical
        mock_mapping = MagicMock()
        mock_mapping.canonical_person_id = canonical_node_id

        with patch(
            "src.services.identity_resolution.lookup_mapping",
            new_callable=AsyncMock,
            return_value=mock_mapping,
        ), patch(
            "src.services.identity_resolution.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid.uuid4(),
        ) as mock_upsert_edge:
            from src.services.identity_resolution import resolve_identity_inline

            await resolve_identity_inline(
                mock_session, workspace_id, entity, entity_node_id
            )

        mock_upsert_edge.assert_called_once()
        edge_kwargs = mock_upsert_edge.call_args.kwargs
        assert edge_kwargs["source_node_id"] == entity_node_id
        assert edge_kwargs["target_node_id"] == canonical_node_id
        assert edge_kwargs["relationship_type"] == "same_as"

    @pytest.mark.asyncio
    async def test_no_edge_when_no_mapping_exists(self, mock_session):
        """When no identity_mapping exists, no same_as edge is created."""
        workspace_id = uuid.uuid4()
        entity_node_id = uuid.uuid4()

        entity = ExtractedEntity(
            entity_type="Person",
            external_id="slack:UXXXXX",
            name="Slack user UXXXXX",
            properties={"platform": "slack", "platform_user_id": "UXXXXX"},
            relationship_type="mentions",
        )

        with patch(
            "src.services.identity_resolution.lookup_mapping",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "src.services.identity_resolution.upsert_edge",
            new_callable=AsyncMock,
        ) as mock_upsert_edge:
            from src.services.identity_resolution import resolve_identity_inline

            await resolve_identity_inline(
                mock_session, workspace_id, entity, entity_node_id
            )

        mock_upsert_edge.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_person_entity_returns_immediately(self, mock_session):
        """When entity is not a Person, resolve_identity_inline returns immediately."""
        workspace_id = uuid.uuid4()
        entity_node_id = uuid.uuid4()

        entity = ExtractedEntity(
            entity_type="Ticket",
            external_id="ENG-123",
            name="ENG-123",
            properties={"identifier": "ENG-123"},
            relationship_type="references",
        )

        with patch(
            "src.services.identity_resolution.lookup_mapping",
            new_callable=AsyncMock,
        ) as mock_lookup:
            from src.services.identity_resolution import resolve_identity_inline

            await resolve_identity_inline(
                mock_session, workspace_id, entity, entity_node_id
            )

        # lookup_mapping should never be called for non-Person entities
        mock_lookup.assert_not_called()
