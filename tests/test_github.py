import json
import subprocess
import unittest

from ranger.github import GitHubClient, GitHubError


class SuccessfulGh:
    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        command = tuple(argv)
        if command == (
            "gh",
            "auth",
            "status",
            "--active",
            "--hostname",
            "github.example.com",
        ):
            return subprocess.CompletedProcess(argv, 0, "authenticated", "")
        if command == (
            "gh",
            "repo",
            "view",
            "acme/api",
            "--json",
            "nameWithOwner,url,defaultBranchRef,isPrivate",
        ):
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    {
                        "nameWithOwner": "acme/api",
                        "url": "https://github.example.com/acme/api",
                        "defaultBranchRef": {"name": "main"},
                        "isPrivate": True,
                    }
                ),
                "",
            )
        if command == (
            "gh",
            "issue",
            "list",
            "--repo",
            "acme/api",
            "--label",
            "agent-ready",
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,body,url,labels,updatedAt",
        ):
            return subprocess.CompletedProcess(
                argv,
                0,
                json.dumps(
                    [
                        {
                            "number": 42,
                            "title": "Add audit export",
                            "body": "Export accepted rows as CSV.",
                            "url": "https://github.example.com/acme/api/issues/42",
                            "labels": [
                                {
                                    "id": "LA_kwDOExample",
                                    "name": "agent-ready",
                                    "description": "Ready for a coding agent",
                                    "color": "0e8a16",
                                }
                            ],
                            "updatedAt": "2026-08-19T08:30:00Z",
                        }
                    ]
                ),
                "",
            )
        return subprocess.CompletedProcess(argv, 1, "", "unexpected command")


class GitHubClientTests(unittest.TestCase):
    def test_loads_repository_and_issue_details(self) -> None:
        client = GitHubClient("github.example.com", runner=SuccessfulGh())

        client.check_auth()
        repository = client.repository("acme/api")
        issues = client.issues("acme/api", "agent-ready")

        self.assertEqual(repository.name, "acme/api")
        self.assertEqual(repository.default_branch, "main")
        self.assertTrue(repository.private)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].repository, "acme/api")
        self.assertEqual(issues[0].number, 42)
        self.assertEqual(issues[0].labels, ("agent-ready",))
        self.assertEqual(issues[0].body, "Export accepted rows as CSV.")

    def test_reports_a_missing_github_cli(self) -> None:
        def missing_gh(*_: object, **__: object) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError

        client = GitHubClient("github.com", runner=missing_gh)

        with self.assertRaisesRegex(GitHubError, "GitHub CLI was not found"):
            client.check_auth()

    def test_reports_invalid_authentication_with_a_remedy(self) -> None:
        def invalid_auth(
            argv: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 1, "", "token is invalid")

        client = GitHubClient("github.com", runner=invalid_auth)

        with self.assertRaisesRegex(
            GitHubError, "gh auth login --hostname github.com"
        ):
            client.check_auth()

    def test_reports_an_inaccessible_repository(self) -> None:
        def inaccessible(
            argv: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 1, "", "repository not found")

        client = GitHubClient("github.com", runner=inaccessible)

        with self.assertRaisesRegex(GitHubError, "repository not found"):
            client.repository("acme/missing")

    def test_rejects_malformed_github_json(self) -> None:
        def malformed(
            argv: list[str], **_: object
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(argv, 0, "not-json", "")

        client = GitHubClient("github.com", runner=malformed)

        with self.assertRaisesRegex(GitHubError, "invalid JSON"):
            client.issues("acme/api", "agent-ready")


if __name__ == "__main__":
    unittest.main()
