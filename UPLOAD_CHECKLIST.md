# Exact upload manifest

Verified against the extracted frozen package
`release_packages/nabiq_v15rx_blind_clean_final/`.

## Upload to the repo (drag all of these onto GitHub's "Upload files")

**From this starter pack**
```
README.md              <- the repo landing page
LICENSE                <- MIT, in both your names
.gitignore
```

**From this starter pack — `package_docs/` (REDACTED copies, use these)**
```
package_docs/PACKAGE_README.md
package_docs/BLIND_TEST_RUNBOOK.md
package_docs/FINAL_SIGNOFF.md
package_docs/checksums.md
```
Upload these four **instead of** the originals in the frozen package. They are
identical except that internal team-process notes naming an individual, and
local Windows paths, have been replaced with generic wording. Each carries a
short note saying so, and `checksums.md` flags the three redacted docs so the
MD5 mismatch reads as intentional rather than as tampering. No rule, result,
command or procedure was changed.

**From the frozen package — root**
```
requirements.txt
```

**From the frozen package — `src/` (all 22 files, keep the folder name)**
```
src/run_nabiq_blind.py               <- fallback runner (this produced the
                                        submitted files)
src/validate_submission_files.py     <- official-style validator
src/phase1_rules_v5_pc.py
src/normalization_maps_v2_pc.py
src/nabiq_v3_pc_pipeline.py
src/nabiq_v3_pc_utils.py
src/nabiq_v4_elite_pipeline.py
src/nabiq_v4_extractors.py
src/nabiq_v5_pipeline.py
src/nabiq_v5_extractors.py
src/nabiq_v5_gulf_fixes.py
src/nabiq_v6_argem_fixes.py
src/nabiq_v7_fnacc_fixes.py
src/nabiq_v8_argem_fixes.py
src/nabiq_v8_tool_packs.py
src/nabiq_v9_micro_fixes.py
src/nabiq_v10_micro_fixes.py
src/nabiq_v11_micro_fixes.py
src/nabiq_v12_micro_fixes.py
src/nabiq_v13_micro_fixes.py
src/nabiq_v14_candidate_rules.py
src/nabiq_v14_micro_fixes.py
src/nabiq_v14_selector.py
src/nabiq_arg_verifier_pc.py
src/v12_scorer.py
src/v15_candidate/run_nabiq_blind_v15rx.py
src/v15_candidate/v15_reextract.py
```

**From the frozen package — the mined schema report (required at runtime)**
```
outputs/reports/nabiq_schema_miner_report.json      (162 KB)
```
`v3mod.load_gazetteers(SCHEMA_REPORT_PATH)` reads this. Without it the chain
will not run. It is derived from the released **training** split only — no gold.

**Placeholders that keep the empty folders alive**
```
data/blind/README_PLACEHOLDER.txt
outputs/submissions/README_PLACEHOLDER.txt
```

## Do NOT put in git

| File | Why | What to do instead |
|---|---|---|
| `data/processed_v13/train_processed.jsonl` | 23 MB of the organisers' released training data. It **is** required at inference (the router, retriever and gazetteers are fitted on it), but redistributing the dataset inside a git repo is poor practice and sits right at GitHub's 25 MiB web-upload limit. | Attach it as a **Release asset** and tell users to drop it at `data/processed_v13/`. |
| `nabiq_v15rx_blind_clean_final.zip` | `FINAL_SIGNOFF.md` forbids repacking or recompressing it. Committing it through git risks that. | Attach the original ZIP as a **Release asset**, byte-for-byte. |
| anything matching `*gold*`, `*answer*`, `*label*` | data-integrity rules | never upload |
| generated `outputs/submissions/*.jsonl` | they are outputs, not code | never upload |

The `.gitignore` in this pack already blocks every row above. Still scan the
file list on the upload screen before you commit.

## Creating the Release (after the first commit)

1. Repo → **Releases** → **Create a new release**
2. Tag `v15rx-final`, title `NABIQ v15rx — frozen blind-test package`
3. Attach: the original `nabiq_v15rx_blind_clean_final.zip` **and**
   `train_processed.jsonl`
4. In the body, paste the MD5 table from `checksums.md` so anyone can verify
   the archive was not altered.

## Then send me the URL

I will put it into line 99 of the paper:

```latex
Code: \url{https://github.com/<owner>/nabiq-arabicfc}.
```
