#!/usr/bin/env python3
"""Check the plan artifact's structure and arithmetic without network access.

This is a documentation check. It does not evaluate a travel agent, validate
external facts, call model APIs, or prove the future application's readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


DEFAULT_PLAN = Path("docs/ostrovok/OSTROVOK_HACKATHON_PLAN_2026-10-23.md")


def check_plan(path: Path) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    errors: list[str] = []
    checks: list[str] = []

    def check(condition: bool, name: str) -> None:
        (checks if condition else errors).append(name)

    check(text.startswith("# О!Собрано"), "expected_document_title")
    check(text.endswith("\n"), "final_newline")
    check("\x00" not in text, "no_nul_bytes")
    check(not re.search(r"\b(?:TODO|TBD|FIXME|PLACEHOLDER)\b", text), "no_unfinished_markers")

    outside: list[str] = []
    fence_char = ""
    fence_size = 0
    fence_language = ""
    fence_body: list[str] = []
    json_blocks = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if not fence_char and match:
            marker, info = match.groups()
            fence_char, fence_size = marker[0], len(marker)
            fence_language = info.strip().lower()
            fence_body = []
        elif fence_char and match and match[1][0] == fence_char and len(match[1]) >= fence_size and not match[2].strip():
            if fence_language == "json":
                json_blocks += 1
                try:
                    json.loads("\n".join(fence_body))
                except json.JSONDecodeError as exc:
                    errors.append(f"invalid_json_block_ending_line_{line_number}: {exc}")
            fence_char = ""
        elif fence_char:
            fence_body.append(line)
        else:
            outside.append(line)
    check(not fence_char, "balanced_code_fences")
    prose = "\n".join(outside)

    sections = [int(value) for value in re.findall(r"^## (\d+)\. ", prose, flags=re.MULTILINE)]
    check(sections == list(range(1, 23)), "all_22_sections_in_order")

    anchors = re.findall(r'<a id="([a-z][a-z0-9_-]*)"></a>', prose)
    check(len(anchors) == len(set(anchors)), "unique_internal_anchors")
    targets = set(re.findall(r"\]\(#([a-z][a-z0-9_-]*)\)", prose))
    check(targets <= set(anchors), "all_internal_links_resolve")

    source_ids = re.findall(r"^\| (S\d{2}) \|", prose, flags=re.MULTILINE)
    cited_ids = set(re.findall(r"\[(S\d{2})\]", prose))
    defined_ids = set(re.findall(r"^\[(S\d{2})\]: https://\S+$", prose, flags=re.MULTILINE))
    check(len(source_ids) == len(set(source_ids)), "unique_source_ids")
    check(cited_ids <= set(source_ids), "all_source_references_resolve")
    check(cited_ids <= defined_ids, "all_source_references_are_clickable")
    check(len(source_ids) >= 25, "source_ledger_present")

    score_rows = []
    for line in prose.splitlines():
        if not re.match(r"^\| \d{1,2} \|", line):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 9:
            continue
        try:
            number = int(cells[0])
            ratings = [int(value) for value in cells[2:8]]
            declared = int(cells[8])
        except ValueError:
            errors.append("non_numeric_concept_score")
            continue
        calculated = sum(rating * weight for rating, weight in zip(ratings, [5, 4, 4, 3, 2, 2], strict=True))
        check(all(1 <= rating <= 5 for rating in ratings), f"concept_{number}_valid_ratings")
        check(calculated == declared, f"concept_{number}_weighted_arithmetic")
        score_rows.append({"id": number, "name": cells[1], "score": declared})
    check([row["id"] for row in score_rows] == list(range(1, 11)), "exactly_10_concepts")
    check(bool(score_rows) and score_rows[0]["score"] == max(row["score"] for row in score_rows), "recommended_concept_has_highest_score")

    case_ids = re.findall(r"^\| (T\d{2}) \|", prose, flags=re.MULTILINE)
    check(case_ids == [f"T{index:02d}" for index in range(1, 21)], "all_20_acceptance_scenarios")
    check("29 октября до 10:00 МСК" in text, "submission_deadline_documented")
    check("не измеряет качество моделей" in text, "documentation_check_scope_disclosed")

    return {
        "status": "passed" if not errors else "failed",
        "scope": "Document structure, references, and arithmetic only; no application or model evaluation.",
        "plan_path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "lines": len(text.splitlines()),
        "sections": len(sections),
        "sources": len(source_ids),
        "json_blocks_checked": json_blocks,
        "concepts": score_rows,
        "acceptance_scenarios": len(case_ids),
        "checks_passed": checks,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", nargs="?", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = check_plan(args.plan)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    print(f"{result['status'].upper()}: {len(result['checks_passed'])} document checks, {len(result['errors'])} errors")
    print(f"{result['sections']} sections; {len(result['concepts'])} concepts; {result['sources']} sources; {result['acceptance_scenarios']} acceptance scenarios")
    print(f"SHA-256: {result['sha256']}")
    for error in result["errors"]:
        print(f"ERROR: {error}")
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
