"""Week 9 Steps 3-4: generate Neutral and Empathy rewrites with one teacher model.

Formal run (Week 10):
  .venv/bin/python src/generate_rewrites.py --teacher formal/teachers/gpt-5.6-sol-medium.json \
      --prompts formal/prompts/v2.1 --ids formal/sample/v0.1/sample_ids.jsonl \
      --out formal/generation --workers 16
Usage (teacher-selection pilot, run once per teacher):
  .venv/bin/python src/generate_rewrites.py --teacher formal/teachers/gpt-5.6-sol.json \
      --ids formal/teacher_pilot/pilot_contexts.jsonl --out formal/teacher_pilot
  .venv/bin/python src/generate_rewrites.py --teacher formal/teachers/gpt-4o-2024-08-06.json \
      --ids formal/teacher_pilot/pilot_contexts.jsonl --out formal/teacher_pilot
  add --dry_run to build every request and write placeholder outputs WITHOUT calling the API
  (output goes to <out>/<teacher_id>__dryrun/), and --show 1 to print the first request.

Writes to <out>/<teacher_id>/:
  raw_rewrites.jsonl        one line per (example_id, condition) call: parsed status/response,
                            the raw text returned, model name returned, ids, usage, timestamps
  pairs.jsonl               examples where BOTH conditions returned status OK
  generation_metadata.json  teacher, provider, API id, dates, settings (incl. not-exposed ones),
                            prompt version + hash, counts
  generate.log

Rules enforced (Rewrite Protocol v2.0):
  - Neutral and Empathy are two separate calls with identical inputs; neither sees the other.
  - Only the condition instruction differs; same teacher and settings for both.
  - Source metadata is never read here (only records_base.jsonl, which has none).
  - Resumable; refuses to continue if the prompt files changed (hash) or the returned model
    name changes mid-batch. Needs OPENAI_API_KEY (except --dry_run).
"""

import argparse
import concurrent.futures as cf
import datetime
import hashlib
import json
import logging
import os
import statistics
import sys
import time

log = logging.getLogger("generate_rewrites")
CONDITIONS = ("neutral", "empathy")
NO_RETRY = {"AuthenticationError", "PermissionDeniedError", "BadRequestError", "NotFoundError"}
SCHEMA = {
    "type": "json_schema", "name": "rewrite_target", "strict": True,
    "schema": {"type": "object", "additionalProperties": False,
               "required": ["status", "rewritten_response", "reason_code"],
               "properties": {"status": {"type": "string", "enum": ["OK", "UNPAIRABLE"]},
                              "rewritten_response": {"type": ["string", "null"]},
                              "reason_code": {"type": ["string", "null"]}}}}
_CLIENT = None
LABEL = {"seeker": "User", "speaker": "User", "supporter": "Supporter", "listener": "Supporter"}


# ------------------------------------------------------------------ prompts
def load_prompts(d):
    """Files are <stem>_v<version>.txt, e.g. common_rewrite_v2.txt (v2.0), *_v2.1.txt (v2.1)."""
    p = {}
    for k, stem in {"common": "common_rewrite", "neutral": "neutral_prompt",
                    "empathy": "empathy_prompt", "input": "input_template"}.items():
        hits = sorted(f for f in os.listdir(d) if f.startswith(stem + "_v") and f.endswith(".txt"))
        assert len(hits) == 1, f"expected one {stem}_v*.txt in {d}, found {hits}"
        p[k] = open(os.path.join(d, hits[0]), encoding="utf-8").read().strip()
    p["version"] = "v" + os.path.basename(os.path.normpath(d)).lstrip("v")
    p["hash"] = hashlib.sha256(json.dumps([p[k] for k in ("common", "neutral", "empathy",
                                                          "input")]).encode()).hexdigest()[:12]
    return p


def build_request(p, cond, rec):
    history = rec["dialogue_context"][:-1]  # the last turn is the current user message
    hist = "\n".join(f"{LABEL[t['speaker']]}: {t['text']}" for t in history) or \
        "(no earlier turns)"
    inp = (p["input"].replace("{dialogue_history}", hist)
           .replace("{current_user_utterance}", rec["current_user_utterance"])
           .replace("{original_response}", rec["original_response"]))
    return p["common"] + "\n\n" + p[cond], inp


