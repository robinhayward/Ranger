from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from mcp import Client

from ranger.github import GitHubError, Issue, Repository
from ranger.mcp_server import create_server


class FakeGitHubClient:
    def __init__(self, host: str) -> None:
        if host not in {"github.com", "github.example.com"}:
            raise AssertionError(f"unexpected host: {host}")

    def check_auth(self) -> None:
        return None

    def repository(self, name: str) -> Repository:
        return Repository(
            name=name,
            url=f"https://github.example.com/{name}",
            default_branch="main",
            private=True,
        )

    def issues(self, repository: str, label: str) -> tuple[Issue, ...]:
        return (
            Issue(
                repository=repository,
                number=42,
                title="Add audit export",
                body="Export accepted rows as CSV.",
                url=f"https://github.example.com/{repository}/issues/42",
                labels=(label, "backend"),
                updated_at="2026-08-26T10:00:00Z",
            ),
        )


class FailingGitHubClient(FakeGitHubClient):
    def check_auth(self) -> None:
        raise GitHubError(
            "GitHub authentication failed for github.com. "
            "Run: gh auth login --hostname github.com"
        )


class McpServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_and_calls_read_only_issue_tool(self) -> None:
        async with Client(
            create_server(FakeGitHubClient), raise_exceptions=True
        ) as client:
            self.assertIsNotNone(client.server_info)
            self.assertEqual(client.server_info.name, "ranger")
            self.assertEqual(client.server_info.version, "0.2.0")
            self.assertIsNotNone(client.instructions)
            self.assertIn("read-only", client.instructions)

            listed = await client.list_tools()
            self.assertEqual([tool.name for tool in listed.tools], ["list_issues"])
            annotations = listed.tools[0].annotations
            self.assertIsNotNone(annotations)
            self.assertTrue(annotations.read_only_hint)
            self.assertFalse(annotations.destructive_hint)
            self.assertTrue(annotations.idempotent_hint)
            self.assertTrue(annotations.open_world_hint)

            result = await client.call_tool(
                "list_issues", {"repositories": ["acme/api"]}
            )

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["label"], "agent-ready")
        self.assertEqual(
            result.structured_content["repositories"][0]["issues"][0]["number"],
            42,
        )
        self.assertEqual(
            result.structured_content["repositories"][0]["issues"][0]["labels"],
            ["agent-ready", "backend"],
        )

    async def test_uses_a_selected_ranger_config(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(
                '[github]\nrepositories = ["acme/configured"]\n'
                'label = "ready-for-agent"\n'
                'host = "github.example.com"\n',
                encoding="utf-8",
            )
            async with Client(
                create_server(FakeGitHubClient), raise_exceptions=True
            ) as client:
                result = await client.call_tool(
                    "list_issues", {"config_path": str(path)}
                )

        self.assertFalse(result.is_error)
        self.assertEqual(result.structured_content["label"], "ready-for-agent")
        self.assertEqual(
            result.structured_content["repositories"][0]["name"],
            "acme/configured",
        )

    async def test_returns_expected_failures_as_tool_errors(self) -> None:
        async with Client(
            create_server(FailingGitHubClient), raise_exceptions=True
        ) as client:
            result = await client.call_tool(
                "list_issues", {"repositories": ["acme/api"]}
            )

        self.assertTrue(result.is_error)
        self.assertIn("gh auth login", result.content[0].text)
        self.assertIsNone(result.structured_content)


if __name__ == "__main__":
    unittest.main()
