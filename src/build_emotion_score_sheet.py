"""Build a manual scoring worksheet for the emotional-validation evaluation (Harini).

Usage:
  python3 src/build_emotion_score_sheet.py \
      --answers results/control_vs_standard_ev_200_train/answers.csv \
      --pilot work/emotion_pilot.jsonl \
      --out work/emotion_scores_worksheet.csv

What it does (it does NOT score anything):
  - Keeps only the rows with prompt_type == "emotion" (the 40 that belong to Harini:
    20 items x 2 blinded model codes).
  - Joins each answer to its FULL context from emotion_pilot.jsonl by item_id, so the
    rater reads the conversation and the coded answer side by side.
  - Leaves validation, helpfulness, appropriateness, and note BLANK for the rater.
  - Pre-fills a closing_flag column: 1 when the final seeker turn is mainly a
    thank-you / closing message (hard to score for validation), else 0. This is a
    reading aid only; the rater still judges every row.

When scoring is finished, export the final deliverable with the 6-column schema:
  python3 src/build_emotion_score_sheet.py --finalize work/emotion_scores_worksheet.csv \
      --out work/emotion_scores.csv
  -> writes item_id,model_code,validation,helpfulness,appropriateness,note
     (drops context/answer/closing_flag) and checks every score is an integer 0-2.
"""
import argparse
import csv
import io
import json
import re
import sys

SCHEMA = ["item_id", "model_code", "validation", "helpfulness", "appropriateness", "note"]
# phrases that mark a final seeker turn as mainly a closing / thank-you
CLOSE = re.compile(r"\b(thank you|thanks|take care|goodbye|good bye|bye|have a (great|good|wonderful|lovely)"
                   r"|happy holidays|stay (safe|healthy)|all the best|see you|god bless)\b", re.I)


def last_seeker_turn(context):
    seeker = [ln[len("Seeker:"):].strip() for ln in context.splitlines() if ln.startswith("Seeker:")]
    return seeker[-1] if seeker else ""


def is_closing(turn):
    """Closing if it is short and dominated by thank-you/farewell language."""
    if not turn:
        return False
    return bool(CLOSE.search(turn)) and len(turn.split()) <= 25


def build(answers_path, pilot_path, out_path):
    ctx = {json.loads(l)["item_id"]: json.loads(l)["context"] for l in open(pilot_path)}
    rows = []
    for r in csv.DictReader(open(answers_path, encoding="utf-8")):
        if r.get("prompt_type") != "emotion":
            continue
        iid = r["item_id"]
        rows.append({"item_id": iid, "model_code": r["model_code"],
                     "closing_flag": 1 if is_closing(last_seeker_turn(ctx.get(iid, ""))) else 0,
                     "context": ctx.get(iid, "<<MISSING CONTEXT>>"), "answer": r["answer"],
                     "validation": "", "helpfulness": "", "appropriateness": "", "note": ""})
    rows.sort(key=lambda x: (x["item_id"], x["model_code"]))
    cols = ["item_id", "model_code", "closing_flag", "context", "answer",
            "validation", "helpfulness", "appropriateness", "note"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    n_items = len({r["item_id"] for r in rows})
    n_flag = sum(r["closing_flag"] for r in rows)
    print(f"Wrote {out_path}: {len(rows)} rows ({n_items} items x model codes), "
          f"{n_flag} rows flagged as closing. Score columns are blank.")
    if len(rows) != 40:
        print(f"  WARNING: expected 40 emotion rows, found {len(rows)}.")


def finalize(sheet_path, out_path):
    # Tolerate a stray title line above the real header (a spreadsheet-export quirk):
    # skip any leading lines until the one that starts with the "item_id" header.
    lines = open(sheet_path, encoding="utf-8-sig").read().splitlines(keepends=True)
    start = next((k for k, ln in enumerate(lines) if ln.lstrip().startswith("item_id,")), 0)
    reader = csv.DictReader(io.StringIO("".join(lines[start:])))
    rows, bad = [], []
    for i, r in enumerate(reader, start=2):
        out = {k: (r.get(k, "") or "").strip() for k in SCHEMA}
        for dim in ("validation", "helpfulness", "appropriateness"):
            v = out[dim]
            if v not in ("0", "1", "2"):
                bad.append(f"line {i} {out['item_id']}/{out['model_code']}: {dim}={v!r} (need 0/1/2)")
        rows.append(out)
    if bad:
        print("NOT WRITTEN - unscored or invalid rows:", *bad, sep="\n  ")
        sys.exit(1)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SCHEMA)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out_path}: {len(rows)} scored rows in the 6-column schema.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers")
    ap.add_argument("--pilot", default="work/emotion_pilot.jsonl")
    ap.add_argument("--finalize")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.finalize:
        finalize(a.finalize, a.out)
    elif a.answers:
        build(a.answers, a.pilot, a.out)
    else:
        ap.error("give --answers (to build the worksheet) or --finalize (to export scores)")


if __name__ == "__main__":
    main()
