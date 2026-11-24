# Phishing website detection with cross-modal consistency verification

Code for the paper *Multimodal LLM-Based Phishing Website Detection via
Cross-Modal Consistency Verification*.

A page is read by four agents in parallel: the URL and its redirect chain, the raw
HTML, the visible text, and the screenshot. Three scores then measure how far the
text side and the visual side disagree — brand (BIS), function (FIS) and information
gap (IGS). A judge combines the four agent votes, these scores and a 46-brand
knowledge base lookup through ten priority rules, and returns the verdict with the
evidence that produced it.

The point of the design is the image-evasive case: a page whose text reads as
harmless while the logo, the form and the wording are carried by an image. Text-side
detectors see nothing there, and that is what the three scores are for.

## Repository layout

| path | contents |
| --- | --- |
| `agents/` | the four agents, the consistency metrics, the RAG lookup, the rule-based judge, the async orchestrator |
| `data/` | dataset loader and HTML/text preprocessing |
| `utils/api.py` | async wrapper around the two model APIs |
| `knowledge_base/` | 46 brands, 84 aliases, and the script that builds the file |
| `run_test.py` | batch runner (single sample, N samples, or the full set) |
| `merge_results.py` | concatenates batch output for the ablation script |
| `run_ablations.py` | ablation study, recomputed offline from saved agent output |
| `extract_features.py`, `run_baselines.py` | feature-based and voting baselines |
| `iep_subset.json` | the 183 annotated image-evasive samples |

## Requirements

Python 3.10 or newer.

```
pip install -r requirements.txt
```

## Data

The experiments use [Phish360](https://web.cs.hacettepe.edu.tr/~selman/phish360-dataset/)
(10,748 samples: 4,332 phishing, 6,416 legitimate, 46 brands). Download it and point
the `PHISH360_PATH` variable at the directory that contains `trainval/` and `test/`.
Each sample directory holds the URL, the raw HTML and a 1280x960 screenshot.

The 183 image-evasive samples are listed in `iep_subset.json` with their ids, labels,
the three scores and the verdict. Raw pages are not redistributed here — download the
dataset and join on `sample_id`.

## Configuration

Keys are read from the environment:

```
export ARK_API_KEY=...
export ZHIPU_API_KEY=...        # only needed for the Zhipu vision backend
export VISION_MODEL=doubao      # doubao (default) or zhipu
```

Alternatively put them in a `config_local.py` next to `config.py`; that file is
ignored by git. The defaults in `config.py` read `YOUR_ARK_API_KEY` placeholders and
will fail until a real key is supplied.

All other knobs — concurrency, truncation lengths, metric weights, the CS threshold,
the suspicious TLD list — are at the top of `config.py`.

## Running

Whole dataset, in batches:

```
python run_test.py --full --prefix full --start 0 --end 1000
python run_test.py --full --prefix full --start 1000 --end 2000 --resume
```

A random subset, useful for a quick check:

```
python run_test.py -n 100 --seed 42
```

Results go to `results/<prefix>_<start>_<end>.json`, with a `_slim.json` copy that
drops the per-sample agent output. The full file is what the ablation script needs.

Ablations:

```
python merge_results.py          # -> results/full_all_merged.json
python run_ablations.py          # -> ablation_results/
```

The ablation script does not call any API: it recomputes the consistency scores from
the saved agent output and re-runs the judge under each configuration.

Baselines:

```
python extract_features.py       # -> features/
python run_baselines.py          # -> baselines/results/
```

## Reported numbers

Full set of 10,748 samples, identical models for every row:

| configuration | accuracy | F1 |
| --- | --- | --- |
| proposed method | 95.60 | 94.38 |
| simple multimodal baseline | 89.86 | 89.17 |
| no consistency metrics | 92.45 | 89.93 |
| without RAG | 92.24 | 89.45 |
| text agent only | 79.79 | 67.17 |
| vision agent only | 79.83 | 68.77 |

66.1% (121/183) of the image-evasive samples are detected, against a 97.5% detection
rate on the remaining phishing samples.

## Citation

```
Shi, Z., Li, H., Liu, Y., Wang, D. Multimodal LLM-Based Phishing Website Detection
via Cross-Modal Consistency Verification. Under review.
```

## License

MIT, see `LICENSE`. The Phish360 dataset is covered by its own terms and is not
redistributed here.
