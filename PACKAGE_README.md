# NABIQ v15rx Clean Final — Blind-Test Package

> **Note.** This copy has been lightly redacted for public release: internal
> team-process notes naming an individual, and local machine paths, were
> replaced with generic wording. No technical content, rule, result or
> procedure was changed. The unredacted original ships byte-for-byte in the
> `v15rx-final` release archive.

This is the final clean blind-test package for NABIQ, developed for the AISA-ArabicFC shared task at ArabicNLP 2026.

Package name: `nabiq_v15rx_blind_clean_final`

---

## Purpose

This package is intended only for blind-test prediction.

It contains the approved blind runners, validator, required source code, and released training data needed to generate prediction files from an organizer-provided blind input file.

It must not be used for development, manual fixing, rule editing, or experimentation during blind-test execution.

---

## Approved runners

Primary runner:

`src/v15_candidate/run_nabiq_blind_v15rx.py`

Fallback runner:

`src/run_nabiq_blind.py`

Mandatory validator:

`src/validate_submission_files.py`

The primary runner should be used first.  
The fallback runner is for emergency use only if the primary runner fails or the validator reports an issue.

---

## Approved active v15rx rules

The primary v15rx runner uses exactly two approved rules:

- **G1:** `calculate_customs.currency` handling based on training-set convention
- **G2:** explicit `recipient_iban` extraction from clear account/IBAN markers only

No other v15 candidate rule is active.

---

## Rejected and inactive components

- **G3:** rejected and inactive. It may exist only as documented dead code in `v15_reextract.py`, but it is not imported or executed.
- **v15 deletion gate:** rejected and inactive. No `v15_gate` or `v15_gate2` files/imports are included in this clean final package.
- No manual row fixes.
- No ID-specific logic.
- No blind-data-specific logic.

---

## Data policy

This package does not contain:

- gold files
- answer files
- label files
- `dev_gold`
- `pseudo_blind_gold`
- `holdout_gold`
- old submission outputs
- notebooks
- `__pycache__`
- `.pyc`
- `.venv`
- cache folders

The included `data/processed_v13/train_processed.jsonl` is released training data used by the runner for routing, retrieval, and train-derived conventions.

Gold files may only be used outside this clean package for post-hoc development-set scoring after predictions are already generated.  
Gold files must not be used during blind prediction.

---

## Verified acceptance result

The clean final package was tested from a fresh extracted folder.

Primary v15rx execution:

- row count: `545/545`
- Track A output created successfully
- Track B output created successfully
- Track B includes `think`
- validator result: `0 errors / 0 warnings`
- verdict: `ALL CHECKS PASSED`

Post-hoc v13/v1.2 fair scoring result for primary v15rx:

- FnAcc: `1.0000`
- ArgEM strict: `0.9160`
- ArgEM v1.2: `0.9380`
- OverallA v12: `0.9628`

Fallback execution:

- row count: `545/545`
- validator result: `0 errors / 0 warnings`
- verdict: `ALL CHECKS PASSED`

Post-hoc v13/v1.2 fair scoring result for fallback:

- FnAcc: `1.0000`
- ArgEM v1.2: `0.9200`

Primary v15rx is the approved runner.  
Fallback is valid but should only be used if needed.

---

## Setup

Python 3.10+ is recommended.

Install requirements:

`pip install -r requirements.txt`

---

## Blind-day procedure

Follow:

`BLIND_TEST_RUNBOOK.md`

Required blind input location:

`data/blind/test.jsonl`

Primary output to submit:

`outputs/submissions/nabiq_blind_track_b_v15rx.jsonl`

Submit Track B only unless the organizers explicitly request Track A as well.

Submission is performed by the designated submission owner only.

---

## Verification

Before blind-day execution, verify:

`checksums.md`

Any checksum mismatch means STOP.

After generating the final submission file, record its MD5 before upload.

---

## Freeze rule

No changes after freeze:

- no code changes
- no rule changes
- no manual row edits
- no new experiments inside the clean package
- no re-zipping from a run folder containing generated outputs
- no submission by anyone except the designated submission owner

Any mismatch, warning, validation issue, or unexpected behavior means STOP and review before submission.

---

## Final status

READY FOR BLIND TEST
