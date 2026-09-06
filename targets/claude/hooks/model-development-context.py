"""Add country-model skill-loading context without an extra model call.

Claude hook contract: https://code.claude.com/docs/en/hooks#sessionstart
This reminder does not itself load a skill or certify that a worker did so.
"""

import json
from pathlib import Path
import sys


def main():
    event = json.load(sys.stdin)
    name = event.get("hook_event_name")
    if name not in {"SessionStart", "SubagentStart"}:
        return
    cwd = Path(event["cwd"]).resolve()
    packages = ("policyengine_us", "policyengine_uk", "policyengine_canada")
    if not any(
        (root / package).is_dir()
        for root in (cwd, *cwd.parents)
        for package in packages
    ):
        return
    context = (
        "This is a PolicyEngine country-model repository. Model implementation, "
        "test-authoring and review roles, including encoding/review coordinators, "
        "require policyengine-model-development loaded with the Skill tool in each "
        "agent's own context before substantive work, followed by its "
        "relevant references. Resolve the available installed skill name and follow "
        "references/agent-loading.md: SKILLS_READY includes successful load evidence; "
        "SKILLS_BLOCKED identifies an unavailable skill/tool before substantive work. "
        "A parent load, dispatch instruction or agent type is not proof of a worker "
        "load. The active workflow owns agent selection and stages; this reminder "
        "does not add validators, fixers or pushers, or itself load any skills."
    )
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": name,
                    "additionalContext": context,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
