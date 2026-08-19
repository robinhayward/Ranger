# Ranger

Ranger is a local, project-agnostic worker for coding agents. GitHub is the queue and audit trail; your developer machine is the execution environment.

This repository currently contains **Phase 1A**: a read-only discovery command that finds up to 100 open GitHub issues labelled `agent-ready` per configured repository. It does not claim tickets, change repositories, invoke an agent, push branches, or open pull requests yet.

## Requirements

- Python 3.11 or newer
- [GitHub CLI](https://cli.github.com/) installed and authenticated

Authenticate once on each developer machine:

```bash
gh auth login --hostname github.com
```

## Install

From a Ranger checkout with [uv](https://docs.astral.sh/uv/):

```bash
uv tool install .
```

Or with pipx:

```bash
pipx install .
```

The installed command is `ranger`; the Python distribution is `ranger-agent` because `ranger` is already used on PyPI.

## Configure

Create `~/.config/ranger/config.toml`:

```toml
[github]
repositories = [
  "your-organisation/api",
  "your-organisation/web",
]
label = "agent-ready"
host = "github.com"
```

Repository configuration contains workflow identity only. Build commands, tests, architecture, and coding rules will remain in each target repository rather than leaking into Ranger.

## Discover work

```bash
ranger run
```

One-off repositories can replace the configured list:

```bash
ranger run --repo your-organisation/api --repo your-organisation/web
```

Use another config, label, or GitHub host with `--config`, `--label`, and `--host`.

For an AI tool or script, request one JSON document:

```bash
ranger run --json
```

No matching issues is a successful result. Configuration, authentication, access, command, and GitHub response errors exit with status `1` and print an actionable message to stderr.

## Develop

The test suite uses only Python's standard library:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
uv build
```

The Phase 1A design and build plan are in [`docs/superpowers`](docs/superpowers). Later slices will add claiming and worktrees, agent execution, repository-defined checks, evidence gathering, and draft pull requests in that order.

## License

Ranger is available under the [MIT License](LICENSE).
