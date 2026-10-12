"""Generate Control and Standard EV rewrites (two INDEPENDENT requests per example).

Workflow (matches Michael's steps):
  1. python generate_pairs.py --work work/ --config gen_config.json --limit 10
     -> inspect the 10 pairs with Nikhil (look at work/pilot_pairs_raw.jsonl)
  2. Edit prompts if needed, bump PROMPT_VERSION, delete work/raw_outputs.jsonl
     and re-run step 1 until Nikhil is happy.
  3. Prompts are now FROZEN. Run again without --limit for the rest:
     python generate_pairs.py --work work/ --config gen_config.json

Safety rails:
  - Resumable: finished (example_id, condition) pairs are skipped.
  - Refuses to continue if the prompt hash changed since the first call.
  - Aborts if the model name returned by the API differs from earlier calls
    ("do not switch models halfway").
  - Control request never sees the EV output and vice versa.

gen_config.json example:
  {"model": "gpt-5.6-sol",            # API model id (check the API docs)
   "displayed_model_name": "FILL IN", # name shown in the console/docs
   "api_params": {}}                  # ONLY settings the model supports; the
                                      # same dict is used for both conditions
Needs: pip install openai ; env var OPENAI_API_KEY.
Adjust call_model() if the API shape for this model differs.
"""

import argparse
import datetime
import hashlib
import json
import logging
import os
import statistics
import sys
import time

log = logging.getLogger("generate_pairs")

PROMPT_VERSION = "v3"

# Version history (full log in prompt_version_log.md):
#  v2: added detail/role preservation, context-for-understanding-only, first person kept
#  v3: v2's "<=15 words" cap was applied to the WHOLE EV reply (compressed 3 of 10).
#      Cap now applies only to the acknowledgement sentence; EV must keep full length.
#      Control also drops the supporter's own EMOTIONS ("I get frustrated too") but
#      keeps factual self-disclosure ("I have a daughter who is 10"), keeps tense/meaning.
#      EV acknowledgement may only name a feeling, not restate facts (no context imports).
COMMON = (
    "Read the conversation context and rewrite the supporter response. "
    "Preserve its factual content and advice. Do not invent facts, events, "
    "or advice. Keep concrete details exactly as in the original (objects, "
    "places, numbers, people, and who did what to whom). Use the context only "
    "to understand the situation: do not add details from it that the original "
    "response does not mention. Keep any statements the supporter makes about "
    "their own experience in the first person. Aim for approximately the "
    "original response length, allowing room for one short sentence. "
    "Return only the rewritten response.\n"
    "Context: {context}\n"
    "Original response: {original}"
)

CONDITION = {
    "control": (
        "Paraphrase the response naturally and remove any emotional "
        "validation: do not acknowledge, normalize, reassure, or restate the "
        "user's feelings, and do not share the supporter's own feelings about "
        'the situation (e.g. "I get frustrated too"). Keep all facts and '
        "advice, including factual statements about the supporter's own "
        'experience (e.g. "I have a daughter who is 10"). Keep verb tense and '
        "the meaning of each remaining sentence. Do not add new content to "
        "replace what you remove."
    ),
    "ev": (
        "Paraphrase the response naturally, keeping its full length and detail, "
        "and add or revise one short acknowledgement sentence (about 15 words or "
        "fewer) of a feeling the user has expressed in the conversation. Do not "
        "shorten or compress the rest of the response. The acknowledgement should "
        "name a feeling only; it must not state facts about what happened. If the "
        "response already contains emotional validation, revise it into that "
        "single acknowledgement instead of adding another."
    ),
}


def build_request(cond, context, original):
    return CONDITION[cond] + "\n\n" + COMMON.format(context=context, original=original)


