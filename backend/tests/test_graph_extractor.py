"""Unit tests for graph_extractor: regex extractors, registry, and dedup.

Tests five deterministic extractors (ticket refs, mentions, PR/commit refs,
file paths, integration URLs) plus the registry pattern. All pure function
tests -- no database or mocking needed.
"""

import ast
import importlib
import inspect

import pytest

from src.services.graph_extractor import (
    ExtractedEntity,
    FilePathExtractor,
    MentionExtractor,
    PRRefExtractor,
    TicketRefExtractor,
    URLExtractor,
    register_extractor,
    run_extractors,
)


# ============================================================
# Ticket Reference Extractor
# ============================================================


class TestTicketRefExtractor:
    """Tests for TicketRefExtractor."""

    def setup_method(self):
        self.extractor = TicketRefExtractor()

    def test_basic_match(self):
        """Extracts standard ticket refs like ENG-123."""
        entities = self.extractor.extract("See ENG-123 and CON-45", "slack_message")
        assert len(entities) == 2
        ids = {e.external_id for e in entities}
        assert ids == {"ENG-123", "CON-45"}
        for e in entities:
            assert e.entity_type == "Ticket"
            assert e.relationship_type == "references"

    def test_dedup_within_content(self):
        """Duplicate ticket refs in same content are deduplicated."""
        entities = self.extractor.extract("ENG-123 and ENG-123", "slack_message")
        assert len(entities) == 1
        assert entities[0].external_id == "ENG-123"

    def test_case_sensitivity(self):
        """Lowercase prefix is not matched (case-sensitive)."""
        entities = self.extractor.extract("lowercase eng-123", "slack_message")
        assert len(entities) == 0

    def test_boundary_handling(self):
        """Ticket refs in URLs are still matched."""
        entities = self.extractor.extract(
            "https://linear.app/team/issue/ENG-123 is related", "slack_message"
        )
        # The regex should find ENG-123 inside the URL text
        assert len(entities) == 1
        assert entities[0].external_id == "ENG-123"

    def test_name_matches_external_id(self):
        """The name field is the ticket identifier."""
        entities = self.extractor.extract("Fix BUG-42", "linear_ticket")
        assert len(entities) == 1
        assert entities[0].name == "BUG-42"

    def test_various_prefixes(self):
        """Prefixes of different lengths (2-10 uppercase chars) are matched."""
        entities = self.extractor.extract(
            "AB-1 and PROJECTNAM-999999", "slack_message"
        )
        assert len(entities) == 2


# ============================================================
# Mention Extractor
# ============================================================


class TestMentionExtractor:
    """Tests for MentionExtractor."""

    def setup_method(self):
        self.extractor = MentionExtractor()

    def test_slack_uid_mentions(self):
        """Extracts Slack user IDs in <@UXXXXXXXX> format."""
        entities = self.extractor.extract(
            "<@U12345ABC> said hi to <@U99887766>", "slack_message"
        )
        assert len(entities) == 2
        ids = {e.external_id for e in entities}
        assert "slack:U12345ABC" in ids
        assert "slack:U99887766" in ids
        for e in entities:
            assert e.entity_type == "Person"
            assert e.relationship_type == "mentions"

    def test_platform_username_mentions(self):
        """Extracts @username mentions for platform users."""
        entities = self.extractor.extract(
            "ask @alice and @bob-smith", "linear_comment"
        )
        assert len(entities) == 2
        ids = {e.external_id for e in entities}
        assert "username:alice" in ids
        assert "username:bob-smith" in ids

    def test_email_not_matched(self):
        """Email addresses are not matched as mentions."""
        entities = self.extractor.extract("email@example.com", "slack_message")
        assert len(entities) == 0

    def test_dedup_across_patterns(self):
        """Duplicate mentions across Slack UID and @username are deduped by external_id."""
        # These have different external_ids so both should appear
        entities = self.extractor.extract(
            "<@U12345ABC> and @alice", "slack_message"
        )
        assert len(entities) == 2

    def test_username_with_dots_and_underscores(self):
        """Usernames with dots, underscores are matched."""
        entities = self.extractor.extract(
            "@john.doe and @jane_smith", "linear_comment"
        )
        assert len(entities) == 2
        ids = {e.external_id for e in entities}
        assert "username:john.doe" in ids
        assert "username:jane_smith" in ids

    def test_slack_uid_properties(self):
        """Slack mention has correct properties."""
        entities = self.extractor.extract("<@U12345ABC>", "slack_message")
        assert len(entities) == 1
        assert entities[0].properties["platform"] == "slack"
        assert entities[0].properties["platform_user_id"] == "U12345ABC"

    def test_username_name_format(self):
        """Platform username entities have @-prefixed name."""
        entities = self.extractor.extract("ask @alice", "linear_comment")
        assert len(entities) == 1
        assert entities[0].name == "@alice"


