"""Week 10: blind training-data audit (Nikhil), independent subsample (Rong), scoring, agreement.

  build:  python3 src/audit_sheet.py build --release formal/release/v0.1 [--frac 0.15]
                                            [--rong_frac 0.22]
          -> formal/audit/v0.1/
               nikhil/training_data_audit_blind.csv + annotation_guide.md   (send to Nikhil)
               rong/training_data_audit_rong_blind.csv + annotation_guide.md (send to Rong)
               audit_key.json                                  (Michael keeps; do NOT send)
               audit_sample.csv                                (which pairs, per stratum)
  score:  python3 src/audit_sheet.py score --filled <Nikhil's filled CSV>
          -> training_data_audit_<rater>.csv (unblinded, one row per pair), audit_summary.md/.json,
             corrections_todo_<rater>.csv (REVISE/REMOVE pairs for Michael)
  agree:  python3 src/audit_sheet.py agree --a <Nikhil filled> --b <Rong filled>
          -> agreement.md/.json (weighted kappa for IP/ER/EX/naturalness, Cohen's kappa + raw
             agreement for the categorical fields), disagreements.csv
  resample: python3 src/audit_sheet.py resample --release formal/release/v0.1 [--llm_n 150]
          Revised plan (Rong, 2026-11-15). Human audit = the 135 pairs already on Rong's sheet
          (Rong's sheet and mapping unchanged); Nikhil gets a new blind sheet with the SAME pairs,
          own random order and A/B labels. LLM audit = 150 further pairs (disjoint from the 135),
          stratified by dataset, seed 42 -> llm/llm_audit_blind.csv, llm_audit_prompts.jsonl,
          llm_output_schema.json, llm_audit_guide.md, llm_audit_ids.csv. The 15% Nikhil sheet
          is retired (its mapping is kept in the key under "superseded_nikhil_15pct").
  llm-score: python3 src/audit_sheet.py llm-score --filled a.csv b.csv --models m1 m2
          -> llm/llm_audit_unblinded.csv, llm_audit_summary.md/.json (flag rates, LLM-LLM
             agreement), llm_flags_to_verify.csv (pairs either LLM flagged, for Michael)

Sampling: a stratified 15-20% (default 15%) of complete exported pairs. Strata = dataset x
sampling stratum (ESConv early/middle/late, ED emotion label), proportional allocation (largest
remainder, at least 1 per stratum), seed 42. Rong's subsample is 20-25% (default 22%) of
Nikhil's sample, stratified by dataset, in its own random order and A/B labels, so neither
rater's sheet reveals the other's mapping.

Blinding: each pair is two rows (A/B) in random order; condition, automated-QC flags and
generation details are only in the key. Ratings are matched to (example_id, condition) via the
key, never by row position.
"""

import argparse
import collections
import csv
import json
import os
import random
import statistics

from prompt_pilot_sheet import ALLOWED, ANNOT, APPLIC, APPLIC_VALUES
from teacher_pilot_sheet import render

SEED = 42
DIMS = ("IP", "ER", "EX")
PAIR_COLS = APPLIC + ["pair_decision", "pair_issue"]
DECISIONS = ("pass", "revise", "remove")
ORDINAL = ["IP_score", "ER_score", "EX_score", "naturalness"]
NOMINAL = ["stance_relation", "evidence_alignment", "stance_preserved_vs_original",
           "facts_preserved", "advice_support_preserved", "unsupported_inference_or_agreement",
           "cold_or_dismissive"]
PLACEHOLDER = ("[UNPAIRABLE", "[INVALID_JSON", "[MISSING")

