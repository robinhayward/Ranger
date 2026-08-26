# Ranger

Ranger is a local, project-agnostic worker for coding agents. GitHub is the
queue and audit trail; your developer machine is the execution environment.

Ranger `0.2.0` provides the Phase 1A read-only discovery through both a CLI and
a local MCP server. It finds up to 100 open GitHub issues labelled
`agent-ready` per configured repository. It does not claim tickets, change
repositories, invoke an agent, push branches, or open pull requests yet.

## Requirements

- Python 3.11 or newer
- [GitHub CLI](https://cli.github.com/) installed and authenticated

Authenticate once on each developer machine:

```bash
gh auth login --hostname github.com
```

## Install

Install the current release directly from its Git tag with
[uv](https://docs.astral.sh/uv/):

```bash
uv tool install "git+https://github.com/robinhayward/Ranger.git@v0.2.0"
```

Verify the installed version:

```bash
ranger --version
```

The installation provides `ranger` and `ranger-mcp`. The Python distribution is
`ranger-agent` because `ranger` is already used on PyPI.

To install an editable checkout for development instead:

```bash
uv tool install --editable .
```

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

No matching issues is a successful result. Configuration, authentication,
access, command, and GitHub response errors exit with status `1` and print an
actionable message to stderr.

## Use Ranger through MCP

Register the installed local stdio server with Codex:

```bash
codex mcp add ranger -- ranger-mcp
codex mcp list
```

Start or restart Codex in your project and ask it to use Ranger to list eligible
issues. The `list_issues` tool can use the global configuration without
arguments, or the agent can supply one-off repositories:

```text
list_issues()
list_issues(repositories=["owner/sample"])
```

The optional tool inputs are `repositories`, `label`, `host`, and `config_path`.
Explicit values replace the corresponding configuration for that call. The tool
is read-only and returns structured repository and issue data.

If the MCP host cannot find `ranger-mcp`, get its absolute path and register
that instead:

```bash
command -v ranger-mcp
codex mcp add ranger -- /absolute/path/to/ranger-mcp
```

## Update

Install the newer Git tag explicitly. For example, when `v0.3.0` is published:

```bash
uv tool install --force "git+https://github.com/robinhayward/Ranger.git@v0.3.0"
ranger --version
```

A pinned tag does not update itself; replace `v0.3.0` with the version you want
to install.

## Troubleshooting

- Authentication errors: run `gh auth login --hostname github.com`.
- Missing configuration: create `~/.config/ranger/config.toml` or give
  `list_issues` an explicit `repositories` list.
- MCP server missing: run `codex mcp list`, then register the absolute
  `ranger-mcp` path as shown above.
- GitHub Enterprise: set `host` in configuration or in the tool call, and
  authenticate that hostname with `gh auth login --hostname HOST`.

## Develop

Install the locked development environment and run all checks:

```bash
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
uv build
```

The Phase 1A and initial MCP designs and plans are in
[`docs/superpowers`](docs/superpowers). Later slices will add claiming and
worktrees, agent execution, repository-defined checks, evidence gathering, and
draft pull requests in that order.

## License

Ranger is available under the [MIT License](LICENSE).
