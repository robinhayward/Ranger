from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ranger import __version__
from ranger.cli import main
from ranger.github import GitHubError, Issue, Repository


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
            private=name == "acme/api",
        )

    def issues(self, repository: str, label: str) -> tuple[Issue, ...]:
        if label != "agent-ready":
            raise AssertionError(f"unexpected label: {label}")
        if repository != "acme/api":
            return ()
        return (
            Issue(
                repository=repository,
                number=42,
                title="Add audit export",
                body="Export accepted rows as CSV.",
                url="https://github.example.com/acme/api/issues/42",
                labels=("agent-ready", "backend"),
                updated_at="2026-08-19T08:30:00Z",
            ),
        )


class FailingGitHubClient(FakeGitHubClient):
    def check_auth(self) -> None:
        raise GitHubError("GitHub authentication failed. Run gh auth login.")


class UnsafeTextGitHubClient(FakeGitHubClient):
    def issues(self, repository: str, label: str) -> tuple[Issue, ...]:
        issue = super().issues(repository, label)[0]
        return (
            replace(
                issue,
                title="Add audit\x1b[31m export",
                body="\x1b]52;c;ignored\x07Export accepted rows as CSV.",
            ),
        )


class CliTests(unittest.TestCase):
    def run_cli(
        self,
        arguments: list[str],
        client_factory: type[FakeGitHubClient] = FakeGitHubClient,
    ) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(arguments, client_factory=client_factory)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_run_displays_repository_and_issue_details(self) -> None:
        result, stdout, stderr = self.run_cli(["run", "--repo", "acme/api"])

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Found 1 eligible issue", stdout)
        self.assertIn("acme/api (private, default branch: main)", stdout)
        self.assertIn("#42 Add audit export", stdout)
        self.assertIn("Export accepted rows as CSV.", stdout)

    def test_run_emits_machine_readable_json(self) -> None:
        result, stdout, _ = self.run_cli(
            ["run", "--repo", "acme/api", "--json"]
        )

        document = json.loads(stdout)

        self.assertEqual(result, 0)
        self.assertEqual(document["label"], "agent-ready")
        self.assertEqual(document["repositories"][0]["name"], "acme/api")
        self.assertEqual(document["repositories"][0]["issues"][0]["number"], 42)
        self.assertEqual(
            document["repositories"][0]["issues"][0]["labels"],
            ["agent-ready", "backend"],
        )

    def test_human_output_strips_terminal_control_characters(self) -> None:
        result, stdout, _ = self.run_cli(
            ["run", "--repo", "acme/api"],
            client_factory=UnsafeTextGitHubClient,
        )

        self.assertEqual(result, 0)
        self.assertNotIn("\x1b", stdout)
        self.assertNotIn("\x07", stdout)
        self.assertIn("Export accepted rows as CSV.", stdout)

    def test_command_line_repositories_replace_configured_repositories(self) -> None:
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                '[github]\nrepositories = ["other/web"]\n', encoding="utf-8"
            )

            result, stdout, _ = self.run_cli(
                [
                    "run",
                    "--config",
                    str(config_path),
                    "--repo",
                    "acme/api",
                ]
            )

        self.assertEqual(result, 0)
        self.assertIn("acme/api", stdout)
        self.assertNotIn("other/web", stdout)

    def test_no_eligible_issues_is_successful(self) -> None:
        result, stdout, stderr = self.run_cli(["run", "--repo", "acme/web"])

        self.assertEqual(result, 0)
        self.assertEqual(stderr, "")
        self.assertIn("No open issues labelled 'agent-ready' were found.", stdout)

    def test_reports_configuration_errors(self) -> None:
        result, stdout, stderr = self.run_cli(
            ["run", "--config", "/missing/ranger/config.toml"]
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("ranger: Configuration not found", stderr)

    def test_reports_github_errors(self) -> None:
        result, stdout, stderr = self.run_cli(
            ["run", "--repo", "acme/api"],
            client_factory=FailingGitHubClient,
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout, "")
        self.assertIn("ranger: GitHub authentication failed", stderr)

    def test_reports_package_version(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_context:
            main(["--version"])

        self.assertEqual(__version__, "0.2.0")
        self.assertEqual(exit_context.exception.code, 0)
        self.assertEqual(stdout.getvalue(), "ranger 0.2.0\n")


if __name__ == "__main__":
    unittest.main()