GUIDE = """# Training-data audit (formal dataset {version}): annotation guide

Each item ({prefix}0001, ...) is one dialogue with the user's current message, the ORIGINAL
supporter reply, and two rewritten replies, A and B. A and B are the two training targets made
from the same original; which is which is hidden and the order is random. Score A and B
separately. Rate independently: do not look at anyone else's ratings.

## Step 1 - context applicability (once per item, BEFORE reading A and B; fill on the A row)
From the dialogue and the user's current message only, for each EPITOME dimension:
- required      - a good supportive reply here should clearly include it
- optional      - it would fit, but a good reply could reasonably leave it out
- not_indicated - it would be unnecessary, forced, or inappropriate here
Columns: IP_applicability, ER_applicability, EX_applicability.

## Step 2 - score each reply (A row and B row)
IP - Interpretations: 0 = none; 1 = generic understanding or vague feeling reference;
     2 = specific, context-supported reflection of the user's feeling/experience.
ER - Emotional Reactions: 0 = none; 1 = implicit or generic warmth;
     2 = clear, proportionate warmth, compassion, or concern.
EX - Explorations: 0 = none; 1 = generic question ("What happened?");
     2 = gentle, specific question about a relevant feeling or experience not yet expressed.
Score what is in the reply, whatever you labelled in step 1. Unsupported emotion inference,
agreement, flattery, taking sides, or blanket reassurance are NOT empathy. For every non-zero
score paste the EXACT span from the reply as evidence, plus a one-line rationale.

Content and stance (vs the ORIGINAL reply):
- stance_relation: agree / disagree / neutral / not_applicable (to the user's explicit claim)
- evidence_alignment: supported / partially_supported / unsupported / not_applicable
- stance_preserved_vs_original, facts_preserved, advice_support_preserved: yes / no
- unsupported_inference_or_agreement: yes / no
- naturalness: 0 = unnatural/formulaic, 1 = acceptable, 2 = natural
- cold_or_dismissive: yes / no
- overall_rationale: one short evidence-based note

## Step 3 - pair decision (once per item; fill on the A row)
- pass   - both replies are usable training targets
- revise - fixable: say exactly what and in which reply (A or B) in pair_issue
- remove - drop the pair (e.g. a reply changes facts/advice/stance, adds unsupported claims,
           or the source pair itself is invalid)
pair_issue: required for revise/remove, e.g. "B adds a question the original did not ask".

Use only the allowed values (lowercase). Keep all rows and columns as they are. Save as UTF-8
CSV (Google Sheets -> File -> Download -> CSV; Excel can corrupt apostrophes). If a reply is a
bracketed placeholder, leave that row's scores empty.
"""


LLM_FLAGS = ["facts_changed", "advice_changed", "stance_changed",
             "unsupported_inference_or_agreement", "added_question", "added_content",
             "original_contradicts_context"]

LLM_PROMPT = """You are auditing training data for a supportive-dialogue model. A REWRITTEN reply \
was produced from an ORIGINAL supporter reply. The rewrite may change wording, tone and the \
amount of emotional warmth; that is intended and is NOT a problem by itself. Your job is to flag \
changes to substance.

Dialogue history:
{history}

User's current message:
{user}

ORIGINAL reply:
{original}

REWRITTEN reply:
{rewrite}

Answer each with "yes" or "no":
- facts_changed: the rewrite states, drops or alters a fact or detail compared with the original.
- advice_changed: the rewrite adds, removes or changes advice, suggestions or support offered.
- stance_changed: the rewrite takes a different position on the user's claim or situation
  (e.g. agrees where the original was neutral or disagreed).
- unsupported_inference_or_agreement: the rewrite asserts a feeling, motive or judgement the
  dialogue does not support, or agrees with / validates something the original did not.
- added_question: the rewrite asks a question the original did not ask.
- added_content: the rewrite adds other new substantive content (claims, information, offers)
  beyond rephrasing and emotional wording.
- original_contradicts_context: the ORIGINAL reply itself contradicts or does not fit the
  dialogue (wrong person, wrong situation, answers something not said).
evidence: for every "yes", quote the exact span(s) and say briefly why; otherwise "".

Return only JSON: {{"facts_changed": "yes|no", "advice_changed": "yes|no", "stance_changed": \
"yes|no", "unsupported_inference_or_agreement": "yes|no", "added_question": "yes|no", \
"added_content": "yes|no", "original_contradicts_context": "yes|no", "evidence": "..."}}
"""

LLM_GUIDE = """# LLM audit (formal dataset {version}): instructions for Nikhil

150 pairs = 300 rows (`llm_audit_blind.csv`; items L0001-L0150, rows A/B, random order, which
condition is which is hidden). These pairs do NOT overlap with the 135 pairs of the human audit.

Run TWO different LLMs, neither of them GPT-5.6 Sol or any OpenAI GPT-5.x model used to generate
the data, each independently on all 300 rows. One call per row, no shared context between rows,
temperature 0 (or the lowest the model allows).

- Prompt per row: `llm_audit_prompts.jsonl` ({{"row_id", "prompt"}}, already filled in), or
  build it from `llm_prompt_template.txt` with the CSV columns.
- Output: JSON per `llm_output_schema.json`.
- Return one CSV per model: a copy of `llm_audit_blind.csv` with the 8 output columns filled
  (`{flags}`, `evidence`), named `llm_audit_<model>.csv`, UTF-8. Keep every row and the
  row_id column unchanged. Note the exact model name/version, date, and settings used.

The LLMs only flag substance problems (facts, advice, stance, unsupported inference/agreement,
added questions or content, original vs context); no IP/ER/EX scoring. Michael verifies every
flag before anything is corrected or removed.
"""


