---
name: review
description: Review code in fresh contexts on three axes (bugs, spec, standards), let the user triage findings into R tasks, then check the fixes in a fresh context. Use at the end of each task group in tasks.md, before a spec is set done, or when the user says /review.
---

# Review

Fresh sub-agents read the code; they never see the build chat. The user decides what to fix.
Never fix findings on your own.

## 1. Pin the range

- Default `since`: the `closed at` commit of the last review round in `tasks.md` `## Review`.
  No round yet: the commit that added `tasks.md`. The user may pass another commit.
- Final review before `status: done`: from the commit that added `tasks.md` to `HEAD`.
- Before spawning: `git rev-parse <since>` resolves, `git diff <since>..HEAD` is not empty, the
  working tree is clean, and all checks pass (`CLAUDE.md`). Fix those first.

## 2. Three sub-agents in parallel

Spawn all three in one message. Each gets only: the diff command, `git log --oneline
<since>..HEAD`, the spec folder path, and its brief below. Never your opinion of the code.
All are read-only: no edits, no commits, never call real X. Throwaway scripts go in a temp dir.
Tell each to ignore changes under `.claude/` and `specs/_template/`: workflow, not product.

**Bugs.** "Find defects that make the code do the wrong thing. Read the code around each hunk and
its tests; run tests or scripts to confirm when you can. Look hardest at: wrong post deleted or
kept, a post deleted twice, progress lost on stop or crash, wrong waits or retries, secrets leaked
to logs, files or wrong permissions, crashes on bad input, errors swallowed. No style comments.
For each finding give file:line, a concrete failure scenario (input or state, then wrong result),
and confidence (high, medium, low). Under 500 words."

**Spec.** "Compare the diff with `spec.md`, `plan.md` and the tasks in range. Report: (a)
acceptance criteria or decisions the tasks claim that are missing or partial; (b) behaviour not
asked for (scope creep); (c) things that look implemented but wrong. Quote the AC or D line for
each. Under 400 words."

**Standards.** "Check the diff against `CLAUDE.md`, `docs/conventions.md`,
`docs/architecture.md` and the plan's decisions. Cite file and rule for each breach. Also flag, as
judgement calls only, these smells: unclear names, duplicated logic, a function using another
module's data more than its own, the same params always travelling together, a primitive standing
in for a domain concept, abstraction the spec does not need. A documented rule beats a smell.
Skip what ruff and mypy enforce. Under 400 words."

## 3. Present

- Show findings under `## Bugs`, `## Spec`, `## Standards`. Do not merge or rerank across axes.
- Drop a finding only if its file or line does not exist or the code plainly contradicts it.
  When in doubt keep it and say why you doubt it.
- For each: what, the failure scenario, and your recommendation: fix, skip, or wrong spec.
- The user decides each one. Ask in rounds, like `grill`.

## 4. Record

In `tasks.md`, under `## Review`, add a round:

```markdown
### Review 1: T1-T16 (6ce922e..a1b2c3d)

- [ ] R1: Resume deletes a post twice after a crash mid-request. (bugs; AC20)
- ~~R2: Rename `do_it`.~~ skipped: name matches the glossary.
```

- R ids are unique per spec folder and never reused.
- Wrong spec: add it to `## Open questions` in `spec.md` or `plan.md`, then settle it with the
  user through `/plan`. Approved ids stay frozen.
- Commit: `<spec id>: review <n> findings`.

## 5. Fix

Fix open R tasks with `/implement`, before the next T task. Each one: failing test first, fix,
checks pass, tick the box, commit `<spec id>: R<n> <summary>`.

If the fix must differ from what the user approved, stop, explain why, and update the R line
before committing.

## 6. Check the fixes in a fresh context

Spawn one read-only sub-agent. It gets only each fixed R line and its commit SHAs. Brief: "For
each R task, say fixed, not fixed, or fixed but broke something, with a concrete scenario. Do not
look for unrelated issues. Under 300 words."

- Not fixed: untick it and go back to step 5.
- Broke something: add a new R task, back to step 5.
- Same R not fixed after two checks: stop and ask the user. Default to offer: fix the
  remaining gaps broadly (the whole class of error, not one case), then one final check limited
  to the reported scenarios, then close. Anything new it finds goes to the next review.
- All fixed: add `closed at <sha>` to the round heading and commit. Next review starts there.
