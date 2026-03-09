# spec-driven-superpowers

A custom OpenSpec schema: standard spec-driven planning, Superpowers execution.

All `/opsx:` commands work normally. The difference is under the hood — tasks,
apply, and verify delegate to the real Superpowers skills rather than
reimplementing their methodology. As Superpowers evolves, this schema
automatically benefits.

## How it works

| Step | What happens |
|---|---|
| proposal | Standard OpenSpec (default template) |
| specs | Standard OpenSpec (default template) |
| design | Standard OpenSpec (default template) |
| **tasks** | Invokes `superpowers:writing-plans` with OpenSpec design + specs as input. Adds a Spec Coverage Map ensuring every Given/When/Then scenario maps to a task. |
| **apply** | Invokes `superpowers:using-git-worktrees` for isolation, then `superpowers:subagent-driven-development` or `superpowers:executing-plans` for TDD execution with code review |
| **verify** | Runs `superpowers:verification-before-completion`, then checks spec-level completeness and coherence against OpenSpec artifacts |
| archive | Standard OpenSpec (merge delta specs) |

## Required skills

This schema delegates to Superpowers skills that must be installed:

```
superpowers:writing-plans
superpowers:executing-plans
superpowers:subagent-driven-development
superpowers:test-driven-development
superpowers:requesting-code-review
superpowers:verification-before-completion
superpowers:using-git-worktrees
```

Install via Claude Code:

```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

## Installation

```bash
# Fork the built-in spec-driven schema
openspec schema fork spec-driven spec-driven-superpowers

# Replace schema.yaml and add the custom tasks template
cp schema.yaml openspec/schemas/spec-driven-superpowers/
cp templates/superpowers-tasks.md openspec/schemas/spec-driven-superpowers/templates/
```

Proposal, specs, and design templates are inherited from spec-driven.
The only new template is `superpowers-tasks.md`.

Set as default in `openspec/config.yaml`:

```yaml
schema: spec-driven-superpowers
```

## Usage

```
/opsx:propose my-change           # or /opsx:new + /opsx:continue step by step
/opsx:apply                       # Superpowers TDD execution
/opsx:verify                      # optional
/opsx:archive                     # merge delta specs, close change
```

## File structure

```
spec-driven-superpowers/
├── schema.yaml                    # Schema delegating to Superpowers skills
├── templates/
│   └── superpowers-tasks.md       # Only custom template (adds Spec Coverage Map)
└── README.md
```

## Customization

Use `openspec/config.yaml` rules to add project-specific constraints:

```yaml
schema: spec-driven-superpowers

context: |
  Python 3.11 backend, pytest, Hetzner VPS (4 cores, 16GB, no GPU)

rules:
  tasks: |
    Use pytest for all tests.
    Target 2-minute tasks max.
  apply: |
    Prefer subagent-driven execution.
    Run ruff check after each commit.
```