# ------------------------------------------------------------------ helpers
def largest_remainder(sizes, total):
    n = sum(sizes.values())
    quota = {k: total * v / n for k, v in sizes.items()}
    alloc = {k: max(1, min(int(q), sizes[k])) for k, q in quota.items()}
    for k in sorted(quota, key=lambda k: (-(quota[k] - int(quota[k])), k)):
        if sum(alloc.values()) >= total:
            break
        if alloc[k] < sizes[k]:
            alloc[k] += 1
    return alloc


def write_csv(path, rows, fields=None):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def make_sheet(pairs, prefix, rng):
    rows, key = [], {}
    order = list(pairs)
    rng.shuffle(order)
    for i, p in enumerate(order, 1):
        item = f"{prefix}{i:04d}"
        conds = ["neutral", "empathy"]
        rng.shuffle(conds)
        for lab, c in zip("AB", conds, strict=True):
            rid = f"{item}-{lab}"
            key[rid] = {"example_id": p["example_id"], "condition": c}
            rows.append({"row_id": rid, "item": item, "label": lab,
                         "source_dataset": p["source_dataset"],
                         "dialogue_history": render(p["dialogue_context"][:-1]) or "(none)",
                         "current_user_message": p["current_user_utterance"],
                         "original_reply": p["original_response"],
                         "rewritten_reply": p[f"{c}_response"],
                         **{k: "" for k in APPLIC + ANNOT + ["pair_decision", "pair_issue"]}})
    return rows, key


# ------------------------------------------------------------------ build
def build(a):
    version = os.path.basename(os.path.normpath(a.release))
    out = a.out or f"formal/audit/{version}"
    pairs = [json.loads(line) for line in
             open(f"{a.release}/paired_rewrites_{version}.jsonl", encoding="utf-8")]
    rng = random.Random(SEED)
    strata = collections.defaultdict(list)
    for p in pairs:
        strata[(p["source_dataset"], p["sampling_stratum"])].append(p)
    target = round(a.frac * len(pairs))
    alloc = largest_remainder({k: len(v) for k, v in strata.items()}, target)
    sample, srows = [], []
    for k in sorted(strata):
        picked = rng.sample(sorted(strata[k], key=lambda p: p["example_id"]), alloc[k])
        sample += picked
        srows += [{"example_id": p["example_id"], "source_dataset": k[0], "stratum": k[1],
                   "in_rong_subsample": ""} for p in picked]
    # Rong: stratified by dataset, from Nikhil's sample
    rong = []
    by_ds = collections.defaultdict(list)
    for p in sample:
        by_ds[p["source_dataset"]].append(p)
    ralloc = largest_remainder({k: len(v) for k, v in by_ds.items()},
                               round(a.rong_frac * len(sample)))
    for ds in sorted(by_ds):
        rong += rng.sample(by_ds[ds], ralloc[ds])
    rong_ids = {p["example_id"] for p in rong}
    for r in srows:
        r["in_rong_subsample"] = "yes" if r["example_id"] in rong_ids else "no"

    n_rows, n_key = make_sheet(sample, "N", random.Random(SEED + 1))
    r_rows, r_key = make_sheet(rong, "R", random.Random(SEED + 2))
    for who, rows in (("nikhil", n_rows), ("rong", r_rows)):
        os.makedirs(f"{out}/{who}", exist_ok=True)
        name = "training_data_audit_blind.csv" if who == "nikhil" else \
            "training_data_audit_rong_blind.csv"
        write_csv(f"{out}/{who}/{name}", rows)
        open(f"{out}/{who}/annotation_guide.md", "w").write(
            GUIDE.format(version=version, prefix="N" if who == "nikhil" else "R"))
    write_csv(f"{out}/audit_sample.csv", srows)
    flags = {p["example_id"]: p["automated_qc_flags"] for p in pairs}
    json.dump({"note": "UNBLINDING KEY - do not share with raters until both ratings are saved",
               "release": a.release, "seed": SEED, "frac": a.frac, "rong_frac": a.rong_frac,
               "n_pairs_release": len(pairs), "n_sample": len(sample), "n_rong": len(rong),
               "automated_qc_flags": {p["example_id"]: flags[p["example_id"]] for p in sample},
               "nikhil": n_key, "rong": r_key},
              open(f"{out}/audit_key.json", "w"), indent=2)
    ds_counts = collections.Counter(p["source_dataset"] for p in sample)
    print(f"Nikhil: {len(sample)} pairs ({len(n_rows)} rows) = {len(sample)/len(pairs):.1%} of "
          f"{len(pairs)}; {dict(ds_counts)}; {len(strata)} strata")
    print(f"Rong:   {len(rong)} pairs ({len(r_rows)} rows) = {len(rong)/len(sample):.1%} of "
          f"Nikhil's sample; {dict(collections.Counter(p['source_dataset'] for p in rong))}")
    print(f"Wrote {out}/ (nikhil/, rong/, audit_key.json, audit_sample.csv)")


