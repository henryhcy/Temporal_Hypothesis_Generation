"""Copy the generated .tex reports into a local clone of the Overleaf project
and push them, WITHOUT disturbing the rest of the Overleaf project.

This is the multi-repo -> one-Overleaf-project workflow: the Overleaf project is
its own git repo (git.overleaf.com/<id>); we treat it as the destination and
only overwrite the two generated files, so other repos feeding the same project
are unaffected. Never make git.overleaf.com a remote of THIS code repo -- that
would overwrite the whole project.

Prerequisites (one time):
    # clone the Overleaf project somewhere OUTSIDE this repo; enter your Overleaf
    # git token when prompted (username = your Overleaf email, or 'git')
    git clone https://git.overleaf.com/<project-id> ../overleaf-aaai

Each update:
    python scripts/make_findings_tex.py         # regenerates Findings_and_Templates.tex
    python scripts/final_templates.py            # regenerates Final_Template_Design.tex
    python scripts/sync_overleaf.py ../overleaf-aaai [--dest sections] [--push]

By default it stages/commits/copies but does NOT push, so you can review; add
--push to push. Auth is the Overleaf clone's own git credential -- this script
never sees your token.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_SRC = _REPO / "docs" / "reference"

# The generated files to mirror into the Overleaf project.
FILES = ["Findings_and_Templates.tex", "Final_Template_Design.tex"]


def _git(clone: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(clone), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("overleaf_clone", type=Path,
                    help="path to your local clone of the Overleaf project")
    ap.add_argument("--dest", default=".",
                    help="subfolder within the Overleaf project to copy into "
                         "(default: project root)")
    ap.add_argument("--push", action="store_true",
                    help="push after committing (default: commit only, review first)")
    ap.add_argument("--message", default="Update generated template report(s)")
    args = ap.parse_args()

    clone = args.overleaf_clone.resolve()
    if not (clone / ".git").exists():
        sys.exit(f"error: {clone} is not a git repo (clone the Overleaf project first)")
    dest = clone / args.dest
    dest.mkdir(parents=True, exist_ok=True)

    missing = [f for f in FILES if not (_SRC / f).exists()]
    if missing:
        sys.exit(f"error: missing generated files (run the generators first): {missing}")

    for f in FILES:
        shutil.copy2(_SRC / f, dest / f)
        print(f"copied {f} -> {dest / f}")

    rel = [str((Path(args.dest) / f)) for f in FILES]
    _git(clone, "add", *rel)
    status = _git(clone, "status", "--porcelain", *rel)
    if not status:
        print("no changes to sync (Overleaf already up to date).")
        return 0
    _git(clone, "commit", "-m", args.message)
    print("committed to the Overleaf clone.")
    if args.push:
        print(_git(clone, "push") or "pushed to Overleaf.")
    else:
        print("not pushed. review, then: git -C "
              f"{clone} push   (or re-run with --push)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
