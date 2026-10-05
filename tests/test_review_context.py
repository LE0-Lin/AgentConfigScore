import base64
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    import collect_review_context as CONTEXT
    import run_review_comparison as COMPARISON
    import prepare_review_pilot as PILOT


class ReviewContextTests(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads((CONTEXT.BASE / "context-protocol.json").read_text(encoding="utf-8"))

    def api(self, files):
        entries, blobs = {}, {}
        for path, value in files.items():
            mode, text = value if isinstance(value, tuple) else ("100644", value)
            raw = text.encode("utf-8")
            sha = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw, usedforsecurity=False).hexdigest()
            entries[path] = {"path": path, "mode": mode, "type": "commit" if mode == "160000" else "blob", "sha": sha, "size": len(raw)}
            blobs[sha] = {"sha": sha, "encoding": "base64", "content": base64.b64encode(raw).decode()}
            for parent in Path(path).parents:
                if parent.as_posix() != ".":
                    name = parent.as_posix()
                    entries[name] = {"path": name, "mode": "040000", "type": "tree", "sha": "1" * 40}
        tree = {"sha": "2" * 40, "truncated": False, "tree": list(entries.values())}

        def fetch(endpoint):
            if "/git/trees/" in endpoint:
                return tree
            return blobs[endpoint.rsplit("/", 1)[-1]]
        return fetch, tree

    def case(self, text):
        return {"id": "test--fixture", "label": "unresolved", "category": "unreviewed", "group": "fixture",
                "rationale": "Not a human annotation.", "source_kind": "repository_snapshot", "source_ref": "fixture only",
                "files": {"AGENTS.md": text}, "provenance": {"repository": "test/fixture", "revision": "a" * 40,
                "path": "AGENTS.md", "source_sha256": hashlib.sha256(text.encode()).hexdigest()}}

    def test_references_ignore_urls_anchors_and_command_strings(self):
        text = "[Guide](docs/guide.md#part)\n`src/main.py` and `pytest tests/`\n[Web](https://example.org/remote.md)\n[Local](#heading)\n"
        references = CONTEXT.local_references(text)
        self.assertIn(("docs/guide.md#part", 1), references)
        self.assertIn(("src/main.py", 2), references)
        self.assertFalse(any("remote.md" in value or value == "#heading" or value == "pytest tests/" for value, _ in references))

    def test_relative_targets_preserve_real_source_and_reject_escape(self):
        self.assertEqual(CONTEXT.relative_target(".ai/AGENTS.md", "../docs/a%20b.md?q=1#part"), "docs/a b.md")
        self.assertEqual(CONTEXT.relative_target("AGENTS.md", "."), ".")
        for target in ("../../outside.md", "/outside.md", "C:/outside.md", "a\\b.md", "*.md"):
            self.assertIsNone(CONTEXT.relative_target("AGENTS.md", target))

    def test_symlinks_cycles_and_gitlinks_are_not_invented_as_absent_files(self):
        fetch, _ = self.api({"AGENTS.md": ("120000", ".ai/AGENTS.md"), ".ai/AGENTS.md": "Root body.",
                            "cycle.md": ("120000", "cycle.md"), "external.md": ("120000", "../outside.md"),
                            "vendor": ("160000", "gitlink fixture")})
        with patch.object(CONTEXT, "github_json", side_effect=fetch):
            tree = CONTEXT.GitEvidence("test/fixture", "a" * 40, self.protocol)
            self.assertEqual(tree.resolve("AGENTS.md"), (".ai/AGENTS.md", "tracked_file"))
            self.assertEqual(tree.resolve("cycle.md")[1], "symlink_cycle")
            self.assertEqual(tree.resolve("external.md")[1], "outside_or_nonportable_path")
            self.assertEqual(tree.resolve("vendor/child.md")[1], "inside_gitlink_unknown")
            self.assertEqual(tree.resolve("absent.md")[1], "not_in_tracked_tree")

    def test_nontruncated_tree_and_blob_identity_are_required(self):
        fetch, tree = self.api({"AGENTS.md": "Root."})
        with patch.object(CONTEXT, "github_json", return_value={**tree, "truncated": True}):
            with self.assertRaisesRegex(ValueError, "complete"):
                CONTEXT.GitEvidence("test/fixture", "a" * 40, self.protocol)
        with patch.object(CONTEXT, "github_json", side_effect=fetch):
            evidence = CONTEXT.GitEvidence("test/fixture", "a" * 40, self.protocol)
        sha = evidence.index["AGENTS.md"]["sha"]
        corrupted = {"sha": sha, "encoding": "base64", "content": base64.b64encode(b"Changed").decode()}
        with patch.object(CONTEXT, "github_json", return_value=corrupted):
            with self.assertRaisesRegex(ValueError, "identity mismatch"):
                evidence.blob(sha)

    def test_collection_retains_root_bytes_and_both_path_interpretations(self):
        text = "[Guide](../docs/guide.md)\nSee CONTRIBUTING.md.\n"
        original = self.case(text)
        fetch, _ = self.api({"AGENTS.md": ("120000", ".ai/AGENTS.md"), ".ai/AGENTS.md": text,
                            "docs/guide.md": "Guide body.\n", "CONTRIBUTING.md": "Contribution context.\n"})
        with patch.object(CONTEXT, "github_json", side_effect=fetch):
            case, audit, archive = CONTEXT.collect_case(original, self.protocol)
        self.assertEqual(original, self.case(text))
        self.assertEqual(case["files"]["AGENTS.md"], text)
        self.assertEqual(case["label"], "unresolved")
        self.assertEqual(case["repository_context"]["content_origins"]["AGENTS.md"], ".ai/AGENTS.md")
        self.assertIn("CONTRIBUTING.md", case["files"])
        self.assertEqual(audit["additional_documents"], 2)
        fact = next(row for row in case["repository_context"]["tracked_path_facts"] if row["reference"] == "CONTRIBUTING.md")
        self.assertEqual(fact["tree_status"], "not_in_tracked_tree")
        self.assertEqual(fact["root_tree_status"], "tracked_file")
        self.assertEqual(COMPARISON._digest(json.loads(gzip.decompress(archive))), case["context_provenance"]["tree_snapshot_sha256"])

    def test_changed_root_is_a_failure_not_a_replaced_or_clean_case(self):
        fetch, _ = self.api({"AGENTS.md": "New root body."})
        with patch.object(CONTEXT, "github_json", side_effect=fetch):
            with self.assertRaisesRegex(ValueError, "differs"):
                CONTEXT.collect_case(self.case("Original root body."), self.protocol)

    def test_document_limits_and_privacy_omissions_never_become_clean_labels(self):
        text = "[One](a.md) [Two](b.md) [Private](c.md)\n"
        files = {"AGENTS.md": text, "a.md": "[Deep](deep.md)\n", "b.md": "Second body.\n",
                 "c.md": 'api_key = "possibly-sensitive"\n', "deep.md": "Deep body."}
        for changed, reason in (({**self.protocol, "maximum_documents_per_case": 1}, "document_count_limit"),
                                ({**self.protocol, "maximum_context_bytes_per_case": 1}, "context_byte_limit"),
                                ({**self.protocol, "maximum_document_bytes": 1}, "document_byte_limit"),
                                ({**self.protocol, "maximum_document_depth": 1}, "document_depth_limit"),
                                (self.protocol, "credential_shaped_document_privacy_exclusion")):
            fetch, _ = self.api(files)
            with self.subTest(reason=reason), patch.object(CONTEXT, "github_json", side_effect=fetch):
                case, _, _ = CONTEXT.collect_case(self.case(text), changed)
            self.assertEqual(case["label"], "unresolved")
            self.assertIn(reason, {row["reason"] for row in case["repository_context"]["omitted_documents"]})
            self.assertNotIn("possibly-sensitive", json.dumps(case))

    def context_corpus(self):
        return COMPARISON.load_corpus(CONTEXT.BASE / "context" / "corpus.json")

    def test_export_preserves_evidence_but_not_provenance_or_extra_fields(self):
        corpus = self.context_corpus()
        case = corpus["cases"][0]
        case["context_provenance"]["private"] = "PRIVATE_SOURCE_SENTINEL"
        case["repository_context"]["private"] = "PRIVATE_CONTEXT_SENTINEL"
        case["repository_context"]["tracked_path_facts"][0]["private"] = "PRIVATE_FACT_SENTINEL"
        packet = COMPARISON.review_packet(corpus)
        serialized = json.dumps(packet)
        self.assertNotIn("PRIVATE_", serialized)
        self.assertNotIn("context_provenance", serialized)
        self.assertIn("two interpretations", packet["prompt"])
        self.assertTrue(all("repository_context" in row for row in packet["cases"]))
        old_hash = packet["packet_sha256"]
        case["repository_context"]["tracked_path_facts"][0]["tree_status"] = "unknown_type"
        self.assertNotEqual(COMPARISON.review_packet(corpus)["packet_sha256"], old_hash)

    def test_metadata_cannot_be_scored_as_a_fake_physical_checkout(self):
        corpus = self.context_corpus()
        # Unit-test declarations, not actual human annotations.
        corpus.update(tier="holdout", label_status="adjudicated", labelers=["Fixture human A", "Fixture human B"])
        corpus["cases"][0]["label"] = "review"
        with patch.object(COMPARISON, "analyze", side_effect=AssertionError("must not scan")):
            with self.assertRaisesRegex(ValueError, "equivalent tool checkout"):
                COMPARISON.evaluate(corpus, [])

    def test_invalid_context_origins_and_facts_fail_validation(self):
        original = self.context_corpus()
        for field, value in (("file", []), ("line", True), ("line", 999999),
                             ("tree_status", "clean"), ("root_relative_path", "../escape.md")):
            data = copy.deepcopy(original)
            data["cases"][0]["repository_context"]["tracked_path_facts"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                COMPARISON.validate_corpus(data)
        data = copy.deepcopy(original)
        data["cases"][0]["repository_context"]["content_origins"].pop("AGENTS.md")
        with self.assertRaisesRegex(ValueError, "every supplied file"):
            COMPARISON.validate_corpus(data)

    def test_frozen_context_provenance_and_parent_cases_remain_verifiable(self):
        parent = COMPARISON.load_corpus(CONTEXT.BASE / "collected" / "corpus.json")
        corpus = self.context_corpus()
        directory = CONTEXT.BASE / "context"
        report = json.loads((directory / "collection.json").read_text(encoding="utf-8"))
        self.assertEqual(COMPARISON._digest(parent), corpus["parent_corpus_sha256"])
        self.assertEqual(COMPARISON._digest(corpus), report["corpus_sha256"])
        self.assertEqual(COMPARISON._digest(self.protocol), report["protocol_sha256"])
        initial = json.loads((CONTEXT.BASE / "context-protocol.initial.json").read_text(encoding="utf-8"))
        self.assertEqual(COMPARISON._digest(initial), self.protocol["method_amendment"]["previous_protocol_sha256"])
        self.assertEqual(self.protocol, json.loads((directory / "protocol.json").read_text(encoding="utf-8")))
        self.assertEqual(corpus["labelers"], [])
        self.assertEqual([case["id"] for case in corpus["cases"]], [case["id"] for case in parent["cases"]])
        for original, case in zip(parent["cases"], corpus["cases"]):
            self.assertEqual(case["label"], "unresolved")
            self.assertEqual(original["files"]["AGENTS.md"], case["files"]["AGENTS.md"])
            source = case["context_provenance"]
            raw = (directory / COMPARISON._fixture_path(source["tree_archive"])).read_bytes()
            tree = json.loads(gzip.decompress(raw))
            self.assertEqual(hashlib.sha256(raw).hexdigest(), source["archive_sha256"])
            self.assertEqual(COMPARISON._digest(tree), source["tree_snapshot_sha256"])
            self.assertFalse(tree["truncated"])
            self.assertEqual(len(tree["tree"]), source["tree_entries"])
            for document in source["documents"]:
                text = case["files"][document["path"]]
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), document["source_sha256"])
                self.assertEqual(len(text.splitlines()), document["line_end"])
                self.assertFalse(CONTEXT.privacy_exclusion(text))
            license_name = original["provenance"]["license_notice"]
            self.assertEqual((directory / license_name).read_bytes(), (CONTEXT.BASE / "collected" / license_name).read_bytes())

    def test_binary_outputs_preserve_bytes_and_refuse_overwrites(self):
        with tempfile.TemporaryDirectory() as temporary:
            binary, text = Path(temporary) / "tree.gz", Path(temporary) / "notice.txt"
            raw = gzip.compress(b"Frozen tree fixture.\r\n", mtime=0)
            COMPARISON._write_outputs([(binary, raw), (text, "UTF-8 text.\n")])
            self.assertEqual(binary.read_bytes(), raw)
            with self.assertRaises(ValueError):
                COMPARISON._write_outputs([(binary, b"changed")])
            self.assertEqual(binary.read_bytes(), raw)

    def test_protocol_rejects_invalid_limits_before_network_access(self):
        CONTEXT.validate_protocol(self.protocol)
        for value in (True, 0, -1, "12", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CONTEXT.validate_protocol({**self.protocol, "maximum_documents_per_case": value})

    def test_pilot_selects_only_first_eligible_case_without_predictions(self):
        corpus = self.context_corpus()
        protocol = json.loads((CONTEXT.BASE / "pilot-protocol.json").read_text(encoding="utf-8"))
        before = copy.deepcopy(corpus)
        packet, manifest = PILOT.prepare(corpus, protocol)
        self.assertEqual(corpus, before)
        self.assertEqual(len(packet["cases"]), 1)
        self.assertEqual(manifest["selected_case_id"], "vercel--next.js")
        self.assertEqual(manifest["status"], "prepared_not_run")
        self.assertEqual([row["eligible_under_resource_limits"] for row in manifest["considered"]], [False, True])
        self.assertEqual((packet, manifest), PILOT.prepare(corpus, protocol))

    def test_pilot_rejects_changed_corpus_and_no_eligible_case(self):
        corpus = self.context_corpus()
        protocol = json.loads((CONTEXT.BASE / "pilot-protocol.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(ValueError, "exact unresolved"):
            PILOT.prepare(corpus, {**protocol, "context_corpus_sha256": "0" * 64})
        with self.assertRaisesRegex(ValueError, "no candidate"):
            PILOT.prepare(corpus, {**protocol, "maximum_text_bytes": 1})

    def test_pilot_rejects_boolean_or_nonpositive_resource_limits(self):
        corpus = self.context_corpus()
        protocol = json.loads((CONTEXT.BASE / "pilot-protocol.json").read_text(encoding="utf-8"))
        for value in (True, 0, -1, "163840"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                PILOT.prepare(corpus, {**protocol, "maximum_packet_bytes": value})

    def retained_pilot(self):
        directory = CONTEXT.BASE / "pilot"
        return (json.loads((directory / "review-packet.json").read_text(encoding="utf-8")),
                json.loads((directory / "response.json").read_text(encoding="utf-8")))

    def test_actual_pilot_response_integrity_is_not_a_correctness_measure(self):
        packet, response = self.retained_pilot()
        with patch.object(COMPARISON, "analyze", side_effect=AssertionError("must not scan")):
            result = COMPARISON.validate_review_artifacts(packet, response)
        committed = json.loads((CONTEXT.BASE / "pilot" / "validation.json").read_text(encoding="utf-8"))
        self.assertEqual(result, committed)
        self.assertEqual(result["answered_cases"], 1)
        self.assertIsNone(result["metrics"])
        self.assertEqual(result["reference_labels"], "not_used")
        run = json.loads((CONTEXT.BASE / "pilot" / "run.json").read_text(encoding="utf-8"))
        self.assertEqual(run["response_sha256"], result["response_sha256"])
        self.assertTrue(all(value is None for value in run["usage"].values()))

    def test_tampered_packets_and_leaked_metadata_fail_integrity_validation(self):
        packet, response = self.retained_pilot()
        changed = copy.deepcopy(packet)
        changed["cases"][0]["files"]["AGENTS.md"] += "Changed input.\n"
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            COMPARISON.validate_review_artifacts(changed, response)
        for mutate in (lambda value: value["cases"][0].update(label="clean"),
                       lambda value: value["cases"].append(value["cases"][0])):
            changed = copy.deepcopy(packet)
            mutate(changed)
            changed["packet_sha256"] = COMPARISON._digest({key: value for key, value in changed.items() if key != "packet_sha256"})
            with self.assertRaisesRegex(ValueError, "blinded review case"):
                COMPARISON.validate_review_artifacts(changed, response)

    def test_validate_cli_requires_no_labels_and_creates_no_score(self):
        directory = CONTEXT.BASE / "pilot"
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_review_comparison.py"), "validate",
                                 "--packet", str(directory / "review-packet.json"), "--predictions", str(directory / "response.json")],
                                cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(result.stdout)["metrics"])


if __name__ == "__main__":
    unittest.main()
