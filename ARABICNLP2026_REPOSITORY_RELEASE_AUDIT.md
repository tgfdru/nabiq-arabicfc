# ArabicNLP 2026 — Repository Release Audit

**Repository:** https://github.com/tgfdru/nabiq-arabicfc
**Project:** NABIQ — Team Wajeh (واجه), University of Bisha
**Paper:** *Wajeh at AISA-ArabicFC: A Non-LLM Classical ML and Retrieval Pipeline for Arabic Function Calling*, ArabicNLP 2026
**Audit date:** 2026-10-16
**Audit environment:** Linux x86-64 VM, git 2.34.1, Python 3.10 (audit host only — *not* the archived runtime)

> **Scope note.** This audit inspected, verified, repaired and **published**.
> The repair commits are listed in §H with their SHAs; each was re-fetched from
> `raw.githubusercontent.com` after the push and checked, so every "published"
> claim below rests on a post-push read of the live repository, not on the
> staged file. What was **not** done is listed in §G (tests 8, 13, 14) and §J —
> above all, no official metric was reproduced here.

---

## A. Repository state before changes

| Item | Value |
|---|---|
| Remote | `https://github.com/tgfdru/nabiq-arabicfc.git` |
| Branch | `main` |
| HEAD | `6c047a3b44495de55a011035855067a738fa7506` — *Delete nabiq-arabicfc-upload.zip*, 2026-08-16 03:31:59 +0300 |
| Working tree | clean |
| Tags on remote | `v15rx-final` → `9866beaa3fd623288230cc46eaa71cb55df222ee` (*Add files via upload*, 2026-08-16 03:10:08 +0300) |
| Tracked files | 40 · 732 KB |

**Correction to an earlier report.** A previous description of this repository
("contains only `.gitignore`, `LICENSE`, `README.md` and an unextracted ZIP")
is **no longer accurate**. The ZIP was extracted and removed at HEAD. Phase C's
extraction work was therefore already complete before this audit began.

### Inventory (HEAD, SHA-256)

| Path | SHA-256 |
|---|---|
| `README.md` | `5de8cd6fbeccddfda4677618dc1b4c3157cb68dfd2cc1e41766bdc885d9e851e` |
| `LICENSE` | `f47bd702600c6dedc3dc0d099015f1aae7d3d8e56a4ba6bf59bf1fc4b37c15e1` |
| `checksums.md` | `febe001eb66cf81a6f512a0e5b450cf15875e13e5ba4c98f23e3f9afea0db576` |
| `FINAL_SIGNOFF.md` | `a003f98f9bea5411c1b59a1fdbf97455d5d83e088024cc71ae17bbd180b7a883` |
| `BLIND_TEST_RUNBOOK.md` | `591cef377300fe5e140b14215ae2fa935a43ac2bb6973497cc2347cdae259385` |
| `requirements-frozen.txt` | `95665a9745f91850f58c9ab8d0cbdf221edf12d29f12c8d8df4938baaf382f73` |
| `src/run_nabiq_blind.py` | `7cbc30dd121ab403717e7a5c5f89cf7a6d0727fcd61ec3b1e2e1b2e3661cdc92` |
| `src/validate_submission_files.py` | `32cdbca89b5cbfc1ccfdbe917c5669561fa58f29c308f0cc711977737b731038` |
| `src/v15_candidate/run_nabiq_blind_v15rx.py` | `3c3d71354388d855d692f276c019c86fc88246cf0daf7cc8f26eecd6011bb7bf` |

Off-repository artifacts:

| Path | SHA-256 | Size |
|---|---|---|
| `NABIQ_ArabicNLP2026_paper.pdf` (staged) | `9b7c2c7f07a148fd9c32dc14b9ad6194c139d6a35ca0967ab092ca4bf0ed6941` | 122,623 B |
| `nabiq_v15rx_blind_clean_final.zip` (frozen package, local only) | `0acc1da7f48cf658fd62449343a614fb123733fb6a339f99d774ce461479e6d9` | 2,084,833 B |

### Problems found

