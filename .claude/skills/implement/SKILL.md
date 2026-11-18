---
name: implement
description: Build a spec task by task from tasks.md. Use when tasks are ready and the user wants code written, or says /implement.
---

# Implement

1. Read `tasks.md`, then only the plan and docs the next task needs. Read a doc only if it exists; small projects skip some.
2. Set spec `status: in-progress`.
3. One task at a time: write test, write code, run tests, tick the box, commit (rules: `specs/README.md`, Commits).
4. Open R tasks under `## Review` come before the next T task.
5. After the last task of a group (the plain heading lines in `tasks.md`), stop and run `/review`.
6. If the project is not a git repo, skip commits, say so once, and never run `git init`.
7. If reality breaks the plan, stop and update `plan.md` with the user.
8. When all boxes are ticked and criteria pass, run a final `/review` over the whole spec, then set `status: done`.
