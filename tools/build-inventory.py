#!/usr/bin/env python3
"""Build the signed whole-artifact inventory from artifact-spec.json.

Hashes every file under the spec's roots (root_files that exist + skill_dirs,
recursively, any type), excluding .bundle sidecars and the inventory itself.
Rejects symlinks and non-regular files, so the inventory describes real files
only and cannot be widened through a symlinked directory. Run from the artifact
root BEFORE signing.
"""
import hashlib
import json
import os
import sys

SPEC = "artifact-spec.json"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(spec):
    inv = spec["inventory_file"]
    files, problems = [], []

    def visit(p):
        if os.path.islink(p):
            problems.append(f"symlink: {p}")
            return
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                visit(os.path.join(p, name))
        elif os.path.isfile(p):
            if p.endswith(".bundle") or os.path.basename(p) == inv:
                return
            files.append(p)
        else:
            problems.append(f"special: {p}")

    for rf in spec["root_files"]:
        if os.path.lexists(rf):
            visit(rf)
    for d in spec["skill_dirs"]:
        if os.path.lexists(d):
            visit(d)
    return sorted(set(files)), problems


def main():
    with open(SPEC, encoding="utf-8") as f:
        spec = json.load(f)
    files, problems = collect(spec)
    if problems:
        for p in problems:
            print(f"build-inventory: refusing, {p}", file=sys.stderr)
        return 2
    inv = spec["inventory_file"]
    with open(inv, "w", encoding="utf-8") as out:
        out.write("# nono whole-artifact inventory: sha256  path\n")
        for p in files:
            out.write(f"{sha256(p)}  {p}\n")
    print(f"build-inventory: wrote {inv} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