def call_model(cfg, text):
    """One API call. Returns (text, returned_model_name, response_id, info_dict)."""
    from openai import OpenAI

    r = OpenAI().responses.create(model=cfg["model"], input=text, **cfg.get("api_params", {}))
    u = getattr(r, "usage", None)
    det = getattr(u, "output_tokens_details", None)
    info = {
        "input_tokens": getattr(u, "input_tokens", None),
        "output_tokens": getattr(u, "output_tokens", None),
        "reasoning_tokens": getattr(det, "reasoning_tokens", None),
        "status": getattr(r, "status", None),
        "incomplete_reason": getattr(getattr(r, "incomplete_details", None), "reason", None),
    }
    return r.output_text.strip(), getattr(r, "model", cfg["model"]), getattr(r, "id", None), info


NO_RETRY = {"AuthenticationError", "PermissionDeniedError", "BadRequestError", "NotFoundError"}


def call_with_retries(cfg, text, label, max_attempts=5):
    """Wraps call_model with logged retries. Returns (result_tuple, n_retries, latency_s)."""
    for attempt in range(1, max_attempts + 1):
        t0 = time.time()
        try:
            res = call_model(cfg, text)
            return res, attempt - 1, time.time() - t0
        except Exception as e:
            name = type(e).__name__
            if name in NO_RETRY or attempt == max_attempts:
                log.error(
                    "%s FAILED (%s, attempt %d/%d): %s", label, name, attempt, max_attempts, e
                )
                raise
            wait = 2**attempt
            log.warning(
                "%s attempt %d/%d failed (%s: %s); retrying in %ds",
                label,
                attempt,
                max_attempts,
                name,
                str(e)[:200],
                wait,
            )
            time.sleep(wait)


def setup_logging(work):
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    for h in (logging.StreamHandler(), logging.FileHandler(f"{work}/generate.log")):
        h.setFormatter(fmt)
        log.addHandler(h)


def prompt_hash():
    return hashlib.sha256(
        json.dumps([PROMPT_VERSION, COMMON, CONDITION], sort_keys=True).encode()
    ).hexdigest()[:12]


