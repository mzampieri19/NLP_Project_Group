"""Sanity checks before and after finalize_pairs.py, plus numbers for your writeup.

BEFORE finalizing (checks your corrections file):
  python -X utf8 verify_export.py --work work/ --corrections corrections.csv

AFTER finalizing (checks the file you send to Rong):
  python -X utf8 verify_export.py --work work/ --final pilot_pairs.jsonl [--expect 200]

(-X utf8 makes Python read/write UTF-8 on Windows, so curly quotes don't turn into
 garbage like 'â€™'.)
"""
import argparse, csv, json, re, statistics as st

FIELDS = ["example_id", "conversation_id", "context", "original_response",
          "control_response", "ev_response"]
MOJIBAKE = re.compile("â€|Ã.|Â")


def load(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def check_corrections(work, path):
    raw = {r["example_id"]: r for r in load(f"{work}/pilot_pairs_raw.jsonl")}
    problems, seen = [], set()
    with open(path, encoding="utf-8-sig", newline="") as f:
        rd = csv.DictReader(f)
        need = ["example_id", "field", "corrected_text", "reason", "corrected_by"]
        if rd.fieldnames != need:
            print(f"HEADER PROBLEM: expected {need}, got {rd.fieldnames}")
            return
        n = 0
        for i, c in enumerate(rd, start=2):
            n += 1
            where = f"line {i} ({c['example_id']})"
            if c["example_id"] not in raw:
                problems.append(f"{where}: unknown example_id")
                continue
            if c["field"] not in ("control_response", "ev_response"):
                problems.append(f"{where}: field must be control_response or ev_response")
                continue
            key = (c["example_id"], c["field"])
            if key in seen:
                problems.append(f"{where}: duplicate row for {c['field']}; combine into one")
            seen.add(key)
            txt = c["corrected_text"].strip()
            if not txt:
                problems.append(f"{where}: corrected_text is empty")
            elif txt == raw[c["example_id"]][c["field"]].strip():
                problems.append(f"{where}: corrected_text is identical to the generated text")
            if not c["reason"].strip():
                problems.append(f"{where}: reason is empty")
            if MOJIBAKE.search(txt):
                problems.append(f"{where}: garbled characters (save the CSV as UTF-8)")
    print(f"{n} correction rows, {len({k[0] for k in seen})} distinct examples.")
    print("PROBLEMS:" if problems else "No problems found.", *problems, sep="\n  ")


def check_final(work, path, expect):
    rows = load(path)
    orig = {r["example_id"]: r for r in load(f"{work}/pilot_pairs_original.jsonl")}
    ids = [r["example_id"] for r in rows]
    bad = []
    if len(rows) != expect:
        bad.append(f"expected {expect} rows, found {len(rows)}")
    if len(set(ids)) != len(ids):
        bad.append("duplicate example_ids")
    if any(list(r) != FIELDS for r in rows):
        bad.append("some rows do not have exactly the six required fields, in order")
    if any(not r["control_response"].strip() or not r["ev_response"].strip() for r in rows):
        bad.append("empty control or ev response")
    if any(MOJIBAKE.search(r["control_response"] + r["ev_response"]) for r in rows):
        bad.append("garbled characters found (check encoding)")
    extra, missing = sorted(set(ids) - set(orig)), sorted(set(orig) - set(ids))
    if extra or missing:
        bad.append("ids differ from work/pilot_pairs_original.jsonl: "
                   f"in final but not original: {extra or 'none'}; "
                   f"in original but not final: {missing or 'none'}. "
                   "The final file is probably stale: rerun finalize_pairs.py")
    print("PROBLEMS:" if bad else "Export looks valid.", *bad, sep="\n  ")

    w = lambda s: len(s.split())
    wo = [w(r["original_response"]) for r in rows]
    wc = [w(r["control_response"]) for r in rows]
    we = [w(r["ev_response"]) for r in rows]
    gap = [e - c for e, c in zip(we, wc)]
    both = [r for r in rows if r["example_id"] in orig]
    edited_c = sum(r["control_response"] != orig[r["example_id"]]["control_response"] for r in both)
    edited_e = sum(r["ev_response"] != orig[r["example_id"]]["ev_response"] for r in both)
    print("\nNumbers for the writeup:")
    print(f"  examples: {len(rows)} from {len({r['conversation_id'] for r in rows})} conversations")
    print(f"  mean words: original {st.mean(wo):.1f}, control {st.mean(wc):.1f}, ev {st.mean(we):.1f}")
    print(f"  EV minus Control words: mean {st.mean(gap):+.1f}, median {st.median(gap):+.1f}, "
          f"max {max(gap):+d}; EV longer in {sum(g > 0 for g in gap)}/{len(gap)}")
    print(f"  hand-edited replies: control {edited_c}, ev {edited_e} "
          f"(of {len(both)} comparable examples; "
          f"{len({r['example_id'] for r in both if r['control_response'] != orig[r['example_id']]['control_response'] or r['ev_response'] != orig[r['example_id']]['ev_response']})} touched)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--corrections")
    ap.add_argument("--final")
    ap.add_argument("--expect", type=int, default=200)
    a = ap.parse_args()
    if a.corrections:
        check_corrections(a.work, a.corrections)
    if a.final:
        check_final(a.work, a.final, a.expect)
    if not (a.corrections or a.final):
        ap.error("give --corrections and/or --final")
