#!/usr/bin/env python3
"""Emit the actual files to per-file sign, from artifact-spec.json, one per line.

These are the files the policy globs cover: existing root_files, the inventory,
and files under skill_dirs whose extension is in skill_extensions. Symlinks and
.bundle sidecars are excluded. ci/sign-skills.yml uses this so the signed set
and the policy both derive from the one spec.
"""
import json
import os

with open("artifact-spec.json", encoding="utf-8") as fh:
    spec = json.load(fh)

exts = set(spec["skill_extensions"])
out = [f for f in spec["root_files"] if os.path.isfile(f) and not os.path.islink(f)]

inv = spec["inventory_file"]
if os.path.isfile(inv) and not os.path.islink(inv):
    out.append(inv)

for d in spec["skill_dirs"]:
    for dirpath, dirs, names in os.walk(d):
        dirs[:] = [x for x in dirs if not os.path.islink(os.path.join(dirpath, x))]
        for n in names:
            p = os.path.join(dirpath, n)
            if os.path.islink(p) or p.endswith(".bundle"):
                continue
            if n.rsplit(".", 1)[-1] in exts:
                out.append(p)

print("\n".join(sorted(set(out))))
