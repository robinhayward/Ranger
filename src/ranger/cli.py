import argparse
from collections.abc import Callable, Sequence
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .config import Config, ConfigError, load_config
from .github import GitHubClient, GitHubError, Issue, Repository


ClientFactory = Callable[[str], GitHubClient]
Discovery = tuple[Repository, tuple[Issue, ...]]


def main(
    argv: Sequence[str] | None = None,
    client_factory: ClientFactory = GitHubClient,
) -> int:
    arguments = _parser().parse_args(argv)
    try:
        config = _config(arguments)
        client = client_factory(config.host)
        client.check_auth()
        discoveries = [
            (
                client.repository(name),
                tuple(sorted(client.issues(name, config.label), key=lambda issue: issue.number)),
            )
            for name in config.repositories
        ]
        discoveries.sort(key=lambda discovery: discovery[0].name.casefold())
    except (ConfigError, GitHubError) as error:
        print(f"ranger: {error}", file=sys.stderr)
        return 1

    if arguments.json_output:
        print(json.dumps(_document(config.label, discoveries), indent=2))
    else:
        _print_text(config.label, discoveries)
    return 0


def entrypoint() -> None:
    raise SystemExit(main())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ranger",
        description="Run coding-agent work from GitHub on your machine.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="discover open GitHub issues ready for an agent"
    )
    run.add_argument(
        "--config",
        type=Path,
        help="TOML configuration path (default: ~/.config/ranger/config.toml)",
    )
    run.add_argument(
        "--repo",
        action="append",
        dest="repositories",
        metavar="OWNER/NAME",
        help="repository to inspect; repeat to replace the configured list",
    )
    run.add_argument("--label", help="discovery label (default: agent-ready)")
    run.add_argument("--host", help="GitHub host (default: github.com)")
    run.add_argument(
        "--json", action="store_true", dest="json_output", help="emit JSON"
    )
    return parser


def _config(arguments: argparse.Namespace) -> Config:
    default_path = Path.home() / ".config" / "ranger" / "config.toml"
    path = arguments.config or default_path
    if arguments.config or path.exists() or not arguments.repositories:
        base = load_config(path)
    else:
        base = Config(repositories=tuple(arguments.repositories))
    return Config(
        repositories=tuple(arguments.repositories or base.repositories),
        label=arguments.label or base.label,
        host=arguments.host or base.host,
    )


def _document(label: str, discoveries: list[Discovery]) -> dict[str, object]:
    repositories: list[dict[str, object]] = []
    for repository, issues in discoveries:
        item = asdict(repository)
        item["issues"] = [asdict(issue) for issue in issues]
        repositories.append(item)
    return {"label": label, "repositories": repositories}


def _print_text(label: str, discoveries: list[Discovery]) -> None:
    issue_count = sum(len(issues) for _, issues in discoveries)
    if not issue_count:
        print(f"No open issues labelled '{label}' were found.")
        return

    suffix = "" if issue_count == 1 else "s"
    print(f"Found {issue_count} eligible issue{suffix}:")
    for repository, issues in discoveries:
        if not issues:
            continue
        visibility = "private" if repository.private else "public"
        branch = repository.default_branch or "none"
        print()
        print(f"{repository.name} ({visibility}, default branch: {branch})")
        print(repository.url)
        for issue in issues:
            print()
            print(f"#{issue.number} {issue.title}")
            print(issue.url)
            print(f"Updated: {issue.updated_at}")
            print(f"Labels: {', '.join(issue.labels)}")
            if issue.body:
                print()
                print(issue.body)
