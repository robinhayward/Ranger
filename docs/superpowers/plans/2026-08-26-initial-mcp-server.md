# Ranger Initial MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Ranger `v0.2.0` with an installable local stdio MCP server exposing the existing read-only GitHub issue discovery.

**Architecture:** Extract configuration resolution and discovery from the CLI into small shared functions, then keep the CLI and a new MCP server as thin adapters. The MCP adapter uses the official MCP Python SDK v2, reports Ranger's package version, exposes one structured `list_issues` tool, and translates expected Ranger failures into model-readable tool errors.

**Tech Stack:** Python 3.11+, standard library, GitHub CLI, Hatchling, official `mcp>=2,<3` Python SDK, `unittest`, `uv`.

**Spec:** `docs/superpowers/specs/2026-08-26-initial-mcp-server-design.md`

## Global Constraints

- Ranger remains standalone and project-agnostic; target repository commands and layout do not enter Ranger.
- GitHub remains the workflow authority and the installed `gh` CLI remains the authentication boundary.
- This release is read-only: no claiming, mutations, worktrees, agent invocation, checks, evidence, pushes, or pull requests.
- All subprocesses use argument arrays and `shell=False`; no credentials or process environments are logged.
- Support Python 3.11 and newer.
- Production MCP dependency is `mcp>=2,<3`; do not add the optional `mcp[cli]` extra.
- Package version, CLI version, MCP server version, and Git tag are exactly `0.2.0` / `v0.2.0`.
- Keep `unittest`; do not add a second test framework.

---

## File Structure

- Create `src/ranger/discovery.py`: shared authenticated discovery and typed document conversion.
- Create `src/ranger/mcp_server.py`: MCP server factory, `list_issues` tool, and stdio entry point.
- Create `tests/test_discovery.py`: direct tests for shared ordering and structured output.
- Create `tests/test_mcp_server.py`: in-memory MCP handshake, schema, success, and error tests.
- Modify `src/ranger/config.py`: shared CLI/MCP configuration resolution.
- Modify `src/ranger/cli.py`: call shared functions and expose `--version`.
- Modify `src/ranger/__init__.py`: single package version source.
- Modify `tests/test_config.py`: configuration override and missing-default coverage.
- Modify `tests/test_cli.py`: CLI version and regression coverage.
- Modify `pyproject.toml`: dynamic version, MCP dependency, and `ranger-mcp` script.
- Modify `README.md`: versioned install, MCP registration, updates, use, and troubleshooting.
- Modify `AGENTS.md`: replace the obsolete zero-runtime-dependency/current-interface statements while retaining the read-only phase boundary.

---

### Task 1: Share Configuration and Discovery Between Adapters

**Files:**
- Create: `src/ranger/discovery.py`
- Create: `tests/test_discovery.py`
- Modify: `src/ranger/config.py`
- Modify: `src/ranger/cli.py`
- Modify: `tests/test_config.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `resolve_config(config_path: Path | None = None, repositories: Sequence[str] | None = None, label: str | None = None, host: str | None = None) -> Config`
- Produces: `discover(config: Config, client_factory: ClientFactory = GitHubClient) -> list[Discovery]`
- Produces: `document(label: str, discoveries: Sequence[Discovery]) -> DiscoveryDocument`
- Preserves: `main(argv, client_factory)` and all existing `ranger run` text/JSON behavior.

- [ ] **Step 1: Write failing configuration-resolution tests**

Add imports and tests to `tests/test_config.py` proving an explicit repository works without a config file, an explicit empty list fails, and explicit values override a file:

```python
from ranger.config import ConfigError, resolve_config

def test_resolves_explicit_repository_without_a_config_file(self) -> None:
    config = resolve_config(
        config_path=None,
        repositories=["acme/api"],
        label="ready-for-agent",
        host="github.example.com",
        default_path=Path("/missing/ranger/config.toml"),
    )
    self.assertEqual(config.repositories, ("acme/api",))
    self.assertEqual(config.label, "ready-for-agent")
    self.assertEqual(config.host, "github.example.com")