1. **No paper in the repository.** The poster QR is labelled *Paper & Code*.
2. **README contradicts the accepted camera-ready in four places** — see §C.
3. **A broken usage command.** The README showed
   `python src/validate_submission_files.py` with no arguments; the script's
   argparse requires `--input`, `--track-a`, `--track-b` (verified at
   `src/validate_submission_files.py:200-203` and by `--help`).
4. **Provenance risk.** `FINAL_SIGNOFF.md` concludes *"v15rx remains the
   approved primary runner"*. Written pre-run, it reads today as if v15rx was
   submitted. It was not.
5. **`requirements.txt` is unpinned**, while the README states exact versions.

---

## B. Changes published

| File | Action | Reason | Commit |
|---|---|---|---|
| `README.md` | replaced | fix 4 scientific contradictions, 1 broken command, add provenance + structure | `786b1568` |
| `NABIQ_ArabicNLP2026_paper.pdf` | added at repo root | QR promises the paper | `b4239622` |
| `ARABICNLP2026_REPOSITORY_RELEASE_AUDIT.md` | added at repo root | this audit trail | `8269adcd` |

Two further changes were made through the GitHub web interface rather than as
commits, and so carry no SHA:

| Target | Change |
|---|---|
| Repository *About* description | replaced a description that claimed the pipeline is "fully deterministic" with one that does not |
| Release `v15rx-final` — notes body only | rewrote the notes to state the 1,125-row count, the `negative_category` leak, the fallback provenance and the hash-seed caveat. The **tag, the commit it points at, and both assets were left untouched** (rule 9) |

**Nothing was deleted, moved, or rewritten.** No force-push, no tag change, no
history rewrite. The `v15rx-final` tag is left exactly as it is.

---

## C. Scientific verification against the accepted camera-ready

