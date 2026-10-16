# NABIQ — Wajeh at AISA-ArabicFC

Code for the system description paper **_Wajeh at AISA-ArabicFC: A Non-LLM
Classical ML and Retrieval Pipeline for Arabic Function Calling_**
(ArabicNLP 2026, co-located with EMNLP 2026).

**Paper:** [`NABIQ_ArabicNLP2026_paper.pdf`](./NABIQ_ArabicNLP2026_paper.pdf)
· OpenReview submission `aWzX1T0ZAG`

NABIQ is a **non-neural** Arabic function-calling system. No large language
model, no pretrained encoder, no inference API, no PyTorch, no GPU. Its only
learned components are a TF-IDF representation and a logistic-regression
classifier from scikit-learn. A complete blind run takes minutes on a single
laptop CPU core.

## Official results (blind test, 1,125 rows)

| Metric | Value |
|---|---|
| FnAcc | 0.9138 — 1028 / 1125 |
| ArgEM | 0.7081 |
| ThinkRate | 1.0000 |
| **Overall A** | **0.7904** — rank 16 |
| **Overall B** | **0.8282** — rank 15 |

### Comparison with the organisers' baselines

All figures below are the organisers' **final** re-scored results on the
1,125-row blind test, using the released argument normaliser. The
pre-normaliser figures circulated during the campaign are **not comparable**
and are not used here.

| System | FnAcc | ArgEM | Overall A | Overall B |
|---|---|---|---|---|
| GPT-4o, zero-shot | 0.9324 | 0.7442 | 0.8195 | — |
| 270M fine-tuned | 0.9813 | 0.6790 | 0.8000 | 0.8074 |
| GPT-4o, 3-shot | 0.8676 | 0.6991 | 0.7665 | — |
| **NABIQ (ours)** | **0.9138** | **0.7081** | **0.7904** | **0.8282** |
| Random selection | 0.0418 | 0.0060 | 0.0203 | 0.0155 |

With no neural component, NABIQ is on a par with the fine-tuned 270M model and
few-shot GPT-4o on ArgEM, **below** zero-shot GPT-4o, and ahead of the
fine-tuned baseline on Overall B.

## Architecture

```
P1  Arabic normalisation   Alef/Hamza/Ya/Ta-marbuta unification, diacritic and
                           tatweel stripping, Eastern→Western digit mapping
P2  Router                 char n-gram TF-IDF + multi-class logistic regression,
                           restricted to the row's candidate set
P3  No-call detector       binary classifier, decision threshold 0.60
P4  Argument extraction    per-tool TF-IDF cosine nearest-argument retriever,
                           regex spans, train-mined gazetteers, canonical maps
P5  Guards + repairs       schema guard, per-tool evidence guard,
                           21 accepted repair rules (13 stage-1 + 8 stage-2)
P6  Evidence gate          a candidate value may replace a prediction only on
                           explicit textual or canonical evidence
P7  Track B trace          deterministic Arabic template over the Track A call
```

## Environment

```
Python 3.13.13
scikit-learn 1.9.0
numpy 2.5.1
scipy 1.18.0
pandas 3.0.5
```

These are the versions recorded in `requirements-frozen.txt`, verified against
this repository. Note that `requirements.txt` is **unpinned** — install from
`requirements-frozen.txt` to match the archived environment exactly.

CPU only. `PYTHONHASHSEED` must be pinned — see *Determinism* below.

## Reproducing the submission

```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export PYTHONHASHSEED=0                              # Windows: set PYTHONHASHSEED=0

python src/run_nabiq_blind.py \
  --input   data/blind/test.jsonl \
  --track-a nabiq_blind_track_a.jsonl \
  --track-b nabiq_blind_track_b.jsonl

python src/validate_submission_files.py \
  --input   data/blind/test.jsonl \
  --track-a nabiq_blind_track_a.jsonl \
  --track-b nabiq_blind_track_b.jsonl
```

The validator checks row count, id uniqueness, field types, absence of `think`
in Track A, and agreement between Tracks A and B on `id`, `tool_called` and
`arguments`.

The submitted files were produced by the **fallback** runner
(`src/run_nabiq_blind.py`). The primary runner (`v15rx`) failed the official
validator on malformed `recipient_iban` values and was not submitted — see
*Known failures*.

## Repository structure

```
src/                         implementation
  run_nabiq_blind.py           fallback runner — produced the submitted files
  validate_submission_files.py official-format validator
  phase1_rules_v5_pc.py        normalisation, rules, evaluation helpers
  nabiq_v*_*.py                staged repair-rule generations (v3 … v14)
  v15_candidate/               primary v15rx runner — NOT the submitted system
data/blind/                  placeholder; the blind input is not redistributed
outputs/                     placeholder; no predictions are committed
checksums.md                 MD5 table for the frozen package
BLIND_TEST_RUNBOOK.md        blind-day procedure (written before the run)
FINAL_SIGNOFF.md             pre-run approval record (see Provenance below)
requirements-frozen.txt      exact archived environment
```

## Provenance — what was actually submitted

This distinction matters and is easy to get wrong when reading this repository.

| | Primary (`v15_candidate/run_nabiq_blind_v15rx.py`) | Fallback (`src/run_nabiq_blind.py`) |
|---|---|---|
| Role **before** blind day | approved primary runner | emergency fallback |
| What happened **on** blind day | outputs **rejected** by the official validator on invalid `recipient_iban` values | passed the validator, 0 errors / 0 warnings |
| Submitted for Track A and Track B | **No** | **Yes** |

