# How to Run the Training Data Pipeline (Member B Runbook)

*Everything from the ESConv file to the `pilot_pairs.jsonl` that goes to Rong. Commands assume you are in the project root, the scripts are in `src/`, and the working folder is `work/`. Change the paths if yours differ. Use `python3`.*

## 1. What the pipeline does

You turn 200 real supporter responses from ESConv into two versions each: **Control** (emotional validation removed) and **EV** (one short acknowledgement of the seeker's feeling at the start). Rong trains one model on each. The two versions must differ only in that validation, so most of the pipeline is about rewriting consistently, catching defects, and keeping a record.

**The flow:**

1. Select 200 responses
2. Generate the first 10 pairs, check them, revise the prompts, and repeat until you freeze the prompts
3. Replace unsuitable examples and send Harini the conversation exclusion list
4. Generate the remaining pairs with the frozen prompts
5. Check all 200 and review them in three passes
6. Write `corrections.csv`, finalize, and verify
7. Send the files to the team

**The scripts:**

| Script | What it does | Main outputs |
| --- | --- | --- |
| `select_turns.py` | Picks the 200 responses and can replace bad ones | `selected_turns.jsonl`, `conversation_ids_to_exclude.json`, `selection_info.json` |
| `generate_pairs.py` | Calls GPT-5.6 Sol twice per example (Control, EV) with logging, retries, and safety guards | `raw_outputs.jsonl`, `pilot_pairs_raw.jsonl`, `prompts.txt`, `generation_settings.json`, `generate.log` |
| `check_pairs.py` | Flags likely problems and builds the review sheet | `review_sheet.csv` |
| `finalize_pairs.py` | Applies your hand corrections, keeps the originals, writes a change log, exports the final data | `pilot_pairs.jsonl`, `pilot_pairs_original.jsonl`, `change_log.csv` |
| `verify_export.py` | Pre-checks your corrections file and checks the final export; prints numbers for the writeup | (prints only) |

## 2. One-time setup

1. Activate your virtual environment and install the API library: `pip install openai`
2. Set your API key in the terminal: `export OPENAI_API_KEY=your-key-here`. The model needs a paid account; the free tier does not support it.
3. Put `ESConv.json` somewhere in the project. **Everyone must use the same copy**, because conversation IDs are positions in the file.
4. Create the working folder: `mkdir -p work`
5. Create `gen_config.json` (plain JSON, no comments):

```
{
  "model": "gpt-5.6-sol",
  "displayed_model_name": "GPT-5.6 Sol",
  "api_params": {"reasoning": {"effort": "low"}}
}
```

`api_params` is passed unchanged to every call for both conditions. Pick the settings once and never change them. Do not use the `gpt-5.6` alias, because it routes to Sol and could change; use the explicit ID.

6. Agree with the team before you start: which model rewrites (GPT-5.6 Sol), how the training split is defined, and the self-disclosure rule (section 7).

## 3. Phase 1: Select the 200 responses

```
python3 src/select_turns.py --esconv ESConv.json --out work
```

**What it does:**

- Works out which conversations count as training. With `--train_ids file.json` it uses your list; otherwise it uses a seeded random 80% split at conversation level.
- Merges consecutive turns by the same speaker, so a "response" is everything the supporter says before the seeker speaks again.
- Picks one random eligible response per conversation until it has 200. Eligible means: directly after a seeker block, 8 to 120 words, not in the first three or last two blocks, and not a greeting or farewell.
- Skips responses labeled only "Affirmation and Reassurance" and/or "Reflection of feelings", because Control would have nothing left to rewrite. Change this with `--skip_strategies`, or pass the flag with no values to skip nothing.
- Gives each response an ID: `pair_001` to `pair_200`.

**Check:** `wc -l work/selected_turns.jsonl` says 200. The seed is fixed, so rerunning gives the same 200.

**Outputs:** `selected_turns.jsonl` (the examples, plus the original strategy labels), `conversation_ids_to_exclude.json` (for Harini), `selection_info.json` (the settings, for your methods section).

## 4. Phase 2: Develop and freeze the prompts

Work on the first 10 pairs only, until the prompts are good enough.

1. **Generate 10 pairs:**

```
python3 src/generate_pairs.py --work work --config gen_config.json --limit 10
```

Each pair is two **independent** requests: the Control prompt and the EV prompt each get the common instructions plus their own condition instruction. The Control output is never fed into the EV request. The prompt text is at the top of `generate_pairs.py`.

2. **Build the review sheet:**

```
python3 src/check_pairs.py --work work
```

Open `work/review_sheet.csv` in Google Sheets. Read each row: the original, Control, and EV, with the context and the `new_words` columns.

3. **Review** Ask four questions of every pair: Are facts and advice preserved? Is Control free of validation? Does EV have exactly one acknowledgement at the start, naming a feeling the seeker actually expressed? Is anything invented, compressed, or reworded beyond what the instruction asked?
4. **If the prompts need changing:** edit the prompt text and bump `PROMPT_VERSION` in `generate_pairs.py`. Archive the old outputs instead of deleting them (`mv work/raw_outputs.jsonl work/raw_outputs_v3.jsonl`), then rerun step 1 for the same 10. The script refuses to continue if the prompts changed but old outputs are still there; that is deliberate, so versions never get mixed.
5. **Stopping rule.** Agree with Nikhil in advance when you freeze. Suggested: freeze after a round where at most one or two of the ten need hand edits and nothing systematic remains. Log every version and why it changed in `prompt_version_log.md`.
6. **Freeze.** From here the prompts and `gen_config.json` do not change.

## 5. Phase 3: Replace unsuitable examples and send Harini the list

Some responses cannot be used no matter how good the prompt is, for example a logistics message with no feeling to acknowledge, or a response that is mostly validation already. Replace them:

```
python3 src/select_turns.py --esconv ESConv.json --out work --exclude_ids pair_005 pair_008
```

Use the same ESConv file (and `--train_ids` if you used it before). This drops those IDs and swaps in new responses **at the same list positions**, from conversations not already used, with new IDs (`pair_201` and up). It backs up the old selection as `selected_turns.before_replace.jsonl` and records the swaps in `selection_info.json`. Skim the new rows: they should have real content to rewrite.

Then send Harini the updated `work/conversation_ids_to_exclude.json`. Send it once, after replacements, so she gets the final list. If she already has an older one, tell her it is superseded.

## 6. Phase 4: Generate the rest

```
python3 src/generate_pairs.py --work work --config gen_config.json
```

No `--limit`. The log's first lines show how many calls it will make now (roughly 2 times the examples not yet done). While it runs, watch the log (also saved to `work/generate.log`):

- A few `retrying` warnings are normal; many in a row means rate limits.
- `WARN: EMPTY OUTPUT` or `status=incomplete` means that output is unusable. It is still saved so nothing disappears silently.
- If the API returns a different model name mid-run, the script stops. Tell the team; do not switch models halfway.
- If it crashes, run the same command again. It resumes and skips finished work.

**Check it finished properly:**

- The end summary shows the expected model name and few retries.
- `wc -l work/pilot_pairs_raw.jsonl` says 200.
- `work/generation_settings.json` and `work/prompts.txt` both show the frozen version and GPT-5.6 Sol.

**To redo specific bad outputs**, delete only those lines from `raw_outputs.jsonl` and rerun the same command. For example, an empty EV output for `pair_042`:

```
grep -v '"example_id": "pair_042", "condition": "ev"' work/raw_outputs.jsonl > /tmp/r.jsonl && mv /tmp/r.jsonl work/raw_outputs.jsonl
```

## 7. Phase 5: Check and review all 200

```
python3 src/check_pairs.py --work work
```

Write down the two summary lines: the flag counts, and the average EV-minus-Control length gap. Both go in the writeup. Do not pad responses to close the gap; report it.

Open `work/review_sheet.csv` in Google Sheets and work in that copy. No script reads it; your edits go into `corrections.csv` later.

**What the flags mean** (they are heuristics: false alarms on good paraphrases, and they miss meaning shifts):

| Flag | Meaning |
| --- | --- |
| `missing/empty`, `format` | Blank output, or junk like "Here is..." |
| `facts_changed?` | Numbers or names missing, or very low word overlap |
| `force_changed?` | "try to", "should", "have to" and similar changed or lost |
| `question_dropped` | The original had a question mark; the rewrite does not |
| `self_disclosure_dropped:*` | A first-person statement was lost |
| `control_has_validation?`, `control_self_emotion?` | Control still comforts or shares feelings |
| `ev_no_ack?` | EV has no feeling acknowledgement |
| `stacked_validation?:ev` | EV has two validating sentences; it should have one |
| `len_vs_original`, `ev_much_longer`, `control_much_longer` | Large length differences |

**The `new_words` columns** show words in the rewrite that are not in the original. A plain word appears in neither original nor context (possible invention). `word(ctx)` came from the context; that is suspicious in Control.

**Review in three passes:**

**Pass 1: emotional self-disclosure.** Filter for rows flagged with both `stacked_validation?:ev` and `self_disclosure_dropped:control`. For each first-person sentence in the original, decide:

| Sentence type | Example | Treatment |
| --- | --- | --- |
| Emotional (the supporter's own feeling or judgment) | "I get frustrated too", "it would worry me also" | Removed from Control; delete from EV so the acknowledgement replaces it |
| Factual (a fact about the supporter's life) | "I have a daughter who is 10" | Kept in both |
| Advice from experience | "I find a walk helps" | Kept in both |

Delete the emotional sentences from EV, keep EV's opening acknowledgement and everything else, and make sure Control did not lose any factual first-person content.

**Pass 2: other flagged rows.** Compare each with the original and fix real defects: add a missing acknowledgement (only for a feeling the seeker expressed), remove validation left in Control, delete an extra validating sentence from EV, restore a lost question or force word. Ignore false alarms. If a pair cannot be fixed in a minute or two, replace it (Phase 3) and generate again (Phase 4). Principles: change as little as possible, keep the generated wording, keep Control and EV parallel, and never edit agreement or deference out of EV.

**Pass 3: random sample of unflagged rows.** Add a `=RAND()` column, paste it as values, sort, and read 30 to 40 rows with no flags. For each ask: facts and advice the same? Same roles, tense, and force? Validation left in Control? Exactly one grounded acknowledgement in EV? EV otherwise worded like Control? Count the rows with any problem. Under about 10 percent is fine; 10 to 20 percent means fix them and look for the same pattern elsewhere; over 20 percent means tell Nikhil before editing more.

In the sheet's last columns, mark each row y or n as you go.

## 8. Phase 6: Corrections, finalize, verify

**Build `corrections.csv`.** Make a tab with exactly these columns, one row per reply you changed:

```
example_id,field,corrected_text,reason,corrected_by
```

- `field` is `control_response` or `ev_response`. If both changed, use two rows.
- `corrected_text` is the complete final reply, not a diff. Combine several edits to one reply into one row.
- `reason` is short and specific, for example "removed emotional self-disclosure so EV matches Control".
- Export as CSV. Sheets quotes cells with commas for you.

**Pre-check:**

```
python3 src/verify_export.py --work work --corrections corrections.csv
```

It should say `No problems found.` It catches unknown IDs, wrong field names, empty text, an edit identical to the generated text, duplicate rows, missing reasons, and garbled characters.

**Finalize** (always pass `--out`, so the file lands where you verify it):

```
python3 src/finalize_pairs.py --work work --corrections corrections.csv --out work/pilot_pairs.jsonl
```

This keeps the generated outputs in `work/pilot_pairs_original.jsonl`, writes `work/change_log.csv`, and exports the final file. It stops on duplicate IDs or empty outputs.

**Verify the export:**

```
python3 src/verify_export.py --work work --final work/pilot_pairs.jsonl --expect 200
```

It should say `Export looks valid.` and print numbers for the writeup: mean words for original, Control, and EV; the EV-minus-Control gap; and how many replies you hand-edited. Write them down.

**Rule: run finalize again after any change** to the selection, the generated pairs, or the corrections. The "original" file always reflects the raw pairs at the time of the last finalize, so an old export and a fresh original will disagree.

## 9. Phase 7: Hand off

| File | Send to |
| --- | --- |
| `work/pilot_pairs.jsonl` | Rong (training) and Nikhil (audit) |
| `work/prompts.txt`, `work/generation_settings.json` | The whole team |
| `work/conversation_ids_to_exclude.json` | Harini |
| `work/change_log.csv`, `work/pilot_pairs_original.jsonl` | Nikhil; keep for your appendix |

Tell Rong: the IDs are unique and do not clash with Asrith's `factual_###` IDs; `context` is one text string with `Seeker:` and `Supporter:` labels; replaced examples have `pair_201` and up. Each line of `pilot_pairs.jsonl` is one complete example with exactly these fields: `example_id`, `conversation_id`, `context`, `original_response`, `control_response`, `ev_response`.

Keep for your own writeup: the flag counts and length gap, the review counts and sample miss rate, the number of hand edits, the replaced pairs and why, and `prompt_version_log.md`.

## 10. Rules that must not be broken

- **Never change the prompts or model settings after the freeze.** The script blocks prompt changes; do not work around it.
- **Never switch models partway through.** Use the same model and settings for both conditions and every example.
- **Never feed the Control output into the EV request,** or the reverse.
- **Never edit agreement or deference out of EV.** That is what Nikhil's audit measures. You fix defects, not agreeableness.
- **Never pad a response to equalize length.** Report the gap.
- **Always keep the original generated outputs and a change log.** Hand edits must be traceable.
- **Use the same ESConv file and split definition as Harini and Nikhil,** or the excluded conversations will not line up.

## 11. Troubleshooting

| Problem | Likely cause and fix |
| --- | --- |
| `only found N usable conversations` | Filters are too strict for the pool. Check `--skip_strategies` and the split. |
| `Prompt changed since first generation` | You edited the prompts while old outputs exist. If the change is intended, bump `PROMPT_VERSION` and archive `raw_outputs.jsonl`. |
| `Model name changed mid-batch` | The API returned a different model. Stop, tell the team, and do not continue with a mixed batch. |
| Authentication or permission error | Check `OPENAI_API_KEY` and that the account is on a paid tier. These errors are not retried. |
| Many empty or `incomplete` outputs | Often a low output limit on a reasoning model. Do not set a tight limit in `api_params`. Delete the bad lines and rerun. |
| `KeyError` or odd header in `finalize_pairs.py` | The corrections file has the wrong columns. Run the pre-check; it reports the header. |
| `ids differ from pilot_pairs_original.jsonl` | The final file is stale. Rerun `finalize_pairs.py` with `--out work/pilot_pairs.jsonl`, then verify again. |
| `expected 200 rows, found N` | You are verifying a partial batch. Use `--expect N` for the pilot, or finish generation. |
| Garbled characters such as `â€™` | The CSV was saved in the wrong encoding. Export again as UTF-8. On Windows, run Python with `-X utf8`. |
| Review sheet looks scrambled in Excel | Open it in Google Sheets instead. |

## 12. File reference

| File | Created by | Purpose |
| --- | --- | --- |
| `selected_turns.jsonl` | `select_turns.py` | The 200 examples, with context, original response, and strategy labels |
| `selection_info.json` | `select_turns.py` | Selection settings and replacements, for the methods section |
| `conversation_ids_to_exclude.json` | `select_turns.py` | Conversations used in training, for Harini |
| `raw_outputs.jsonl` | `generate_pairs.py` | Every individual model call, with model name and timestamp |
| `pilot_pairs_raw.jsonl` | `generate_pairs.py` | Assembled pairs before any human edit |
| `prompts.txt`, `generation_settings.json` | `generate_pairs.py` | Required records: exact prompts, model, date, settings |
| `generate.log` | `generate_pairs.py` | Timing, tokens, retries, warnings |
| `review_sheet.csv` | `check_pairs.py` | Side-by-side review with flags |
| `corrections.csv` | You | Your hand edits |
| `pilot_pairs_original.jsonl`, `change_log.csv` | `finalize_pairs.py` | Untouched outputs and the log of every edit |
| `pilot_pairs.jsonl` | `finalize_pairs.py` | The final checked data for Rong |
