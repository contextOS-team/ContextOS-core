"""Unit tests for identity resolution: email-based deterministic matching,
roster fetching, fuzzy name matching, and seed_roster orchestration.

Tests canonical Person node creation, email-based grouping, mapping lookup,
inline resolution during graph extraction, roster fetch functions for
Linear/Slack/GitHub, fuzzy name matching, and seed_roster orchestration.
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


# ============================================================
# Test: fetch_linear_roster
# ============================================================


class TestFetchLinearRoster:
    """Tests for fetch_linear_roster()."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_active_users_with_correct_fields(self, mock_session):
        """fetch_linear_roster returns list of dicts with platform_user_id,
        display_name, email for active users."""
        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()
        settings = MagicMock()

        # Mock get_valid_access_token
        with patch(
            "src.services.identity_resolution.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="test-token",
        ), patch(
            "src.services.identity_resolution.LinearGraphQLClient"
        ) as MockClient:
            client_instance = AsyncMock()
            MockClient.return_value = client_instance
            # Simulate fetch_all_pages returning active users
            client_instance.fetch_all_pages = AsyncMock(return_value=[
                {
                    "id": "user-1",
                    "name": "Alice Smith",
                    "displayName": "Alice",
                    "email": "alice@example.com",
                    "active": True,
                },
                {
                    "id": "user-2",
                    "name": "Bob Jones",
                    "displayName": "Bob",
                    "email": "bob@example.com",
                    "active": True,
                },
            ])

            from src.services.identity_resolution import fetch_linear_roster

            result = await fetch_linear_roster(mock_session, workspace_id, user_id, settings)

        assert len(result) == 2
        assert result[0]["platform_user_id"] == "user-1"
        assert result[0]["display_name"] == "Alice"
        assert result[0]["email"] == "alice@example.com"
        assert result[1]["platform_user_id"] == "user-2"

    @pytest.mark.asyncio
    async def test_skips_inactive_users(self, mock_session):
        """fetch_linear_roster skips inactive/deactivated users."""
        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()
        settings = MagicMock()

        with patch(
            "src.services.identity_resolution.get_valid_access_token",
            new_callable=AsyncMock,
            return_value="test-token",
        ), patch(
            "src.services.identity_resolution.LinearGraphQLClient"
        ) as MockClient:
            client_instance = AsyncMock()
            MockClient.return_value = client_instance
            client_instance.fetch_all_pages = AsyncMock(return_value=[
                {
                    "id": "user-1",
                    "name": "Alice",
                    "displayName": "Alice",
                    "email": "alice@example.com",
                    "active": True,
                },
                {
                    "id": "user-2",
                    "name": "Deactivated User",
                    "displayName": "Deactivated",
                    "email": "deactivated@example.com",
                    "active": False,
                },
            ])

            from src.services.identity_resolution import fetch_linear_roster

            result = await fetch_linear_roster(mock_session, workspace_id, user_id, settings)

        assert len(result) == 1
        assert result[0]["platform_user_id"] == "user-1"


# ============================================================
# Test: fetch_slack_roster
# ============================================================


