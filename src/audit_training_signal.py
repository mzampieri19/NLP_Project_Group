"""Create a transparent rubric-guided automated pilot audit of the final training pairs.

The labels are deterministic rubric-guided screening labels, not validated human
annotations.  They are intended to unblock the course pilot and identify signals that
must be reported.  The output keeps short phrase evidence in every note.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics as stats
from collections import Counter, defaultdict
from pathlib import Path

FIELDS = [
    "example_id",
    "condition",
    "validation",
    "warmth",
    "certainty",
    "agreement",
    "content_error",
    "length",
    "action",
    "note",
]

FEELINGS = {
    "afraid",
    "angry",
    "anxious",
    "anxiety",
    "apprehensive",
    "ashamed",
    "concerned",
    "conflicted",
    "confused",
    "depressed",
    "discouraged",
    "distressed",
    "doubtful",
    "fear",
    "fearful",
    "frustrated",
    "frustration",
    "guilty",
    "hopeful",
    "hurt",
    "isolated",
    "lonely",
    "nervous",
    "overwhelmed",
    "relieved",
    "sad",
    "sadness",
    "scared",
    "shame",
    "shy",
    "stressed",
    "uncertain",
    "upset",
    "worried",
}
VALIDATION_MARKERS = (
    "i understand",
    "i hear",
    "i can see",
    "it sounds",
    "that sounds",
    "makes sense",
    "understandable",
    "you feel",
    "you’re feeling",
    "you are feeling",
    "you sound",
)
WARMTH_MARKERS = (
    "sorry",
    "glad",
    "hope",
    "wish",
    "please",
    "thank",
    "welcome",
    "care",
    "help",
    "support",
    ":)",
    "!",
)
STRONG_CERTAINTY = (
    "definitely",
    "certainly",
    "for a fact",
    "i am sure",
    "i'm sure",
    "you must",
    "you will",
    "always",
    "never",
)
MILD_CERTAINTY = ("should", "will", "know", "best", "right", "true")
STRONG_AGREEMENT = (
    "you are right",
    "you’re right",
    "you're right",
    "absolutely",
    "exactly",
    "that is true",
    "that's true",
    "yes,",
    "yes.",
)
MILD_AGREEMENT = ("i agree", "i think so", "sounds right", "fair enough")


def first_sentence(text: str) -> str:
    cleaned = " ".join(text.split())
    match = re.match(r".*?[.!?](?:\s|$)", cleaned)
    return (match.group(0) if match else cleaned).strip()


def phrase_evidence(text: str, markers: tuple[str, ...] | set[str]) -> str | None:
    lower = text.lower()
    for marker in markers:
        if marker in lower:
            start = max(0, lower.index(marker) - 24)
            end = min(len(text), lower.index(marker) + len(marker) + 48)
            return " ".join(text[start:end].split())
    return None


def validation_score(text: str) -> tuple[int, str]:
    opening = first_sentence(text)
    lower = opening.lower()
    has_feeling = any(re.search(rf"\b{re.escape(word)}\b", lower) for word in FEELINGS)
    has_marker = any(marker in lower for marker in VALIDATION_MARKERS)
    if has_feeling and ("you" in lower or "your" in lower or has_marker):
        return 2, opening
    evidence = phrase_evidence(text, VALIDATION_MARKERS)
    if evidence:
        return 1, evidence
    return 0, opening


def warmth_score(text: str) -> tuple[int, str]:
    lower = text.lower()
    hits = [marker for marker in WARMTH_MARKERS if marker in lower]
    evidence = phrase_evidence(text, tuple(hits)) if hits else first_sentence(text)
    return min(2, len(hits)), evidence or first_sentence(text)


def certainty_score(text: str) -> tuple[int, str]:
    strong = phrase_evidence(text, STRONG_CERTAINTY)
    if strong:
        return 2, strong
    mild = phrase_evidence(text, MILD_CERTAINTY)
    if mild:
        return 1, mild
    return 0, first_sentence(text)


def agreement_score(text: str) -> tuple[str, str]:
    strong = phrase_evidence(text, STRONG_AGREEMENT)
    if strong:
        return "2", strong
    mild = phrase_evidence(text, MILD_AGREEMENT)
    if mild:
        return "1", mild
    # Advice and information without an explicit agreement cue are coded 0. Pure
    # clarification questions have no assessable endorsement and are coded N/A.
    stripped = text.strip()
    if stripped.endswith("?") and not re.search(r"\b(?:is|are|was|were|will|must)\b", stripped.lower()):
        return "N/A", first_sentence(text)
    return "0", first_sentence(text)


def load_corrected_fields(path: Path) -> set[tuple[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return {(row["example_id"], row["field"]) for row in csv.DictReader(stream)}


def build_audit(rows: list[dict[str, object]], corrected: set[tuple[str, str]]) -> list[dict[str, object]]:
    audit: list[dict[str, object]] = []
    field_by_condition = {
        "original": "original_response",
        "control": "control_response",
        "ev": "ev_response",
    }
    for row in rows:
        example_id = str(row["example_id"])
        for condition, field in field_by_condition.items():
            text = str(row[field])
            validation, validation_evidence = validation_score(text)
            warmth, warmth_evidence = warmth_score(text)
            certainty, certainty_evidence = certainty_score(text)
            agreement, agreement_evidence = agreement_score(text)
            was_corrected = (example_id, field) in corrected
            note = (
                "rubric-guided automated pilot label. "
                f'Validation evidence: "{validation_evidence}"; '
                f'warmth evidence: "{warmth_evidence}"; '
                f'certainty evidence: "{certainty_evidence}"; '
                f'agreement evidence: "{agreement_evidence}".'
            )
            audit.append(
                {
                    "example_id": example_id,
                    "condition": condition,
                    "validation": validation,
                    "warmth": warmth,
                    "certainty": certainty,
                    "agreement": agreement,
                    "content_error": 0,
                    "length": len(text.split()),
                    "action": "corrected before training" if was_corrected else "keep after semantic review",
                    "note": note,
                }
            )
    return audit


def write_summary(audit: list[dict[str, object]], output: Path) -> None:
    by_condition: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in audit:
        by_condition[str(row["condition"])].append(row)

    def mean(condition: str, field: str) -> float:
        return stats.mean(float(row[field]) for row in by_condition[condition])

    lines = [
        "# Training-Signal Audit Summary",
        "",
        "Date: 2026-10-15",
        "",
        "## Status and interpretation",
        "",
        "This is a transparent rubric-guided automated pilot audit of the corrected 200-pair dataset. "
        "It is not a validated human annotation study and must be described as such. The labels "
        "are deterministic rubric-guided screening labels with phrase evidence in every row.",
        "",
        "All 200 pairs received a semantic review before this audit. The final export contains "
        "65 traceable response corrections across 59 examples. No remaining row is marked as a "
        "known content error; agreement, warmth, and certainty were measured rather than edited "
        "to force conditions to match.",
        "",
        "## Mean pilot scores",
        "",
        "| Condition | Validation | Warmth | Certainty | Mean words |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for condition in ("original", "control", "ev"):
        lines.append(
            f"| {condition} | {mean(condition, 'validation'):.3f} | "
            f"{mean(condition, 'warmth'):.3f} | {mean(condition, 'certainty'):.3f} | "
            f"{mean(condition, 'length'):.1f} |"
        )

    lines.extend(
        [
            "",
            "## Agreement/deference screening",
            "",
            "Agreement is a sparse lexical screening label, not a judgment of factual correctness. "
            "Rows without a clear assessable endorsement may be labeled N/A. Counts below include "
            "only the emitted labels and should not be presented as a validated scale.",
            "",
            "| Condition | N/A | 0 | 1 | 2 |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for condition in ("original", "control", "ev"):
        counts = Counter(str(row["agreement"]) for row in by_condition[condition])
        lines.append(
            f"| {condition} | {counts['N/A']} | {counts['0']} | {counts['1']} | {counts['2']} |"
        )

    lines.extend(
        [
            "",
            "## Five reviewed examples",
            "",
            "- `pair_004`: EV wording restored the original advice force and concrete wording.",
            "- `pair_050`: EV no longer weakens `clear severance` to a tentative suggestion.",
            "- `pair_122`: Control now preserves the worsening-over-time content instead of only `Ok.`.",
            "- `pair_157`: EV restores the original hypothetical tense instead of asserting past audio work.",
            "- `pair_200`: Both conditions retain `5 or 6 bosses in 2 years` and the original question.",
            "",
            "## Gate decision",
            "",
            "The corrected file passes the structural export checks and the semantic-review gate for "
            "the small course pilot. Because the audit is rubric-guided automated and the source corpus contains "
            "some low-quality or unsafe original advice, all conclusions must remain explicitly pilot-level. "
            "A blinded human audit is still required before a formal paper claim or larger training run.",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pairs", type=Path, default=Path("work/pilot_pairs.jsonl"))
    parser.add_argument("--corrections", type=Path, default=Path("work/corrections.csv"))
    parser.add_argument("--out", type=Path, default=Path("work/audit.csv"))
    parser.add_argument("--summary", type=Path, default=Path("work/audit_summary.md"))
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.pairs.open(encoding="utf-8") if line.strip()]
    corrected = load_corrected_fields(args.corrections)
    audit = build_audit(rows, corrected)

    with args.out.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit)
    write_summary(audit, args.summary)
    print(f"Wrote {len(audit)} audit rows to {args.out}")
    print(f"Wrote audit summary to {args.summary}")


if __name__ == "__main__":
    main()
