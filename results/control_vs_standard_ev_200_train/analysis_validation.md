# Analysis validation

- Original inputs: src/validate_pilot_inputs.py passes (200 matched training pairs, 30 factual items/60 prompts, 20 emotional contexts, no training/evaluation conversation overlap).
- Human labels: summarize_blinded_pilot.py validates all 160 exact expected identities, uniqueness and score ranges; imported originals remain byte-identical to their source files.
- Freeze: all eight frozen files matched both working files and Git commit blobs before mapping read; every frozen input is verified on every analysis run.
- Paired analysis: independent checks reconcile Delta_S to condition-specific accuracy-gap counts and emotional mean contrasts to their paired context differences.
- Bootstrap: all-zero and all-one paired contrasts return exact zero-width intervals at the known effect; repeated full analysis yields an identical pilot_metrics.json hash.
- Failure handling: deliberately altered frozen data in a disposable copy is rejected before analysis; original inputs were not altered for this test.
- Code quality: Ruff lint and formatting checks pass for the two new analysis scripts. Repository-wide legacy lint was not changed or asserted.

These checks verify computation and provenance, not annotation correctness, clinical expertise, causal mechanism, or generalization across training seeds.
