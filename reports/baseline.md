# Baseline Evaluation

*Measures the deterministic detector's classification quality and revenue exposure over the 1,000-event synthetic benchmark (seed 42).*

**Total events evaluated:** 1,000

## Confusion Matrix

| | Predicted at-risk | Predicted not at-risk |
|---|---:|---:|
| **Actually recoverable** | True Positives (TP): 438 | False Negatives (FN): 0 |
| **Actually not recoverable** | False Positives (FP): 224 | True Negatives (TN): 338 |

## Metrics

| Metric | Value |
|---|---:|
| Precision | 0.6616 |
| Recall | 1.0000 |
| F1 Score | 0.7964 |

## Sanity Check

| Check | Result | Status |
|---|---:|---|
| status=succeeded with at_risk=True | 0 | PASS |

## Revenue

| Measure | Amount |
|---|---:|
| Total revenue | ₹9,824,112 |
| Revenue (at_risk=True) | ₹6,538,889 |
| At-risk percentage | 66.6% |

## Recoverability Tiering (ground_truth_recoverable=True only)

| Tier assignment | Count | Share |
|---|---:|---:|
| Total ground-truth recoverable | 438 | 100% |
| Assigned high/medium | 317 | 72.4% |
| Assigned low/none | 121 | 27.6% |