`FINAL_SIGNOFF.md` and `BLIND_TEST_RUNBOOK.md` in this repository were written
**before** the blind run and therefore record v15rx as the approved primary
runner. They describe the plan, not the outcome. The post-run handoff record
states that both uploaded files were fallback outputs and that the primary
outputs were rejected by the validator.

The existing git tag `v15rx-final` names the frozen *package*, which contains
both runners. It does **not** mean that the v15rx runner produced the
submission.

The fallback runner in this repository is byte-identical to the frozen package:
`src/run_nabiq_blind.py` MD5 `543d20c004fc6118fe4260a6be88636b`, matching
`checksums.md`.

## Determinism

The pipeline has no random seed at inference, but that is **not** the same as
being deterministic. Tie-breaking in the gazetteer-mining and
candidate-collection paths iterates unordered Python containers and so inherits
the interpreter's hash order. Re-running the archived package on the
development-as-blind input under two different hash seeds changes **5 of 545
rows**, all of them tie-breaks between orthographic variants of the same city.
Repeating a run at a fixed seed is identical.

This package is therefore reproducible **only under a pinned
`PYTHONHASHSEED`**. Sorting the affected traversals is the fix this diagnosis
implies; **it is not present in the archived package**, which is preserved as
submitted. We do **not** claim that the submitted fallback was byte-identical
across fresh processes.

## Data integrity

This repository contains **no gold, answer or label files** of any kind — no
`dev_gold`, no `pseudo_blind_gold`, no `holdout_gold`, no cached submissions.
The blind runner refuses any input path whose filename contains `gold`,
`answer` or `label`.

### A label proxy in the input

The distributed rows carry a `negative_category` field, which is null for every
positive training row and populated for every negative one, and which the
organisers have confirmed is nulled in the blind test.

Our `build_none_text` helper **concatenates this field into the feature string
that the no-call detector vectorises**, at training and at inference alike. We
did not intend this and did not catch it before the freeze. The router, the
nearest-argument retriever, the span extractors and both guards do not read the
field; **the no-call detector does.**

Measured post-submission, at the shipped threshold of 0.60:

| | with the field | with it blanked |
|---|---|---|
| No-call recall (5-fold CV on train) | 0.9600 | 0.5400 |
| Development FnAcc (frozen chain rerun) | 1.0000 | 0.9706 |
| Development Overall A | 0.9520 | 0.9343 |

That magnitude is about a third of the development-to-test FnAcc difference and
about a tenth of our development-estimate error. Predictions are **not**
byte-identical when the field is stripped. Section 5 and Appendix C of the
paper report this in full.

### Files not tracked in git

- `data/blind/test.jsonl` — the blind input, from the organisers or from
  [`TuwaiqAcademy/AISA-ArabicFC`](https://huggingface.co/datasets/TuwaiqAcademy/AISA-ArabicFC).
- `data/processed_v13/train_processed.jsonl` — the released **training** split
  in processed form, used to fit the router, the nearest-argument retriever and
  the gazetteers. Download it from the
  [`v15rx-final` release](../../releases) and place it at
  `data/processed_v13/`. It contains training data only; it is kept out of the
  repo because redistributing 23 MB of the organisers' dataset through git is
  poor practice, not because of any integrity concern.

Integrity of the frozen archive can be checked against the MD5 table in
`checksums.md`.

## Known failures (documented in the paper)

1. **G2 / IBAN — an acceptance-coverage gap.** Our acceptance suite measured
   the *run* (row count, validator verdict, Track A/B agreement) but never
   *per-rule coverage*. On the dev-as-blind acceptance input the G2 rule
   (explicit `recipient_iban` re-extraction) produced zero insertions across
   the 24 predicted `transfer_money` rows, so a green acceptance run certified
   an effectively unexercised path. It then failed the official validator on
   the real blind set. Acceptance criteria should include "each new rule fired
   on ≥ k rows and every emitted value validated", not only "the run passed".

2. **The dev→test gap.** 21 repair rules were accepted under a
   zero-regression protocol applied to the same 500 positive development cases,
   each decision informed by the errors the previous one left behind. That is
   adaptive overfitting: the submitted fallback fell from ArgEM 0.9200 on the
   development-as-blind acceptance run to 0.7081 on test. A rehearsal on 545
   rows held out from train, run before the blind release, predicted the
   official Overall A to within 0.0033, against 0.1724 for the tuned
   development estimate.

3. **The evidence gate does not reach every value.** It governs candidate
   replacements over a subset of tools, so a first-pass retrieved value can
   survive without textual support — 2.1% of emitted development values.

## Citation

If you use this code, please cite the paper and the shared task:

```bibtex
@inproceedings{aldosari-alshahri-2026-wajeh,
  title     = {Wajeh at {AISA-ArabicFC}: A Non-{LLM} Classical {ML} and Retrieval Pipeline for Arabic Function Calling},
  author    = {Aldosari, Abdullah and Alshahri, Nader},
  booktitle = {Proceedings of The Fourth Arabic Natural Language Processing Conference: Shared Tasks},
  year      = {2026},
  address   = {Budapest, Hungary},
  publisher = {Association for Computational Linguistics}
}
```

## License

Code: MIT (see `LICENSE`). Dataset: Apache 2.0 (AISA-ArabicFC).
