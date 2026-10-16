"""Extract the binding roster and incident ledger; no third-party dependencies."""

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "Synthetic Bank Complete Generation Brief (1).docx"


def main():
    with ZipFile(SOURCE) as archive:
        tree = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = [
        "".join(t.text or "" for t in p.findall(".//w:t", ns)) for p in tree.findall(".//w:p", ns)
    ]
    start = paragraphs.index("Appendix G Document roster")
    end = paragraphs.index("Appendix H Minimum evaluation handoff")
    rows = paragraphs[start:end]
    rows = rows[rows.index("Title and required fact") + 1 :]
    assert len(rows) == 96 * 4, len(rows)
    roster = [
        dict(zip(("entity_id", "stories", "zone", "obligation"), rows[i : i + 4], strict=True))
        for i in range(0, len(rows), 4)
    ]
    start = paragraphs.index("Appendix D Fixed incident ledger")
    end = paragraphs.index("D2 Adjacent incident distractors")
    rows = paragraphs[start:end]
    rows = rows[rows.index("Story") + 1 :]
    assert len(rows) == 30 * 8, len(rows)
    incidents = [
        dict(
            zip(
                (
                    "incident_id",
                    "date",
                    "service",
                    "family",
                    "minutes",
                    "failed",
                    "change_related",
                    "story",
                ),
                rows[i : i + 8],
                strict=True,
            )
        )
        for i in range(0, len(rows), 8)
    ]
    seed = {
        "source_filename": SOURCE.name,
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "reference_clock": "2026-09-15T10:00:00Z",
        "seed": 20260915,
        "roster": roster,
        "payment_incidents": incidents,
    }
    destination = ROOT / "canonical" / "brief_seed.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Extracted {len(roster)} supporting slots and {len(incidents)} payment incidents.")


if __name__ == "__main__":
    main()