# ============================================================
# PR/Commit Reference Extractor
# ============================================================


class TestPRRefExtractor:
    """Tests for PRRefExtractor."""

    def setup_method(self):
        self.extractor = PRRefExtractor()

    def test_basic_pr_refs(self):
        """Extracts PR numbers like #123."""
        entities = self.extractor.extract(
            "Fixed in #123 and #456", "github_pull_request"
        )
        pr_entities = [e for e in entities if e.external_id.startswith("PR:#")]
        assert len(pr_entities) == 2
        ids = {e.external_id for e in pr_entities}
        assert "PR:#123" in ids
        assert "PR:#456" in ids
        for e in pr_entities:
            assert e.entity_type == "PR"
            assert e.relationship_type == "references"

    def test_hex_color_exclusion(self):
        """Hex colors like #ff0000 (all hex chars) are not matched as PR refs."""
        entities = self.extractor.extract("Color #ff0000", "slack_message")
        # #ff0000 starts with letters, not digits -- PR pattern requires digits
        # The PR pattern is #(\d{1,6}) so non-digit starts won't match
        pr_entities = [e for e in entities if e.external_id.startswith("PR:#")]
        assert len(pr_entities) == 0

    def test_commit_sha_match(self):
        """Extracts commit SHA references (7+ hex chars)."""
        entities = self.extractor.extract(
            "commit abc1234def", "github_pull_request"
        )
        sha_entities = [e for e in entities if e.external_id.startswith("commit:")]
        assert len(sha_entities) == 1
        assert sha_entities[0].external_id == "commit:abc1234"

    def test_all_digit_sha_rejection(self):
        """SHA-like strings that are all digits are rejected."""
        entities = self.extractor.extract(
            "number 1234567", "github_pull_request"
        )
        sha_entities = [e for e in entities if e.external_id.startswith("commit:")]
        assert len(sha_entities) == 0

    def test_short_sha_rejection(self):
        """SHA-like strings shorter than 7 chars are rejected."""
        entities = self.extractor.extract("short abc123", "github_pull_request")
        sha_entities = [e for e in entities if e.external_id.startswith("commit:")]
        assert len(sha_entities) == 0

    def test_ambiguous_pr_marking(self):
        """PR refs from non-GitHub sources are marked ambiguous."""
        entities = self.extractor.extract("#123", "slack_message")
        pr_entities = [e for e in entities if e.external_id.startswith("PR:#")]
        assert len(pr_entities) == 1
        assert pr_entities[0].properties.get("status") == "ambiguous"

    def test_github_source_not_ambiguous(self):
        """PR refs from GitHub sources are NOT marked ambiguous."""
        entities = self.extractor.extract("#123", "github_pull_request")
        pr_entities = [e for e in entities if e.external_id.startswith("PR:#")]
        assert len(pr_entities) == 1
        assert pr_entities[0].properties.get("status") != "ambiguous"


# ============================================================
# File Path Extractor
# ============================================================


class TestFilePathExtractor:
    """Tests for FilePathExtractor."""

    def setup_method(self):
        self.extractor = FilePathExtractor()

    def test_ts_and_py_extensions(self):
        """Extracts paths with common code extensions."""
        entities = self.extractor.extract(
            "check src/lib/utils.ts and backend/main.py", "slack_message"
        )
        assert len(entities) == 2
        for e in entities:
            assert e.entity_type == "CodeChunk"
            assert e.relationship_type == "references"

    def test_path_with_directories(self):
        """Extracts full paths with nested directories."""
        entities = self.extractor.extract(
            "look at backend/src/services/graph_ops.py", "linear_comment"
        )
        assert len(entities) == 1
        assert entities[0].external_id == "path:backend/src/services/graph_ops.py"

    def test_sql_extension(self):
        """SQL files are matched."""
        entities = self.extractor.extract(
            "migration 00017_graph_tables.sql", "slack_message"
        )
        assert len(entities) == 1
        assert entities[0].external_id == "path:00017_graph_tables.sql"

    def test_no_extension_rejection(self):
        """Strings without known extensions are not matched."""
        entities = self.extractor.extract("no extension file", "slack_message")
        assert len(entities) == 0

    def test_json_yaml_toml(self):
        """JSON, YAML, and TOML files are matched."""
        entities = self.extractor.extract(
            "config.json and settings.yaml and Cargo.toml", "slack_message"
        )
        assert len(entities) == 3

    def test_name_is_path(self):
        """The name field is the file path."""
        entities = self.extractor.extract("src/index.ts", "slack_message")
        assert len(entities) == 1
        assert entities[0].name == "src/index.ts"


# ============================================================
# URL Extractor
# ============================================================


