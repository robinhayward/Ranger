# Ranger Engineering Guide

## Product Boundary

Ranger is a standalone, project-agnostic coding-agent worker. Do not add assumptions about a target repository's language, package manager, framework, commands, or layout. Target-repository behavior belongs in that repository's configuration and `AGENTS.md`.

GitHub is the shared workflow authority. Local state may support execution and recovery in later phases but must not become a competing ownership system.

## Current Phase

Phase 1A is read-only GitHub issue discovery. Do not add claiming, worktrees, agent invocation, persistence, checks, pushes, or pull requests without an approved later-phase design.

## Development

Ranger supports Python 3.11 and newer and currently has no runtime Python dependencies.

Run all checks from the repository root:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m compileall -q src tests
uv build
```

Write a focused failing test before production behavior. Tests may replace the external `gh` process boundary but should exercise Ranger's real parsing, coordination, output, and error handling.

Execute subprocesses with argument arrays and `shell=False`. Never log credentials or dump the process environment. Keep GitHub mutations out of Phase 1A.
