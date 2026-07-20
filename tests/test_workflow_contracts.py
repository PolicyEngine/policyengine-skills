"""Contract tests for the canonical-workflow + thin-launcher architecture (issue #62).

Each consolidated workflow has exactly one behavioral definition —
skills/<name>/references/workflow.md. The skill's SKILL.md is the cross-client
launcher (Claude Code gives a skill precedence over a same-named command, so the skill
is the entry point on both surfaces); references/claude-launcher.md carries the
Claude-only role/agent mapping; targets/claude/commands/<name>.md is a compatibility
stub that just invokes the skill on older Claude Code versions. These tests keep that
architecture from silently regressing into per-surface copies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / "targets" / "claude" / "commands"
SKILLS = REPO_ROOT / "skills"
BUNDLES = REPO_ROOT / "bundles"

# Workflows migrated to the canonical + thin-launcher architecture. encode-policy-v2
# joins this list in its own PR (production-sensitive; migrated last).
CONSOLIDATED = ("review-program", "fix-pr")

# Runtime-specific orchestration tokens. Claude tokens may appear only in the Claude
# launcher; Codex tokens only in SKILL.md. The canonical references must use neither.
CLAUDE_TOKENS = (
    "$ARGUMENTS",
    "TeamCreate",
    "TaskCreate",
    "AskUserQuestion",
    "subagent_type",
    "run_in_background",
    "CLAUDE_PLUGIN_ROOT",
)
CODEX_TOKENS = ("`worker`", "`explorer`")


def canonical_path(name: str) -> Path:
    return SKILLS / name / "references" / "workflow.md"


def test_each_consolidated_workflow_has_one_canonical_definition() -> None:
    for name in CONSOLIDATED:
        canonical = canonical_path(name)
        assert canonical.exists(), f"{name}: missing canonical workflow.md"
        text = canonical.read_text()
        assert "(canonical)" in text.splitlines()[0], (
            f"{name}: canonical workflow.md must declare itself canonical in its title"
        )
        # Roles are folded into workflow.md; the old role-simulation file is gone.
        assert not (SKILLS / name / "references" / "subagents.md").exists(), (
            f"{name}: references/subagents.md should be deleted after consolidation"
        )


def test_launchers_point_at_the_canonical_workflow() -> None:
    for name in CONSOLIDATED:
        command = (COMMANDS / f"{name}.md").read_text()
        skill = (SKILLS / name / "SKILL.md").read_text()
        adapter = (SKILLS / name / "references" / "claude-launcher.md").read_text()
        # The command is a compatibility stub that routes to the skill by name.
        assert f"`{name}` skill" in command, (
            f"{name}: command stub must route to the skill"
        )
        assert f"skills/{name}/references/workflow.md" in command, (
            f"{name}: command stub must name the canonical workflow path"
        )
        # The skill is the cross-client launcher.
        assert "references/workflow.md" in skill, (
            f"{name}: SKILL.md must reference the canonical workflow"
        )
        assert "references/claude-launcher.md" in skill, (
            f"{name}: SKILL.md must route Claude Code to the Claude adapter"
        )
        assert "workflow.md" in adapter, (
            f"{name}: Claude adapter must point back at the canonical workflow"
        )


def test_launchers_do_not_duplicate_phase_definitions() -> None:
    # Phases are defined once, in the canonical document. A launcher or adapter that
    # grows its own "## Phase N" sections is recreating the duplication this
    # architecture removed.
    for name in CONSOLIDATED:
        canonical = canonical_path(name).read_text()
        assert re.search(r"^## Phase 0", canonical, re.M), (
            f"{name}: canonical workflow must define the phases"
        )
        for launcher in (
            (COMMANDS / f"{name}.md").read_text(),
            (SKILLS / name / "SKILL.md").read_text(),
            (SKILLS / name / "references" / "claude-launcher.md").read_text(),
        ):
            assert not re.search(r"^#+ Phase \d", launcher, re.M), (
                f"{name}: launchers must not define phases"
            )


def test_canonical_workflow_is_surface_neutral() -> None:
    # workflow.md serves both runtimes and may name neither's mechanics. The Claude
    # adapter (claude-launcher.md) is exempt from the Claude-token ban — holding those
    # tokens is its whole job — but must not name Codex mechanics.
    for name in CONSOLIDATED:
        workflow = canonical_path(name).read_text()
        for token in CLAUDE_TOKENS + CODEX_TOKENS:
            assert token not in workflow, (
                f"skills/{name}/references/workflow.md contains runtime-specific "
                f"token {token}"
            )
        adapter = (SKILLS / name / "references" / "claude-launcher.md").read_text()
        for token in CODEX_TOKENS:
            assert token not in adapter, (
                f"skills/{name}/references/claude-launcher.md contains Codex "
                f"token {token}"
            )


def test_codex_skill_bodies_avoid_claude_tokens() -> None:
    for name in CONSOLIDATED:
        text = (SKILLS / name / "SKILL.md").read_text()
        for token in CLAUDE_TOKENS:
            assert token not in text, (
                f"skills/{name}/SKILL.md contains Claude-only token {token}"
            )


def required_agents(name: str) -> set[str]:
    """Unprefixed specialized agent names from the Claude adapter's role table."""
    adapter = (SKILLS / name / "references" / "claude-launcher.md").read_text()
    table = adapter.split("## Role → agent type", 1)[1]
    agents = set()
    for row in re.finditer(r"^\|[^|]+\|\s*`([a-z0-9-]+)`", table, re.M):
        if row.group(1) != "general-purpose":
            agents.add(row.group(1))
    return agents


