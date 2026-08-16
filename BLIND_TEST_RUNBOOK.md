# BLIND TEST RUNBOOK — NABIQ v15rx Clean Final

> **Note.** This copy has been lightly redacted for public release: internal
> team-process notes naming an individual, and local machine paths, were
> replaced with generic wording. No technical content, rule, result or
> procedure was changed. The unredacted original ships byte-for-byte in the
> `v15rx-final` release archive.

Package: `nabiq_v15rx_blind_clean_final`  
Approved ZIP: `release_packages/nabiq_v15rx_blind_clean_final.zip`  
Approved ZIP MD5: recorded externally after final ZIP creation

Primary runner: `src/v15_candidate/run_nabiq_blind_v15rx.py`  
Fallback runner: `src/run_nabiq_blind.py`  
Validator: `src/validate_submission_files.py`

This runbook is for blind-test execution only.  
Do not modify code, rules, datasets, outputs, or package files during blind-day execution.

---

## 0. Pre-run rules

All commands must be run from the clean package root.

Do not run from the full development project.  
Do not use old versions, experiments, notebooks, or previous submissions.

Allowed package root example:

```powershell
<your clean package root>\nabiq_v15rx_blind_clean_final
```

Absolutely forbidden:

- no code changes
- no rule changes
- no manual row edits
- no manual prediction fixes
- no use of gold / answer / label files during prediction
- no dev_gold / holdout_gold / pseudo_blind_gold
- no submitting by anyone except the designated submission owner
- no re-zipping from a run folder containing generated outputs

If any error or warning appears, stop and review before submission.

---

## 1. Place the blind file

Place the organizer-provided blind file here:

```text
data/blind/test.jsonl
```

The file name must not contain:

```text
gold
answer
label
dev_gold
holdout_gold
pseudo_blind_gold
```

If the runner refuses the file because of the filename, stop immediately and verify that the correct blind input file was provided.

---

## 2. Run the primary runner: v15rx

```powershell
python src/v15_candidate/run_nabiq_blind_v15rx.py --input data/blind/test.jsonl --track-a outputs/submissions/nabiq_blind_track_a_v15rx.jsonl --track-b outputs/submissions/nabiq_blind_track_b_v15rx.jsonl
```

Expected:

- command completes successfully
- output row count matches input row count
- Track A file is created
- Track B file is created

---

## 3. Validate primary outputs

```powershell
python src/validate_submission_files.py --input data/blind/test.jsonl --track-a outputs/submissions/nabiq_blind_track_a_v15rx.jsonl --track-b outputs/submissions/nabiq_blind_track_b_v15rx.jsonl
```

Required result:

```text
RESULT: 0 error(s), 0 warning(s)
VERDICT: ALL CHECKS PASSED.
```

If there is any error or warning, do not submit. Stop and review.

---

## 4. Primary submission decision

If the validator is clean:

```text
0 errors
0 warnings
ALL CHECKS PASSED
```

Prepare this file for submission:

```text
outputs/submissions/nabiq_blind_track_b_v15rx.jsonl
```

Submit Track B only unless the organizers explicitly request Track A as well.

Submission is done by the designated submission owner only.

---

## 5. Run fallback only if needed

Run fallback only if one of these happens:

- primary runner crashes
- primary output is missing
- validator reports errors
- validator reports warnings
- row count mismatch
- suspicious `recipient_iban`
- schema violation
- unexpected format issue

Fallback is for emergency only.  
Do not submit fallback output unless the submission owner reviews and approves.

---

## 6. Fallback command

```powershell
python src/run_nabiq_blind.py --input data/blind/test.jsonl --track-a outputs/submissions/nabiq_blind_track_a_fallback.jsonl --track-b outputs/submissions/nabiq_blind_track_b_fallback.jsonl
```

---

## 7. Validate fallback outputs

```powershell
python src/validate_submission_files.py --input data/blind/test.jsonl --track-a outputs/submissions/nabiq_blind_track_a_fallback.jsonl --track-b outputs/submissions/nabiq_blind_track_b_fallback.jsonl
```

Required fallback result:

```text
RESULT: 0 error(s), 0 warning(s)
VERDICT: ALL CHECKS PASSED.
```

If fallback also has any error or warning, stop. Do not submit.

---

## 8. Final output record

Before submitting, record the MD5 of the final file being submitted.

For primary Track B:

```powershell
Get-FileHash -Algorithm MD5 outputs/submissions/nabiq_blind_track_b_v15rx.jsonl
```

Save:

- submitted filename
- MD5 hash
- submission time
- screenshot or confirmation from the submission platform

---

## 9. Stop conditions

Stop immediately if:

- any script fails
- validator has any error
- validator has any warning
- output row count does not match input row count
- Track B does not match Track A on `id`, `tool_called`, and `arguments`
- `recipient_iban` is suspicious
- schema validation fails
- any code change seems necessary
- any manual row edit seems necessary
- any gold / answer / label file is required

Do not fix silently.  
Do not submit until the submission owner reviews the issue.

---

## 10. Final rule

Primary approved runner:

```text
src/v15_candidate/run_nabiq_blind_v15rx.py
```

Fallback runner:

```text
src/run_nabiq_blind.py
```

Approved final package:

```text
nabiq_v15rx_blind_clean_final.zip
```

Approved ZIP MD5:

```text
recorded externally after final ZIP creation
```

No changes after freeze.  
No submission by anyone except the designated submission owner.
