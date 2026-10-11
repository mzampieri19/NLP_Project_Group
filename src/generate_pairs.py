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
import os
import sys

PROMPT_VERSION = "v1"

COMMON = (
    "Read the conversation context and rewrite the supporter response. "
    "Preserve its factual content and advice. Do not invent facts, events, "
    "or advice. Aim for approximately the original response length, allowing "
    "room for one short sentence. Return only the rewritten response.\n"
    "Context: {context}\n"
    "Original response: {original}"
)

CONDITION = {
    "control": (
        "Paraphrase the response naturally and remove any emotional "
        "validation, such as acknowledging, normalizing, or reassuring "
        "the user about their feelings. Keep all facts and advice."
    ),
    "ev": (
        "Paraphrase the response naturally and make sure it clearly "
        "acknowledges the user's feelings in this situation. If the response "
        "already contains emotional validation, revise it as needed instead of "
        "adding another sentence; otherwise add one brief sentence."
    ),
}


def build_request(cond, context, original):
    return CONDITION[cond] + "\n\n" + COMMON.format(context=context, original=original)


def call_model(cfg, text):
    from openai import OpenAI

    r = OpenAI().responses.create(model=cfg["model"], input=text, **cfg.get("api_params", {}))
    return r.output_text.strip(), getattr(r, "model", cfg["model"]), getattr(r, "id", None)


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

    with open(raw_path, "a") as f:
        for t in turns:
            for cond in ("control", "ev"):  # independent requests
                if (t["example_id"], cond) in done:
                    continue
                text, model, rid = call_model(
                    cfg, build_request(cond, t["context"], t["original_response"])
                )
                seen_models.add(model)
                if len(seen_models) > 1:
                    sys.exit(
                        f"Model name changed mid-batch:\n{seen_models}. Stop and tell the team."
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
    n_control = sum(1 for k in by if k[1] == "control")
    n_examples = len(by) // 2
    print(f"{len(rows)} outputs saved; {n_examples if False else n_control} examples have control.")


if __name__ == "__main__":
    main()
