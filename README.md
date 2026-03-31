# policyengine-skills

Portable PolicyEngine skills and Claude wrapper source.

This repository is the canonical source of truth for:

- reusable PolicyEngine `SKILL.md` content
- bundle definitions for install profiles like `complete` and `app-development`
- Claude-only wrapper assets such as commands, agents, and hooks

The public Claude marketplace repo stays at `PolicyEngine/policyengine-claude`, but it is generated from this repository.

## Repository layout

```text
policyengine-skills/
├── bundles/                 # Bundle manifests for Claude install profiles
├── skills/                  # Portable skill folders with SKILL.md
├── targets/claude/          # Claude-only wrapper assets
├── scripts/                 # Build and install helpers
└── tests/                   # Wrapper build tests
```

## Install

### Codex

Codex can consume the portable skills directly:

```bash
git clone https://github.com/PolicyEngine/policyengine-skills.git
cd policyengine-skills
./scripts/install_codex.sh
```

This installs symlinks into `~/.codex/skills`.

### Claude Code

Claude Code users should install the generated wrapper:

```bash
/plugin marketplace add PolicyEngine/policyengine-claude
/plugin install complete@policyengine-claude
```

For local testing of just the portable skills:

```bash
git clone https://github.com/PolicyEngine/policyengine-skills.git
cd policyengine-skills
./scripts/install_claude_skills.sh
```

This installs symlinks into `~/.claude/skills`.

## Development

All source edits happen here.

Useful commands:

```bash
uv run pytest
python3 scripts/build_claude_wrapper.py --source-root . --output-root build/policyengine-claude
```

The generated wrapper repo must not be edited by hand.

## Sync to policyengine-claude

`targets/claude/` contains the Claude-only assets that are overlaid on top of the shared skills.

GitHub Actions in this repo:

- validate bundle manifests and the wrapper build
- generate the Claude wrapper
- sync the generated output into `PolicyEngine/policyengine-claude`

## MCP

This repository does not ship a standalone MCP server yet. If PolicyEngine tool integrations move to MCP later, they should live under `mcp/`.
