# Checksums — nabiq_v15rx_blind_clean_final

> **Note.** This copy has been lightly redacted for public release: internal
> team-process notes naming an individual, and local machine paths, were
> replaced with generic wording. No technical content, rule, result or
> procedure was changed. The unredacted original ships byte-for-byte in the
> `v15rx-final` release archive.

Generated: 2026-07-19  
Hash algorithm: MD5

These checksums cover the frozen clean package files used for blind-test execution.

Verify before every blind-day run.  
Any mismatch means: STOP and do not submit until the submission owner reviews the issue.

---

## File checksums

| File | MD5 |
|---|---|
| `src/v15_candidate/run_nabiq_blind_v15rx.py` † | `12669260eb6156278eb84d85595bf7e3` |
| `src/v15_candidate/v15_reextract.py` † | `87130c01de381121927dbd434445b404` |
| `src/run_nabiq_blind.py` | `543d20c004fc6118fe4260a6be88636b` |
| `src/validate_submission_files.py` | `ec284b2b65f439cbb76cc8378c2a4726` |
| `requirements.txt` | `3889bc09316b3da8790154733e9a975e` |
| `README.md` † | `628f068a6971ae880d2b6cb273f85afe` |
| `BLIND_TEST_RUNBOOK.md` † | `7534a5a944e6861d786905d7111d9b93` |
| `FINAL_SIGNOFF.md` † | `c9b44768933dde4152e26ede603521fe` |
| `outputs/submissions/README_PLACEHOLDER.txt` | `c69671ee63bf2f2c16946218db0c0e9d` |

† These files were redacted for public release (see the note at the
top of each). Their MD5 here refers to the **original** file inside the
`v15rx-final` release archive, not to the redacted copy in this repository. The
redaction replaced an internal team-process note naming an individual with
generic wording; no rule, threshold or line of logic was changed. Every
unflagged checksum above matches this repository byte-for-byte --- including
`run_nabiq_blind.py` and `validate_submission_files.py`, the two files that
actually produced and checked the submission.

---

## Final ZIP checksum

Final ZIP MD5 is recorded externally after final ZIP creation.

Do not record the ZIP MD5 here before the final ZIP is recreated.

---

## Verification rule

Before running on blind data:

1. Verify this file's checksums.
2. Verify the final ZIP MD5.
3. Run only from the clean package root.
4. Do not modify code, rules, outputs, or package files.
5. Do not use gold, answer, label, dev_gold, holdout_gold, or pseudo_blind_gold files.

Any mismatch, warning, or unexpected file means STOP.