# ------------------------------------------------------------------ API
def call_model(cfg, instructions, inp, use_schema=True):
    from openai import OpenAI
    kw = dict(cfg.get("api_params", {}))
    if use_schema:
        kw["text"] = {"format": SCHEMA}
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OpenAI(max_retries=0)  # retries are handled (and logged) by call_with_retries
    r = _CLIENT.responses.create(model=cfg["model"], instructions=instructions, input=inp, **kw)
    u = getattr(r, "usage", None)
    det = getattr(u, "output_tokens_details", None)
    info = {"input_tokens": getattr(u, "input_tokens", None),
            "output_tokens": getattr(u, "output_tokens", None),
            "reasoning_tokens": getattr(det, "reasoning_tokens", None),
            "status": getattr(r, "status", None),
            "incomplete_reason": getattr(getattr(r, "incomplete_details", None), "reason", None)}
    return r.output_text.strip(), getattr(r, "model", cfg["model"]), getattr(r, "id", None), info


def dry_call(cfg, instructions, inp):
    ref = inp.split("<REFERENCE_RESPONSE>")[1].split("</REFERENCE_RESPONSE>")[0]
    txt = json.dumps({"status": "OK", "rewritten_response": f"[DRY RUN] {ref}",
                      "reason_code": None})
    return txt, cfg["model"], None, {"input_tokens": (len(instructions) + len(inp)) // 4,
                                     "output_tokens": None, "reasoning_tokens": None,
                                     "status": "dry_run", "incomplete_reason": None}


def call_with_retries(fn, label, max_attempts=5):
    for attempt in range(1, max_attempts + 1):
        t0 = time.time()
        try:
            return fn(), attempt - 1, time.time() - t0
        except Exception as e:  # noqa: BLE001 - logged and re-raised
            name = type(e).__name__
            if name in NO_RETRY or attempt == max_attempts:
                log.error("%s FAILED (%s, attempt %d/%d): %s", label, name, attempt,
                          max_attempts, e)
                raise
            wait = 2 ** attempt
            log.warning("%s attempt %d/%d failed (%s: %s); retrying in %ds", label, attempt,
                        max_attempts, name, str(e)[:200], wait)
            time.sleep(wait)


