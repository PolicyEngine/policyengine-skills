# Claude Code launcher: fix-pr

Read this file only when executing the fix-pr workflow in Claude Code. The canonical
workflow is [workflow.md](workflow.md) — read it first; this file maps its abstract
operations onto Claude Code mechanics and adds nothing else.

## Mechanics

- **"Ask the user"** → `AskUserQuestion` (posting mode, missing PR argument, the
  Phase 2 fix-plan checkpoint questions, and the per-issue and research re-ask
  questions — use the canonical option sets, marking the canonical recommendation
  first).
- **"Delegate role X"** → spawn an agent with the type from the table below and a
  prompt containing: the role's task spec from the canonical workflow, the concrete
  `RUN_ROOT`/`WORKTREE_ID`/`PREFIX` values, the file paths it reads and writes, and —
  for fix roles — "fix ONLY the issues assigned to you in the fix plan" plus "DO NOT
  commit; fix-pusher handles all commits". Include `Load skills:` lines naming the
  role's skills from the canonical Roles table (prefix plugin skills with `complete:`,
  e.g. `complete:policyengine-model-development`).
- **"Concurrently"** (evidence extractors) → spawn all in a single message with
  `run_in_background: true`; wait for the batch.
- **Coordinator context protection** → you are the coordinator in the canonical
  orchestration contract: read ONLY the short handoff files it lists; never read the
  diff, code files, or full review reports; never use Edit/Write on repository files
  yourself.

## Role → agent type

| Canonical role | subagent_type |
|---|---|
| context-gatherer | `general-purpose` |
| evidence-extractor-{N} | `general-purpose` |
| fix-parameters | `complete:country-models:rules-engineer` |
| fix-variables | `complete:country-models:rules-engineer` |
| fix-tests | `complete:country-models:edge-case-generator` |
| fix-ci | `complete:country-models:ci-fixer` |
| fix-verifier | `complete:country-models:implementation-validator` |
| fix-pusher | `complete:country-models:pr-pusher` |
| comment-writer | `general-purpose` |
