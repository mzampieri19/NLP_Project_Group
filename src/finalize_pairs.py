"""Apply human corrections, keep originals, write a change log, export for Rong.

Usage: python finalize_pairs.py --work work/ --corrections corrections.csv

corrections.csv columns: example_id, field, corrected_text, reason, corrected_by
  field is one of: control_response, ev_response
Leave the file header-only (or omit --corrections) if nothing needs fixing.

Outputs:
  work/pilot_pairs_original.jsonl   untouched generated outputs (retained)
  work/change_log.csv               every edit: id, field, old, new, reason, by, date
  pilot_pairs.jsonl                 FINAL checked data for Rong (one example per line,
                                    exactly: example_id, conversation_id, context,
                                    original_response, control_response, ev_response)
"""

import argparse
import csv
import datetime
import json
import shutil

FIELDS = [
    "example_id",
    "conversation_id",
    "context",
    "original_response",
    "control_response",
    "ev_response",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--corrections")
    ap.add_argument("--out", default="pilot_pairs.jsonl")
    a = ap.parse_args()

    shutil.copy(f"{a.work}/pilot_pairs_raw.jsonl", f"{a.work}/pilot_pairs_original.jsonl")
    rows = {
        json.loads(loads)["example_id"]: json.loads(loads)
        for loads in open(f"{a.work}/pilot_pairs_raw.jsonl")
    }

    log = []
    if a.corrections:
        for c in csv.DictReader(open(a.corrections)):
            r = rows[c["example_id"]]
            assert c["field"] in ("control_response", "ev_response"), c
            log.append(
                [
                    c["example_id"],
                    c["field"],
                    r[c["field"]],
                    c["corrected_text"],
                    c["reason"],
                    c.get("corrected_by", ""),
                    datetime.date.today().isoformat(),
                ]
            )
            r[c["field"]] = c["corrected_text"].strip()

    with open(f"{a.work}/change_log.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            ["example_id", "field", "old_text", "new_text", "reason", "corrected_by", "date"]
        )
        w.writerows(log)

    ids = list(rows)
    assert len(ids) == len(set(ids)), "duplicate example_ids"
    with open(a.out, "w") as f:
        for i in ids:
            r = rows[i]
            assert r["control_response"].strip() and r["ev_response"].strip(), f"empty output {i}"
            f.write(json.dumps({k: r[k] for k in FIELDS}) + "\n")
    print(f"Exported {len(ids)} examples to {a.out}; {len(log)} corrections logged.")


if __name__ == "__main__":
    main()
