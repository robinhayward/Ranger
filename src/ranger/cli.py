import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

from .config import ConfigError, resolve_config
from .discovery import ClientFactory, Discovery, discover, document
from .github import GitHubClient, GitHubError


def main(
    argv: Sequence[str] | None = None,
    client_factory: ClientFactory = GitHubClient,
) -> int:
    arguments = _parser().parse_args(argv)
    try:
        config = resolve_config(
            config_path=arguments.config,
            repositories=arguments.repositories,
            label=arguments.label,
            host=arguments.host,
        )
        discoveries = discover(config, client_factory)
    except (ConfigError, GitHubError) as error:
        print(f"ranger: {_terminal_text(str(error))}", file=sys.stderr)
        return 1

    if arguments.json_output:
        print(json.dumps(document(config.label, discoveries), indent=2))
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


def _print_text(label: str, discoveries: list[Discovery]) -> None:
    issue_count = sum(len(issues) for _, issues in discoveries)
    if not issue_count:
        print(f"No open issues labelled '{_terminal_text(label)}' were found.")
        return

    suffix = "" if issue_count == 1 else "s"
    print(f"Found {issue_count} eligible issue{suffix}:")
    for repository, issues in discoveries:
        if not issues:
            continue
        visibility = "private" if repository.private else "public"
        branch = repository.default_branch or "none"
        print()
        print(
            f"{_terminal_text(repository.name)} "
            f"({visibility}, default branch: {_terminal_text(branch)})"
        )
        print(_terminal_text(repository.url))
        for issue in issues:
            print()
            print(f"#{issue.number} {_terminal_text(issue.title)}")
            print(_terminal_text(issue.url))
            print(f"Updated: {_terminal_text(issue.updated_at)}")
            print(f"Labels: {_terminal_text(', '.join(issue.labels))}")
            if issue.body:
                print()
                print(_terminal_text(issue.body))


def _terminal_text(value: str) -> str:
    return "".join(
        character
        for character in value
        if character in "\n\t" or character.isprintable()
    )
