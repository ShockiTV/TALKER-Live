# [Change Name] Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** [One sentence from proposal]

**Architecture:** [2-3 sentences from design]

**Tech Stack:** [Key technologies/libraries from design]

---

## Spec Coverage Map

<!-- Cross-reference every Given/When/Then scenario from specs/ to a task.
     This is the bridge between OpenSpec requirements and Superpowers tasks.
     No scenario may be left unmapped. -->

| Scenario | Spec Source | Task |
|----------|-----------|------|
| [scenario name] | specs/[domain]/spec.md | Task N |

---

<!-- Below this point, follow the standard Superpowers writing-plans format.
     The superpowers:writing-plans skill defines the task structure:
     - Bite-sized tasks (2-5 min each)
     - Exact file paths (create/modify/test)
     - Complete code (not pseudocode)
     - TDD steps: write failing test → verify RED → implement → verify GREEN → commit
     - Exact commands with expected output

     The Spec Coverage Map above is the only addition to the standard format. -->

- [ ] Task 1: [name]
- [ ] Task 2: [name]
- [ ] ...

---

### Task 1: [Component Name]

**Files:**
- Create: `exact/path/to/file`
- Modify: `exact/path/to/existing:line-range`
- Test: `tests/exact/path/to/test`

**Step 1: Write the failing test**

```
[complete test code]
```

**Step 2: Run test to verify it fails**

Run: `[exact test command]`
Expected: FAIL with "[expected failure message]"

**Step 3: Write minimal implementation**

```
[complete implementation code]
```

**Step 4: Run test to verify it passes**

Run: `[exact test command]`
Expected: PASS

**Step 5: Commit**

```bash
git add [files]
git commit -m "[conventional commit message]"
```