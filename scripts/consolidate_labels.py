"""One-off: rewrite every post's `tags` to the taxonomy in config/labels.yml.

Run from the repo root: python scripts/consolidate_labels.py
Tags already in the taxonomy are kept; retired tags follow `aliases`; anything
unknown is reported and dropped. A post ends up with 1-4 labels.
"""
from __future__ import annotations

import collections
import glob
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


def main() -> int:
    tax = yaml.safe_load((ROOT / "config" / "labels.yml").read_text(encoding="utf-8"))
    allowed = {label for labels in tax["labels"].values() for label in labels}
    aliases = tax["aliases"]
    missing: set[str] = set()
    changed = 0
    for path in sorted(glob.glob(str(ROOT / "content" / "posts" / "*.md"))):
        text = Path(path).read_text(encoding="utf-8")
        m = FM_RE.match(text)
        fm = yaml.safe_load(m.group(1))
        new: list[str] = []
        for tag in fm.get("tags", []):
            if tag in allowed:
                targets = [tag]
            elif tag in aliases:
                targets = aliases[tag]
            else:
                missing.add(tag)
                targets = []
            for t in targets:
                if t not in new:
                    new.append(t)
        if not new:
            new = [tax["labels"][fm["pillar"]][0]]
        new = new[:4]
        if new == fm.get("tags"):
            continue
        block = "tags:\n" + "".join(f"- {t}\n" for t in new)
        head = m.group(0)
        head2 = re.sub(r"^tags:.*?(?=^[a-z_]+:)", block, head, count=1, flags=re.S | re.M)
        if head2 == head:
            print(f"could not rewrite tags in {path}")
            return 1
        Path(path).write_text(head2 + text[len(head):], encoding="utf-8", newline="\n")
        changed += 1
    counts = collections.Counter()
    for path in glob.glob(str(ROOT / "content" / "posts" / "*.md")):
        fm = yaml.safe_load(FM_RE.match(Path(path).read_text(encoding="utf-8")).group(1))
        assert 1 <= len(fm["tags"]) <= 4 and all(t in allowed for t in fm["tags"]), path
        counts.update(fm["tags"])
    print(f"changed {changed} posts; unknown tags dropped: {sorted(missing) or 'none'}")
    print(f"{len(counts)} labels in use: {counts.most_common()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
