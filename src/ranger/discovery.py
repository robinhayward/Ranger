from collections.abc import Callable, Sequence
from typing import TypedDict

from .config import Config
from .github import GitHubClient, Issue, Repository


ClientFactory = Callable[[str], GitHubClient]
Discovery = tuple[Repository, tuple[Issue, ...]]


class IssueDocument(TypedDict):
    repository: str
    number: int
    title: str
    body: str
    url: str
    labels: list[str]
    updated_at: str


class RepositoryDocument(TypedDict):
    name: str
    url: str
    default_branch: str | None
    private: bool
    issues: list[IssueDocument]


class DiscoveryDocument(TypedDict):
    label: str
    repositories: list[RepositoryDocument]


def discover(
    config: Config,
    client_factory: ClientFactory = GitHubClient,
) -> list[Discovery]:
    client = client_factory(config.host)
    client.check_auth()
    discoveries = [
        (
            client.repository(name),
            tuple(
                sorted(
                    client.issues(name, config.label),
                    key=lambda issue: issue.number,
                )
            ),
        )
        for name in config.repositories
    ]
    discoveries.sort(key=lambda item: item[0].name.casefold())
    return discoveries


def document(
    label: str,
    discoveries: Sequence[Discovery],
) -> DiscoveryDocument:
    return {
        "label": label,
        "repositories": [
            {
                "name": repository.name,
                "url": repository.url,
                "default_branch": repository.default_branch,
                "private": repository.private,
                "issues": [
                    {
                        "repository": issue.repository,
                        "number": issue.number,
                        "title": issue.title,
                        "body": issue.body,
                        "url": issue.url,
                        "labels": list(issue.labels),
                        "updated_at": issue.updated_at,
                    }
                    for issue in issues
                ],
            }
            for repository, issues in discoveries
        ],
    }
