#!/usr/bin/env python3
"""Emit the nono policy include patterns from artifact-spec.json, one per line.

Single source of truth: lib/common.sh (local policy) and ci/sign-skills.yml both
read this. Root files are included only when they exist on disk, because a missing
literal include can block startup on macOS under deny; optional files (such as
AGENTS.md) are therefore covered only when present.
"""
import json
import os

with open("artifact-spec.json", encoding="utf-8") as fh:
    spec = json.load(fh)

patterns = [f for f in spec["root_files"] if os.path.exists(f)]
patterns.append(spec["inventory_file"])
for d in spec["skill_dirs"]:
    for ext in spec["skill_extensions"]:
        patterns.append(f"{d}/**/*.{ext}")

print("\n".join(patterns))
