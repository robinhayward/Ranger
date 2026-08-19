from collections.abc import Callable
from dataclasses import dataclass
import json
import subprocess
from typing import Any


class GitHubError(RuntimeError):
    """GitHub CLI could not complete a Ranger operation."""


@dataclass(frozen=True)
class Repository:
    name: str
    url: str
    default_branch: str | None
    private: bool


@dataclass(frozen=True)
class Issue:
    repository: str
    number: int
    title: str
    body: str
    url: str
    labels: tuple[str, ...]
    updated_at: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitHubClient:
    def __init__(self, host: str, runner: Runner = subprocess.run) -> None:
        self.host = host
        self._runner = runner

    def check_auth(self) -> None:
        result = self._run(
            "auth", "status", "--active", "--hostname", self.host, check=False
        )
        if result.returncode:
            detail = result.stderr.strip()
            suffix = f"\nGitHub CLI: {detail}" if detail else ""
            raise GitHubError(
                f"GitHub authentication failed for {self.host}. "
                f"Run: gh auth login --hostname {self.host}{suffix}"
            )

    def repository(self, name: str) -> Repository:
        result = self._run(
            "repo",
            "view",
            name,
            "--json",
            "nameWithOwner,url,defaultBranchRef,isPrivate",
        )
        data = _json_object(result.stdout, f"repository {name}")
        branch_ref = data.get("defaultBranchRef")
        if branch_ref is None:
            default_branch = None
        elif isinstance(branch_ref, dict):
            default_branch = _field(branch_ref, "name", str, f"repository {name}")
        else:
            raise GitHubError(
                f"GitHub returned an invalid defaultBranchRef for repository {name}"
            )
        return Repository(
            name=_field(data, "nameWithOwner", str, f"repository {name}"),
            url=_field(data, "url", str, f"repository {name}"),
            default_branch=default_branch,
            private=_field(data, "isPrivate", bool, f"repository {name}"),
        )

    def issues(self, repository: str, label: str) -> tuple[Issue, ...]:
        result = self._run(
            "issue",
            "list",
            "--repo",
            repository,
            "--label",
            label,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,body,url,labels,updatedAt",
        )
        data = _json_array(result.stdout, f"issues for {repository}")
        return tuple(_issue(item, repository) for item in data)

    def _run(
        self, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        command = ["gh", *arguments]
        try:
            result = self._runner(
                command, capture_output=True, text=True, check=False
            )
        except FileNotFoundError as error:
            raise GitHubError(
                "GitHub CLI was not found. Install it from https://cli.github.com/"
            ) from error
        if check and result.returncode:
            detail = result.stderr.strip() or "unknown GitHub CLI error"
            raise GitHubError(f"GitHub command failed: {detail}")
        return result


def _issue(data: Any, repository: str) -> Issue:
    context = f"issue in {repository}"
    if not isinstance(data, dict):
        raise GitHubError(f"GitHub returned an invalid {context}")
    labels = _field(data, "labels", list, context)
    label_names = tuple(
        _field(label, "name", str, context)
        if isinstance(label, dict)
        else _invalid_label(context)
        for label in labels
    )
    body = data.get("body")
    if body is None:
        body = ""
    if not isinstance(body, str):
        raise GitHubError(f"GitHub returned an invalid body for {context}")
    return Issue(
        repository=repository,
        number=_field(data, "number", int, context),
        title=_field(data, "title", str, context),
        body=body,
        url=_field(data, "url", str, context),
        labels=label_names,
        updated_at=_field(data, "updatedAt", str, context),
    )


def _json_object(output: str, context: str) -> dict[str, Any]:
    data = _json(output, context)
    if not isinstance(data, dict):
        raise GitHubError(f"GitHub returned invalid JSON for {context}: expected object")
    return data


def _json_array(output: str, context: str) -> list[Any]:
    data = _json(output, context)
    if not isinstance(data, list):
        raise GitHubError(f"GitHub returned invalid JSON for {context}: expected array")
    return data


def _json(output: str, context: str) -> Any:
    try:
        return json.loads(output)
    except json.JSONDecodeError as error:
        raise GitHubError(f"GitHub returned invalid JSON for {context}") from error


def _field(
    data: dict[str, Any], key: str, expected: type, context: str
) -> Any:
    value = data.get(key)
    if not isinstance(value, expected) or (
        expected is int and isinstance(value, bool)
    ):
        raise GitHubError(f"GitHub returned an invalid {key} for {context}")
    return value


def _invalid_label(context: str) -> str:
    raise GitHubError(f"GitHub returned an invalid label for {context}")