# ------------------------------------------------------------------ resample (revised plan)
def resample(a):
    version = os.path.basename(os.path.normpath(a.release))
    out = a.out or f"formal/audit/{version}"
    kj = json.load(open(f"{out}/audit_key.json"))
    pairs = {p["example_id"]: p for p in (json.loads(line) for line in open(
        f"{a.release}/paired_rewrites_{version}.jsonl", encoding="utf-8"))}
    human_ids = sorted({v["example_id"] for v in kj["rong"].values()})
    human = [pairs[e] for e in human_ids]
    n_rows, n_key = make_sheet(human, "N", random.Random(SEED + 3))
    assert all(n_key[r]["example_id"] in set(human_ids) for r in n_key)

    # LLM audit: disjoint from the human pairs, stratified by dataset, seed 42
    rest = collections.defaultdict(list)
    for e in sorted(pairs):
        if e not in set(human_ids):
            rest[pairs[e]["source_dataset"]].append(pairs[e])
    alloc = largest_remainder({k: len(v) for k, v in rest.items()}, a.llm_n)
    rng = random.Random(SEED)
    llm = [p for ds in sorted(rest) for p in rng.sample(rest[ds], alloc[ds])]
    assert not {p["example_id"] for p in llm} & set(human_ids)
    l_rows, l_key = make_sheet(llm, "L", random.Random(SEED + 4))
    for r in l_rows:
        for c in APPLIC + ANNOT + ["pair_decision", "pair_issue"]:
            del r[c]
        r.update({f: "" for f in LLM_FLAGS + ["evidence"]})

    # outputs: Nikhil's new human sheet (old 15% sheet retired), LLM pack, key
    os.makedirs(f"{out}/nikhil", exist_ok=True)
    old = f"{out}/nikhil/training_data_audit_blind.csv"
    if os.path.exists(old):
        os.remove(old)
    write_csv(f"{out}/nikhil/training_data_audit_nikhil_blind.csv", n_rows)
    open(f"{out}/nikhil/annotation_guide.md", "w").write(GUIDE.format(version=version,
                                                                      prefix="N"))
    L = f"{out}/llm"
    os.makedirs(L, exist_ok=True)
    write_csv(f"{L}/llm_audit_blind.csv", l_rows)
    with open(f"{L}/llm_audit_prompts.jsonl", "w", encoding="utf-8") as f:
        for r in l_rows:
            f.write(json.dumps({"row_id": r["row_id"], "prompt": LLM_PROMPT.format(
                history=r["dialogue_history"], user=r["current_user_message"],
                original=r["original_reply"], rewrite=r["rewritten_reply"])},
                ensure_ascii=False) + "\n")
    open(f"{L}/llm_prompt_template.txt", "w").write(LLM_PROMPT)
    schema = {"type": "object", "additionalProperties": False,
              "required": LLM_FLAGS + ["evidence"],
              "properties": {**{f: {"type": "string", "enum": ["yes", "no"]} for f in LLM_FLAGS},
                             "evidence": {"type": "string"}}}
    json.dump(schema, open(f"{L}/llm_output_schema.json", "w"), indent=2)
    open(f"{L}/llm_output_schema.json", "a").write("\n")
    open(f"{L}/llm_audit_guide.md", "w").write(LLM_GUIDE.format(
        version=version, flags="`, `".join(LLM_FLAGS)))
    write_csv(f"{L}/llm_audit_ids.csv", [{"example_id": p["example_id"],
                                          "source_dataset": p["source_dataset"],
                                          "stratum": p["sampling_stratum"]} for p in llm])
    write_csv(f"{out}/audit_sample.csv",
              [{"example_id": p["example_id"], "source_dataset": p["source_dataset"],
                "stratum": p["sampling_stratum"], "audit": "human"} for p in human]
              + [{"example_id": p["example_id"], "source_dataset": p["source_dataset"],
                  "stratum": p["sampling_stratum"], "audit": "llm"} for p in llm])
    if "superseded_nikhil_15pct" not in kj:
        kj["superseded_nikhil_15pct"] = kj["nikhil"]
    kj.update({"plan": "revised 2026-11-15 (Rong): human audit = Rong's 135 pairs rated by "
                       "Nikhil and Rong; LLM audit = 150 disjoint pairs, stratified by dataset",
               "n_sample": len(human), "nikhil": n_key, "llm": l_key, "llm_n": len(llm),
               "llm_seed": SEED,
               "automated_qc_flags": {p["example_id"]: p["automated_qc_flags"]
                                      for p in human + llm}})
    json.dump(kj, open(f"{out}/audit_key.json", "w"), indent=2)
    c = collections.Counter
    print(f"Human: {len(human)} pairs ({len(n_rows)} rows on Nikhil's new sheet; Rong's sheet "
          f"unchanged) {dict(c(p['source_dataset'] for p in human))}")
    print(f"LLM:   {len(llm)} pairs ({len(l_rows)} rows) "
          f"{dict(c(p['source_dataset'] for p in llm))}"
          f"; together {len(human) + len(llm)} = {(len(human) + len(llm)) / len(pairs):.1%} "
          f"of {len(pairs)}")