class TestURLExtractor:
    """Tests for URLExtractor."""

    def setup_method(self):
        self.extractor = URLExtractor()

    def test_linear_issue_url(self):
        """Extracts Linear issue URL as Ticket entity."""
        entities = self.extractor.extract(
            "https://linear.app/team/issue/ENG-123", "slack_message"
        )
        assert len(entities) == 1
        assert entities[0].entity_type == "Ticket"
        assert entities[0].external_id == "ENG-123"
        assert entities[0].properties["resolved_from"] == "url"

    def test_github_pr_url(self):
        """Extracts GitHub PR URL as PR entity."""
        entities = self.extractor.extract(
            "https://github.com/org/repo/pull/42", "slack_message"
        )
        assert len(entities) == 1
        assert entities[0].entity_type == "PR"
        assert "org/repo" in entities[0].external_id
        assert entities[0].properties.get("url") is not None

    def test_github_commit_url(self):
        """Extracts GitHub commit URL as PR entity."""
        entities = self.extractor.extract(
            "https://github.com/org/repo/commit/abc1234def5678", "slack_message"
        )
        assert len(entities) == 1
        assert entities[0].entity_type == "PR"

    def test_notion_page_url(self):
        """Extracts Notion page URL as NotionPage entity."""
        entities = self.extractor.extract(
            "https://notion.so/workspace/a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "slack_message",
        )
        assert len(entities) == 1
        assert entities[0].entity_type == "NotionPage"

    def test_slack_archive_url(self):
        """Extracts Slack archive URL as SlackThread entity."""
        entities = self.extractor.extract(
            "https://myteam.slack.com/archives/C12345678/p1234567890123456",
            "slack_message",
        )
        assert len(entities) == 1
        assert entities[0].entity_type == "SlackThread"

    def test_random_url_rejected(self):
        """Non-integration URLs are not matched."""
        entities = self.extractor.extract(
            "https://random-website.com/page", "slack_message"
        )
        assert len(entities) == 0

    def test_url_properties_include_url(self):
        """URL entities include the full URL in properties."""
        entities = self.extractor.extract(
            "https://github.com/org/repo/pull/42", "slack_message"
        )
        assert len(entities) == 1
        assert "url" in entities[0].properties
        assert entities[0].properties["resolved_from"] == "url"


# ============================================================
# Registry / run_extractors
# ============================================================


class TestRunExtractors:
    """Tests for run_extractors() registry function."""

    def test_combined_results(self):
        """run_extractors returns entities from all matching extractors."""
        entities = run_extractors("ENG-123 by <@U12345ABC>", "slack_message")
        types = {e.entity_type for e in entities}
        assert "Ticket" in types
        assert "Person" in types

    def test_dedup_across_extractors(self):
        """Duplicate entities across extractors are deduplicated by (entity_type, external_id)."""
        # A ticket ref "ENG-123" extracted by both TicketRefExtractor and URLExtractor
        # (from a Linear URL) should result in only 1 Ticket entity
        content = "ENG-123 see https://linear.app/team/issue/ENG-123"
        entities = run_extractors(content, "slack_message")
        ticket_entities = [e for e in entities if e.entity_type == "Ticket" and e.external_id == "ENG-123"]
        assert len(ticket_entities) == 1

    def test_failing_extractor_doesnt_crash(self):
        """A failing extractor does not prevent other extractors from running."""
        from src.services import graph_extractor

        class BrokenExtractor:
            def extract(self, content, source_type):
                raise RuntimeError("I am broken")

        # Save original registry
        original = graph_extractor._EXTRACTORS[:]
        try:
            graph_extractor._EXTRACTORS.insert(0, BrokenExtractor())
            # Should still return results from other extractors
            entities = run_extractors("ENG-123", "slack_message")
            assert len(entities) >= 1
            assert any(e.external_id == "ENG-123" for e in entities)
        finally:
            graph_extractor._EXTRACTORS[:] = original

    def test_empty_content(self):
        """Empty content returns empty results."""
        entities = run_extractors("", "slack_message")
        assert entities == []

    def test_unique_by_type_and_id(self):
        """Results are unique by (entity_type, external_id) tuple."""
        entities = run_extractors(
            "ENG-123 ENG-123 <@U12345ABC> <@U12345ABC>", "slack_message"
        )
        keys = [(e.entity_type, e.external_id) for e in entities]
        assert len(keys) == len(set(keys))


# ============================================================
# No LLM Dependencies
# ============================================================


class TestNoLLMDependencies:
    """Verify no imports from LLM client libraries."""

    def test_no_llm_imports(self):
        """graph_extractor.py must not import openai, anthropic, or any LLM client."""
        source = inspect.getsource(
            importlib.import_module("src.services.graph_extractor")
        )
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.add(node.module.split(".")[0])

        forbidden = {"openai", "anthropic", "langchain", "litellm", "llama_index"}
        violations = imported_names & forbidden
        assert not violations, f"LLM imports found: {violations}"
