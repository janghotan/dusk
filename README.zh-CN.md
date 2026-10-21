# dusk — 磁盘占用探查器

[English](README.md)

> 一款轻量级 Python 命令行工具，用于查找占用空间较大的文件和目录，支持限制扫描深度、排除匹配项以及输出 JSON。需要 Python 3.10+，运行时无需第三方依赖。

## 使用方法

```sh
./dusk [路径]
./dusk ~/Downloads --depth 2 --top 15
./dusk . --exclude '*.pyc' --exclude .git --all
./dusk /var/log --json
```

- `--depth N`：最大目录遍历深度（默认：`2`）。
- `--top N`：显示最大的 N 个结果（默认：`20`）。
- `--all`：包含名称以 `.` 开头的隐藏条目。
- `--exclude PATTERN`：排除匹配文件名或相对路径的 glob 模式；可重复使用。
- `--json`：输出机器可读的 JSON。
- `--progress`：每扫描 500 个条目时，将进度输出到标准错误流。

## 行为说明

符号链接会被列出，但不会跟随。无法读取的子目录会显示警告，扫描会继续；无效的起始路径会以状态码 `2` 退出。按下 `Ctrl-C` 会以状态码 `130` 退出。无效命令行参数会由 `argparse` 以状态码 `2` 报错。

目录大小是其下普通文件逻辑大小的合计（并非磁盘实际分配的块数）。扫描期间如果文件系统发生变化，统计结果可能受到影响。

## 开发与测试

运行测试：

```sh
python -m unittest discover -s tests -v
python -m compileall -q dusk_cli.py
```
