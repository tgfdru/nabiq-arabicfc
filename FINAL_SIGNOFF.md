# FINAL SIGNOFF — NABIQ v15rx Clean Final

> **Note.** This copy has been lightly redacted for public release: internal
> team-process notes naming an individual, and local machine paths, were
> replaced with generic wording. No technical content, rule, result or
> procedure was changed. The unredacted original ships byte-for-byte in the
> `v15rx-final` release archive.

- **Date:** 2026-07-19
- **Package name:** `nabiq_v15rx_blind_clean_final`
- **Primary runner:** `src/v15_candidate/run_nabiq_blind_v15rx.py`
- **Fallback runner:** `src/run_nabiq_blind.py`
- **Validator:** `src/validate_submission_files.py`
- **Final ZIP MD5:** recorded in `checksums.md` after final ZIP creation

---

## Approved active rules

The primary runner uses exactly two accepted v15rx rules:

- **G1:** `calculate_customs.currency` handling
- **G2:** explicit `recipient_iban` extraction from clear account/IBAN markers only

No other v15 candidate rule is active.

---

## Rejected and inactive components

- **G3:** rejected and inactive. It may exist only as documented dead code, but it is not imported or executed.
- **v15 deletion gate:** rejected and inactive. No gate files or gate imports are included in the clean final package.
- No manual row fixes.
- No ID-specific logic.
- No blind-data-specific logic.

---

## Clean package confirmations

Verified in the final clean package:

- no gold files
- no answer files
- no label files
- no `dev_gold`
- no `pseudo_blind_gold`
- no `holdout_gold`
- no old submission outputs
- no notebooks
- no `__pycache__`
- no `.pyc`
- no `.venv`
- no cache folders
- no dataset modification scripts required for blind execution

The package is intended for prediction only.  
Gold files may only be used outside the clean package for offline development-set scoring after predictions are generated.

---

## Acceptance test environment

Acceptance testing was performed from a fresh extracted package folder:

`<local acceptance-test directory>`

Input used for acceptance testing:

`<local project root>/outputs/blind_prep/dev_as_blind_input.jsonl`

This input was used as a blind-style input file for execution testing.  
The runner did not use gold, answer, or label files during prediction.

---

## Primary runner acceptance result

Primary command completed successfully.

Generated outputs:

- `outputs/submissions/acceptance_track_a_v15rx.jsonl`
- `outputs/submissions/acceptance_track_b_v15rx.jsonl`

Execution result:

- row count: `545/545`
- Track A created successfully
- Track B created successfully
- Track B includes `think`
- Track A and Track B match on `id`, `tool_called`, and `arguments`

---

## Primary validator result

Validator result for primary outputs:

- `0 errors`
- `0 warnings`
- `VERDICT: ALL CHECKS PASSED`

---

## Primary post-hoc scoring result

Post-hoc scoring was performed outside the clean package using the v13/v1.2 fair scorer.

Primary v15rx result:

- **FnAcc:** `1.0000` `(545/545)`
- **ArgEM strict:** `0.9160` `(458/500)`
- **ArgEM v1.2:** `0.9380` `(469/500)`
- **OverallA v12:** `0.9628`

This confirms the expected v15rx dev-replay score.

---

## Fallback acceptance result

Fallback command completed successfully.

Generated outputs:

- `outputs/submissions/acceptance_track_a_fallback.jsonl`
- `outputs/submissions/acceptance_track_b_fallback.jsonl`

Fallback validator result:

- `0 errors`
- `0 warnings`
- `VERDICT: ALL CHECKS PASSED`

Fallback post-hoc scoring result:

- **FnAcc:** `1.0000` `(545/545)`
- **ArgEM strict:** `0.8960` `(448/500)`
- **ArgEM v1.2:** `0.9200` `(460/500)`
- **OverallA v12:** `0.9520`

The fallback is valid, but v15rx remains the approved primary runner.

---

## Final blind-test decision

Approved primary runner:

`src/v15_candidate/run_nabiq_blind_v15rx.py`

Approved fallback runner:

`src/run_nabiq_blind.py`

Approved submission preference:

`outputs/submissions/nabiq_blind_track_b_v15rx.jsonl`

Track B should be submitted unless organizers explicitly request Track A as well.

---

## Freeze rule

From this point forward:

- no code changes
- no rule changes
- no manual fixes
- no row editing
- no new experiments inside the clean package
- no re-zipping from a run folder containing generated outputs
- no submission by anyone except the designated submission owner

Any mismatch, warning, validation issue, or unexpected behavior means STOP and review before submission.

---

## Final status

**READY FOR BLIND TEST**
