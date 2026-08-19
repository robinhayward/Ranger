# Ranger Phase 1A GitHub Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an installable `ranger` command that discovers configured `agent-ready` GitHub issues without mutating GitHub.

**Architecture:** A small standard-library Python package separates TOML loading, the authenticated `gh` subprocess boundary, and CLI presentation. Structured dataclasses flow from GitHub JSON to deterministic text or JSON output.

**Tech Stack:** Python 3.11+, `argparse`, `dataclasses`, `json`, `subprocess`, `tomllib`, `unittest`, Hatchling packaging, GitHub CLI.

**Spec:** `docs/superpowers/specs/2026-08-19-phase-1a-github-discovery-design.md`

## Global Constraints

- The installed command is `ranger`; the Python distribution is `ranger-agent`.
- Runtime Python dependencies are forbidden in Phase 1A.
- GitHub operations are read-only and run as argument arrays without a shell.
- The default label is exactly `agent-ready` and the default host is exactly `github.com`.
- Python 3.11 is the minimum supported version.
- No eligible issues is a successful result.

---

### Task 1: Configuration Contract

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/ranger/__init__.py`
- Create: `src/ranger/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: TOML with `[github] repositories`, optional `label`, and optional `host`.
- Produces: `Config(repositories: tuple[str, ...], label: str, host: str)` and `load_config(path: Path) -> Config`.

- [ ] **Step 1: Write failing tests** for valid defaults, empty repositories, missing files, and malformed `owner/name` identifiers using literal temporary TOML documents.
- [ ] **Step 2: Verify RED** with `python -m unittest tests.test_config -v`; imports must fail because `ranger.config` does not exist.
- [ ] **Step 3: Implement the minimum config loader** with `tomllib.load`, immutable dataclasses, and direct validation. Raise `ConfigError` with user-facing messages.
- [ ] **Step 4: Verify GREEN** with `PYTHONPATH=src python -m unittest tests.test_config -v`.

### Task 2: Read-only GitHub Boundary

**Files:**
- Create: `src/ranger/github.py`
- Test: `tests/test_github.py`

**Interfaces:**
- Consumes: `host`, repository identifiers, a label, and a callable compatible with `subprocess.run`.
- Produces: `GitHubClient.check_auth()`, `GitHubClient.repository(name) -> Repository`, and `GitHubClient.issues(name, label) -> tuple[Issue, ...]`.

- [ ] **Step 1: Write failing tests** whose fake process results contain complete representative `gh` JSON for repository metadata and issue fields. Cover successful parsing, missing `gh`, invalid authentication, command failure, and malformed JSON.
- [ ] **Step 2: Verify RED** with `PYTHONPATH=src python -m unittest tests.test_github -v`; imports must fail because `ranger.github` does not exist.
- [ ] **Step 3: Implement the boundary** using `subprocess.run(..., capture_output=True, text=True, check=False)` for:

```text
gh auth status --active --hostname HOST
gh repo view --repo OWNER/NAME --json nameWithOwner,url,defaultBranchRef,isPrivate
gh issue list --repo OWNER/NAME --label LABEL --state open --limit 100 --json number,title,body,url,labels,updatedAt
```

Convert the JSON to frozen dataclasses and translate process and JSON failures into `GitHubError`.
- [ ] **Step 4: Verify GREEN** with `PYTHONPATH=src python -m unittest tests.test_github -v`.

### Task 3: Discovery CLI

**Files:**
- Create: `src/ranger/cli.py`
- Create: `src/ranger/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `main(argv: Sequence[str] | None = None, client_factory=GitHubClient) -> int`.
- Produces: the `ranger run` command, deterministic human output, JSON output, and process exit codes.

- [ ] **Step 1: Write failing CLI tests** for text output, JSON output, command-line repository overrides, the no-work message, and concise config/GitHub errors. Assert on observable stdout, stderr, and return values rather than mock call counts.
- [ ] **Step 2: Verify RED** with `PYTHONPATH=src python -m unittest tests.test_cli -v`; imports must fail because `ranger.cli` does not exist.
- [ ] **Step 3: Implement minimal coordination**: parse `run`, resolve `~/.config/ranger/config.toml`, apply overrides, validate auth once, discover every repository, sort results, and render. Both console and module entry points must raise `SystemExit(main())`.
- [ ] **Step 4: Verify GREEN** with `PYTHONPATH=src python -m unittest tests.test_cli -v` and then `PYTHONPATH=src python -m unittest discover -s tests -v`.

### Task 4: Open-source Handoff and Install Verification

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `AGENTS.md`

**Interfaces:**
- Consumes: the finished CLI behavior and documented current limitations.
- Produces: install, authentication, configuration, use, test, and contribution instructions.

- [ ] **Step 1: Document `uv tool install .` and `pipx install .`, `gh auth login`, the exact TOML schema, CLI overrides, JSON output, and Phase 1A's read-only boundary.**
- [ ] **Step 2: Run the full verification:**

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
uv build
```

- [ ] **Step 3: Install the built wheel into a temporary isolated environment** and run `ranger --help`, `ranger run --help`, and `python -m ranger --help`.
- [ ] **Step 4: Inspect `git diff --check`, the staged diff, and a secret-pattern scan before committing the self-contained Phase 1A slice.**