def test_rejects_an_explicit_empty_repository_list(self) -> None:
    with self.assertRaisesRegex(ConfigError, "at least one repository"):
        resolve_config(
            repositories=[],
            default_path=Path("/missing/ranger/config.toml"),
        )

def test_explicit_values_override_a_selected_config(self) -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "config.toml"
        path.write_text(
            '[github]\nrepositories = ["configured/api"]\n'
            'label = "configured"\nhost = "github.com"\n',
            encoding="utf-8",
        )
        config = resolve_config(
            config_path=path,
            repositories=["override/web"],
            label="agent-ready",
            host="github.example.com",
        )
    self.assertEqual(config.repositories, ("override/web",))
    self.assertEqual(config.label, "agent-ready")
    self.assertEqual(config.host, "github.example.com")
```

Use an optional keyword-only `default_path` seam so tests never depend on the developer's real home directory; normal callers omit it.

- [ ] **Step 2: Run the configuration tests and confirm the missing function fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_config -v
```

Expected: import failure for `resolve_config`.

- [ ] **Step 3: Implement shared configuration resolution**

Add to `src/ranger/config.py`:

```python
from collections.abc import Sequence

def resolve_config(
    config_path: Path | None = None,
    repositories: Sequence[str] | None = None,
    label: str | None = None,
    host: str | None = None,
    *,
    default_path: Path | None = None,
) -> Config:
    path = config_path or default_path or (
        Path.home() / ".config" / "ranger" / "config.toml"
    )
    repository_values = (
        None if repositories is None else tuple(repositories)
    )
    if config_path is not None or path.exists() or repository_values is None:
        base = load_config(path)
    else:
        base = Config(repositories=repository_values)
    return Config(
        repositories=(
            base.repositories
            if repository_values is None
            else repository_values
        ),
        label=base.label if label is None else label,
        host=base.host if host is None else host,
    )
```

Run the configuration and existing CLI tests. Expected: PASS.

- [ ] **Step 4: Write failing shared-discovery tests**

Create `tests/test_discovery.py` with a fake client that deliberately returns repositories and issues out of order. Assert that `discover()` sorts repositories case-insensitively and issues numerically, calls `check_auth()`, and that `document()` returns JSON-native lists including `labels`:

```python
import unittest

from ranger.config import Config
from ranger.discovery import discover, document
from ranger.github import Issue, Repository

class FakeGitHubClient:
    auth_checked = False

    def __init__(self, host: str) -> None:
        self.host = host

    def check_auth(self) -> None:
        type(self).auth_checked = True

    def repository(self, name: str) -> Repository:
        return Repository(
            name=name,
            url=f"https://github.com/{name}",
            default_branch="main",
            private=False,
        )

    def issues(self, repository: str, label: str) -> tuple[Issue, ...]:
        numbers = (10, 2) if repository == "acme/Zeta" else ()
        return tuple(
            Issue(
                repository=repository,
                number=number,
                title=f"Issue {number}",
                body="Body",
                url=f"https://github.com/{repository}/issues/{number}",
                labels=(label,),
                updated_at="2026-08-26T10:00:00Z",
            )
            for number in numbers
        )

discoveries = discover(
    Config(repositories=("acme/Zeta", "acme/alpha")),
    client_factory=FakeGitHubClient,
)
result = document("agent-ready", discoveries)

self.assertTrue(FakeGitHubClient.auth_checked)
self.assertEqual(
    [repository["name"] for repository in result["repositories"]],
    ["acme/alpha", "acme/Zeta"],
)
self.assertEqual(
    [issue["number"] for issue in result["repositories"][1]["issues"]],
    [2, 10],
)
self.assertIsInstance(
    result["repositories"][1]["issues"][0]["labels"], list
)
```

- [ ] **Step 5: Run the discovery test and confirm the missing module fails**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_discovery -v
```

Expected: import failure for `ranger.discovery`.

- [ ] **Step 6: Implement the shared discovery module**

Create `src/ranger/discovery.py` with precise `TypedDict` result types and no UI concerns:

```python
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
            tuple(sorted(client.issues(name, config.label), key=lambda issue: issue.number)),
        )
        for name in config.repositories
    ]
    discoveries.sort(key=lambda item: item[0].name.casefold())
    return discoveries