def parse(text):
    """-> (status, rewritten_response, reason_code, parse_error)"""
    try:
        o = json.loads(text)
    except json.JSONDecodeError as e:
        return "INVALID_JSON", None, None, str(e)
    st = o.get("status")
    if st == "OK" and isinstance(o.get("rewritten_response"), str) \
            and o["rewritten_response"].strip():
        return "OK", o["rewritten_response"].strip(), None, None
    if st == "UNPAIRABLE":
        return "UNPAIRABLE", None, o.get("reason_code") or "unspecified", None
    return "INVALID_JSON", None, None, f"unexpected object: {text[:200]}"


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True)
    ap.add_argument("--ids", required=True, help="jsonl with an example_id field per line")
    ap.add_argument("--records", default="formal/extract/records_base.jsonl")
    ap.add_argument("--prompts", default="formal/prompts/v2.0")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--no_schema", action="store_true",
                    help="do not request JSON-schema output (if a model rejects it)")
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--show", type=int, default=0, help="print the first N requests")
    ap.add_argument("--json_attempts", type=int, default=3,
                    help="fresh attempts when the output is not valid JSON (v2.0 pilot used 2)")
    ap.add_argument("--redo_invalid", action="store_true",
                    help="redo calls stored as INVALID_JSON (old rows are moved to "
                         "raw_rewrites_superseded.jsonl)")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel API calls (e.g. 16 for the formal run; lower it on 429s)")
    a = ap.parse_args()

    cfg = json.load(open(a.teacher))
    p = load_prompts(a.prompts)
    tdir = os.path.join(a.out, cfg["teacher_id"] + ("__dryrun" if a.dry_run else ""))
    os.makedirs(tdir, exist_ok=True)
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(), logging.FileHandler(f"{tdir}/generate.log")):
        h.setFormatter(fmt)
        log.addHandler(h)
    if not a.dry_run and not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY is not set (use --dry_run to test without the API).")

    ids = [json.loads(line)["example_id"] for line in open(a.ids) if line.strip()]
    if a.limit:
        ids = ids[: a.limit]
    want = set(ids)
    recs = {}
    for line in open(a.records, encoding="utf-8"):
        r = json.loads(line)
        if r["example_id"] in want:
            recs[r["example_id"]] = r
    missing = want - set(recs)
    assert not missing, f"ids not in records: {sorted(missing)[:5]}"

    raw_path = f"{tdir}/raw_rewrites.jsonl"
    rows = [json.loads(line) for line in open(raw_path)] if os.path.exists(raw_path) else []
    if a.redo_invalid and any(r["status"] == "INVALID_JSON" for r in rows):
        old = [r for r in rows if r["status"] == "INVALID_JSON"]
        rows = [r for r in rows if r["status"] != "INVALID_JSON"]
        with open(f"{tdir}/raw_rewrites_superseded.jsonl", "a", encoding="utf-8") as f:
            for r in old:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp = raw_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, raw_path)
        print(f"--redo_invalid: moved {len(old)} INVALID_JSON rows to "
              f"raw_rewrites_superseded.jsonl; they will be called again")
    if rows and rows[0]["prompt_hash"] != p["hash"]:
        sys.exit("Prompt files changed since the first call in this folder. Make a new prompt "
                 "version and a new output folder instead of mixing versions.")
    done = {(r["example_id"], r["condition"]) for r in rows}
    seen_models = {r["response_model"] for r in rows}
    todo = [(e, c) for e in ids for c in CONDITIONS if (e, c) not in done]
    log.info("START teacher=%s model=%s params=%s prompts=%s/%s dry_run=%s",
             cfg["teacher_id"], cfg["model"], cfg.get("api_params"), p["version"], p["hash"],
             a.dry_run)
    log.info("%d examples; %d calls done; %d to make", len(ids), len(done), len(todo))

    for eid, cond in todo[: a.show]:
        instr, inp = build_request(p, cond, recs[eid])
        print(f"\n===== {eid} / {cond} =====\n--- instructions ---\n{instr}\n"
              f"--- input ---\n{inp}\n")

    def one_call(k, eid, cond):
        """Make one (example, condition) call incl. retries; returns the raw_rewrites row."""
        instr, inp = build_request(p, cond, recs[eid])
        label = f"[{k}/{len(todo)}] {eid}/{cond}"
        if a.dry_run:
            fn = lambda: dry_call(cfg, instr, inp)  # noqa: E731
        else:
            fn = lambda: call_model(cfg, instr, inp, not a.no_schema)  # noqa: E731
        failed, retries, secs = [], 0, 0.0
        for attempt in range(1, a.json_attempts + 1):
            try:
                (text, model, rid, info), r, s_ = call_with_retries(fn, label)
            except Exception as ex:  # noqa: BLE001
                if getattr(ex, "code", None) != "invalid_prompt":
                    raise
                # OpenAI's content filter rejected the input (ESConv has self-harm/abuse
                # topics). Deterministic for the same prompt, so record it and move on; QC
                # excludes the pair.
                log.warning("%s PROMPT_FLAGGED by the provider; recorded, pair will be "
                            "excluded", label)
                text, model, rid = None, cfg["model"], None
                info = {"status": "rejected", "incomplete_reason": None,
                        "error": str(ex)[:500]}
                status, resp, reason, perr = "PROMPT_FLAGGED", None, "invalid_prompt", None
                break
            retries, secs = retries + r, secs + s_
            status, resp, reason, perr = parse(text)
            if status != "INVALID_JSON" or a.dry_run or attempt == a.json_attempts:
                break
            # usually a runaway: valid reply followed by whitespace until max_output_tokens
            log.warning("%s invalid JSON (api status=%s, attempt %d/%d), retrying: %s", label,
                        info.get("status"), attempt, a.json_attempts, perr)
            failed.append({"raw_text": text, "parse_error": perr, "usage": info,
                           "response_id": rid, "latency_s": round(s_, 2)})
            retries += 1
        log.info("%s %s %.1fs in=%s out=%s reasoning=%s words=%s", label, status, secs,
                 info.get("input_tokens"), info.get("output_tokens"),
                 info.get("reasoning_tokens"), len(resp.split()) if resp else "-")
        return {"example_id": eid, "condition": cond, "teacher_id": cfg["teacher_id"],
                "status": status, "rewritten_response": resp, "reason_code": reason,
                "parse_error": perr, "raw_text": text, "response_model": model,
                "response_id": rid, "usage": info, "latency_s": round(secs, 2),
                "retries": retries, "failed_attempts": failed,
                "prompt_version": p["version"], "prompt_hash": p["hash"],
                "timestamp_utc": datetime.datetime.now(datetime.UTC).isoformat(
                    timespec="seconds")}

    # Calls run in a thread pool; rows are written by this (main) thread only, as they finish,
    # so the file is always valid and an interrupted run resumes from what is on disk.
    lat, n_retry, n_api_fail = [], 0, 0
    with open(raw_path, "a", encoding="utf-8") as f, \
            cf.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futs = {pool.submit(one_call, k, e, c): (e, c) for k, (e, c) in enumerate(todo, 1)}
        for fut in cf.as_completed(futs):
            try:
                row = fut.result()
            except Exception as ex:  # noqa: BLE001 - already logged; rerun resumes
                n_api_fail += 1
                if type(ex).__name__ in NO_RETRY:
                    pool.shutdown(cancel_futures=True)
                    sys.exit(f"Stopping: {type(ex).__name__}: {ex}")
                continue
            seen_models.add(row["response_model"])
            if len(seen_models) > 1:
                pool.shutdown(cancel_futures=True)
                sys.exit(f"Model name changed mid-batch: {seen_models}. Stop and tell the team.")
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            rows.append(row)
            n_retry += row["retries"]
            lat.append(row["latency_s"])
    if n_api_fail:
        log.warning("%d calls failed after all retries and were NOT written; rerun the same "
                    "command to retry only those.", n_api_fail)

    # pairs where both conditions are OK
    by = {(r["example_id"], r["condition"]): r for r in rows}
    n_pairs = n_unpair = 0
    with open(f"{tdir}/pairs.jsonl", "w", encoding="utf-8") as f:
        for eid in ids:
            n, e = by.get((eid, "neutral")), by.get((eid, "empathy"))
            if not (n and e):
                continue
            if n["status"] == "OK" and e["status"] == "OK":
                r = recs[eid]
                f.write(json.dumps({
                    "example_id": eid, "source_dataset": r["source_dataset"],
                    "dialogue_context": r["dialogue_context"],
                    "current_user_utterance": r["current_user_utterance"],
                    "original_response": r["original_response"],
                    "neutral_response": n["rewritten_response"],
                    "empathy_response": e["rewritten_response"],
                    "teacher_id": cfg["teacher_id"]}, ensure_ascii=False) + "\n")
                n_pairs += 1
            else:
                n_unpair += 1

    stamps = sorted(r["timestamp_utc"] for r in rows)
    settings = {**cfg.get("api_params", {}),
                **{s: "not exposed" for s in cfg.get("settings_not_exposed", [])},
                "structured_output": "none" if a.no_schema else "json_schema (strict)"}
    json.dump({"teacher_id": cfg["teacher_id"], "provider": cfg.get("provider"),
               "api": cfg.get("api"), "api_model_id": cfg["model"],
               "displayed_model_name": cfg.get("displayed_model_name"),
               "model_names_returned_by_api": sorted(seen_models),
               "generation_settings_both_conditions": settings,
               "prompt_version": p["version"], "prompt_hash": p["hash"],
               "prompt_dir": a.prompts, "first_call_utc": stamps[0] if stamps else None,
               "last_call_utc": stamps[-1] if stamps else None, "dry_run": a.dry_run,
               "n_calls": len(rows),
               "status_counts": {s: sum(r["status"] == s for r in rows)
                                 for s in ("OK", "UNPAIRABLE", "INVALID_JSON",
                                           "PROMPT_FLAGGED")},
               "json_attempts_per_call": a.json_attempts,
               "n_ok_pairs": n_pairs, "n_dropped_pairs": n_unpair,
               "n_calls_with_retries": sum(r["retries"] > 0 for r in rows),
               "n_invalid_json_first_attempts": sum(bool(r["failed_attempts"]) for r in rows),
               "n_incomplete_api_status": sum(
                   (r["usage"] or {}).get("status") == "incomplete"
                   or any((x["usage"] or {}).get("status") == "incomplete"
                          for x in r["failed_attempts"]) for r in rows),
               "tokens_total": {t: sum((r["usage"] or {}).get(t) or 0 for r in rows)
                                for t in ("input_tokens", "output_tokens", "reasoning_tokens")},
               "requests": "2 independent calls per example (neutral, empathy); identical input",
               "note": cfg.get("note")},
              open(f"{tdir}/generation_metadata.json", "w"), indent=2)
    if lat:
        log.info("DONE %d calls, %d retries, mean latency %.1fs", len(lat), n_retry,
                 statistics.mean(lat))
    log.info("%d OK pairs, %d dropped (UNPAIRABLE/invalid). Folder: %s", n_pairs, n_unpair, tdir)


if __name__ == "__main__":
    main()