| # | Previous README claim | Camera-ready | Status |
|---|---|---|---|
| 1 | "no decision path reads `negative_category` … predictions are byte-identical when stripped" | §5 / App. C: `build_none_text` concatenates it into the no-call detector's feature string; "**the no-call detector does**" read it. Blanking it costs 0.0294 FnAcc, 0.0177 Overall A; 5-fold CV no-call recall 0.9600 → 0.5400 | **CONTRADICTED** — corrected |
| 2 | "ArgEM +0.167 over the fine-tuned baseline (0.541), +0.638 over GPT-4o (0.070)" | Table 2 (organisers' final re-scored): 270M = 0.6790, GPT-4o zero-shot = 0.7442. "Pre-normaliser figures … are not comparable and are not used here." | **RETRACTED FIGURES** — corrected |
| 3 | "fully deterministic … byte-reproducible"; "every traversal is now explicitly sorted" | App. A: sorting "**is not present in the archived package**"; "we do **not** claim … byte-identical across fresh processes"; 5/545 rows differ across hash seeds | **CONTRADICTED** — corrected |
| 4 | "blind test, 1,050 rows"; "125 negative instances" | **1,125** rows (FnAcc 1028/1125); 50 train + 45 dev negatives | **FACTUALLY WRONG** — corrected |

**Metrics published in the corrected README** (FnAcc 0.9138, ArgEM 0.7081,
Overall A 0.7904, Overall B 0.8282, ThinkRate 1.0000, 1,125 rows) are quoted
**as reported by the organisers in the accepted paper**. They were **not**
reproduced in this audit: the blind input and the official evaluator were not
available here.

---

## D. Provenance — primary vs fallback

**Verified from the post-run handoff record** (`NABIQ_HANDOFF_20260729/README_HANDOFF.txt`, local):

> "Both uploaded files are Fallback outputs. Both Fallback files passed the
> official validator. Validator result: 0 errors, 0 warnings… Primary files are
> NOT approved for submission… The Primary outputs failed the validator because
> of invalid `recipient_iban` values."

| Source | Date | Says |
|---|---|---|
| `FINAL_SIGNOFF.md` (in repo) | pre-run | v15rx = approved primary; fallback valid but not preferred |
| `BLIND_TEST_RUNBOOK.md` (in repo) | pre-run | fallback is "emergency only" |
| `README_HANDOFF.txt` (local, post-run) | 2026-07-29 | **fallback was uploaded for both tracks**; primary rejected |
| Camera-ready §5 | accepted | same |

**Integrity corroboration:** `src/run_nabiq_blind.py` — the fallback runner that
produced the submission — has MD5 `543d20c004fc6118fe4260a6be88636b`, matching
`checksums.md` **byte-for-byte**.

**Not verified:** the original blind-day validator log. The primary blind
outputs were not retained, so the rejection could **not** be independently
re-run. The handoff record is the sole evidence, and is cited as such. **No
validator log was reconstructed or synthesised in this audit.**

**Release-naming consequence:** the existing tag `v15rx-final` names the frozen
*package*. Rule 9 forbids rewriting it, so it is left untouched; the corrected
README states explicitly that the tag does not imply v15rx produced the
submission. A new release, if created, should be named
`arabicnlp2026-submission-archive`, **not** `v15rx-final`.

---

## E. Artifact integrity — checksum verification

`checksums.md` marks four files `†` (redacted for public release; their MD5
refers to the original inside the release archive). The **unflagged** entries
were verified against this repository:

| File | Expected MD5 | Result |
|---|---|---|
| `src/run_nabiq_blind.py` | `543d20c004fc6118fe4260a6be88636b` | **PASS** |
| `src/validate_submission_files.py` | `ec284b2b65f439cbb76cc8378c2a4726` | **PASS** |
| `requirements.txt` | `3889bc09316b3da8790154733e9a975e` | **PASS** |
| `outputs/submissions/README_PLACEHOLDER.txt` | `c69671ee63bf2f2c16946218db0c0e9d` | **PASS** |

The two `†` v15_candidate files differ from the table, **as documented** by the
redaction footnote. This is expected, not a defect.

---

## F. Licensing

| Item | Finding | Evidence |
|---|---|---|
| Code licence | **MIT**, © 2026 Abdullah Aldosari and Nader Alshahri | `LICENSE` lines 1–3 |
| Dataset licence | Apache 2.0, per the AISA-ArabicFC dataset card | organisers' published card; **not re-verified live in this audit** |
| Training file redistribution | **Not performed.** `data/processed_v13/train_processed.jsonl` is untracked; the README links the official Hugging Face source | `.gitignore`, `data/blind/README_PLACEHOLDER.txt` |
| Blind gold / labels | **None present.** A filename scan for `*gold*`, `*label*`, `*answer*` returned zero files | §G test 5 |

---

## G. Executed tests

Environment: Linux VM, git 2.34.1, Python 3.10. **Not** the archived runtime
(Python 3.13.13 + pinned stack), so no inference result here is comparable to
the official submission.

| # | Test | Command | Result | Evidence |
|---|---|---|---|---|
| 1 | Clone / remote reachable | `git clone --depth 1 https://github.com/tgfdru/nabiq-arabicfc.git` | **PASS** | HEAD `6c047a3` |
| 2 | Working tree clean | `git status --porcelain` | **PASS** | empty |
| 3 | Source compiles | `python3 -m py_compile $(find src -name '*.py')` | **PASS** | 26 files, no output |
| 4 | Secret scan | `grep -rInE "(api[_-]?key\|secret\|token\|password\|BEGIN .*PRIVATE KEY\|sk-…\|ghp_…)"` | **PASS** | 9 hits, all the linguistic word "token" in NLP comments; zero credentials |
| 5 | Restricted-data scan | `find . -iname '*gold*' -o -iname '*label*' -o -iname '*answer*'` | **PASS** | zero files |
| 6 | MD5 integrity (4 unflagged) | `md5sum` vs `checksums.md` | **PASS** | §E |
| 7 | Validator CLI | `python3 src/validate_submission_files.py --help` | **PASS** | flags `--input --track-a --track-b` confirmed |
| 8 | Runner CLI | `python3 src/run_nabiq_blind.py --help` | **NOT RUN** | `ModuleNotFoundError: sklearn` — audit VM lacks the stack. Flags read from source `run_nabiq_blind.py:292-295`: `--input`, `--track-a`, `--track-b`, `--train` |
| 9 | Frozen env matches README | `grep -E '^(scikit-learn\|numpy\|scipy\|pandas)==' requirements-frozen.txt` | **PASS** | numpy 2.5.1, pandas 3.0.5, scikit-learn 1.9.0, scipy 1.18.0 — exact match |
| 10 | Paper PDF readable + correct | `pypdf` text extraction, page 1 | **PASS** | 10 pages; title, both authors, affiliation present |
| 11 | GitHub API reachable anonymously | `curl -o /dev/null -w '%{http_code}' https://api.github.com/repos/tgfdru/nabiq-arabicfc` | **PASS** | `200` |
| 12 | Poster QR decode | OpenCV `QRCodeDetector` on `NABIQ_Poster_A0.pdf` p.1 | **PASS** | `https://github.com/tgfdru/nabiq-arabicfc` |
| 13 | Blind-test metric reproduction | — | **NOT RUN** | blind input and official evaluator unavailable. Metrics cited from the paper, not reproduced |
| 14 | Hash-seed determinism replay | — | **NOT RUN** | requires the archived runtime and the dev-as-blind input. The 5/545 result is cited from the paper, not re-measured here |
| 15 | `git push` from the audit VM | `GIT_TERMINAL_PROMPT=0 git push --dry-run origin main` | **FAIL** | `fatal: could not read Username for 'https://github.com'` — no credential. Publication went through the authenticated browser session instead (§H) |
| 16 | Published README matches the staged file | SHA-256 of `raw.githubusercontent.com/.../main/README.md` | **PASS** | `dfacec53a6b3c0d1c4b700c4507c49cab8674f4b30e7e1d3598a525fa92c967b`, 11,131 B — identical to the staged file |
| 17 | Retracted strings absent from the published README | string count on the fetched file | **PASS** | `fully deterministic` 0 · `byte-reproducible` 0 · `1,050` 0 · `+0.167` 0 · `no decision path reads` 0 |
| 18 | Corrected strings present in the published README | string count on the fetched file | **PASS** | `1,125` 2 · `the no-call detector does` 1 · `0.6790` 1 · `not present in the archived package` 1 |
| 19 | Published paper PDF is bit-identical | SHA-256 of `raw.githubusercontent.com/.../main/NABIQ_ArabicNLP2026_paper.pdf` | **PASS** | `9b7c2c7f07a148fd9c32dc14b9ad6194c139d6a35ca0967ab092ca4bf0ed6941`, 122,623 B — matches the staged file |
| 20 | Release assets survived the notes rewrite | GitHub releases API | **PASS** | `nabiq_v15rx_blind_clean_final.zip` 2,084,833 B and `train_processed.jsonl` 24,315,543 B still attached; tag still `v15rx-final` → `9866beaa` |

---

## H. GitHub publication

**PERFORMED.** Two automated paths were blocked and a third succeeded:

| Path | Outcome |
|---|---|
| Session GitHub API proxy | **blocked** — `HTTP 403`, *"GitHub access to this repository is not enabled for this session."* The mechanism it names (`add_repo`) does not exist in this environment |
| Local `git push` from the audit VM | **blocked** — no credential helper, no stored token (test 15) |
| The owner's already-authenticated GitHub web session | **succeeded** — all changes below were committed through it |

### Commits on `main`

| SHA | Message | UTC |
|---|---|---|
| `786b15689b51489f017f629e08cd7d8fc5491a46` | Align README with the accepted camera-ready | 2026-10-16 14:05:14 |
| `b42396226d2d00319c38020c414b70f8464c6e5c` | Add the accepted ArabicNLP 2026 camera-ready paper | 2026-10-16 14:17:30 |
| `8269adcd453567110a9151387976c905432ed5d6` | Add the repository release audit — **this file** | 2026-10-16 14:22 |

Branch `main` advanced `6c047a3` → `786b1568` → `b4239622` → `8269adcd`. Linear
history, no force-push, no history rewrite, no deletion, no file moved or
renamed.

This report cannot state its own content hash, so one further commit after
`8269adcd` replaces this file with the present revision — the only change in it
is the two self-references in this section and in §B.

### Release

`https://github.com/tgfdru/nabiq-arabicfc/releases/tag/v15rx-final` — **notes
body rewritten in place** (5,875 B). What was deliberately **not** changed:

- the tag name `v15rx-final`, and the commit it points at (`9866beaa`);
- both release assets, verified still attached at their original sizes (test 20).

Rule 9 forbids moving or rewriting the tag, so the misleading *name* stands. It
is mitigated in two places instead: the published README states that the tag
names the frozen *package*, which contains both runners, and does not mean the
v15rx runner produced the submission; the rewritten notes say the same. A
separate, truthfully named release (`arabicnlp2026-submission-archive`) was
**not** created — it would duplicate the same two assets under a second name,
which is a decision for the authors, not for this audit.

### Verification method

Every published claim in this report was checked by re-fetching the live file
from `raw.githubusercontent.com` with `cache: 'no-store'` **after** the push and
hashing or string-counting the bytes that came back — see tests 16–20. The
staged files were not treated as evidence of what is published.

---

## I. QR and accessibility

| Check | Result |
|---|---|
| QR decodes to the intended URL | **PASS** — `https://github.com/tgfdru/nabiq-arabicfc` |
| Repository publicly reachable without authentication | **PASS** — anonymous clone and anonymous API both succeeded |
| Source browsable without downloading a ZIP | **PASS** — `src/` is a normal tree at HEAD |
| Paper openable from the repository | **PASS** — `NABIQ_ArabicNLP2026_paper.pdf` at the root, bit-identical (test 19) |
| README free of contradictions against the camera-ready | **PASS** — all four corrected and re-verified on the published file (tests 16–18) |
| Documented release available | **PASS** — `v15rx-final` with both assets and rewritten notes (test 20) |
| Repository description free of retracted claims | **PASS** — the "fully deterministic" wording is gone |
| Label *"Paper & Code"* accurate | **PASS** — both are now reachable from the QR target in two clicks |

The poster PDF was **not** modified, and the QR target URL did not change, so no
re-print is required.

---

## J. Open issues

1. **No automated credential path exists for this repository.** Publication
   succeeded only through the owner's authenticated browser session. Any future
   change needs that session, or a token the authors install themselves.
2. **The original blind-day validator log does not exist.** The primary outputs
   were not retained. This is permanent and is disclosed in the paper.
3. **The tag `v15rx-final` is misleadingly named** but must not be rewritten.
   Mitigated by an explicit note in the corrected README.
4. **The dataset licence was not re-verified live** in this audit; it is cited
   from the organisers' card.
5. **No metric in this repository has been independently reproduced.** All
   official numbers are quoted from the accepted paper.
6. **`FINAL_SIGNOFF.md` and `BLIND_TEST_RUNBOOK.md` remain pre-run documents.**
   They are left unaltered as historical record; the README now frames them.

---

## K. Final assessment

### **PASS WITH WARNINGS** — safe to show the QR

**What is verified and sound.** The repository is public, clean, secret-free,
free of gold/label/answer material, fully browsable, compiles end to end, and
its four unflagged checksums match the frozen package byte-for-byte — including
the runner that actually produced the submission. The code licence is MIT and
unambiguous. Provenance is resolved from primary post-run evidence, not from
filenames. The accepted camera-ready is in the repository and bit-identical to
the staged copy. Every claim the published README makes about the system now
either matches the accepted paper or is explicitly marked as not reproduced
here.

**The four contradictions found at the start are closed.** The most serious was
the README's denial that any decision path reads `negative_category`, which
contradicted the paper's own voluntary disclosure of a label leak into the
no-call detector. A repository that denies what its paper admits is worse than
one that says nothing, and that is now corrected and verified on the live file.

**Why this is not a full PASS.** Three limits are structural, not editorial, and
are stated rather than papered over:

1. **No official metric was reproduced.** The blind input and the organisers'
   evaluator are not available here, so FnAcc 0.9138 / ArgEM 0.7081 / Overall A
   0.7904 / Overall B 0.8282 are quoted from the accepted paper and labelled as
   quoted. Tests 13 and 14 were not run and are recorded as not run.
2. **The blind-day validator log is permanently gone.** The primary outputs were
   not retained, so the `recipient_iban` rejection rests on the post-run handoff
   record alone. Nothing was reconstructed to fill the gap.
3. **The tag `v15rx-final` is still misleadingly named,** because rule 9 forbids
   touching it. The mitigation is documentary, in the README and the release
   notes, not a rename.

**Residual risk to a reader arriving from the poster QR: low.** The repository
no longer asserts anything the paper contradicts, and what it cannot prove it
labels as unproven.
