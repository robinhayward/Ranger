import unittest

from ranger.config import Config
from ranger.discovery import discover, document
from ranger.github import Issue, Repository


class FakeGitHubClient:
    auth_checked = False

    def __init__(self, host: str) -> None:
        if host != "github.com":
            raise AssertionError(f"unexpected host: {host}")

    def check_auth(self) -> None:
        type(self).auth_checked = True

    def repository(self, name: str) -> Repository:
        return Repository(
            name=name,
            url=f"https://github.com/{name}",
            default_branch="main",
            private=False,
        )

    def issues(self, repository: str, label: str) -> tuple[Issue, ...]:
        numbers = (10, 2) if repository == "acme/Zeta" else ()
        return tuple(
            Issue(
                repository=repository,
                number=number,
                title=f"Issue {number}",
                body="Body",
                url=f"https://github.com/{repository}/issues/{number}",
                labels=(label,),
                updated_at="2026-08-26T10:00:00Z",
            )
            for number in numbers
        )


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeGitHubClient.auth_checked = False

    def test_discovers_and_documents_issues_deterministically(self) -> None:
        discoveries = discover(
            Config(repositories=("acme/Zeta", "acme/alpha")),
            client_factory=FakeGitHubClient,
        )
        result = document("agent-ready", discoveries)

        self.assertTrue(FakeGitHubClient.auth_checked)
        self.assertEqual(
            [repository["name"] for repository in result["repositories"]],
            ["acme/alpha", "acme/Zeta"],
        )
        self.assertEqual(
            [
                issue["number"]
                for issue in result["repositories"][1]["issues"]
            ],
            [2, 10],
        )
        self.assertEqual(
            result["repositories"][1]["issues"][0],
            {
                "repository": "acme/Zeta",
                "number": 2,
                "title": "Issue 2",
                "body": "Body",
                "url": "https://github.com/acme/Zeta/issues/2",
                "labels": ["agent-ready"],
                "updated_at": "2026-08-26T10:00:00Z",
            },
        )


if __name__ == "__main__":
    unittest.main()
