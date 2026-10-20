# Midterm: checked pilot results

## Problem and motivation

Can targeted emotional-validation training improve recognition of user feelings without increasing deference to false factual beliefs? This pilot tests feasibility and measurement; it does not identify a unique mechanism.

## Research gap and approach

Compare matched Control and Standard EV rewrites from the same 200 ESConv conversations. Both start from Qwen3-8B with thinking disabled and use identical QLoRA settings, seed 42, and three epochs. Control and EV differ in the response target. Audit limitations include longer EV responses and AI-assisted rewrite review.

## Completed pilot

Two trained adapters; 160 blinded outputs; 120 factual and 40 emotional ratings supplied by human team members. Freeze commit ee9146e records item decisions and four separately disclosed AI-assisted rubric revisions before unblinding. Actual hardware: RTX 4090 24GB. Training runtimes approximately 6.0 and 6.1 minutes; inference approximately 5.9 minutes, excluding setup/downloads.

## Preliminary results

Original human emotional-validation means: EV 1.70/2 versus Control 0.55/2 (20 paired contexts). Targeted AI-assisted review: EV 1.80 versus Control 0.40; this is sensitivity analysis, not independent human confirmation.

On the 20 quality-screened factual items, no-belief accuracy is 13/20 for each model. False-belief accuracy is 7/20 for EV and 8/20 for Control. S_EV = 30 pp; S_Control = 25 pp; Delta_S = +5 pp, paired item-bootstrap 95% interval [-10, +20] pp. Direct planted-answer endorsement is 11/20 for EV versus 12/20 for Control. Baseline-correct to endorsement transitions are 6/13 versus 5/13. Do not hide any of these measures.

Sensitivity: repaired 21-item Delta_S = +4.8 pp [-9.5, +19.0]; original 30-item Delta_S = +13.3 pp [-3.3, +30.0]. Original30 contains flagged item defects; screened20 is post hoc and changes source balance. These nested sets are not independent replications.

## What we can say

The pilot shows a positive emotional-validation score signal on the present evaluation. It does not establish an increase in factual sycophancy: the screened effect is small and imprecise, and the all-item direct-endorsement measure moves in the opposite direction. It also does not establish absence of a practically important effect.

## Limitations and next steps

One trained pair, one seed, 20 screened factual items, single initial human rater per domain, targeted AI assistance, and closing-heavy emotional evaluation. Item-bootstrap intervals do not quantify training-run uncertainty. Emotion naming in brief closing replies is not comprehensive empathetic competence.

Decision: repair evaluation before formal training. Prospectively define acceptable factual answers and unequivocally false planted beliefs; sample emotional dialogue stages including active distress; add independent human annotation checks; freeze evaluation and then run the planned multiple seeds. Preserve the present pilot and report its limitations without rewriting history.

Full counts, intervals and provenance: pilot_summary.md, pilot_metrics.json, adjudication_policy.md, score_freeze_manifest.json.
