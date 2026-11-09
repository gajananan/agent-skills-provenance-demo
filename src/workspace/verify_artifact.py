#!/usr/bin/env python3
"""Whole-artifact verification: the consumer-side COMPLETENESS gate.

nono verifies that each covered file that is PRESENT is signed and unmodified.
This check adds the completeness that this demo's glob-based, per-file config does
not establish on its own: it enforces the artifact's expected contents against a
SIGNED inventory, and rejects anything unexpected.

Steps:
  1. The inventory's authenticity is anchored in nono (`nono trust verify
     .nono-inventory`), so it cannot be forged or edited.
  2. Parse and validate the inventory (64-hex digest, relative paths, no "..",
     no duplicates).
  3. Authenticate artifact-spec.json against the inventory BEFORE trusting the
     roots it declares.
  4. Every listed file must be a present, regular (non-symlink) file whose sha256
     matches (catches removal, modification and symlink substitution).
  5. No unexpected entry may exist under the roots: symlinks and special files are
     rejected; only the exact .bundle sidecars of listed files and the inventory's
     own sidecar are exempt (catches additions of any type).

Exit 0 only when the artifact matches the signed inventory exactly.
"""
import hashlib
import json
import os
import re
import subprocess
import sys

SPEC = "artifact-spec.json"
INVENTORY = ".nono-inventory"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg):
    print(f"verify-artifact: FAIL, {msg}", file=sys.stderr)


def main():
    if not os.path.isfile(INVENTORY) or os.path.islink(INVENTORY):
        fail(f"{INVENTORY} is missing or not a regular file")
        return 3

    # 1. Authenticity of the inventory itself, anchored in nono.
    rc = subprocess.run(
        ["nono", "trust", "verify", INVENTORY],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode
    if rc != 0:
        fail("the inventory's signature did not verify")
        return 4

    # 2. Parse and validate the inventory.
    listed = {}
    with open(INVENTORY, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("  ", 1)
            if len(parts) != 2:
                fail(f"inventory line {n} is malformed")
                return 5
            digest, path = parts[0], parts[1]
            if not HEX64.match(digest):
                fail(f"inventory line {n}: bad digest format")
                return 5
            if path.startswith("/") or ".." in path.split("/") or path.strip() != path:
                fail(f"inventory line {n}: unsafe path {path!r}")
                return 5
            if path in listed:
                fail(f"inventory: duplicate entry {path!r}")
                return 5
            listed[path] = digest

    # 3. Authenticate artifact-spec.json against the inventory before using it.
    if SPEC not in listed:
        fail(f"{SPEC} is not covered by the inventory")
        return 6
    if os.path.islink(SPEC) or not os.path.isfile(SPEC) or sha256(SPEC) != listed[SPEC]:
        fail(f"{SPEC} is missing, a symlink, or does not match the inventory")
        return 6
    with open(SPEC, encoding="utf-8") as f:
        spec = json.load(f)

    problems = []

    # 4. Listed files present, regular, unmodified.
    for path, digest in listed.items():
        if os.path.islink(path):
            problems.append(f"symlink:  {path}")
        elif not os.path.isfile(path):
            problems.append(f"removed:  {path}")
        elif sha256(path) != digest:
            problems.append(f"modified: {path}")

    # 5. No unexpected entry under the roots.
    exempt = {p + ".bundle" for p in listed}
    exempt.add(INVENTORY)
    exempt.add(INVENTORY + ".bundle")

    def scan(p):
        if os.path.islink(p):
            problems.append(f"symlink:  {p}")
            return
        if os.path.isdir(p):
            for name in sorted(os.listdir(p)):
                scan(os.path.join(p, name))
        elif os.path.isfile(p):
            if p in listed or p in exempt:
                return
            problems.append(f"added:    {p}")
        else:
            problems.append(f"special:  {p}")

    for rf in spec.get("root_files", []):
        if os.path.lexists(rf):
            scan(rf)
    for d in spec.get("skill_dirs", []):
        if os.path.lexists(d):
            scan(d)

    if problems:
        fail("the artifact does not match the signed inventory:")
        for p in sorted(set(problems)):
            print(f"  {p}", file=sys.stderr)
        return 7

    print(f"verify-artifact: OK, {len(listed)} files match the signed inventory "
          "(no adds, removals, symlinks or modifications)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
