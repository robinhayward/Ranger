# Ranger Initial MCP Server Design

## Goal

Deliver an installable, versioned local MCP server that lets a coding agent use
Ranger's existing Phase 1A GitHub issue discovery from inside an agent session.
The server must remain read-only, project-agnostic, and independent of any model
provider or paid model API.

The release is Ranger `0.2.0`, tagged `v0.2.0` in Git. A developer will be able
to install that version directly from the Ranger GitHub repository, register the
installed server command with an MCP host, and try it from a sample repository.

## Scope

This release includes:

- a local stdio MCP server installed as `ranger-mcp`;
- one read-only `list_issues` tool;
- the same configuration, GitHub authentication, discovery semantics, ordering,
  and structured result used by the existing CLI;
- server and CLI version reporting sourced from one package version;
- installation, MCP registration, update, usage, and troubleshooting
  documentation;
- a Git tag for the released version.

This release does not claim issues, change labels or assignees, create branches
or worktrees, invoke a coding agent, run repository checks, gather evidence,
push commits, open pull requests, run an HTTP service, or package an agent
skill. Those remain later, separately designed phases.

## Approaches Considered

### One distribution using the official MCP Python SDK

Add the MCP server to the existing `ranger-agent` distribution and use the
official MCP Python SDK v2. The CLI and MCP adapter share Ranger's discovery
functions. This is the selected approach because installation and versioning
remain a single operation, while the SDK owns protocol framing, schemas, and
stdio behavior.

### Separate MCP distribution

A separate `ranger-mcp` package could depend on `ranger-agent`. This would allow
independent release cycles, but the initial server has no reason to version
separately and two installable packages would add release and compatibility
work.

### Standard-library protocol implementation

Ranger could preserve its zero-dependency runtime by implementing MCP and
JSON-RPC directly. This is rejected because protocol compatibility and
maintenance cost outweigh avoiding one purpose-built dependency.

## User Workflow

The release is installed from its Git tag:

```bash
uv tool install "git+https://github.com/robinhayward/Ranger.git@v0.2.0"
```

The existing GitHub CLI remains responsible for credentials:

```bash
gh auth login --hostname github.com
```

The developer either creates the existing global Ranger configuration or asks
the MCP tool to inspect explicit `OWNER/NAME` repositories. The server is then
registered with Codex:

```bash
codex mcp add ranger -- ranger-mcp
```

Other MCP hosts can launch the same `ranger-mcp` command over stdio. A host that
does not inherit the user's tool bin directory can be configured with the
absolute path returned by `command -v ranger-mcp`.

Future versions are installed from their new Git tag with the tool installer's
force/reinstall option. The README must show the exact supported update command
rather than implying that a pinned Git tag updates itself.

## Architecture

```text
MCP host (Codex, Claude Code, IDE)
                |
                | stdio MCP
                v
        ranger.mcp_server
                |
                v
      shared Ranger discovery
                |
                v
     GitHubClient -> installed gh CLI
```

The existing CLI remains available for humans and scripts. It becomes a second
adapter over the same discovery operation rather than keeping private
coordination code that the MCP server would have to duplicate.

The production MCP dependency is constrained to the current major line,
`mcp>=2,<3`. The optional MCP development CLI and Inspector are not production
dependencies.

## Components

### Shared discovery

A small internal module owns authenticated discovery, deterministic sorting, and
conversion to the structured document already emitted by `ranger run --json`.
It accepts a validated `Config` and an injectable GitHub client factory. The CLI
and MCP handler both call it.

Configuration resolution also becomes shared behavior. Explicit repositories,
label, host, and configuration path override the default configuration in the
same way for both interfaces.

### CLI adapter

The CLI continues to parse arguments and render human-readable or JSON output.
Its externally visible `ranger run` behavior stays compatible. A top-level
`ranger --version` option reports the package version.

### MCP adapter

The `ranger-mcp` console entry point starts one local stdio server and writes no
application output to stdout because stdout belongs to the MCP protocol. The
server reports the Ranger package version during initialization and includes
short server instructions stating that this release is read-only.

It exposes one tool:

```text
list_issues(
  repositories: list[str] | null = null,
  label: str | null = null,
  host: str | null = null,
  config_path: str | null = null
) -> discovery document
```

When `repositories` is supplied, it replaces configured repositories. Without
it, Ranger loads `config_path` or the default
`~/.config/ranger/config.toml`. Explicit `label` and `host` override configured
values. The result contains the label, repository metadata, and matching issue
details in the existing deterministic JSON shape.

The tool is annotated as read-only, non-destructive, and idempotent. Its name
stays provider-neutral because MCP hosts already namespace tools by server.

## Data Flow

1. The MCP host launches `ranger-mcp` and completes the MCP handshake.
2. The agent calls `list_issues`, optionally supplying configuration overrides.
3. Ranger resolves and validates configuration.
4. Ranger checks the active `gh` authentication for the selected host.
5. Ranger loads repository metadata and up to 100 open issues with the selected
   label for each repository.
6. Ranger sorts repositories and issue numbers deterministically.
7. The MCP tool returns the structured discovery document.

No local ownership state is created and no GitHub mutation occurs.

## Errors and Safety

Configuration and GitHub failures become concise MCP tool errors with the same
actionable remedies as the CLI. Unexpected exceptions are not converted into
successful-looking documents. Credentials and environment variables are never
returned, logged, or passed as MCP arguments.

All subprocesses continue to use argument arrays with `shell=False`. GitHub
content is returned as structured data rather than interpolated into commands.
The MCP process may log diagnostics only to stderr.

## Versioning and Release

`src/ranger/__init__.py` is the single source of the semantic version. Package
metadata, `ranger --version`, and MCP initialization all report `0.2.0`.

The release commit is tagged `v0.2.0`, and both the branch and tag are pushed to
the Ranger remote. Later compatible features increment the minor version;
patches that do not alter the public contract increment the patch version; an
incompatible CLI or MCP contract requires a major version increment.

## Testing

The implementation is test-driven and keeps the external `gh` process as the
replaceable boundary.

Required automated evidence:

- existing configuration, GitHub, and CLI tests remain green;
- shared discovery tests prove authentication, ordering, and document shape;
- MCP tests list the server tools and invoke `list_issues` through an MCP client
  with a fake GitHub boundary;
- MCP errors remain tool errors rather than protocol crashes;
- server metadata and CLI output report `0.2.0`;
- source compilation and wheel/sdist builds succeed;
- an isolated installation from the built wheel exposes both `ranger` and
  `ranger-mcp`;
- an installed stdio server completes a real MCP handshake and tool call.

The repository's standard checks remain:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
uv build
```

## Acceptance Test

After the release is pushed, a developer can install `v0.2.0` from GitHub,
register `ranger-mcp` with a supported local MCP host, configure or explicitly
name a sample GitHub repository, and receive its open `agent-ready` issues from
the `list_issues` tool. The existing `ranger run` command still returns the same
result outside the agent session.

## Sources

- [OpenAI MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Official MCP Python SDK](https://py.sdk.modelcontextprotocol.io/)
- [Connecting an MCP stdio server to a host](https://py.sdk.modelcontextprotocol.io/get-started/real-host/)
