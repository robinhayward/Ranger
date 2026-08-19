# Ranger Phase 1A GitHub Discovery Design

## Goal

Deliver the first useful Ranger slice: an installable, project-agnostic Python CLI that authenticates through GitHub CLI, discovers open issues carrying an `agent-ready` label across configured repositories, and prints enough issue and repository context for a developer or AI wrapper to select work.

## Scope

Phase 1A includes:

- a `ranger run` command;
- repositories supplied by TOML configuration or repeated `--repo OWNER/NAME` options;
- GitHub CLI authentication validation;
- read-only repository metadata and discovery of up to 100 matching issues per repository;
- human-readable output and stable JSON output;
- actionable failures for missing configuration, missing GitHub CLI, invalid authentication, malformed GitHub responses, and inaccessible repositories;
- install and usage documentation.

It does not claim issues, mutate GitHub, create branches or worktrees, invoke a coding agent, persist jobs, run target-repository checks, push code, or open pull requests. Those belong to later Phase 1 slices.

## User Interface

The normal workflow is:

```bash
gh auth login --hostname github.com
ranger run
```

The default configuration path is `~/.config/ranger/config.toml`:

```toml
[github]
repositories = ["owner/api", "owner/web"]
label = "agent-ready"
host = "github.com"
```

Repositories passed with `--repo` replace the configured list for that invocation. `--label` and `--host` replace their configured values. `--config` selects another file. `--json` emits one JSON document instead of presentation text.

No eligible work is a successful result, not an error.

## Architecture

Ranger uses Python 3.11 or newer and has no runtime Python dependencies.

- `config.py` loads and validates TOML into an immutable `Config` value.
- `github.py` owns the external `gh` process boundary and converts JSON into `Repository` and `Issue` values.
- `cli.py` parses arguments, resolves configuration and overrides, coordinates discovery, and renders text or JSON.
- `__main__.py` and the package console-script entry point both call the same CLI function.

The GitHub boundary executes argument arrays directly, never shell strings. It uses the installed `gh` client so Ranger reuses GitHub's supported credential storage and enterprise-host selection rather than handling tokens itself.

## Data Flow

1. Parse `ranger run` options.
2. Load TOML unless every required value is supplied on the command line.
3. Validate repository identifiers before starting external processes.
4. Run `gh auth status --active --hostname HOST`.
5. For each configured repository, load repository metadata and open issues labelled with the configured discovery label.
6. Parse the returned JSON and attach the repository identity to each issue.
7. Sort discoveries by repository and issue number for deterministic output.
8. Render text for a human or JSON for another tool.

## Error Handling and Safety

All Phase 1A GitHub operations are read-only. Ranger stops with exit code `1` and a concise remedy when GitHub CLI is absent, authentication fails, an external command fails, or returned JSON does not satisfy Ranger's expected shape. Argument syntax errors continue to use argparse's exit code `2`.

Ranger does not print tokens or subprocess environments. Repository commands include the configured host so enterprise authentication and queries cannot diverge. Human-facing output removes non-printing control characters from untrusted GitHub and error text before writing it to a terminal; JSON output preserves the source data using JSON escaping. Error messages may include GitHub CLI stderr, stripped of surrounding whitespace, because that is necessary to diagnose repository access and authentication failures.

## Testing and Verification

Tests use `unittest` from the standard library. Configuration tests use temporary files. GitHub tests replace only the external process runner with deterministic completed-process values and exercise the real parsing and error translation. CLI tests exercise real argument parsing, coordination, rendering, and exit codes with an in-memory GitHub client.

Release verification for this slice is:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
uv build
```

An isolated install must also prove that both `ranger --help` and `python -m ranger --help` start successfully. Live discovery cannot be claimed until a machine has a valid `gh` login and access to at least one configured repository.

## Packaging

The distribution is named `ranger-agent` because the `ranger` name is already occupied on PyPI. The installed command remains `ranger`. Version `0.1.0` represents the first usable but incomplete release. The repository uses the MIT license and a `src/` layout so tests exercise the installed package boundary rather than importing accidentally from the repository root.