class TestFetchSlackRoster:
    """Tests for fetch_slack_roster()."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_users_with_correct_fields(self, mock_session):
        """fetch_slack_roster returns list of dicts with platform_user_id,
        display_name, email."""
        workspace_id = uuid.uuid4()

        slack_response = {
            "ok": True,
            "members": [
                {
                    "id": "U001",
                    "name": "alice",
                    "is_bot": False,
                    "deleted": False,
                    "profile": {
                        "real_name": "Alice Smith",
                        "email": "alice@example.com",
                    },
                },
            ],
            "response_metadata": {"next_cursor": ""},
        }

        with patch(
            "src.services.identity_resolution.get_bot_token",
            new_callable=AsyncMock,
            return_value="xoxb-test-token",
        ), patch("httpx.AsyncClient") as MockHttpx:
            mock_client = AsyncMock()
            MockHttpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockHttpx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.json.return_value = slack_response
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)

            from src.services.identity_resolution import fetch_slack_roster

            result = await fetch_slack_roster(mock_session, workspace_id)

        assert len(result) == 1
        assert result[0]["platform_user_id"] == "U001"
        assert result[0]["display_name"] == "Alice Smith"
        assert result[0]["email"] == "alice@example.com"

    @pytest.mark.asyncio
    async def test_skips_bots_and_deleted_users(self, mock_session):
        """fetch_slack_roster skips bots and deleted users."""
        workspace_id = uuid.uuid4()

        slack_response = {
            "ok": True,
            "members": [
                {
                    "id": "U001",
                    "name": "alice",
                    "is_bot": False,
                    "deleted": False,
                    "profile": {"real_name": "Alice", "email": "alice@example.com"},
                },
                {
                    "id": "UBOT",
                    "name": "slackbot",
                    "is_bot": True,
                    "deleted": False,
                    "profile": {"real_name": "Slackbot"},
                },
                {
                    "id": "UDEL",
                    "name": "departed",
                    "is_bot": False,
                    "deleted": True,
                    "profile": {"real_name": "Departed User"},
                },
            ],
            "response_metadata": {"next_cursor": ""},
        }

        with patch(
            "src.services.identity_resolution.get_bot_token",
            new_callable=AsyncMock,
            return_value="xoxb-test-token",
        ), patch("httpx.AsyncClient") as MockHttpx:
            mock_client = AsyncMock()
            MockHttpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockHttpx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.json.return_value = slack_response
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)

            from src.services.identity_resolution import fetch_slack_roster

            result = await fetch_slack_roster(mock_session, workspace_id)

        assert len(result) == 1
        assert result[0]["platform_user_id"] == "U001"

    @pytest.mark.asyncio
    async def test_handles_cursor_pagination(self, mock_session):
        """fetch_slack_roster handles cursor-based pagination (two pages)."""
        workspace_id = uuid.uuid4()

        page1 = {
            "ok": True,
            "members": [
                {
                    "id": "U001",
                    "name": "alice",
                    "is_bot": False,
                    "deleted": False,
                    "profile": {"real_name": "Alice", "email": "alice@example.com"},
                },
            ],
            "response_metadata": {"next_cursor": "cursor_page2"},
        }
        page2 = {
            "ok": True,
            "members": [
                {
                    "id": "U002",
                    "name": "bob",
                    "is_bot": False,
                    "deleted": False,
                    "profile": {"real_name": "Bob", "email": "bob@example.com"},
                },
            ],
            "response_metadata": {"next_cursor": ""},
        }

        with patch(
            "src.services.identity_resolution.get_bot_token",
            new_callable=AsyncMock,
            return_value="xoxb-test-token",
        ), patch("httpx.AsyncClient") as MockHttpx:
            mock_client = AsyncMock()
            MockHttpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockHttpx.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_resp1 = MagicMock()
            mock_resp1.json.return_value = page1
            mock_resp1.status_code = 200

            mock_resp2 = MagicMock()
            mock_resp2.json.return_value = page2
            mock_resp2.status_code = 200

            mock_client.get = AsyncMock(side_effect=[mock_resp1, mock_resp2])

            from src.services.identity_resolution import fetch_slack_roster

            result = await fetch_slack_roster(mock_session, workspace_id)

        assert len(result) == 2
        assert result[0]["platform_user_id"] == "U001"
        assert result[1]["platform_user_id"] == "U002"


# ============================================================
# Test: fetch_github_roster
# ============================================================


class TestFetchGithubRoster:
    """Tests for fetch_github_roster()."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_collaborators_with_login(self, mock_session):
        """fetch_github_roster returns collaborators with login as platform_user_id."""
        workspace_id = uuid.uuid4()
        settings = MagicMock()

        with patch(
            "src.services.identity_resolution.get_installation_token",
            new_callable=AsyncMock,
            return_value="ghs_test-token",
        ), patch(
            "src.services.identity_resolution.get_cached_repos",
            new_callable=AsyncMock,
            return_value=[{"full_name": "org/repo1"}],
        ), patch(
            "src.services.identity_resolution.create_github_client"
        ) as MockGhClient:
            mock_client = AsyncMock()
            MockGhClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockGhClient.return_value.__aexit__ = AsyncMock(return_value=False)

            # Collaborators response (no Link header = single page)
            collab_response = MagicMock()
            collab_response.status_code = 200
            collab_response.json.return_value = [
                {"login": "alice", "id": 1},
                {"login": "bob", "id": 2},
            ]
            collab_response.headers = {}

            # User detail responses (for email lookup)
            alice_resp = MagicMock()
            alice_resp.status_code = 200
            alice_resp.json.return_value = {"login": "alice", "email": "alice@example.com", "name": "Alice Smith"}
            alice_resp.headers = {}

            bob_resp = MagicMock()
            bob_resp.status_code = 200
            bob_resp.json.return_value = {"login": "bob", "email": None, "name": "Bob"}
            bob_resp.headers = {}

            mock_client.get = AsyncMock(side_effect=[collab_response, alice_resp, bob_resp])

            with patch(
                "src.services.identity_resolution.check_rate_limit",
                new_callable=AsyncMock,
            ):
                from src.services.identity_resolution import fetch_github_roster

                result = await fetch_github_roster(mock_session, workspace_id, settings)

        assert len(result) == 2
        alice = next(r for r in result if r["platform_user_id"] == "alice")
        assert alice["email"] == "alice@example.com"
        bob = next(r for r in result if r["platform_user_id"] == "bob")
        assert bob["email"] is None

    @pytest.mark.asyncio
    async def test_attempts_per_user_email_lookup(self, mock_session):
        """fetch_github_roster attempts GET /users/{login} to get public email."""
        workspace_id = uuid.uuid4()
        settings = MagicMock()

        with patch(
            "src.services.identity_resolution.get_installation_token",
            new_callable=AsyncMock,
            return_value="ghs_test-token",
        ), patch(
            "src.services.identity_resolution.get_cached_repos",
            new_callable=AsyncMock,
            return_value=[{"full_name": "org/repo1"}],
        ), patch(
            "src.services.identity_resolution.create_github_client"
        ) as MockGhClient:
            mock_client = AsyncMock()
            MockGhClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockGhClient.return_value.__aexit__ = AsyncMock(return_value=False)

            collab_response = MagicMock()
            collab_response.status_code = 200
            collab_response.json.return_value = [{"login": "charlie", "id": 3}]
            collab_response.headers = {}

            user_resp = MagicMock()
            user_resp.status_code = 200
            user_resp.json.return_value = {"login": "charlie", "email": "charlie@example.com", "name": "Charlie"}
            user_resp.headers = {}

            mock_client.get = AsyncMock(side_effect=[collab_response, user_resp])

            with patch(
                "src.services.identity_resolution.check_rate_limit",
                new_callable=AsyncMock,
            ):
                from src.services.identity_resolution import fetch_github_roster

                result = await fetch_github_roster(mock_session, workspace_id, settings)

        assert len(result) == 1
        # Verify the user endpoint was called
        calls = mock_client.get.call_args_list
        assert any("/users/charlie" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_deduplicates_across_repos(self, mock_session):
        """fetch_github_roster deduplicates collaborators across multiple repos."""
        workspace_id = uuid.uuid4()
        settings = MagicMock()

        with patch(
            "src.services.identity_resolution.get_installation_token",
            new_callable=AsyncMock,
            return_value="ghs_test-token",
        ), patch(
            "src.services.identity_resolution.get_cached_repos",
            new_callable=AsyncMock,
            return_value=[{"full_name": "org/repo1"}, {"full_name": "org/repo2"}],
        ), patch(
            "src.services.identity_resolution.create_github_client"
        ) as MockGhClient:
            mock_client = AsyncMock()
            MockGhClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockGhClient.return_value.__aexit__ = AsyncMock(return_value=False)

            # repo1 collaborators
            collab_resp1 = MagicMock()
            collab_resp1.status_code = 200
            collab_resp1.json.return_value = [{"login": "alice", "id": 1}]
            collab_resp1.headers = {}

            # alice user detail
            alice_resp = MagicMock()
            alice_resp.status_code = 200
            alice_resp.json.return_value = {"login": "alice", "email": "alice@example.com", "name": "Alice"}
            alice_resp.headers = {}

            # repo2 collaborators (same alice)
            collab_resp2 = MagicMock()
            collab_resp2.status_code = 200
            collab_resp2.json.return_value = [{"login": "alice", "id": 1}]
            collab_resp2.headers = {}

            mock_client.get = AsyncMock(side_effect=[collab_resp1, alice_resp, collab_resp2])

            with patch(
                "src.services.identity_resolution.check_rate_limit",
                new_callable=AsyncMock,
            ):
                from src.services.identity_resolution import fetch_github_roster

                result = await fetch_github_roster(mock_session, workspace_id, settings)

        # alice should appear only once
        assert len(result) == 1
        assert result[0]["platform_user_id"] == "alice"


# ============================================================
# Test: compute_name_similarity
# ============================================================


class TestComputeNameSimilarity:
    """Tests for compute_name_similarity()."""

    def test_similar_names_high_score(self):
        """compute_name_similarity('John Smith', 'Smith, John') returns score >= 80."""
        from src.services.identity_resolution import compute_name_similarity

        score = compute_name_similarity("John Smith", "Smith, John")
        assert score >= 80

    def test_dissimilar_names_zero(self):
        """compute_name_similarity('John Smith', 'Jane Doe') returns 0 (below threshold)."""
        from src.services.identity_resolution import compute_name_similarity

        score = compute_name_similarity("John Smith", "Jane Doe")
        assert score == 0.0


# ============================================================
# Test: find_fuzzy_candidates
# ============================================================


class TestFindFuzzyCandidates:
    """Tests for find_fuzzy_candidates()."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_creates_candidate_edge_for_similar_names(self, mock_session):
        """find_fuzzy_candidates creates candidate same_as edge with
        status=candidate and confidence score for name matches across
        different emails."""
        from src.models.graph_node import GraphNode

        workspace_id = uuid.uuid4()

        # Two canonical Person nodes with similar names but different person IDs
        canonical_1_id = uuid.uuid4()
        canonical_2_id = uuid.uuid4()

        node1 = MagicMock(spec=GraphNode)
        node1.id = canonical_1_id
        node1.name = "John Smith"
        node1.properties = {"canonical": True, "canonical_person_id": str(uuid.uuid4())}

        node2 = MagicMock(spec=GraphNode)
        node2.id = canonical_2_id
        node2.name = "Smith, John"
        node2.properties = {"canonical": True, "canonical_person_id": str(uuid.uuid4())}

        # Mock session to return the two canonical nodes
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [node1, node2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.services.identity_resolution.upsert_edge",
            new_callable=AsyncMock,
            return_value=uuid.uuid4(),
        ) as mock_upsert_edge:
            from src.services.identity_resolution import find_fuzzy_candidates

            count = await find_fuzzy_candidates(mock_session, workspace_id)

        assert count == 1
        mock_upsert_edge.assert_called_once()
        edge_kwargs = mock_upsert_edge.call_args.kwargs
        assert edge_kwargs["relationship_type"] == "same_as"
        assert edge_kwargs["properties"]["status"] == "candidate"
        assert 0.5 <= edge_kwargs["properties"]["confidence"] <= 0.9
        assert edge_kwargs["properties"]["match_type"] == "fuzzy_name"

    @pytest.mark.asyncio
    async def test_no_edge_for_dissimilar_names(self, mock_session):
        """find_fuzzy_candidates does NOT create edge when score is below threshold 80."""
        from src.models.graph_node import GraphNode

        workspace_id = uuid.uuid4()

        node1 = MagicMock(spec=GraphNode)
        node1.id = uuid.uuid4()
        node1.name = "Alice Johnson"
        node1.properties = {"canonical": True, "canonical_person_id": str(uuid.uuid4())}

        node2 = MagicMock(spec=GraphNode)
        node2.id = uuid.uuid4()
        node2.name = "Bob Williams"
        node2.properties = {"canonical": True, "canonical_person_id": str(uuid.uuid4())}

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [node1, node2]
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch(
            "src.services.identity_resolution.upsert_edge",
            new_callable=AsyncMock,
        ) as mock_upsert_edge:
            from src.services.identity_resolution import find_fuzzy_candidates

            count = await find_fuzzy_candidates(mock_session, workspace_id)

        assert count == 0
        mock_upsert_edge.assert_not_called()


# ============================================================
# Test: seed_roster
# ============================================================


class TestSeedRoster:
    """Tests for seed_roster()."""

    @pytest.fixture
    def mock_session(self):
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_upserts_and_calls_resolve_and_fuzzy(self, mock_session):
        """seed_roster upserts identity_mapping rows and calls
        resolve_by_email + find_fuzzy_candidates."""
        workspace_id = uuid.uuid4()
        members = [
            {"platform_user_id": "U001", "display_name": "Alice", "email": "alice@example.com"},
            {"platform_user_id": "U002", "display_name": "Bob", "email": "bob@example.com"},
        ]

        with patch(
            "src.services.identity_resolution.upsert_identity_mapping",
            new_callable=AsyncMock,
        ) as mock_upsert_mapping, patch(
            "src.services.identity_resolution.resolve_by_email",
            new_callable=AsyncMock,
            return_value=2,
        ) as mock_resolve, patch(
            "src.services.identity_resolution.find_fuzzy_candidates",
            new_callable=AsyncMock,
            return_value=0,
        ) as mock_fuzzy, patch(
            "src.services.identity_resolution.backfill_identity_resolution",
            new_callable=AsyncMock,
            return_value=0,
        ):
            from src.services.identity_resolution import seed_roster

            count = await seed_roster(mock_session, workspace_id, "slack", members)

        assert count == 2
        assert mock_upsert_mapping.call_count == 2
        mock_resolve.assert_called_once_with(mock_session, workspace_id)
        mock_fuzzy.assert_called_once_with(mock_session, workspace_id)
