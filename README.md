# NABIQ — Wajeh at AISA-ArabicFC

Code for the system description paper **_Wajeh at AISA-ArabicFC: A Non-LLM
Classical ML and Retrieval Pipeline for Arabic Function Calling_**
(ArabicNLP 2026, co-located with EMNLP 2026).

NABIQ is a **fully deterministic, non-neural** Arabic function-calling system.
No large language model, no pretrained encoder, no inference API, no PyTorch,
no GPU. Its only learned components are a TF-IDF representation and a
logistic-regression classifier from scikit-learn. A complete blind run takes
minutes on a single laptop CPU core and is byte-reproducible.

## Official results (blind test, 1,050 rows)

| Metric | Value |
|---|---|
| FnAcc | 0.9138 |
| ArgEM | 0.7081 |
| ThinkRate | 1.0000 |
| **Overall A** | **0.7904** — rank 16 |
| **Overall B** | **0.8282** — rank 15 |

Our ArgEM of 0.7081 is +0.167 over the fine-tuned AISA-Think baseline (0.541)
and +0.638 over zero-shot GPT-4o (0.070), with no neural component at all.

## Architecture

```
Arabic normalisation      Alef/Hamza/Ya/Ta-marbuta unification, diacritic and
                          tatweel stripping, Eastern→Western digit mapping
        ↓
Tool routing              char n-gram + word TF-IDF → logistic regression,
                          restricted to the row's candidate tool set
        ↓
No-call detector          binary classifier for the negative class
                          (dev FnAcc 0.9706 → 1.0000)
        ↓
Argument extraction       per-tool TF-IDF cosine nearest-argument retrieval
                          + direct span extraction (regex + train-mined
                          gazetteers) + canonical mappings
        ↓
Guards                    schema guard (drop off-schema keys, coerce types)
                          evidence guard (no speculative optional arguments)
        ↓
Evidence gate             a value may enter a prediction only if it is a
                          normalised substring of the utterance, a member of a
                          closed canonical map, or a date whose day and month
                          tokens occur in the text
        ↓
Track B                   parameterised Arabic `think` template rendered from
                          the Track A prediction (ThinkRate 1.0000)
```

## Environment

```
Python 3.13.13
scikit-learn 1.9.0
numpy 2.5.1
scipy 1.18.0
pandas 3.0.5
```

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

python src/validate_submission_files.py
```

The validator checks row count, id uniqueness, field types, absence of `think`
in Track A, and agreement between Tracks A and B on `id`, `tool_called` and
`arguments`.

The submitted files were produced by the **fallback** runner
(`src/run_nabiq_blind.py`). The primary runner (`v15rx`) failed the official
validator on malformed `recipient_iban` values and was not submitted — see
*Known failures*.

## Determinism

The pipeline has no random seed at inference, but that is not the same as being
deterministic. Tie-breaking in the gazetteer-mining and candidate-collection
paths originally iterated unordered Python containers and so inherited the
interpreter's hash order, which made a handful of rows vary between runs. Every
such traversal is now explicitly sorted and `PYTHONHASHSEED` is pinned. With
those in place, repeated runs of the frozen package produce byte-identical
output files.

## Data integrity

This repository contains **no gold, answer or label files** of any kind — no
`dev_gold`, no `pseudo_blind_gold`, no `holdout_gold`, no cached submissions.
The blind runner refuses any input path whose filename contains `gold`,
`answer` or `label`.

The distributed input rows carry a `negative_category` field which, for the
corpus's 125 negative instances, effectively identifies them as no-call cases.
Our row builder copies this field into the constructed record alongside
`dialect`, but **no decision path reads it** — not the router, the retriever,
the extractors, the guards, or the no-call detector. Predictions are
byte-identical when the field is stripped from the input. Our blind FnAcc of
0.9138 is itself evidence of that.

Two files are **not** tracked in git and must be fetched before a run:

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
   (explicit `recipient_iban` re-extraction) fired on too few rows to expose
   its malformed-IBAN behaviour, so a green acceptance run certified an
   effectively unexercised path. It then failed the official validator on the
   real blind set. Cost: 0.9380 → 0.9200 ArgEM on the acceptance replay.
   Acceptance criteria should include "each new rule fired on ≥ k rows and
   every emitted value validated", not only "the run passed".

2. **The dev→test gap.** 21 repair rules were accepted under a
   zero-regression protocol applied to the same 500 positive development cases,
   each decision informed by the errors the previous one left behind. That is
   adaptive overfitting: development ArgEM 0.938 → blind ArgEM 0.708. A
   held-out slice of the development set should have been reserved.

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

@inproceedings{nacar-etal-2026-aisa-arabicfc,
  title     = {{AISA-ArabicFC}: The First Shared Task on Arabic Function Calling for Agentic AI Systems},
  author    = {Nacar, Omer and Al Khalifa, Mohammed and Alzaharani, Saeed},
  booktitle = {Proceedings of The Fourth Arabic Natural Language Processing Conference: Shared Tasks},
  year      = {2026},
  address   = {Budapest, Hungary},
  publisher = {Association for Computational Linguistics}
}
```

## Authors

Abdullah Aldosari · Nader Alshahri — University of Bisha, Saudi Arabia

## License

MIT — see [LICENSE](LICENSE).