def write_prompts_txt(work):
    with open(f"{work}/prompts.txt", "w") as f:
        f.write(f"PROMPT VERSION: {PROMPT_VERSION}   HASH: {prompt_hash()}\n\n")
        f.write("== Common rewrite instructions ==\n" + COMMON + "\n\n")
        for c, t in CONDITION.items():
            f.write(f"== {c} instruction (prepended to the common instructions) ==\n{t}\n\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    setup_logging(a.work)
    cfg = json.load(open(a.config))
    turns = [json.loads(loads) for loads in open(f"{a.work}/selected_turns.jsonl")]
    if a.limit:
        turns = turns[: a.limit]

    raw_path = f"{a.work}/raw_outputs.jsonl"
    rows = [json.loads(loads) for loads in open(raw_path)] if os.path.exists(raw_path) else []
    done = {(r["example_id"], r["condition"]) for r in rows}
    if rows and rows[0]["prompt_hash"] != prompt_hash():
        sys.exit(
            "Prompt changed since first generation. Prompts must be frozen. "
            "If you intend a new version, bump PROMPT_VERSION and delete raw_outputs.jsonl."
        )
    seen_models = {r["response_model"] for r in rows}

    todo = [(t, c) for t in turns for c in ("control", "ev") if (t["example_id"], c) not in done]
    log.info(
        "START model=%s params=%s prompt=%s/%s",
        cfg["model"],
        cfg.get("api_params", {}),
        PROMPT_VERSION,
        prompt_hash(),
    )
    log.info(
        "%d examples in scope; %d calls already done; %d calls to make now",
        len(turns),
        len(done),
        len(todo),
    )
    lat, tin, tout, treas = [], 0, 0, 0
    n_retries = n_empty = n_incomplete = 0
    run_start = time.time()

    with open(raw_path, "a") as f:
        for t in turns:
            for cond in ("control", "ev"):  # independent requests
                if (t["example_id"], cond) in done:
                    continue
                label = f"[{len(lat) + 1}/{len(todo)}] {t['example_id']}/{cond}"
                (text, model, rid, info), retries, secs = call_with_retries(
                    cfg, build_request(cond, t["context"], t["original_response"]), label
                )
                n_retries += retries
                lat.append(secs)
                tin += info.get("input_tokens") or 0
                tout += info.get("output_tokens") or 0
                treas += info.get("reasoning_tokens") or 0
                seen_models.add(model)
                if len(seen_models) > 1:
                    log.error("Model name changed mid-batch: %s", seen_models)
                    sys.exit(
                        f"Model name changed mid-batch: {seen_models}. Stop and tell the team."
                    )
                warn = []
                if not text.strip():
                    n_empty += 1
                    warn.append("EMPTY OUTPUT")
                if info.get("status") not in (None, "completed"):
                    n_incomplete += 1
                    warn.append(f"status={info['status']} ({info.get('incomplete_reason')})")
                eta = (len(todo) - len(lat)) * statistics.mean(lat)
                log.info(
                    "%s ok %.1fs in=%s out=%s reasoning=%s words=%d eta~%.0fs %s",
                    label,
                    secs,
                    info.get("input_tokens"),
                    info.get("output_tokens"),
                    info.get("reasoning_tokens"),
                    len(text.split()),
                    eta,
                    ("WARN: " + ", ".join(warn)) if warn else "",
                )
                row = {
                    "example_id": t["example_id"],
                    "condition": cond,
                    "response": text,
                    "response_model": model,
                    "response_id": rid,
                    "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                    "prompt_version": PROMPT_VERSION,
                    "prompt_hash": prompt_hash(),
                }
                f.write(json.dumps(row) + "\n")
                f.flush()
                rows.append(row)

    # assemble raw pairs (originals, before any human correction)
    by = {(r["example_id"], r["condition"]): r["response"] for r in rows}
    with open(f"{a.work}/pilot_pairs_raw.jsonl", "w") as f:
        for t in [json.loads(loads) for loads in open(f"{a.work}/selected_turns.jsonl")]:
            if (t["example_id"], "control") in by and (t["example_id"], "ev") in by:
                f.write(
                    json.dumps(
                        {
                            "example_id": t["example_id"],
                            "conversation_id": t["conversation_id"],
                            "context": t["context"],
                            "original_response": t["original_response"],
                            "control_response": by[(t["example_id"], "control")],
                            "ev_response": by[(t["example_id"], "ev")],
                        }
                    )
                    + "\n"
                )

    write_prompts_txt(a.work)
    first = rows[0]["timestamp_utc"] if rows else None
    json.dump(
        {
            "displayed_model_name": cfg.get("displayed_model_name", "FILL IN"),
            "api_model_id": cfg["model"],
            "model_names_returned_by_api": sorted(seen_models),
            "api_params_used_for_both_conditions": cfg.get("api_params", {}),
            "generation_date_first_call_utc": first,
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": prompt_hash(),
            "requests": "2 independent requests per example (control, ev)",
            "n_outputs_so_far": len(rows),
        },
        open(f"{a.work}/generation_settings.json", "w"),
        indent=2,
    )
    n_pairs = sum(1 for k in by if k[1] == "control" and (k[0], "ev") in by)
    log.info(
        "DONE in %.0fs. %d calls this run, %d retries, %d empty, %d incomplete.",
        time.time() - run_start,
        len(lat),
        n_retries,
        n_empty,
        n_incomplete,
    )
    if lat:
        ls = sorted(lat)
        log.info(
            "Latency s: mean %.1f, median %.1f, p95 %.1f, max %.1f",
            statistics.mean(lat),
            statistics.median(lat),
            ls[int(0.95 * (len(ls) - 1))],
            ls[-1],
        )
        log.info("Tokens this run: input %d, output %d (of which reasoning %d)", tin, tout, treas)
    log.info(
        "%d outputs saved in total; %d complete pairs. Log: %s/generate.log",
        len(rows),
        n_pairs,
        a.work,
    )


if __name__ == "__main__":
    main()
