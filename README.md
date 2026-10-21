# dusk — Disk Usage Scout

A small Python CLI for finding large files and directories. Requires Python 3.10+ and has no runtime dependencies.

## Usage

```sh
./dusk [PATH]
./dusk ~/Downloads --depth 2 --top 15
./dusk . --exclude '*.pyc' --exclude .git --all
./dusk /var/log --json
```

- `--depth N`: maximum directory depth to descend (default: 2).
- `--top N`: show the N largest results (default: 20).
- `--all`: include entries whose names begin with `.`.
- `--exclude PATTERN`: exclude entries by basename or relative path glob; repeatable.
- `--json`: emit machine-readable JSON.
- `--progress`: print scan progress to standard error every 500 entries.

Symlinks are reported but never followed. Unreadable subdirectories produce warnings and scanning continues; an invalid root exits with status 2. Ctrl-C exits with status 130. Invalid CLI arguments exit with argparse's status 2.

Directory totals sum regular file sizes below each directory (logical file size, not allocated blocks). This is a best-effort scan: filesystem changes during traversal can affect totals.

## Development

```sh
python -m unittest discover -s tests -v
python -m compileall -q dusk_cli.py
```
