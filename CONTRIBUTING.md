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

## Testing

Run:

```bash
uv run pytest
python3 scripts/build_claude_wrapper.py --source-root . --output-root build/policyengine-claude
```

## Versioning

The wrapper version currently lives in:

- `targets/claude/marketplace.template.json`
- `bundles/*.json`

Keep them aligned when cutting a release.