```

Implement `document()` by explicitly copying every repository and issue field and converting label tuples to lists. Do not use `Any` or serialize to JSON and parse it back:

```python
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
```

- [ ] **Step 7: Convert the CLI to the shared functions**

Replace `_config`, `_document`, and the in-function discovery loop in `src/ranger/cli.py` with `resolve_config`, `discover`, and `document`. Keep `_print_text` unchanged apart from importing the shared `Discovery` type. The coordination becomes:

```python
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
```

- [ ] **Step 8: Run focused and full tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_config tests.test_discovery tests.test_cli -v
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
```

Expected: all tests pass; compileall exits `0`.

- [ ] **Step 9: Commit the shared core**

```bash
git add src/ranger/config.py src/ranger/discovery.py src/ranger/cli.py tests/test_config.py tests/test_discovery.py
git commit -m "refactor: share Ranger issue discovery"
```

---

### Task 2: Establish Ranger 0.2.0 as the Single Version

**Files:**
- Modify: `src/ranger/__init__.py`
- Modify: `src/ranger/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `ranger.__version__ == "0.2.0"`.
- Produces: `ranger --version` printing exactly `ranger 0.2.0` and exiting `0`.
- Produces: Hatch package metadata version from `src/ranger/__init__.py`.

- [ ] **Step 1: Write failing CLI version tests**

Add to `tests/test_cli.py`:

```python
def test_reports_package_version(self) -> None:
    stdout = StringIO()
    with redirect_stdout(stdout), self.assertRaises(SystemExit) as exit_context:
        main(["--version"])
    self.assertEqual(exit_context.exception.code, 0)
    self.assertEqual(stdout.getvalue(), "ranger 0.2.0\n")
```

Also import `__version__` in a direct assertion so the package version source is covered.

- [ ] **Step 2: Run the focused test and confirm failure**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_cli.CliTests.test_reports_package_version -v
```

Expected: argparse rejects `--version`.

- [ ] **Step 3: Implement the single version source**

Set `src/ranger/__init__.py` to:

```python
"""Ranger local coding-agent orchestrator."""

__version__ = "0.2.0"
```

In `pyproject.toml`, replace `version = "0.1.0"` with `dynamic = ["version"]` and add:

```toml
[tool.hatch.version]
path = "src/ranger/__init__.py"
```

Import `__version__` in `cli.py` and add this top-level parser option before the required subparsers:

```python
parser.add_argument(
    "--version",
    action="version",
    version=f"%(prog)s {__version__}",
)
```

- [ ] **Step 4: Verify tests and package metadata**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_cli -v
uv build
python -c "import zipfile; p=next(__import__('pathlib').Path('dist').glob('*.whl')); z=zipfile.ZipFile(p); print(next(n for n in z.namelist() if n.endswith('METADATA')), z.read(next(n for n in z.namelist() if n.endswith('METADATA'))).decode().split('Version: ',1)[1].splitlines()[0])"
```

Expected: tests pass and wheel metadata prints version `0.2.0`.

- [ ] **Step 5: Commit versioning**

```bash
git add src/ranger/__init__.py src/ranger/cli.py tests/test_cli.py pyproject.toml
git commit -m "chore: version Ranger 0.2.0"
```

---

### Task 3: Add the Read-Only MCP Server

**Files:**
- Create: `src/ranger/mcp_server.py`
- Create: `tests/test_mcp_server.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: `resolve_config`, `discover`, `document`, `DiscoveryDocument`, `ClientFactory`, `GitHubClient`, and `__version__` from Tasks 1-2.
- Produces: `create_server(client_factory: ClientFactory = GitHubClient) -> MCPServer`.
- Produces: module-level `mcp` server and `main() -> None` stdio entry point.
- Produces: `ranger-mcp` installed console command.
- Produces: MCP tool `list_issues(repositories=None, label=None, host=None, config_path=None) -> DiscoveryDocument`.

