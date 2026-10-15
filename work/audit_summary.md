# Training-Signal Audit Summary

Date: 2026-10-15

## Status and interpretation

This is a transparent rubric-guided automated pilot audit of the corrected 200-pair dataset. It is not a validated human annotation study and must be described as such. The labels are deterministic rubric-guided screening labels with phrase evidence in every row.

All 200 pairs received a semantic review before this audit. The final export contains 65 traceable response corrections across 59 examples. No remaining row is marked as a known content error; agreement, warmth, and certainty were measured rather than edited to force conditions to match.

## Mean pilot scores

| Condition | Validation | Warmth | Certainty | Mean words |
| --- | ---: | ---: | ---: | ---: |
| original | 0.225 | 0.545 | 0.485 | 25.1 |
| control | 0.065 | 0.360 | 0.290 | 19.0 |
| ev | 1.680 | 0.510 | 0.355 | 24.4 |

## Agreement/deference screening

Agreement is a sparse lexical screening label, not a judgment of factual correctness. Rows without a clear assessable endorsement may be labeled N/A. Counts below include only the emitted labels and should not be presented as a validated scale.

| Condition | N/A | 0 | 1 | 2 |
| --- | ---: | ---: | ---: | ---: |
| original | 29 | 162 | 0 | 9 |
| control | 34 | 161 | 0 | 5 |
| ev | 28 | 165 | 0 | 7 |

## Five reviewed examples

- `pair_004`: EV wording restored the original advice force and concrete wording.
- `pair_050`: EV no longer weakens `clear severance` to a tentative suggestion.
- `pair_122`: Control now preserves the worsening-over-time content instead of only `Ok.`.
- `pair_157`: EV restores the original hypothetical tense instead of asserting past audio work.
- `pair_200`: Both conditions retain `5 or 6 bosses in 2 years` and the original question.

## Gate decision

The corrected file passes the structural export checks and the semantic-review gate for the small course pilot. Because the audit is rubric-guided automated and the source corpus contains some low-quality or unsafe original advice, all conclusions must remain explicitly pilot-level. A blinded human audit is still required before a formal paper claim or larger training run.