def test_bundles_ship_the_agents_behind_every_workflow_skill() -> None:
    # Agent names in claude-launcher.md are unprefixed and resolved by suffix at
    # runtime, so any bundle that ships a consolidated workflow skill must also ship
    # an agent file for every specialized agent the adapter names.
    for name in CONSOLIDATED:
        needed = required_agents(name)
        assert needed, f"{name}: no specialized agents parsed from claude-launcher.md"
        for bundle_path in sorted(BUNDLES.glob("*.json")):
            bundle = json.loads(bundle_path.read_text())
            if f"./skills/{name}" not in bundle.get("skills", []):
                continue
            shipped = {Path(a).stem for a in bundle.get("agents", [])}
            missing = needed - shipped
            assert not missing, (
                f"{bundle_path.name} ships skills/{name} but lacks agents: "
                f"{sorted(missing)}"
            )


def test_bundles_ship_the_skill_behind_every_thin_command() -> None:
    # Generic closure rule: if a bundle includes commands/<name>.md and skills/<name>
    # exists in the repo, the bundle must also include that skill — the thin command
    # cannot run without its canonical references.
    for bundle_path in sorted(BUNDLES.glob("*.json")):
        bundle = json.loads(bundle_path.read_text())
        skills = set(bundle.get("skills", []))
        for command_entry in bundle.get("commands", []):
            name = Path(command_entry).stem
            if (SKILLS / name).is_dir():
                assert f"./skills/{name}" in skills, (
                    f"{bundle_path.name} ships commands/{name}.md without "
                    f"./skills/{name}"
                )


# --- Deleted-skill reference lint -------------------------------------------------

# Skills deleted in the July 2026 catalog rebuild (#61). Their content now lives in
# skills/policyengine-model-development/references/. No file may reference them.
DELETED_SKILLS = (
    "policyengine-parameter-patterns",
    "policyengine-variable-patterns",
    "policyengine-testing-patterns",
    "policyengine-code-style",
    "policyengine-code-organization",
    "policyengine-vectorization",
    "policyengine-aggregation",
    "policyengine-period-patterns",
    "policyengine-review-patterns",
)

