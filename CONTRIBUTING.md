# Contributing

## Source of truth

Make all content changes in `policyengine-skills`.

Do not edit `PolicyEngine/policyengine-claude` directly unless you are fixing a sync emergency. The normal workflow is:

1. Edit portable skills, bundles, or `targets/claude` in this repo.
2. Run tests.
3. Run the wrapper build locally if the change affects Claude packaging.
4. Merge here.
5. Let CI sync the generated wrapper repo.

## Bundle manifests

Claude install profiles are defined in `bundles/*.json`.

Each bundle file lists:

- `skills`
- `commands`
- `agents`
- `hooks`

All paths are repository-relative and are validated during test/build.

## Claude wrapper assets

Claude-only files live in `targets/claude/`:

- `agents/`
- `commands/`
- `hooks/`
- `marketplace.template.json`
- `README.md`

## Skill authoring rules

See [skills/README.md](skills/README.md) for the full list. The load-bearing ones:

1. **Verify every API claim** by executing it or reading the live source before
   writing it down. Nothing goes in from memory.
2. **Mark runnable examples**: `<!-- verify -->` on the line before a ```python
   fence makes CI execute it (fast, household-tier, asserted).
   `<!-- verify: slow -->` marks population-scale examples (run at authoring time
   and via `PE_SKILLS_RUN_SLOW=1 uv run pytest tests/test_skill_examples.py`).
3. **Anti-rot lint**: `tests/test_no_stale_references.py` bans known-dead patterns.
   Deliberate history notes — and explicitly-scoped engine-development examples of
   patterns banned for analysis — take `<!-- stale-ok -->` on the preceding line.
4. Descriptions stay ≤1024 characters (Codex hard limit).

## Testing

Run:

```bash
uv run pytest --ignore=tests/test_skill_examples.py
python3 scripts/build_claude_wrapper.py --source-root . --output-root build/policyengine-claude

# Example harness (needs policyengine installed):
uv run pytest tests/test_skill_examples.py
```

## Keeping the website in sync

policyengine.org/us/ai-agents (in `PolicyEngine/policyengine-app-v2`,
`website/src/app/[countryId]/ai-agents/`) displays catalog stats from a
checked-in data module. When skills/agents/commands/bundles are added or removed,
regenerate the counts and update that module in an app-v2 PR:

```bash
python3 scripts/export_site_stats.py
```

## Versioning

The wrapper version lives in `targets/claude/marketplace.template.json`;
every `bundles/*.json` must carry the same version
(`tests/test_build_claude_wrapper.py` enforces alignment).
