#!/usr/bin/env python3
"""Deterministic agent stand-in (NOT an LLM) that GENUINELY consumes the skill.

This is the wrapped process. nono verifies the covered instruction files before
it starts, so by the time this runs the files it reads are the ones the publisher
signed. Unlike a live model, its journey is reproducible on every run.

It does not pretend: it opens the selected SKILL.md, parses it, validates it, and
derives the command to run from the skill's own documented step, checked against a
strict allowlist. If SKILL.md is missing, malformed, or does not document the
expected step, it FAILS with a nonzero exit instead of claiming success. A run
marker on stdout proves the process actually executed.
"""
import glob
import os
import re
import shlex
import subprocess
import sys

RUN_MARKER = os.environ.get("DEMO_RUN_MARKER", "WRAPPED_PROCESS_RAN")

# The only commands this agent is permitted to run, keyed by the skill name it
# finds in SKILL.md. The documented command must EXACTLY equal the allowlisted
# argv (parsed, not substring-matched); both must agree.
ALLOWLIST = {
    "repo-insights": ["python3", ".claude/skills/repo-insights/scripts/insights.py"],
}


def parse_skill(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    name_m = re.search(r"^name:\s*(.+?)\s*$", text, re.MULTILINE)
    name = name_m.group(1).strip() if name_m else None
    cmd_m = re.search(r"`([^`]*scripts/[^`]+\.py)`", text)
    documented = cmd_m.group(1).strip() if cmd_m else None
    return name, documented


def fail(msg):
    print(f"agent: FAIL, {msg}", file=sys.stderr)
    return False


def main():
    print("agent: discovering skills under .claude/skills ...")
    skills = sorted(glob.glob(".claude/skills/*/SKILL.md"))
    for s in skills:
        print("  found:", s)

    target = ".claude/skills/repo-insights/SKILL.md"
    if target not in skills:
        return 2 if fail(f"expected skill {target} is not present (nothing to consume)") else 2

    print(f"agent: opening and reading {target} ...")
    try:
        name, documented = parse_skill(target)
    except OSError as e:
        return 2 if fail(f"could not open {target}: {e}") else 2

    if not name:
        return 3 if fail("SKILL.md has no 'name' in its front matter") else 3

    allowed_argv = ALLOWLIST.get(name)
    if not allowed_argv:
        return 4 if fail(f"skill '{name}' is not on the agent's allowlist") else 4

    # Exact argv match: parse the documented command and require it to equal the
    # allowlisted command exactly. Extra arguments, a different path or a shell
    # operator all change the token list and are rejected.
    try:
        documented_argv = shlex.split(documented or "")
    except ValueError:
        documented_argv = []
    if documented_argv != allowed_argv:
        return 5 if fail(f"documented command {documented!r} does not exactly match the allowlist {allowed_argv}") else 5

    print(f"agent: documented command exactly matches the allowlist: {documented}")
    print("agent: running it in the sandbox ...")
    # Execute with this interpreter for portability; the argv is already proven
    # equal to the allowlist, so only the interpreter name is substituted.
    rc = subprocess.run([sys.executable] + allowed_argv[1:]).returncode

    # Proof-of-execution marker the demo harness asserts on. Absent if nono
    # refused to launch this process at all.
    print(f"{RUN_MARKER} skill={name} rc={rc}")
    print(f"agent: skill finished (rc={rc}); the agent stayed within its sandbox.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
