import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import dusk_cli


class DuskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "big.bin").write_bytes(b"x" * 2048)
        (self.root / "small.txt").write_text("hey")
        (self.root / ".secret").write_text("hidden")
        (self.root / "sub").mkdir()
        (self.root / "sub" / "nested.dat").write_bytes(b"y" * 512)
        try:
            (self.root / "link").symlink_to(self.root / "big.bin")
        except OSError:
            pass

    def tearDown(self):
        self.temp.cleanup()

    def test_scan_depth_and_directory_sizes(self):
        entries = list(dusk_cli.scan(str(self.root), depth=1))
        by_name = {Path(e.path).name: e for e in entries}
        self.assertEqual(by_name[self.root.name].size, 2587)
        self.assertIn("big.bin", by_name)
        self.assertNotIn(".secret", by_name)
        self.assertIn("nested.dat", by_name)
        self.assertEqual(by_name["sub"].size, 512)

    def test_hidden_and_exclude_filtering(self):
        entries = list(dusk_cli.scan(str(self.root), depth=2, include_all=True, patterns=["*.bin"]))
        names = {Path(e.path).name for e in entries}
        self.assertIn(".secret", names)
        self.assertNotIn("big.bin", names)

    def test_symlink_is_not_followed(self):
        link = self.root / "link"
        if link.is_symlink():
            entry = next(e for e in dusk_cli.scan(str(self.root), depth=1) if e.path == str(link))
            self.assertEqual(entry.kind, "symlink")
            self.assertEqual(entry.size, os.lstat(link).st_size)

    def test_file_size_formatting(self):
        self.assertEqual(dusk_cli.human_size(12), "12 B")
        self.assertEqual(dusk_cli.human_size(1536), "1.5 KiB")

    def test_json_and_top_sorting(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(dusk_cli.main([str(self.root), "--depth", "1", "--top", "2", "--json"]), 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(len(payload["entries"]), 2)
        sizes = [row["size"] for row in payload["entries"]]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_missing_path_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = dusk_cli.main([str(self.root / "missing")])
        self.assertEqual(code, 2)
        self.assertIn("cannot access", err.getvalue())

    def test_root_symlink_rejected(self):
        link = self.root / "rootlink"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(OSError):
            list(dusk_cli.scan(str(link)))


if __name__ == "__main__":
    unittest.main()