# ------------------------------------------------------------------ LLM audit scoring
def yn(v):
    v = (v or "").strip().lower()
    return {"true": "yes", "false": "no", "1": "yes", "0": "no"}.get(v, v)


def llm_score(a):
    kj = json.load(open(a.key))
    key = kj["llm"]
    assert len(a.filled) == len(a.models) >= 1, "give one --models name per --filled file"
    res = {}
    for path, m in zip(a.filled, a.models, strict=True):
        rows = list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))
        assert {r["row_id"] for r in rows} == set(key), f"{path}: row_ids differ from the key"
        errs = [f"{r['row_id']}: {f}={r.get(f)!r}" for r in rows for f in LLM_FLAGS
                if yn(r.get(f)) not in ("yes", "no")]
        if errs:
            raise SystemExit(f"{path}: {len(errs)} bad cells:\n  " + "\n  ".join(errs[:40]))
        res[m] = {r["row_id"]: {**{f: yn(r[f]) for f in LLM_FLAGS},
                                "evidence": r.get("evidence", "")} for r in rows}
    out = a.out or os.path.join(os.path.dirname(a.key), "llm")
    os.makedirs(out, exist_ok=True)
    table = []
    for rid in sorted(key):
        k = key[rid]
        for m in a.models:
            table.append({"example_id": k["example_id"], "condition": k["condition"],
                          "row_id": rid, "model": m, **res[m][rid]})
    write_csv(f"{out}/llm_audit_unblinded.csv", table)

    summ = {"n_pairs": len(key) // 2, "models": a.models, "flag_rate": {}, "agreement": {}}
    for m in a.models:
        summ["flag_rate"][m] = {c: {f: sum(res[m][r][f] == "yes" for r in key
                                           if key[r]["condition"] == c) for f in LLM_FLAGS}
                                for c in ("neutral", "empathy")}
    if len(a.models) >= 2:
        m1, m2 = a.models[:2]
        for f in LLM_FLAGS:
            x = [res[m1][r][f] for r in sorted(key)]
            y = [res[m2][r][f] for r in sorted(key)]
            summ["agreement"][f] = {"kappa": cohen_kappa(x, y, ["no", "yes"]),
                                    "raw_agreement": round(sum(i == j for i, j in zip(
                                        x, y, strict=True)) / len(x), 3)}
    verify = collections.defaultdict(list)
    for t in table:
        for f in LLM_FLAGS:
            if t[f] == "yes":
                verify[t["example_id"]].append((t["model"], t["condition"], f, t["evidence"]))
    vrows = []
    for e, hits in sorted(verify.items(), key=lambda kv: -len({h[0] for h in kv[1]})):
        vrows.append({"example_id": e, "action": "", "new_text": "",
                      "reason": " | ".join(f"{m}:{c}:{f}" for m, c, f, _ in hits),
                      "flagged_by": "LLM:" + "+".join(sorted({h[0] for h in hits})),
                      "decided_by": "", "n_models_flagging": len({h[0] for h in hits}),
                      "evidence": " || ".join(dict.fromkeys(
                          f"[{m}/{c}] {ev}" for m, c, _, ev in hits if ev))})
    if vrows:
        write_csv(f"{out}/llm_flags_to_verify.csv", vrows)
    summ["pairs_flagged_by_any"] = len(vrows)
    summ["pairs_flagged_by_all"] = sum(r["n_models_flagging"] == len(a.models) for r in vrows)
    json.dump(summ, open(f"{out}/llm_audit_summary.json", "w"), indent=2)
    open(f"{out}/llm_audit_summary.json", "a").write("\n")
    L = ["# LLM audit summary (unblinded)", "",
         f"{summ['n_pairs']} pairs, models: {', '.join(a.models)}. Pairs flagged by any model: "
         f"{summ['pairs_flagged_by_any']}; by all: {summ['pairs_flagged_by_all']}.", "",
         "| Flag | " + " | ".join(f"{m} N | {m} E" for m in a.models) + " | kappa | raw |",
         "|---|" + "---|---|" * len(a.models) + "---|---|"]
    for f in LLM_FLAGS:
        ag = summ["agreement"].get(f, {})
        L.append(f"| {f} | " + " | ".join(
            f"{summ['flag_rate'][m]['neutral'][f]} | {summ['flag_rate'][m]['empathy'][f]}"
            for m in a.models) + f" | {ag.get('kappa', '')} | {ag.get('raw_agreement', '')} |")
    L += ["", "Counts are rows flagged (out of 150 per condition). `llm_flags_to_verify.csv`: one "
          "row per flagged pair; Michael verifies and fills action/new_text before copying "
          "confirmed rows into formal/release/corrections.csv."]
    open(f"{out}/llm_audit_summary.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# ------------------------------------------------------------------ read + validate a filled sheet
def load_filled(path, key):
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig", newline="")))
    assert {r["row_id"] for r in rows} == set(key), f"{path}: row_ids differ from the key"
    errs, items = [], collections.defaultdict(dict)
    for r in rows:
        it = items[r["item"]]
        for c in PAIR_COLS:  # pair-level: one value per item, from either row
            v = (r.get(c) or "").strip()
            v = v if c == "pair_issue" else v.lower()
            if v:
                ok = APPLIC_VALUES if c in APPLIC else DECISIONS if c == "pair_decision" else None
                if ok and v not in ok:
                    errs.append(f"{r['row_id']}: {c}={v!r}")
                elif c != "pair_issue" and it.setdefault(c, v) != v:
                    errs.append(f"{r['item']}: conflicting {c} on A and B rows")
                elif c == "pair_issue":
                    it[c] = (it.get(c, "") + " " + v).strip()
        if r["rewritten_reply"].startswith(PLACEHOLDER):
            r["_skip"] = True
            continue
        for c, ok in ALLOWED.items():
            v = (r.get(c) or "").strip().lower()
            r[c] = v
            if v not in ok:
                errs.append(f"{r['row_id']}: {c}={v!r}")
    for item, it in items.items():
        for c in APPLIC + ["pair_decision"]:
            if c not in it:
                errs.append(f"{item}: {c} missing")
        if it.get("pair_decision") in ("revise", "remove") and not it.get("pair_issue"):
            errs.append(f"{item}: pair_issue required for {it['pair_decision']}")
    if errs:
        raise SystemExit(f"{path}: fix these cells first ({len(errs)}):\n  "
                         + "\n  ".join(sorted(errs)[:60]))
    return rows, items


def by_pair(rows, items, key):
    """-> {example_id: {"item":..., "pair": {...}, "neutral": row, "empathy": row}}"""
    out = {}
    for r in rows:
        k = key[r["row_id"]]
        d = out.setdefault(k["example_id"], {"item": r["item"], "pair": items[r["item"]]})
        if not r.get("_skip"):
            d[k["condition"]] = r
            d[f"{k['condition']}_label"] = r["label"]
    return out


def mean(xs):
    return round(statistics.mean(xs), 2) if xs else None


# ------------------------------------------------------------------ score (Nikhil)
def score(a):
    kj = json.load(open(a.key))
    key = kj[a.rater]
    rows, items = load_filled(a.filled, key)
    P = by_pair(rows, items, key)
    out = a.out or os.path.dirname(a.key)
    full = [e for e, d in P.items() if "neutral" in d and "empathy" in d]

    # unblinded per-pair table
    table = []
    for e, d in sorted(P.items()):
        row = {"example_id": e, "item": d["item"], "source_dataset": None,
               **{c: d["pair"].get(c, "") for c in PAIR_COLS},
               "automated_qc_flags": "|".join(kj["automated_qc_flags"].get(e, []))}
        for c in ("neutral", "empathy"):
            r = d.get(c, {})
            row["source_dataset"] = row["source_dataset"] or r.get("source_dataset")
            row[f"{c}_label"] = d.get(f"{c}_label", "")
            for f in ANNOT:
                row[f"{c}_{f}"] = r.get(f, "")
        table.append(row)
    write_csv(f"{out}/training_data_audit_{a.rater}.csv", table)

    res = {"rater": a.rater, "n_pairs": len(P), "n_complete": len(full)}
    for c in ("neutral", "empathy"):
        rs = [P[e][c] for e in full]
        res[c] = {**{d: mean([int(x[f"{d}_score"]) for x in rs]) for d in DIMS},
                  "naturalness": mean([int(x["naturalness"]) for x in rs]),
                  **{f"{f}=no": sum(x[f] == "no" for x in rs) for f in
                     ("facts_preserved", "advice_support_preserved",
                      "stance_preserved_vs_original")},
                  **{f"{f}=yes": sum(x[f] == "yes" for x in rs) for f in
                     ("unsupported_inference_or_agreement", "cold_or_dismissive")}}
    diff = {d: {e: int(P[e]["empathy"][f"{d}_score"]) - int(P[e]["neutral"][f"{d}_score"])
                for e in full} for d in DIMS}
    res["empathy_minus_neutral"] = {d: mean(list(diff[d].values())) for d in DIMS}
    res["by_applicability"] = {
        f"{d}/{lvl}": {"n": len(es), "neutral": mean([int(P[e]["neutral"][f"{d}_score"])
                                                      for e in es]),
                       "empathy": mean([int(P[e]["empathy"][f"{d}_score"]) for e in es]),
                       "share_E_gt_N": mean([diff[d][e] > 0 for e in es])}
        for d in DIMS for lvl in APPLIC_VALUES
        for es in [[e for e in full if P[e]["pair"][f"{d}_applicability"] == lvl]]}
    dec = collections.Counter(d["pair"]["pair_decision"] for d in P.values())
    res["pair_decisions"] = dict(dec)
    by_ds = collections.defaultdict(collections.Counter)
    for t in table:
        by_ds[t["source_dataset"]][t["pair_decision"]] += 1
    res["pair_decisions_by_dataset"] = {k: dict(v) for k, v in by_ds.items()}
    json.dump(res, open(f"{out}/audit_summary_{a.rater}.json", "w"), indent=2)

    todo = [{"example_id": t["example_id"], "action": "remove" if t["pair_decision"] == "remove"
             else "", "new_text": "", "reason": t["pair_issue"],
             "flagged_by": a.rater.capitalize(), "decided_by": "",
             "audit_decision": t["pair_decision"], "neutral_was_label": t["neutral_label"],
             "empathy_was_label": t["empathy_label"]}
            for t in table if t["pair_decision"] in ("revise", "remove")]
    if todo:
        write_csv(f"{out}/corrections_todo_{a.rater}.csv", todo)

    L = [f"# Training-data audit summary ({a.rater}, unblinded)", "",
         f"{len(P)} audited pairs ({len(full)} with both conditions scored). Pair decisions: "
         + ", ".join(f"{k} {v}" for k, v in dec.most_common()) + ".", "",
         "| Dataset | pass | revise | remove |", "|---|---|---|---|"]
    L += [f"| {k} | {v['pass']} | {v['revise']} | {v['remove']} |" for k, v in by_ds.items()]
    L += ["", "| Condition | IP | ER | EX | Natural | Facts✗ | Advice✗ | Stance✗ | Unsupported | "
          "Cold |", "|---|---|---|---|---|---|---|---|---|---|"]
    for c in ("neutral", "empathy"):
        o = res[c]
        L.append(f"| {c} | {o['IP']} | {o['ER']} | {o['EX']} | {o['naturalness']} | "
                 f"{o['facts_preserved=no']} | {o['advice_support_preserved=no']} | "
                 f"{o['stance_preserved_vs_original=no']} | "
                 f"{o['unsupported_inference_or_agreement=yes']} | {o['cold_or_dismissive=yes']} |")
    d = res["empathy_minus_neutral"]
    L += ["", f"Empathy - Neutral: IP {d['IP']:+}, ER {d['ER']:+}, EX {d['EX']:+}.", "",
          "| Dim / applicability | n | Neutral | Empathy | Share E>N |", "|---|---|---|---|---|"]
    L += [f"| {k} | {v['n']} | {v['neutral']} | {v['empathy']} | {v['share_E_gt_N']} |"
          for k, v in res["by_applicability"].items()]
    L += ["", f"REVISE/REMOVE pairs: {len(todo)} -> `corrections_todo_{a.rater}.csv` (Michael "
          "fills action + new_text, then copies rows into formal/release/corrections.csv). "
          "Labels A/B in that file are the rater's view; neutral_was_label / "
          "empathy_was_label map them."]
    open(f"{out}/audit_summary_{a.rater}.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


# ------------------------------------------------------------------ agreement
def cohen_kappa(x, y, cats, weights=None):
    """Cohen's kappa; weights='linear' or 'quadratic' for ordinal categories (in order)."""
    n, k = len(x), len(cats)
    if n == 0:
        return None
    idx = {c: i for i, c in enumerate(cats)}
    obs = [[0] * k for _ in range(k)]
    for a, b in zip(x, y, strict=True):
        obs[idx[a]][idx[b]] += 1
    ra = [sum(row) for row in obs]
    cb = [sum(obs[i][j] for i in range(k)) for j in range(k)]

    def w(i, j):
        if weights is None:
            return 0.0 if i == j else 1.0
        d = abs(i - j) / (k - 1)
        return d if weights == "linear" else d * d
    po = sum(w(i, j) * obs[i][j] for i in range(k) for j in range(k)) / n
    pe = sum(w(i, j) * ra[i] * cb[j] for i in range(k) for j in range(k)) / (n * n)
    if pe == 0:
        return 1.0 if po == 0 else None
    return round(1 - po / pe, 3)


def agree(a):
    kj = json.load(open(a.key))
    ra, ia = load_filled(a.a, kj["nikhil"])
    rb, ib = load_filled(a.b, kj["rong"])
    A, B = by_pair(ra, ia, kj["nikhil"]), by_pair(rb, ib, kj["rong"])
    common = sorted(set(A) & set(B))
    assert common, "no pairs in common: is --b Rong's sheet from the same audit build?"
    res, dis = {"n_pairs": len(common)}, []
    fields = [(f, ["0", "1", "2"], a.weights) for f in ORDINAL] + \
        [(f, sorted(ALLOWED[f]), None) for f in NOMINAL]
    for f, cats, wts in fields:
        x, y = [], []
        for e in common:
            for c in ("neutral", "empathy"):
                if c in A[e] and c in B[e]:
                    x.append(A[e][c][f])
                    y.append(B[e][c][f])
                    if A[e][c][f] != B[e][c][f]:
                        dis.append({"example_id": e, "condition": c, "field": f,
                                    "nikhil": A[e][c][f], "rong": B[e][c][f],
                                    "nikhil_row": f"{A[e]['item']}-{A[e][c + '_label']}",
                                    "rong_row": f"{B[e]['item']}-{B[e][c + '_label']}"})
        res[f] = {"n": len(x), "kappa": cohen_kappa(x, y, cats, wts),
                  "kappa_type": f"weighted ({wts})" if wts else "cohen",
                  "raw_agreement": round(sum(i == j for i, j in zip(x, y, strict=True))
                                         / len(x), 3) if x else None}
    for f, cats in [(c, list(APPLIC_VALUES)) for c in APPLIC] + [("pair_decision",
                                                                  list(DECISIONS))]:
        x = [A[e]["pair"][f] for e in common]
        y = [B[e]["pair"][f] for e in common]
        res[f] = {"n": len(x), "kappa": cohen_kappa(x, y, cats), "kappa_type": "cohen",
                  "raw_agreement": round(sum(i == j for i, j in zip(x, y, strict=True))
                                         / len(x), 3)}
        dis += [{"example_id": e, "condition": "pair", "field": f, "nikhil": i, "rong": j,
                 "nikhil_row": A[e]["item"], "rong_row": B[e]["item"]}
                for e, i, j in zip(common, x, y, strict=True) if i != j]
    out = a.out or os.path.dirname(a.key)
    json.dump(res, open(f"{out}/agreement.json", "w"), indent=2)
    if dis:
        write_csv(f"{out}/disagreements.csv", dis)
    L = ["# Inter-rater agreement (Nikhil vs Rong, before adjudication)", "",
         f"{len(common)} pairs rated by both. Ordinal fields: weighted kappa ({a.weights}); "
         "categorical fields: Cohen's kappa + raw agreement. Kappa is unstable when one "
         "category dominates; read it together with raw agreement.", "",
         "| Field | n | kappa | type | raw agreement |", "|---|---|---|---|---|"]
    L += [f"| {f} | {v['n']} | {v['kappa']} | {v['kappa_type']} | {v['raw_agreement']} |"
          for f, v in res.items() if isinstance(v, dict)]
    L += ["", f"{len(dis)} disagreeing cells -> `disagreements.csv`. Keep both raw rating files "
          "unchanged; record adjudicated values in a separate file."]
    open(f"{out}/agreement.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--release", default="formal/release/v0.1")
    b.add_argument("--frac", type=float, default=0.15)
    b.add_argument("--rong_frac", type=float, default=0.22)
    b.add_argument("--out")
    s = sub.add_parser("score")
    s.add_argument("--filled", required=True)
    s.add_argument("--rater", default="nikhil", choices=["nikhil", "rong"])
    s.add_argument("--key", default="formal/audit/v0.1/audit_key.json")
    s.add_argument("--out")
    g = sub.add_parser("agree")
    g.add_argument("--a", required=True, help="Nikhil's filled sheet")
    g.add_argument("--b", required=True, help="Rong's filled sheet")
    g.add_argument("--key", default="formal/audit/v0.1/audit_key.json")
    g.add_argument("--weights", default="linear", choices=["linear", "quadratic"])
    g.add_argument("--out")
    r = sub.add_parser("resample")
    r.add_argument("--release", default="formal/release/v0.1")
    r.add_argument("--llm_n", type=int, default=150)
    r.add_argument("--out")
    m = sub.add_parser("llm-score")
    m.add_argument("--filled", nargs="+", required=True)
    m.add_argument("--models", nargs="+", required=True)
    m.add_argument("--key", default="formal/audit/v0.1/audit_key.json")
    m.add_argument("--out")
    a = ap.parse_args()
    {"build": build, "score": score, "agree": agree, "resample": resample,
     "llm-score": llm_score}[a.cmd](a)


if __name__ == "__main__":
    main()
