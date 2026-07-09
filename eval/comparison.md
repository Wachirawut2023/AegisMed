# A/B Test Comparison

## Headline Accuracy

| Model | Accuracy |
|---|---|
| baseline | 76% |
| tuned | 76% |

## Per-Source Breakdown

| Source | baseline | tuned |
|---|---||---|
| CUPCase | 3/5 | 4/5 |
| RareBench/HMS | 4/5 | 3/5 |
| RareBench/LIRICAL | 2/2 | 2/2 |
| RareBench/MME | 2/4 | 2/4 |
| RareBench/RAMEDIS | 5/5 | 5/5 |

## Case-by-case wins

- Both correct: 15
- Only baseline: 1
- Only tuned: 1
- Both missed: 4

### Cases baseline caught but tuned missed

- rarebench-hms-0: Vasculitis, autoinflammation, immunodeficiency, and hematologic defects syndrome

### Cases tuned caught but baseline missed

- cupcase-1: metastatic melanoma
