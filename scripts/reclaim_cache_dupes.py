#!/usr/bin/env python3
"""Reclaim disk from rsync-duplicated HF cache models.

BSD rsync (no -H) broke the HF cache dedup on the NAS-grabbed models: the weight
bytes now exist as REAL files in BOTH snapshots/<sha>/ and blobs/. oMLX loads via
~/.omlx/models/<name> -> snapshots/<sha>/, so for those models blobs/ is pure
duplicate and can be removed.

SAFETY: a model is only reclaimed when EVERY file in its snapshot dir is a real
file (not a symlink into blobs/). Properly symlink-deduped caches (champion + the
two `hf download` gaps) have snapshot SYMLINKS -> blobs/, so deleting blobs would
break them — those are detected and SKIPPED automatically.

Usage:
  python scripts/reclaim_cache_dupes.py            # dry-run (report only)
  python scripts/reclaim_cache_dupes.py --apply    # delete redundant blobs/
"""
from __future__ import annotations
import os, sys, shutil

CACHE = os.path.expanduser("~/.cache/huggingface/hub")
APPLY = "--apply" in sys.argv

def du(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except OSError:
                pass
    return total

def snap_dir(model_dir: str) -> str | None:
    root = os.path.join(model_dir, "snapshots")
    if not os.path.isdir(root):
        return None
    subs = [os.path.join(root, d) for d in os.listdir(root)
            if os.path.isdir(os.path.join(root, d))]
    return subs[0] if subs else None

def snapshot_is_real(snap: str) -> bool:
    """True iff the snapshot is self-contained (no entry is a symlink)."""
    entries = os.listdir(snap)
    if not entries:
        return False
    return not any(os.path.islink(os.path.join(snap, e)) for e in entries)

def main() -> int:
    total_reclaim = 0
    print(f"{'MODEL':52s} {'state':10s} {'blobs':>8s}  action")
    print("-" * 90)
    for name in sorted(os.listdir(CACHE)):
        if not name.startswith("models--"):
            continue
        mdir = os.path.join(CACHE, name)
        blobs = os.path.join(mdir, "blobs")
        snap = snap_dir(mdir)
        if snap is None or not os.path.isdir(blobs):
            print(f"{name:52s} {'no-blobs':10s} {'-':>8s}  skip")
            continue
        blob_sz = du(blobs)
        if snapshot_is_real(snap):
            total_reclaim += blob_sz
            act = f"DELETE blobs/ (-{blob_sz/1e9:.1f} GB)"
            if APPLY:
                shutil.rmtree(blobs)
                act = f"deleted blobs/ (-{blob_sz/1e9:.1f} GB)"
            print(f"{name:52s} {'deref(2x)':10s} {blob_sz/1e9:7.1f}G  {act}")
        else:
            print(f"{name:52s} {'symlinked':10s} {blob_sz/1e9:7.1f}G  KEEP (snapshot symlinks->blobs)")
    print("-" * 90)
    verb = "Reclaimed" if APPLY else "Reclaimable"
    print(f"{verb}: {total_reclaim/1e9:.1f} GB" + ("" if APPLY else "   (re-run with --apply)"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