- [ ] **Step 1: Add the official SDK dependency before running MCP tests**

Change `pyproject.toml` to:

```toml
dependencies = ["mcp>=2,<3"]

[project.scripts]
ranger = "ranger.cli:entrypoint"
ranger-mcp = "ranger.mcp_server:main"
```

Run `uv sync` so the official SDK is available to the tests. Do not add `mcp[cli]`, pytest, or snapshot libraries.

- [ ] **Step 2: Write failing in-memory MCP tests**

Create `tests/test_mcp_server.py` using `unittest.IsolatedAsyncioTestCase`, the official `mcp.Client`, and a local fake GitHub client. Cover server identity, exactly one tool, its read-only annotations, structured success, a supplied config path, and actionable tool errors:

```python
class McpServerTests(unittest.IsolatedAsyncioTestCase):
    async def test_lists_and_calls_read_only_issue_tool(self) -> None:
        async with Client(
            create_server(FakeGitHubClient), raise_exceptions=True
        ) as client:
            self.assertEqual(client.server_info.name, "ranger")
            self.assertEqual(client.server_info.version, "0.2.0")
            self.assertIn("read-only", client.instructions)

            listed = await client.list_tools()
            self.assertEqual([tool.name for tool in listed.tools], ["list_issues"])
            self.assertTrue(listed.tools[0].annotations.read_only_hint)

            result = await client.call_tool(
                "list_issues", {"repositories": ["acme/api"]}
            )
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["label"], "agent-ready")
            self.assertEqual(
                result.structured_content["repositories"][0]["issues"][0]["number"],
                42,
            )

    async def test_returns_expected_failures_as_tool_errors(self) -> None:
        async with Client(
            create_server(FailingGitHubClient), raise_exceptions=True
        ) as client:
            result = await client.call_tool(
                "list_issues", {"repositories": ["acme/api"]}
            )
            self.assertTrue(result.is_error)
            self.assertIn("gh auth login", result.content[0].text)
            self.assertIsNone(result.structured_content)
```

- [ ] **Step 3: Run the MCP tests and confirm the missing module fails**

Run:

```bash
uv run python -m unittest tests.test_mcp_server -v
```

Expected: import failure for `ranger.mcp_server`.

- [ ] **Step 4: Implement the server factory and tool**

Create `src/ranger/mcp_server.py`:

```python
from pathlib import Path

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from . import __version__
from .config import ConfigError, resolve_config
from .discovery import ClientFactory, DiscoveryDocument, discover, document
from .github import GitHubClient, GitHubError

INSTRUCTIONS = (
    "Ranger discovers GitHub issues for coding agents. This Ranger release is "
    "read-only: it never claims issues or changes repositories. Use list_issues "
    "to find open issues with the configured label."
)

def create_server(
    client_factory: ClientFactory = GitHubClient,
) -> MCPServer:
    server = MCPServer(
        "ranger",
        title="Ranger",
        description="Read-only GitHub issue discovery for coding agents.",
        instructions=INSTRUCTIONS,
        version=__version__,
    )

    @server.tool(
        title="List agent-ready GitHub issues",
        annotations=ToolAnnotations(
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=True,
        ),
    )
    def list_issues(
        repositories: list[str] | None = None,
        label: str | None = None,
        host: str | None = None,
        config_path: str | None = None,
    ) -> DiscoveryDocument:
        """List open GitHub issues carrying Ranger's ready label."""
        try:
            config = resolve_config(
                config_path=None if config_path is None else Path(config_path),
                repositories=repositories,
                label=label,
                host=host,
            )
            return document(config.label, discover(config, client_factory))
        except (ConfigError, GitHubError) as error:
            raise ToolError(str(error)) from error

    return server

mcp = create_server()

def main() -> None:
    mcp.run()
```

Keep `mcp.run()` only inside `main`; importing the module must not start stdio.

- [ ] **Step 5: Run MCP, regression, and compilation tests**

Run:

```bash
uv run python -m unittest tests.test_mcp_server -v
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
```

Expected: all tests pass; compileall exits `0`.

- [ ] **Step 6: Commit the MCP server**

