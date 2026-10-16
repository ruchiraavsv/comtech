"""Mutation checks: the release gate must reject corrupted evidence and permissions."""

import json
import shutil
import unittest
from uuid import uuid4

from validate import DEFAULT_ROOT, validate


class CorpusValidationTests(unittest.TestCase):
    def setUp(self):
        self.scratch = DEFAULT_ROOT.parent / ".cache" / "northstar-validation"
        self.temp = self.scratch / str(uuid4())
        self.temp.mkdir(parents=True)
        self.root = self.temp / "dataset"
        shutil.copytree(DEFAULT_ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__"))

    def tearDown(self):
        # Only delete this test's newly created, verified workspace scratch path.
        assert self.temp.resolve().is_relative_to(self.scratch.resolve())
        shutil.rmtree(self.temp)

    def mutate_jsonl(self, name, mutation):
        path = self.root / name
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        mutation(rows)
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_rejects_changed_incident_measurement(self):
        path = self.root / "corpus/documents/DOC-INC-2026-043.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("`44700`", "`44701`"), encoding="utf-8"
        )
        report = validate(self.root)
        self.assertFalse(report["passed"])
        self.assertTrue(
            any("Fixed family aggregate mismatch: retry_idempotency" in e for e in report["errors"])
        )

    def test_rejects_chunk_permission_drift(self):
        def mutation(rows):
            chunk = next(row for row in rows if row["document_id"] == "DOC-SEC-001")
            chunk["allowed_roles"] = ["viewer", "administrator"]

        self.mutate_jsonl("corpus/chunks.jsonl", mutation)
        report = validate(self.root)
        self.assertFalse(report["passed"])
        self.assertTrue(
            any("Chunk metadata mismatch allowed_roles: DOC-SEC-001" in e for e in report["errors"])
        )

    def test_rejects_broken_supersession(self):
        def mutation(rows):
            row = next(row for row in rows if row["document_id"] == "DOC-POL-002-v1")
            row["effective_to"] = "2026-04-02T00:00:00Z"

        self.mutate_jsonl("corpus/manifest.jsonl", mutation)
        report = validate(self.root)
        self.assertFalse(report["passed"])
        self.assertTrue(
            any("Invalid supersession interval: DOC-POL-002-v2" in e for e in report["errors"])
        )

    def test_rejects_broken_citation(self):
        path = self.root / "corpus/documents/DOC-ADR-021.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "DOC-MTG-017.md#section-01", "DOC-MTG-017.md#section-99"
            ),
            encoding="utf-8",
        )
        report = validate(self.root)
        self.assertFalse(report["passed"])
        self.assertTrue(any("Broken target anchor: DOC-ADR-021" in e for e in report["errors"]))


if __name__ == "__main__":
    unittest.main()
