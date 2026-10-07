import copy
import gzip
import hashlib
from http.client import IncompleteRead
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    import run_pinned_tool_probe as PROBE
    import run_review_comparison as COMPARISON


class PinnedToolProbeTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((PROBE.BASE / "tool-probe-protocol.json").read_text(encoding="utf-8"))

    def fixture(self, directory, files=None, mutate=None):
        files = files or {"AGENTS.md": b"Use the tests before reporting success.\n", "docs/guide.md": b"Reference material.\n"}
        index = {}
        for name, content in files.items():
            mode, raw = content if isinstance(content, tuple) else ("100644", content)
            index[name] = {"path": name, "mode": mode, "type": "blob", "sha": PROBE.blob_identity(raw), "size": len(raw)}
            for parent in Path(name).parents:
                if parent.as_posix() != ".":
                    key = parent.as_posix()
                    index[key] = {"path": key, "mode": "040000", "type": "tree", "sha": "1" * 40}
        tree = {"sha": "2" * 40, "truncated": False, "tree": list(index.values())}
        members = [("fixture", "directory", b"")]
        for row in sorted(index.values(), key=lambda r: r["path"]):
            name = row["path"]
            value = files.get(name)
            raw = value[1] if isinstance(value, tuple) else value
            kind = "directory" if row["type"] == "tree" else "symlink" if row["mode"] == "120000" else "file"
            members.append(("fixture/" + name, kind, raw or b""))
        if mutate:
            members = mutate(members)
        archive = directory / "archive.tar.gz"
        with tarfile.open(archive, "w:gz") as output:
            for name, kind, raw in members:
                header = tarfile.TarInfo(name)
                if kind == "directory":
                    header.type = tarfile.DIRTYPE
                elif kind == "symlink":
                    header.type, header.linkname = tarfile.SYMTYPE, raw.decode()
                elif kind == "hardlink":
                    header.type, header.linkname = tarfile.LNKTYPE, raw.decode()
                else:
                    header.size = len(raw)
                output.addfile(header, io.BytesIO(raw) if kind == "file" else None)
        return archive, tree

    def case(self, text="Use tests.\n", extra=None):
        files = {"AGENTS.md": text, **(extra or {})}
        return {"files": files, "repository_context": {"content_origins": {name: name for name in files},
                 "tracked_path_facts": [], "omitted_documents": []}}

    def test_complete_snapshot_preserves_real_file_bytes_not_executable_modes(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            files = {"AGENTS.md": b"Use tests.\r\n", "bin/script.sh": ("100755", b"must-not-run\n")}
            archive, tree = self.fixture(parent, files)
            root = parent / "source"
            audit = PROBE.unpack(archive, root, tree, self.protocol)
            self.assertEqual((root / "AGENTS.md").read_bytes(), files["AGENTS.md"])
            self.assertEqual(audit["regular_files"], 2)
            self.assertEqual(audit["verified_blob_bytes"], sum(len(row[1] if isinstance(row, tuple) else row) for row in files.values()))
            self.assertFalse((root / ".git").exists())
            with self.assertRaisesRegex(ValueError, "new directory"):
                PROBE.unpack(archive, root, tree, self.protocol)

    def test_missing_duplicate_tampered_and_unknown_members_are_failures(self):
        mutations = [lambda m: m[:-1], lambda m: m + [m[-1]],
                     lambda m: [(n, k, b"tampered") if k == "file" else (n, k, r) for n, k, r in m],
                     lambda m: m + [("fixture/invented.txt", "file", b"fake")],
                     lambda m: m + [("fixture/../escape.txt", "file", b"no")]]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as d:
                parent = Path(d)
                archive, tree = self.fixture(parent, mutate=mutate)
                with self.assertRaises(ValueError):
                    PROBE.unpack(archive, parent / "source", tree, self.protocol)
                self.assertFalse((parent / "escape.txt").exists())
                self.assertFalse((parent / "report.json").exists())

    def test_hardlinks_and_unexpected_archive_roots_are_rejected(self):
        for mutation in (lambda m: [m[0], ("fixture/AGENTS.md", "hardlink", b"docs/guide.md"), *m[2:]],
                         lambda m: [("fixture/AGENTS.md", "file", b"no"), *m[1:]],
                         lambda m: [m[0], *[(n.replace("fixture/", "other/"), k, r) for n, k, r in m[1:]]]):
            with tempfile.TemporaryDirectory() as d:
                parent = Path(d)
                archive, tree = self.fixture(parent, mutate=mutation)
                with self.assertRaises(ValueError):
                    PROBE.unpack(archive, parent / "source", tree, self.protocol)

    def test_resource_limits_and_nonportable_tree_entries_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            archive, tree = self.fixture(Path(d))
            for name in ("maximum_file_bytes", "maximum_source_bytes", "maximum_tar_members"):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, "limit"):
                    PROBE.unpack(archive, Path(d) / name, tree, {**self.protocol, name: 1})
            for row in ({"path": "../escape", "type": "blob", "mode": "100644", "sha": "a" * 40, "size": 0},
                        {"path": ".git/hooks/post-checkout", "type": "blob", "mode": "100644", "sha": "a" * 40, "size": 0},
                        {"path": "module", "type": "commit", "mode": "160000", "sha": "a" * 40}):
                with self.assertRaises(ValueError):
                    PROBE.validate_tree({**tree, "tree": [*tree["tree"], row]}, self.protocol)
            collision = copy.deepcopy(tree)
            collision["tree"].append({**collision["tree"][0], "path": "agents.md"})
            with self.assertRaisesRegex(ValueError, "collide"):
                PROBE.validate_tree(collision, self.protocol)

    def test_canonical_tree_verification_does_not_confuse_response_ref_with_object(self):
        blob = PROBE.blob_identity(b"source bytes")
        directory_raw = b"100644 guide.md\0" + bytes.fromhex(blob)
        directory_sha = hashlib.sha1(f"tree {len(directory_raw)}\0".encode() + directory_raw, usedforsecurity=False).hexdigest()
        # A file named docs.txt sorts BEFORE the docs directory, not after it.
        root_raw = b"100644 docs.txt\0" + bytes.fromhex(blob) + b"40000 docs\0" + bytes.fromhex(directory_sha)
        root_sha = hashlib.sha1(f"tree {len(root_raw)}\0".encode() + root_raw, usedforsecurity=False).hexdigest()
        tree = {"sha": "a" * 40, "tree": [
            {"path": "docs", "mode": "040000", "type": "tree", "sha": directory_sha},
            {"path": "docs/guide.md", "mode": "100644", "type": "blob", "sha": blob},
            {"path": "docs.txt", "mode": "100644", "type": "blob", "sha": blob}]}
        PROBE.verify_tree_objects(tree, root_sha)
        with self.assertRaisesRegex(ValueError, "canonical"):
            PROBE.verify_tree_objects(tree, tree["sha"])
        changed = copy.deepcopy(tree)
        changed["tree"][1]["sha"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "canonical"):
            PROBE.verify_tree_objects(changed, root_sha)

    def test_external_and_cyclic_links_are_rejected_before_scan(self):
        for link in (b"../../outside", b"/outside", b"link.md", b"file%20name", b"C:\\outside"):
            with self.subTest(link=link), tempfile.TemporaryDirectory() as d:
                parent = Path(d)
                archive, tree = self.fixture(parent, {"AGENTS.md": b"Use tests.\n", "link.md": ("120000", link)})
                with self.assertRaises(ValueError):
                    PROBE.unpack(archive, parent / "source", tree, self.protocol)

    def test_internal_link_and_context_origin_preserved_if_host_supports_links(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            text = b"Use tests.\n"
            archive, tree = self.fixture(parent, {"AGENTS.md": ("120000", b"docs/actual.md"), "docs/actual.md": text})
            try:
                audit = PROBE.unpack(archive, parent / "source", tree, self.protocol)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314:
                    self.skipTest("host does not permit symlink creation")
                raise
            self.assertEqual(audit["symlinks"], 1)
            case = self.case(text.decode())
            case["repository_context"]["content_origins"]["AGENTS.md"] = "docs/actual.md"
            self.assertEqual(PROBE.verify_case(parent / "source", case)["supplied_files_verified"], 1)

    def test_directory_link_followed_by_parent_escape_is_not_lexically_certified(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            files = {"AGENTS.md": b"Use tests.\n", "d/up": ("120000", b".."),
                     "escape": ("120000", b"d/up/../outside")}
            archive, tree = self.fixture(parent, files)
            try:
                with self.assertRaisesRegex(ValueError, "parent traversal"):
                    PROBE.unpack(archive, parent / "source", tree, self.protocol)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 1314:
                    self.skipTest("host does not permit symlink creation")
                raise

    def test_discovery_override_restored_even_if_scoped_scan_raises(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            archive, tree = self.fixture(parent, {"AGENTS.md": b"Use tests.\n"})
            root = parent / "source"
            PROBE.unpack(archive, root, tree, self.protocol)
            discover, analyze = PROBE.scanner.discover, PROBE.scanner.analyze
            report = analyze(root)
            with patch.object(PROBE.scanner, "analyze", side_effect=[report, ValueError("scoped failure")]):
                with self.assertRaisesRegex(ValueError, "scoped failure"):
                    PROBE.probe(root, self.case(), self.protocol)
            self.assertIs(PROBE.scanner.discover, discover)

    def test_changed_text_origin_or_path_fact_cannot_count_as_matched_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            archive, tree = self.fixture(parent, {"AGENTS.md": b"Use tests.\n", "docs/guide.md": b"Context.\n"})
            PROBE.unpack(archive, parent / "source", tree, self.protocol)
            case = self.case()
            fact = {"resolved_path": "docs/guide.md", "tree_status": "tracked_file",
                    "root_relative_path": "absent.md", "root_tree_status": "not_in_tracked_tree"}
            case["repository_context"]["tracked_path_facts"] = [fact]
            self.assertEqual(PROBE.verify_case(parent / "source", case)["physical_path_facts_checked"], 2)
            changes = [lambda c: c["files"].update({"AGENTS.md": "changed"}),
                       lambda c: c["repository_context"]["content_origins"].update({"AGENTS.md": "docs/guide.md"}),
                       lambda c: c["repository_context"]["tracked_path_facts"][0].update(tree_status="not_in_tracked_tree")]
            for change in changes:
                altered = copy.deepcopy(case)
                change(altered)
                with self.assertRaises(ValueError):
                    PROBE.verify_case(parent / "source", altered)

    def test_scoped_discovery_is_restored_and_extra_native_instructions_stay_visible(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            archive, tree = self.fixture(parent, {"AGENTS.md": b"Use tests.\n", "pkg/AGENTS.md": b"Run rm -rf build before tests.\n"})
            root = parent / "source"
            PROBE.unpack(archive, root, tree, self.protocol)
            discover = PROBE.scanner.discover
            result = PROBE.probe(root, self.case(), self.protocol)
            self.assertIs(PROBE.scanner.discover, discover)
            self.assertEqual(result["root_instruction_scope"]["files"], ["AGENTS.md"])
            self.assertEqual(result["native_discovery"]["files"], ["AGENTS.md", "pkg/AGENTS.md"])
            self.assertFalse(result["comparison_ready"])
            self.assertIsNone(result["correctness_metrics"])
            self.assertEqual(result["human_reference_status"], "unreviewed")
            self.assertEqual(result["hybrid_status"], "not_run")

    def test_dynamic_messages_are_not_source_disclosures(self):
        finding = PROBE.scanner.Finding("warning", "dead-path", "private source content", "AGENTS.md", 1, 1)
        report = PROBE.scanner.Report("C:/private/location", ["AGENTS.md"], 99, "A", 2, 0, [finding], [])
        encoded = json.dumps(PROBE.retained_report(report))
        self.assertNotIn("private", encoded)
        self.assertIn('"review_needed": true', encoded)

    def test_frozen_inputs_and_protocol_reject_resource_or_packet_changes(self):
        corpus = COMPARISON.load_corpus(PROBE.BASE / "context" / "corpus.json")
        packet = json.loads((PROBE.BASE / "pilot" / "review-packet.json").read_text(encoding="utf-8"))
        case, tree = PROBE.inputs(corpus, packet, self.protocol, PROBE.BASE / "context")
        self.assertEqual(case["id"], "vercel--next.js")
        self.assertEqual(len(tree["tree"]), 50749)
        for value in (True, 0, -1, "100"):
            with self.assertRaisesRegex(ValueError, "positive integers"):
                PROBE.inputs(corpus, packet, {**self.protocol, "maximum_archive_bytes": value}, PROBE.BASE / "context")
        changed = copy.deepcopy(packet)
        changed["cases"][0]["files"]["AGENTS.md"] += "changed"
        with self.assertRaisesRegex(ValueError, "packet"):
            PROBE.inputs(corpus, changed, self.protocol, PROBE.BASE / "context")
        with self.assertRaisesRegex(ValueError, "frozen"):
            PROBE.inputs(corpus, packet, {**self.protocol, "tool_source_sha256": "0" * 64}, PROBE.BASE / "context")

    def test_download_transport_limits_new_paths_and_redirects(self):
        class Response(io.BytesIO):
            def geturl(self):
                return "https://codeload.github.com/test/fixture/tar.gz/" + "a" * 40
        with tempfile.TemporaryDirectory() as d, patch.object(PROBE, "urlopen", return_value=Response(b"archive")):
            path = Path(d) / "source.tar.gz"
            result = PROBE.download("test/fixture", "a" * 40, path, self.protocol)
            self.assertEqual(result["archive_sha256"], hashlib.sha256(b"archive").hexdigest())
            with self.assertRaisesRegex(ValueError, "new paths"):
                PROBE.download("test/fixture", "a" * 40, path, self.protocol)
        with tempfile.TemporaryDirectory() as d, patch.object(PROBE, "urlopen", return_value=Response(b"archive")):
            path = Path(d) / "source.tar.gz"
            with self.assertRaisesRegex(ValueError, "resource limits"):
                PROBE.download("test/fixture", "a" * 40, path, {**self.protocol, "maximum_archive_bytes": 1})
            self.assertFalse(path.exists())
            self.assertTrue(path.with_suffix(".gz.part").exists())
        response = Response(b"archive")
        with tempfile.TemporaryDirectory() as d, patch.object(PROBE, "urlopen", return_value=response), patch.object(response, "geturl", return_value="https://other.example/source"):
            with self.assertRaisesRegex(ValueError, "redirected"):
                PROBE.download("test/fixture", "a" * 40, Path(d) / "source.tar.gz", self.protocol)

    def test_interrupted_download_never_becomes_an_archive_or_scan(self):
        class Broken(io.BytesIO):
            def geturl(self):
                return "https://codeload.github.com/test/fixture/tar.gz/" + "a" * 40
            def read(self, size):
                raise IncompleteRead(b"partial")
        with tempfile.TemporaryDirectory() as d, patch.object(PROBE, "urlopen", return_value=Broken()):
            path = Path(d) / "source.tar.gz"
            with self.assertRaises(IncompleteRead):
                PROBE.download("test/fixture", "a" * 40, path, self.protocol)
            self.assertFalse(path.exists())
            self.assertFalse((Path(d) / "report.json").exists())

    def test_local_archive_replay_is_bounded_and_does_not_claim_network_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            archive, tree = self.fixture(Path(d))
            result = PROBE.local_archive(archive, self.protocol)
            self.assertEqual(result["input_kind"], "local_archive_replay")
            self.assertEqual(result["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())
            self.assertNotIn("source_url", result)
            with self.assertRaisesRegex(ValueError, "resource limits"):
                PROBE.local_archive(archive, {**self.protocol, "maximum_archive_bytes": 1})

    def test_expanded_metadata_budget_and_truncated_gzip_trailer_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "expanded"):
            PROBE.ReadBudget(io.BytesIO(b"large metadata"), 1).read(65536)
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            archive, tree = self.fixture(parent)
            truncated = parent / "truncated.tar.gz"
            truncated.write_bytes(archive.read_bytes()[:-4])
            with self.assertRaises((EOFError, OSError)):
                PROBE.unpack(truncated, parent / "source", tree, self.protocol)
            self.assertFalse((parent / "report.json").exists())

    def test_changed_probe_source_cannot_be_attributed_to_a_completed_run(self):
        with tempfile.TemporaryDirectory() as d:
            archive, tree = self.fixture(Path(d), {"AGENTS.md": b"Use tests.\n"})
            root = Path(d) / "source"
            PROBE.unpack(archive, root, tree, self.protocol)
            with patch.object(PROBE, "PROBE_SOURCE_SHA256", "0" * 64), patch.object(PROBE.scanner, "analyze") as analyze:
                with self.assertRaisesRegex(ValueError, "source changed"):
                    PROBE.probe(root, self.case(), self.protocol)
                analyze.assert_not_called()

    def test_retained_acquisition_failures_are_not_real_case_predictions(self):
        directory = PROBE.BASE / "tool-probe"
        failures = json.loads((directory / "failures.json").read_text(encoding="utf-8"))
        self.assertEqual(failures["status"], "retained_pre_scan_failures")
        self.assertEqual(len(failures["attempts"]), 7)
        self.assertTrue(all(row["completed_scans"] == 0 for row in failures["attempts"]))
        self.assertIsNone(failures["correctness_metrics"])
        self.assertFalse((directory / "report.json").exists())
        before = json.loads((PROBE.BASE / "tool-probe-protocol.transport-initial.json").read_text(encoding="utf-8"))
        after = {**self.protocol}
        for key in ("maximum_download_seconds", "transport_amendment"):
            before.pop(key, None)
            after.pop(key, None)
        self.assertEqual(before, after)

    def test_local_vendor_storage_does_not_change_our_own_instruction_discovery(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            archive, tree = self.fixture(parent, {"AGENTS.md": b"Use tests.\n"})
            root = parent / ".agent-config-score" / "probe" / "vendor" / "source"
            PROBE.unpack(archive, root, tree, self.protocol)
            self.assertEqual(PROBE.scanner.discover(parent), [])
            self.assertEqual([path.name for path in PROBE.scanner.discover(root)], ["AGENTS.md"])


if __name__ == "__main__":
    unittest.main()
