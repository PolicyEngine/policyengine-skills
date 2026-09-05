# Claude Code launcher: encode-policy-v2

Read the canonical [workflow.md](workflow.md). This adapter maps capabilities without
adding stages, audits, test commands or approval prompts.

- Parse raw arguments, including local-only mode and source reuse/budget, as specified.
- The workflow is registered only as a skill, without a same-named command stub. Resolve
  its installed base directory from the Skill result. Pass the installed review-program
  directory and canonical paths to the fresh review coordinator; do not search the
  filesystem or recursively invoke a compatibility stub.
- Use the runtime's user-question tool for unresolved material scope/reuse/repair
  decisions. Batch related questions within its actual capacity; honor prior decisions.
- The coordinator performs research, requirements, coverage/validation, Git and reporting.
  It may inspect code and evidence directly. Do not delegate those routine steps merely
  to preserve a summary-only context rule.
- For the substantive `implementer` and `test-author`, use `general-purpose` agents with
  the full canonical role, exact owned paths, artifact contracts, relevant skill sections,
  concrete `WORKTREE_ROOT`, `WORKTREE_ID`, `RUN_ROOT`, `PREFIX` and local/publication mode.
  A specialized standalone agent is not required and must not add its own audits,
  dependency sync, formatting, test suites, commits or pushes to this role contract.
- Retain the same workers for repairs. Start test-source analysis while implementation
  runs when independent; finalize tests only against the actual variable contract. Use
  runtime-supported messaging, or coordinator handoffs when unavailable. Never assume
  team, background, monitor or message parameters exist.
- Every model worker must have access to the `Skill` tool and invoke the installed
  `policyengine-model-development` skill by its resolved name before work, then read its
  role references. Include the canonical loading contract in dispatch and require the
  successful Skill result in `SKILLS_READY`; a `Load skills:` list alone does not load
  anything. If the selected agent lacks Skill access or the skill is unavailable, apply
  `SKILLS_BLOCKED` instead of silently using a general-purpose agent without it.
- Wait for completion notifications with the canonical progress/recovery bounds. Routine
  progress can arrive by message or artifact; a partial report is not DONE. If delegation
  is unavailable, perform the roles directly, retaining independent review context.
- Invoke review-program in a fresh `general-purpose` coordinator with its exact local or
  published arguments, approved scope and source manifest. It owns its reviewer topology
  and artifact contracts. Leave sufficient runtime capacity for those reviewers.
- Only the encoding coordinator stages, commits, pushes and writes GitHub state. In
  `--local`, it may make local implementation/review-fix commits but never creates an
  issue/PR, pushes or posts comments. Otherwise use explicit verified targets and the
  canonical pre-edit head check; don't map Git work to a standalone pusher routine.
- Resolve skill names by the installed suffix, not an assumed plugin namespace. Load
  only the references needed for the assigned task.
