#!/usr/bin/env python3
"""dusk: Disk Usage Scout, a terminal disk usage explorer."""
from __future__ import annotations

import argparse
import fnmatch
import heapq
import json
import os
import stat
import sys
from dataclasses import asdict, dataclass
from typing import Iterator


@dataclass(frozen=True)
class Entry:
    path: str
    size: int
    kind: str


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if value < 1024 or unit == "PiB":
            return f"{int(value)} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PiB"


def is_excluded(path: str, patterns: list[str], root: str) -> bool:
    rel = os.path.relpath(path, root)
    name = os.path.basename(path)
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(path, p) for p in patterns)


def scan(root: str, depth: int = 2, include_all: bool = False,
         patterns: list[str] | None = None, progress: bool = False) -> Iterator[Entry]:
    """Yield entries depth first. Symlinks are described but never traversed."""
    root = os.path.abspath(os.path.expanduser(root))
    patterns = patterns or []
    try:
        root_stat = os.lstat(root)
    except OSError as exc:
        raise OSError(exc.errno, f"cannot access '{root}': {exc.strerror}", root) from exc
    if stat.S_ISLNK(root_stat.st_mode):
        raise OSError(f"refusing to scan symbolic link '{root}'; use its target path explicitly", root)
    if stat.S_ISREG(root_stat.st_mode):
        yield Entry(root, root_stat.st_size, "file")
        return
    if not stat.S_ISDIR(root_stat.st_mode):
        raise OSError(f"'{root}' is not a regular file or directory", root)

    visited = 0
    def walk(directory: str, level: int) -> tuple[int, list[Entry]]:
        nonlocal visited
        try:
            with os.scandir(directory) as stream:
                children = sorted(stream, key=lambda item: item.name.casefold())
        except OSError as exc:
            print(f"dusk: warning: cannot read '{directory}': {exc.strerror}", file=sys.stderr)
            return 0, []

        total = 0
        # Per-directory rows are retained until its total is known. The final output collector is bounded.
        rows: list[Entry] = []
        for child in children:
            child_path = os.path.join(directory, child.name)
            if not include_all and child.name.startswith("."):
                continue
            if is_excluded(child_path, patterns, root):
                continue
            try:
                info = child.stat(follow_symlinks=False)
            except OSError as exc:
                print(f"dusk: warning: cannot stat '{child_path}': {exc.strerror}", file=sys.stderr)
                continue
            visited += 1
            if progress and visited % 500 == 0:
                print(f"\rdusk: scanned {visited:,} entries…", end="", file=sys.stderr, flush=True)
            if stat.S_ISLNK(info.st_mode):
                rows.append(Entry(child_path, info.st_size, "symlink"))
                total += info.st_size
            elif stat.S_ISDIR(info.st_mode):
                if level < depth:
                    sub_total, sub_entries = walk(child_path, level + 1)
                    rows.append(Entry(child_path, sub_total, "directory"))
                    total += sub_total
                    rows.extend(sub_entries)
                else:
                    rows.append(Entry(child_path, 0, "directory"))
            elif stat.S_ISREG(info.st_mode):
                rows.append(Entry(child_path, info.st_size, "file"))
                total += info.st_size
        return total, rows

    size, entries = walk(root, 0)
    yield Entry(root, size, "directory")
    yield from entries


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dusk", description="Disk Usage Scout — find what is taking up space.",
        epilog="Examples:\n  dusk .\n  dusk ~/Downloads --depth 2 --top 15\n  dusk /var/log --exclude '*.gz' --all\n  dusk . --json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=".", help="directory or file to inspect (default: current directory)")
    parser.add_argument("--depth", type=int, default=2, metavar="N", help="maximum directory traversal depth (default: 2)")
    parser.add_argument("--top", type=int, default=20, metavar="N", help="number of largest entries to display (default: 20)")
    parser.add_argument("--all", action="store_true", help="include hidden entries (names starting with .)")
    parser.add_argument("--exclude", action="append", default=[], metavar="PATTERN", help="exclude names or relative paths matching a glob (repeatable)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--progress", action="store_true", help="show scan progress on stderr every 500 entries")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.depth < 0:
        parser.error("--depth must be zero or greater")
    if args.top < 1:
        parser.error("--top must be at least 1")
    try:
        # Retain only the largest N rows; the tree walk itself is depth-first.
        heap: list[tuple[int, str, int, Entry]] = []
        count = 0
        for entry in scan(args.path, args.depth, args.all, args.exclude, args.progress):
            count += 1
            key = (entry.size, _reverse_path_key(entry.path), count, entry)
            if len(heap) < args.top:
                heapq.heappush(heap, key)
            elif key[:2] > heap[0][:2]:
                heapq.heapreplace(heap, key)
        shown = sorted((item[3] for item in heap), key=lambda e: (-e.size, e.path.casefold()))
    except OSError as exc:
        print(f"dusk: error: {exc.strerror or str(exc)}", file=sys.stderr)
        return 2
    if args.progress:
        print(f"\rdusk: scanned {count:,} entries.\n", file=sys.stderr)
    if args.json:
        print(json.dumps({"path": os.path.abspath(os.path.expanduser(args.path)), "count": count,
                          "entries": [asdict(entry) | {"human_size": human_size(entry.size)} for entry in shown]}, indent=2))
    else:
        print(f"Disk Usage Scout  ·  {os.path.abspath(os.path.expanduser(args.path))}")
        print(f"{'SIZE':>10}  {'TYPE':<9}  PATH")
        print(f"{'─' * 10}  {'─' * 9}  {'─' * 40}")
        for entry in shown:
            print(f"{human_size(entry.size):>10}  {entry.kind:<9}  {entry.path}")
        if count > len(shown):
            print(f"\nShowing {len(shown)} of {count} entries. Use --top {count} to show all.")
        print("\nDirectory sizes sum regular file sizes below them (logical sizes). Symlinks are never followed.")
    return 0


def _reverse_path_key(path: str) -> str:
    # Reverse lexical order so equal-sized paths prefer ascending order in the min heap.
    return "".join(chr(0x10ffff - ord(char)) for char in path.casefold())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\ndusk: cancelled", file=sys.stderr)
        raise SystemExit(130)
