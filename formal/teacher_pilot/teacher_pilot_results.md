# Teacher-selection pilot results (unblinded)

| Teacher | Cond | IP | ER | EX | Natural | Facts✗ | Advice✗ | Stance✗ | Unsupported |
|---|---|---|---|---|---|---|---|---|---|
| gpt-4o-2024-08-06 | neutral | 0.56 | 0.33 | 0.22 | 1.78 | 0 | 0 | 0 | 0 |
| gpt-4o-2024-08-06 | empathy | 0.44 | 0.33 | 0.22 | 1.78 | 2 | 1 | 0 | 0 |
| gpt-5.6-sol | neutral | 0.33 | 0.33 | 0.22 | 2 | 0 | 0 | 0 | 0 |
| gpt-5.6-sol | empathy | 1.56 | 0.33 | 0.22 | 2 | 0 | 0 | 0 | 0 |

| Teacher | Empathy-Neutral IP | ER | EX | Share of contexts Empathy > Neutral on >=1 dim |
|---|---|---|---|---|
| gpt-4o-2024-08-06 | -0.11 | +0 | +0 | 0 |
| gpt-5.6-sol | +1.22 | +0 | +0 | 1 |

Both teachers are compared on the same 9 of 10 contexts: those where EVERY teacher produced both conditions. Rows skipped as UNPAIRABLE/invalid: T09-A (gpt-5.6-sol/empathy).

Decision rule (plan): choose ONE teacher with a clear, appropriate EPITOME contrast and the least content/stance drift. Record the decision and reason in formal/DECISIONS.md.
