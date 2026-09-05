# Claude Code launcher: review-program

Read the canonical [workflow.md](workflow.md) first. This adapter maps its operations
to Claude Code; it adds no review stages or completion gates.

- **Arguments**: preserve positional arguments and flags, including `--sources` and
  `--source-budget`, according to the canonical grammar.
- **Questions**: use `AskUserQuestion` for missing/ambiguous PR identity or a posting
  decision. Honor decisions already provided; review can finish before asking to post.
- **Delegation**: launch `general-purpose` agents for the canonical `policy-reviewer`
  and `code-reviewer` together when both apply. Use the active `Agent`/delegation tool's
  actual schema; do not pass `run_in_background` or `team_name` unless it supports them.
  Each prompt includes its full canonical task, exact snapshot/diff/report paths,
  concrete `WORKTREE_ROOT`, `WORKTREE_ID`, `RUN_ROOT`, `PREFIX`, `SNAPSHOT`, scope,
  source budget and `Load skills:` entries. Resolve installed skill names by suffix,
  never by assuming the `complete:` namespace.
- **Agent contracts**: use these general-purpose agents rather than specialized
  document-collector/program-reviewer/validator agents whose standalone routines add
  overlapping work. Reviewers do not create nested teams or delegate verification.
  Do not require `TeamCreate`; use it only if available and required by that runtime.
- **Completion**: wait for background completion notifications. Follow the canonical
  progress deadlines and bounded recovery behavior if a role stalls or fails. Do not poll files or treat a partial file
  as a finished report. The coordinator reads the reports and writes both final outputs.
- **Adjudication**: only for the specific material uncertainty allowed in Phase 5,
  launch a general-purpose agent with the remaining source budget and the disputed
  question. No automatic verifier per finding, source, page or parameter.
- **Coordinator reads**: the diff, code, source evidence and findings are available
  to the coordinator as needed. There is no summary-only context restriction here.