```bash
git add pyproject.toml uv.lock src/ranger/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: add Ranger MCP issue discovery"
```

---

### Task 4: Document, Install, Verify, Tag, and Push v0.2.0

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Verify: built `dist/` artifacts and isolated tool installation
- Git: release commits, `v0.2.0` tag, `origin/main`

**Interfaces:**
- Consumes: installed `ranger` and `ranger-mcp` commands from Task 3.
- Produces: reproducible GitHub-tag installation and update instructions.
- Produces: pushed `main` and annotated tag `v0.2.0`.

- [ ] **Step 1: Update user documentation**

Revise `README.md` to include:

```bash
uv tool install "git+https://github.com/robinhayward/Ranger.git@v0.2.0"
gh auth login --hostname github.com
codex mcp add ranger -- ranger-mcp
codex mcp list
```

Document both tool inputs:

```text
list_issues()                                  # uses ~/.config/ranger/config.toml
list_issues(repositories=["owner/sample"])    # one-off repository
```

Document the exact update pattern:

```bash
uv tool install --force "git+https://github.com/robinhayward/Ranger.git@v0.3.0"
```

Explain that `v0.3.0` is an example and must be replaced with the desired
published tag, and show `ranger --version`. Add troubleshooting for `gh auth`,
a missing global config, and MCP hosts that cannot find `ranger-mcp` on `PATH`.

- [ ] **Step 2: Keep engineering instructions accurate**

Update `AGENTS.md` so the current phase includes the read-only MCP adapter,
states that `mcp>=2,<3` is the only runtime Python dependency, and gives these
checks:

```bash
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
uv build
```

Retain the explicit prohibition on claiming, worktrees, agent invocation,
checks, pushes to target repositories, and pull requests.

- [ ] **Step 3: Run the full source verification**

Run:

```bash
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q src tests
uv build
git diff --check
```

Expected: every command exits `0`; both wheel and source distribution are for
`ranger_agent-0.2.0`.

- [ ] **Step 4: Install the built wheel in an isolated tool directory**

Create a task-specific temporary directory with `mktemp -d`, set
`UV_TOOL_DIR` and `UV_TOOL_BIN_DIR` inside it, and install the wheel:

```bash
uv tool install --from dist/ranger_agent-0.2.0-py3-none-any.whl ranger-agent
```

Run the isolated commands by absolute path:

```bash
<temp-bin>/ranger --version
<temp-bin>/ranger --help
<temp-bin>/ranger-mcp
```

Expected: version is `0.2.0`, both help/entry points exist, and `ranger-mcp`
waits silently for MCP input rather than exiting or printing to stdout. Stop the
waiting process with Ctrl-C.

- [ ] **Step 5: Prove an installed stdio handshake and tool call**

Using the Python environment created by the isolated tool install, connect an
official `mcp.Client` through `StdioServerParameters` to the absolute
`ranger-mcp` command. Assert server name/version, list exactly `list_issues`, and
call it with `repositories=[]`; the expected result is an MCP tool error
containing `at least one repository`. This exercises the installed process and
the tool over real stdio without depending on live GitHub credentials.

- [ ] **Step 6: Review the complete diff and commit documentation**

Inspect `git diff`, confirm only Ranger MCP scope is present, then:

```bash
git add README.md AGENTS.md docs/superpowers/plans/2026-08-26-initial-mcp-server.md
git commit -m "docs: explain Ranger MCP installation"
```

- [ ] **Step 7: Run final completion verification from a clean tree**

Run every command from Step 3 again, check `git status --short --branch`, and
confirm the installed stdio verification from Step 5 still passes. Inspect the
release commit history and confirm package, MCP handshake, and docs all say
`0.2.0`.

- [ ] **Step 8: Create and push the release tag**

Create an annotated tag only after all verification succeeds:

```bash
git tag -a v0.2.0 -m "Ranger 0.2.0"
git push origin main
git push origin v0.2.0
```

Then fetch remote references and verify `origin/main`, local `main`, and
`refs/tags/v0.2.0^{}` resolve to the release commit. Do not claim delivery from
local state alone.
