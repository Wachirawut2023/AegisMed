# AegisMed evaluation results

**Model:** `accounts/fireworks/models/deepseek-v4-flash`  
**Intake step:** on — questions auto-answered from the case  
**Demo mode:** False   
**Case pool:** eval-only holdout, disjoint from fine-tuning data (`aegismed.data_split`)  

## Headline: correct diagnosis surfaced in **16/21 = 76%** of cases

| Source | Hit rate |
|---|---|
| CUPCase | 4/5 (80%) |
| RareBench/HMS | 3/5 (60%) |
| RareBench/LIRICAL | 2/2 (100%) |
| RareBench/MME | 2/4 (50%) |
| RareBench/RAMEDIS | 5/5 (100%) |

## Per-case
| Case | Source | Correct diagnosis | Found? |
|---|---|---|---|
| cupcase-8 | CUPCase | Meningioma | ✅ |
| rarebench-mme-0 | RareBench/MME | Alacrimia-choreoathetosis-liver dysfunction syndrome | ❌ |
| rarebench-lirical-2 | RareBench/LIRICAL | Bamforth-Lazarus syndrome | ✅ |
| rarebench-lirical-0 | RareBench/LIRICAL | Cleidocranial dysplasia | ✅ |
| rarebench-ramedis-14 | RareBench/RAMEDIS | Citrullinemia type I | ✅ |
| rarebench-ramedis-13 | RareBench/RAMEDIS | Glutaric acidemia type I | ✅ |
| cupcase-1 | CUPCase | metastatic melanoma | ✅ |
| cupcase-11 | CUPCase | Intra-abdominal desmoid-type fibromatosis | ✅ |
| rarebench-mme-4 | RareBench/MME | Cerebrocostomandibular syndrome | ❌ |
| rarebench-hms-14 | RareBench/HMS | Stickler syndrome type 1 | ✅ |
| rarebench-mme-9 | RareBench/MME | Spondylometaphyseal dysplasia, Sedaghatian type | ✅ |
| rarebench-ramedis-10 | RareBench/RAMEDIS | Glutaric acidemia type I | ✅ |
| cupcase-4 | CUPCase | COVID-19-related encephalomyelitis | ❌ |
| cupcase-3 | CUPCase | Hydatid disease | ✅ |
| rarebench-hms-0 | RareBench/HMS | Vasculitis, autoinflammation, immunodeficiency, and hematologic defects syndrome | ❌ |
| rarebench-hms-5 | RareBench/HMS | Familial mediterranean fever | ✅ |
| rarebench-hms-1 | RareBench/HMS | Spondyloarthropathy, susceptibility to, 1 | ❌ |
| rarebench-ramedis-8 | RareBench/RAMEDIS | 3-hydroxy-3-methylglutaric aciduria | ✅ |
| rarebench-mme-7 | RareBench/MME | Cerebrocostomandibular syndrome | ✅ |
| rarebench-hms-11 | RareBench/HMS | Familial cold inflammatory syndrome 1 | ✅ |
| rarebench-ramedis-11 | RareBench/RAMEDIS | Phenylketonuria | ✅ |

_“Found” means the correct diagnosis (or a known synonym) appeared anywhere in the board's output. Matching is text-based and approximate; skim mismatches by hand before trusting a number._