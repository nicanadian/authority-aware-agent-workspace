"""Safe artifact writer tests."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from authority_workspace.artifacts import (
    ArtifactPathError,
    DuplicateArtifactError,
    build_manifest_entries,
    resolve_output_path,
    write_json,
    write_jsonl,
    write_markdown,
)


class SafeArtifactWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "artifacts"

    def read_bytes(self, relative_path):
        return (self.root / relative_path).read_bytes()

    def test_write_jsonl_writes_utf8_deterministic_records(self):
        records = [
            {"b": 2, "a": "café"},
            {"emoji": "🚀", "nested": {"z": 0, "a": 1}},
        ]

        written_path = write_jsonl(self.root, "events/run.jsonl", records)

        self.assertEqual(written_path, (self.root / "events" / "run.jsonl").resolve(strict=False))
        raw = self.read_bytes("events/run.jsonl")
        self.assertIn("café".encode("utf-8"), raw)
        self.assertIn("🚀".encode("utf-8"), raw)
        self.assertEqual(
            raw.decode("utf-8"),
            '{"a":"café","b":2}\n'
            '{"emoji":"🚀","nested":{"a":1,"z":0}}\n',
        )

    def test_parent_directories_created_for_all_writers(self):
        write_jsonl(self.root, "jsonl/deep/events.jsonl", [{"ok": True}])
        write_json(self.root, "json/deep/summary.json", {"ok": True})
        write_markdown(self.root, "md/deep/summary.md", "# Summary\n")

        self.assertTrue((self.root / "jsonl/deep/events.jsonl").is_file())
        self.assertTrue((self.root / "json/deep/summary.json").is_file())
        self.assertTrue((self.root / "md/deep/summary.md").is_file())

    def test_summary_json_write_uses_temp_file_and_replace(self):
        replace_calls = []
        real_replace = os.replace

        def recording_replace(src, dst):
            src_path = Path(src)
            dst_path = Path(dst)
            replace_calls.append((src_path, dst_path, src_path.exists()))
            real_replace(src, dst)

        with mock.patch("authority_workspace.artifacts.os.replace", recording_replace):
            write_json(self.root, "summaries/summary.json", {"b": 2, "a": 1})

        self.assertEqual(len(replace_calls), 1)
        src, dst, src_existed_at_replace = replace_calls[0]
        self.assertTrue(src_existed_at_replace)
        self.assertEqual(dst, (self.root / "summaries" / "summary.json").resolve(strict=False))
        self.assertEqual(src.parent, dst.parent)
        self.assertNotEqual(src, dst)
        self.assertFalse(src.exists())
        self.assertEqual(
            self.read_bytes("summaries/summary.json").decode("utf-8"),
            '{"a":1,"b":2}\n',
        )

    def test_summary_markdown_write_uses_temp_file_and_replace(self):
        replace_calls = []
        real_replace = os.replace

        def recording_replace(src, dst):
            src_path = Path(src)
            dst_path = Path(dst)
            replace_calls.append((src_path, dst_path, src_path.exists()))
            real_replace(src, dst)

        with mock.patch("authority_workspace.artifacts.os.replace", recording_replace):
            write_markdown(self.root, "summaries/summary.md", "# Café 🚀\n")

        self.assertEqual(len(replace_calls), 1)
        src, dst, src_existed_at_replace = replace_calls[0]
        self.assertTrue(src_existed_at_replace)
        self.assertEqual(dst, (self.root / "summaries" / "summary.md").resolve(strict=False))
        self.assertEqual(src.parent, dst.parent)
        self.assertNotEqual(src, dst)
        self.assertFalse(src.exists())
        self.assertEqual(
            self.read_bytes("summaries/summary.md").decode("utf-8"),
            "# Café 🚀\n",
        )

    def test_jsonl_write_uses_temp_file_and_replace(self):
        replace_calls = []
        real_replace = os.replace

        def recording_replace(src, dst):
            src_path = Path(src)
            dst_path = Path(dst)
            replace_calls.append((src_path, dst_path, src_path.exists()))
            real_replace(src, dst)

        with mock.patch("authority_workspace.artifacts.os.replace", recording_replace):
            write_jsonl(self.root, "events/events.jsonl", [{"ok": True}])

        self.assertEqual(len(replace_calls), 1)
        src, dst, src_existed_at_replace = replace_calls[0]
        self.assertTrue(src_existed_at_replace)
        self.assertEqual(dst, (self.root / "events" / "events.jsonl").resolve(strict=False))
        self.assertEqual(src.parent, dst.parent)
        self.assertFalse(src.exists())

    def test_jsonl_write_failure_preserves_existing_file(self):
        write_jsonl(self.root, "events.jsonl", [{"old": True}])

        with self.assertRaises(TypeError):
            write_jsonl(self.root, "events.jsonl", [{"bad": object()}])

        self.assertEqual(self.read_bytes("events.jsonl"), b'{"old":true}\n')

    def test_absolute_paths_rejected(self):
        with self.assertRaises(ArtifactPathError):
            resolve_output_path(self.root, "/tmp/escape.jsonl")

    def test_dot_dot_paths_rejected(self):
        invalid_paths = ["../escape.jsonl", "nested/../escape.jsonl"]

        for relative_path in invalid_paths:
            with self.subTest(relative_path=relative_path):
                with self.assertRaises(ArtifactPathError):
                    resolve_output_path(self.root, relative_path)

    def test_backslashes_and_control_characters_rejected(self):
        invalid_paths = ["windows\\escape.jsonl", "bad\nname.jsonl"]

        for relative_path in invalid_paths:
            with self.subTest(relative_path=relative_path):
                with self.assertRaises(ArtifactPathError):
                    resolve_output_path(self.root, relative_path)

    def test_symlinked_parents_escaping_root_rejected(self):
        self.root.mkdir(parents=True)
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (self.root / "link").symlink_to(outside, target_is_directory=True)

        with self.assertRaises(ArtifactPathError):
            resolve_output_path(self.root, "link/escape.jsonl")
        self.assertFalse((outside / "escape.jsonl").exists())

    def test_duplicate_manifest_entries_rejected(self):
        write_jsonl(self.root, "events.jsonl", [{"ok": True}])

        with self.assertRaises(DuplicateArtifactError):
            build_manifest_entries(self.root, ["events.jsonl", "events.jsonl"])

    def test_manifest_hashes_byte_sizes_and_line_counts_match_contents(self):
        write_jsonl(self.root, "events.jsonl", [{"b": 2}, {"a": 1}])
        write_json(self.root, "summary.json", {"ok": True})
        write_markdown(self.root, "notes.md", "# Notes\nBody\n")

        entries = build_manifest_entries(
            self.root,
            ["events.jsonl", "summary.json", "notes.md"],
        )

        self.assertEqual([entry["path"] for entry in entries], ["events.jsonl", "summary.json", "notes.md"])
        for entry in entries:
            relative_path = entry["path"]
            contents = self.read_bytes(relative_path)
            self.assertEqual(entry["sha256"], "sha256:" + hashlib.sha256(contents).hexdigest())
            self.assertEqual(entry["bytes"], len(contents))
            expected_lines = len(contents.decode("utf-8").splitlines()) if relative_path.endswith(".jsonl") else 0
            self.assertEqual(entry["jsonl_line_count"], expected_lines)
            self.assertRegex(entry["sha256"], r"^sha256:[0-9a-f]{64}$")

    def test_manifest_paths_are_validated(self):
        with self.assertRaises(ArtifactPathError):
            build_manifest_entries(self.root, ["../escape.jsonl"])


if __name__ == "__main__":
    unittest.main()