# Burn-down list: files that still carry pre-rebuild skill references. Shrink this list
# as encode-policy-v2 is consolidated (its PR) and the agents/commands are migrated
# (follow-up); never add to it.
DEAD_REFERENCE_BURNDOWN = {
    "skills/encode-policy-v2/SKILL.md",
    "skills/encode-policy-v2/references/subagents.md",
    "skills/encode-policy-v2/references/workflow.md",
    "targets/claude/agents/country-models/ci-fixer.md",
    "targets/claude/agents/country-models/document-collector.md",
    "targets/claude/agents/country-models/edge-case-generator.md",
    "targets/claude/agents/country-models/implementation-validator.md",
    "targets/claude/agents/country-models/program-reviewer.md",
    "targets/claude/agents/country-models/rules-engineer.md",
    "targets/claude/agents/country-models/test-creator.md",
    "targets/claude/agents/dashboard/backend-builder.md",
    "targets/claude/agents/dashboard/dashboard-architecture-validator.md",
    "targets/claude/agents/dashboard/dashboard-integrator.md",
    "targets/claude/agents/dashboard/dashboard-plan-validator.md",
    "targets/claude/agents/dashboard/dashboard-planner.md",
    "targets/claude/agents/dashboard/dashboard-scaffold.md",
    "targets/claude/agents/dashboard/frontend-builder.md",
    "targets/claude/agents/reference-validator.md",
    "targets/claude/commands/backdate-program.md",
    "targets/claude/commands/encode-policy-v2.md",
    "targets/claude/commands/encode-reform.md",
}

# Precise skill-reference forms whose target must exist as a skills/ directory.
SKILL_REFERENCE_PATTERNS = (
    re.compile(r"\$(policyengine-[a-z0-9-]+)"),
    re.compile(r"complete:(policyengine-[a-z0-9-]+)"),
    re.compile(r"Skill: (policyengine-[a-z0-9-]+)"),
)


def iter_lintable_files():
    for root in (SKILLS, REPO_ROOT / "targets" / "claude"):
        yield from sorted(root.rglob("*.md"))


def deleted_skill_hits(text: str) -> list[str]:
    return [dead for dead in DELETED_SKILLS if dead in text]


def unresolvable_references(text: str, existing: set[str]) -> list[str]:
    hits = []
    for pattern in SKILL_REFERENCE_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1).rstrip("-")
            # Pre-rebuild installs used a `-skill` directory suffix; a suffixed
            # reference that resolves to a current skill is legacy naming, not rot.
            if name.endswith("-skill"):
                name = name[: -len("-skill")]
            if name not in existing:
                hits.append(match.group(0))
    return hits


def existing_skill_names() -> set[str]:
    return {p.name for p in SKILLS.iterdir() if p.is_dir()}


def test_no_references_to_deleted_skills() -> None:
    offenders = []
    for path in iter_lintable_files():
        rel = str(path.relative_to(REPO_ROOT))
        if rel in DEAD_REFERENCE_BURNDOWN:
            continue
        for dead in deleted_skill_hits(path.read_text()):
            offenders.append(f"{rel}: {dead}")
    assert not offenders, "references to deleted skills:\n" + "\n".join(offenders)


def test_explicit_skill_references_resolve() -> None:
    existing = existing_skill_names()
    offenders = []
    for path in iter_lintable_files():
        rel = str(path.relative_to(REPO_ROOT))
        if rel in DEAD_REFERENCE_BURNDOWN:
            continue
        for ref in unresolvable_references(path.read_text(), existing):
            offenders.append(f"{rel}: {ref}")
    assert not offenders, "unresolvable skill references:\n" + "\n".join(offenders)


def test_burndown_list_does_not_go_stale() -> None:
    # Every burn-down entry must still exist and still contain an offending
    # reference under at least one lint; once a file is cleaned, remove it from
    # the list so the lints cover it.
    existing = existing_skill_names()
    for rel in sorted(DEAD_REFERENCE_BURNDOWN):
        path = REPO_ROOT / rel
        assert path.exists(), f"burn-down entry no longer exists: {rel}"
        text = path.read_text()
        assert deleted_skill_hits(text) or unresolvable_references(text, existing), (
            f"burn-down entry is clean — remove it from the list: {rel}"
        )
