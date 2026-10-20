# Initial inspection and completed integration, 2026-10-20

## Verified state

- Local main fast-forwarded cleanly from 69efa39 to 51262265c450a5a1b4df067a586d2f37822490b1.
- Latest upstream commit adds the emotional scoring worksheet builder. The preceding commit adds the context selector and Harini's 40 original ratings.
- Imported Asrith's two supplied CSVs byte-for-byte into this result directory. They are byte-identical to the earlier Downloads versions. Copied Harini's existing `work/emotion_scores.csv` here without changing any values.
- The supplied factual scores cover every expected item/model/prompt identity (120 rows); emotional scores cover every expected item/model identity (40 rows). Score ranges and audit identities validate.
- The summarizer calculates statistics only. It neither generates ratings nor reads the condition mapping. `pilot_summary.md` and `blinded_metrics.json` remain provisional.

## GPU inspection

- Successfully connected to the authorized GPU instance. NVIDIA GeForce RTX 4090, 24,564 MiB; no compute processes, 0% utilization at inspection. Both saved training environments also record RTX 4090. Use this hardware name in reporting, rather than the earlier 4090D description.
- Remote repository: `/root/rivermind-data/NLP_Project_Group`; HEAD c3d55fd. It contains the historical uncommitted Transformers compatibility change in `src/train_lora.py` and two local configuration files. These were inspected and left intact. No remote pull, reset, installation, training, or inference was performed.
- Both 200-example, three-epoch adapters are present. Reported training runtimes are 362.64 s (Control) and 367.65 s (EV); inference runtime is 354.83 s for 160 answers. These exclude provisioning/download/setup overhead.
- Final adapter weight size: 174,655,536 bytes each.
- Control adapter SHA-256: `c60fcfccc8532360761f683701716f3714deb25684a7ca50149fef315cde3c27`.
- EV adapter SHA-256: `b6a3eb2110e2b78410d6c01e514471d0858a716a470749e389a0c661ac57efe7`.
- Remote training data, emotional contexts, factual items, and answers match the corresponding local files by SHA-256. Answer hash: `64f13e17c4f8e07611b8265d66e2a6b58c8aaaf99cd8a139981290fd61028e0a`.
- The private mapping file exists on the GPU. Its contents were not opened. Adapter presence and hashes were verified, but weights were not downloaded during this inspection.

## Remaining work

Review the eight ambiguous and two invalid factual items, and the emotional-score inconsistencies listed in `pilot_summary.md`. Preserve initial labels and record every adjudication. Then freeze final scores, unblind, calculate Delta_S, and decide whether to repair the evaluation before formal experiments. No new GPU run is needed for this integration step.

Changes from this integration are local and have not been committed or pushed. This note supersedes the stale pre-training status in `PROJECT_CONTEXT.md` and `LOCAL_WEEK5_4090D.md` for the current pilot.

## Completion update

The sections above describe the initial inspection. Subsequent work completed the ten flagged-item decisions, recorded four targeted AI-assisted emotional-rating revisions while preserving original labels, and froze them in ee9146e before reading the GPU mapping. Model A = EV and model B = Control. Unblinded results and paired-bootstrap intervals are in pilot_summary.md and pilot_metrics.json. The pilot analysis is complete; the scientific decision is to repair evaluation before formal training. Asrith's original handoff was pushed in bd9e51e. No new training or inference was performed.
