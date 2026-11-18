# Testing

What to test and how. General rules; project specifics live in `conventions.md`.

## What each task tests

A task is not done until its tests cover all that apply:

1. **Acceptance criteria.** At least one test per AC the task names. Mark the group with a
   comment: `# T14: loop, retries (AC18, AC21)`.
2. **Outside input.** For each place data enters from outside (HTTP reply, file, env, flag,
   user text, clock), one test each for: missing, empty, wrong type, malformed. The result is a
   clear error or a safe default, never a crash or traceback.
3. **Side effects and saved state.** Assert the state saved at each step (state, message, wait
   time), not just the end. For each write, send or delete: what if it fails or stops halfway?
   State on disk stays valid and nothing done is lost or done twice.
4. **Sequences.** For anything that counts, retries, waits or resumes: test a sequence of steps,
   including the mixes (fail, other, fail), not just one step.
5. **Bug fixes.** First a test that fails with the reported scenario, then the fix.

Skip what the type checker or linter already proves, and the behaviour of third-party libraries.

## How to write them

- Test behaviour through the public interface. A refactor that keeps behaviour keeps tests green.
- Fake only the boundaries: network, clock, keychain, randomness. Use the real thing for your own
  modules, files (`tmp_path`) and local databases.
- Deterministic: no real network, no real sleeps, no wall-clock time, no unseeded randomness.
- One behaviour per test. The name reads as that behaviour:
  `test_already_gone_counts_as_done`, not `test_engine_3`.
- Assert what a user or caller could see: return values, saved state, calls sent out, messages.
  Not private fields or call order inside your own code.
- Keep the suite fast (seconds). A slow test is a missing fake.

## Kinds of test

| Kind | When |
|---|---|
| Unit | Default. Logic with no I/O. |
| Integration | A module with its real neighbours (DB, files). |
| Smoke | One happy path per command, through the real entry point. |
| Live (real service) | Never in the suite. Manual, by the user. |
| Mutation | In the final review before a spec is `done`, on the riskiest modules. Survivors are test gaps; triage them like review findings. Some survivors change nothing (equivalent); skip those. |
