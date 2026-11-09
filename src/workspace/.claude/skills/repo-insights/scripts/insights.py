#!/usr/bin/env python3
"""repo-insights helper: count files by extension in this repository."""
import os
from collections import Counter

counts = Counter()
for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
    for name in files:
        counts[os.path.splitext(name)[1] or "(none)"] += 1

print("repo-insights: file types in this repository")
for ext, n in counts.most_common(10):
    print(f"  {ext:10} {n}")
