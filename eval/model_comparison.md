# AegisMed model comparison

**Run date:** 2026-07-09 16:37 UTC  
**Cases:** 75  
**Intake step:** on — questions auto-answered from the case  
**Note:** each model is scored in a single pass at temperature 0.4 — results are one sample, not an average across repeats, so small differences (a few percentage points) may just be noise.  

## Headline

| Model | Model ID | Correct | Hit rate | Errors | Avg latency/case |
|---|---|---|---|---|---|
| Fine-tuned | `accounts/wachirawut2002-fqt88/models/aegismed-gemma-tuned#accounts/wachirawut2002-fqt88/deployments/nqid2132` | 35/75 | 47% | 0 | 22.54s |
| Base (Gemma 3) | `accounts/fireworks/models/gemma-3-27b-it#accounts/wachirawut2002-fqt88/deployments/c5sb5mph` | 34/75 | 45% | 1 | 21.9s |
| Gemma 4 | `accounts/fireworks/models/gemma-4-31b-it#accounts/wachirawut2002-fqt88/deployments/rk0psoca` | 6/75 | 8% | 64 | 19.65s |

## Per-source hit rate

| Source | Fine-tuned | Base (Gemma 3) | Gemma 4 |
|---|---|---|---|
| CUPCase | 9/15 (60%) | 9/15 (60%) | 1/15 (7%) |
| RareBench/HMS | 6/15 (40%) | 6/15 (40%) | 0/15 (0%) |
| RareBench/LIRICAL | 6/15 (40%) | 6/15 (40%) | 1/15 (7%) |
| RareBench/MME | 3/15 (20%) | 3/15 (20%) | 0/15 (0%) |
| RareBench/RAMEDIS | 11/15 (73%) | 10/15 (67%) | 4/15 (27%) |

## Per-case results

| Case | Source | Correct diagnosis | Fine-tuned | Base (Gemma 3) | Gemma 4 |
|---|---|---|---|---|---|
| cupcase-8 | CUPCase | Meningioma | ✅ | ✅ | ⚠️ |
| rarebench-mme-1 | RareBench/MME | Alacrimia-choreoathetosis-liver dysfunction syndrome | ❌ | ❌ | ⚠️ |
| rarebench-mme-14 | RareBench/MME | Alacrimia-choreoathetosis-liver dysfunction syndrome | ❌ | ❌ | ⚠️ |
| rarebench-mme-6 | RareBench/MME | Shprintzen-Goldberg syndrome | ✅ | ✅ | ⚠️ |
| rarebench-hms-13 | RareBench/HMS | Antisynthetase syndrome | ❌ | ❌ | ⚠️ |
| rarebench-mme-13 | RareBench/MME | SHORT syndrome | ✅ | ✅ | ⚠️ |
| rarebench-lirical-7 | RareBench/LIRICAL | Joubert syndrome 30 | ✅ | ✅ | ⚠️ |
| rarebench-ramedis-0 | RareBench/RAMEDIS | Ornithine transcarbamylase deficiency | ❌ | ❌ | ✅ |
| cupcase-14 | CUPCase | Anti-MDA5 positive dermatomyositis | ✅ | ✅ | ⚠️ |
| rarebench-mme-0 | RareBench/MME | Alacrimia-choreoathetosis-liver dysfunction syndrome | ❌ | ❌ | ⚠️ |
| rarebench-ramedis-1 | RareBench/RAMEDIS | Phenylketonuria | ✅ | ✅ | ⚠️ |
| rarebench-lirical-8 | RareBench/LIRICAL | Bleeding disorder, platelet-type, 15 | ✅ | ✅ | ✅ |
| rarebench-ramedis-6 | RareBench/RAMEDIS | Glycogen storage disease Ia | ❌ | ❌ | ❌ |
| rarebench-ramedis-9 | RareBench/RAMEDIS | Smith-Lemli-Opitz syndrome | ✅ | ✅ | ✅ |
| rarebench-hms-7 | RareBench/HMS | Takayasu arteritis | ❌ | ❌ | ⚠️ |
| cupcase-9 | CUPCase | Giant cell arteritis (GCA) | ✅ | ✅ | ⚠️ |
| rarebench-lirical-14 | RareBench/LIRICAL | Brachydactyly-short stature-retinitis pigmentosa syndrome | ❌ | ❌ | ⚠️ |
| rarebench-lirical-11 | RareBench/LIRICAL | Oliver-Mcfarlane syndrome | ❌ | ❌ | ⚠️ |
| rarebench-hms-3 | RareBench/HMS | Primary Sjögren syndrome | ✅ | ✅ | ⚠️ |
| rarebench-lirical-2 | RareBench/LIRICAL | Bamforth-Lazarus syndrome | ❌ | ❌ | ⚠️ |
| rarebench-hms-8 | RareBench/HMS | Systemic sclerosi | ❌ | ❌ | ⚠️ |
| rarebench-ramedis-12 | RareBench/RAMEDIS | Canavan disease | ✅ | ✅ | ⚠️ |
| rarebench-mme-3 | RareBench/MME | Ataxia-intellectual disability-oculomotor apraxia-cerebellar cysts syndrome | ❌ | ❌ | ⚠️ |
| rarebench-lirical-13 | RareBench/LIRICAL | Recurrent metabolic encephalomyopathic crises-rhabdomyolysis-cardiac arrhythmia-intellectual disability syndrome | ❌ | ❌ | ⚠️ |
| rarebench-lirical-0 | RareBench/LIRICAL | Cleidocranial dysplasia | ✅ | ✅ | ⚠️ |
| rarebench-ramedis-14 | RareBench/RAMEDIS | Citrullinemia type I | ✅ | ✅ | ⚠️ |
| rarebench-ramedis-13 | RareBench/RAMEDIS | Glutaric acidemia type I | ✅ | ✅ | ✅ |
| cupcase-1 | CUPCase | metastatic melanoma | ✅ | ✅ | ⚠️ |
| rarebench-lirical-12 | RareBench/LIRICAL | Myasthenic syndrome, congenital, 8 | ✅ | ✅ | ⚠️ |
| rarebench-mme-11 | RareBench/MME | Cerebrocostomandibular syndrome | ❌ | ❌ | ❌ |
| rarebench-ramedis-5 | RareBench/RAMEDIS | X-linked hypophosphatemia | ✅ | ✅ | ⚠️ |
| cupcase-7 | CUPCase | Acute left adrenal infarction | ❌ | ❌ | ⚠️ |
| cupcase-11 | CUPCase | Intra-abdominal desmoid-type fibromatosis | ❌ | ❌ | ⚠️ |
| rarebench-mme-4 | RareBench/MME | Cerebrocostomandibular syndrome | ❌ | ❌ | ⚠️ |
| cupcase-6 | CUPCase | High-grade serous ovarian cancer (pT3bN1M0) | ❌ | ❌ | ⚠️ |
| rarebench-ramedis-7 | RareBench/RAMEDIS | Phenylketonuria | ✅ | ✅ | ⚠️ |
| rarebench-hms-6 | RareBench/HMS | Granulomatosis with polyangiitis | ❌ | ❌ | ⚠️ |
| rarebench-mme-10 | RareBench/MME | Microcephaly 2, primary, autosomal recessive, with or without cortical malformations | ❌ | ❌ | ⚠️ |
| rarebench-lirical-3 | RareBench/LIRICAL | CODAS syndrome | ❌ | ❌ | ⚠️ |
| rarebench-mme-8 | RareBench/MME | Cataract-growth hormone deficiency-sensory neuropathy-sensorineural hearing loss-skeletal dysplasia syndrome | ✅ | ✅ | ⚠️ |
| rarebench-ramedis-4 | RareBench/RAMEDIS | PMM2-CDG | ✅ | ❌ | ⚠️ |
| rarebench-ramedis-3 | RareBench/RAMEDIS | Ornithine transcarbamylase deficiency | ✅ | ✅ | ⚠️ |
| rarebench-mme-12 | RareBench/MME | Alacrimia-choreoathetosis-liver dysfunction syndrome | ❌ | ❌ | ⚠️ |
| rarebench-ramedis-2 | RareBench/RAMEDIS | Medium chain acyl-CoA dehydrogenase deficiency | ❌ | ❌ | ❌ |
| rarebench-hms-14 | RareBench/HMS | Stickler syndrome type 1 | ✅ | ✅ | ⚠️ |
| rarebench-mme-9 | RareBench/MME | Spondylometaphyseal dysplasia, Sedaghatian type | ❌ | ❌ | ⚠️ |
| rarebench-lirical-10 | RareBench/LIRICAL | Autosomal dominant hyper-IgE syndrome | ✅ | ✅ | ⚠️ |
| cupcase-10 | CUPCase | PCE (Perchloroethylene) intoxication | ❌ | ❌ | ⚠️ |
| rarebench-lirical-5 | RareBench/LIRICAL | Multiple endocrine neoplasia type 1 | ✅ | ✅ | ⚠️ |
| rarebench-hms-4 | RareBench/HMS | IgG4 related disease | ✅ | ✅ | ⚠️ |
| rarebench-hms-10 | RareBench/HMS | Buerger disease | ❌ | ❌ | ⚠️ |
| cupcase-5 | CUPCase | Methanol poisoning | ✅ | ✅ | ⚠️ |
| cupcase-0 | CUPCase | Fibroadenoma in axillary accessory breast | ❌ | ❌ | ⚠️ |
| rarebench-hms-12 | RareBench/HMS | Systemic lupus erythematosus | ✅ | ✅ | ⚠️ |
| rarebench-ramedis-10 | RareBench/RAMEDIS | Glutaric acidemia type I | ✅ | ✅ | ✅ |
| cupcase-2 | CUPCase | Lightning strike injury | ✅ | ✅ | ⚠️ |
| rarebench-lirical-6 | RareBench/LIRICAL | Galloway-Mowat syndrome 4 | ❌ | ⚠️ | ⚠️ |
| cupcase-4 | CUPCase | COVID-19-related encephalomyelitis | ✅ | ✅ | ⚠️ |
| cupcase-3 | CUPCase | Hydatid disease | ✅ | ✅ | ✅ |
| rarebench-hms-0 | RareBench/HMS | Vasculitis, autoinflammation, immunodeficiency, and hematologic defects syndrome | ❌ | ❌ | ⚠️ |
| rarebench-hms-5 | RareBench/HMS | Familial mediterranean fever | ✅ | ✅ | ⚠️ |
| rarebench-hms-1 | RareBench/HMS | Spondyloarthropathy, susceptibility to, 1 | ❌ | ❌ | ⚠️ |
| rarebench-mme-5 | RareBench/MME | Microcephaly-Capillary malformation syndrome | ❌ | ❌ | ⚠️ |
| cupcase-13 | CUPCase | de Winter syndrome | ❌ | ❌ | ⚠️ |
| cupcase-12 | CUPCase | Gorlin syndrome | ✅ | ✅ | ⚠️ |
| rarebench-lirical-9 | RareBench/LIRICAL | Recurrent metabolic encephalomyopathic crises-rhabdomyolysis-cardiac arrhythmia-intellectual disability syndrome | ❌ | ❌ | ⚠️ |
| rarebench-hms-9 | RareBench/HMS | Immunoglobulin A vasculitis | ❌ | ❌ | ⚠️ |
| rarebench-ramedis-8 | RareBench/RAMEDIS | 3-hydroxy-3-methylglutaric aciduria | ❌ | ❌ | ❌ |
| rarebench-mme-2 | RareBench/MME | Ataxia-intellectual disability-oculomotor apraxia-cerebellar cysts syndrome | ❌ | ❌ | ⚠️ |
| rarebench-mme-7 | RareBench/MME | Cerebrocostomandibular syndrome | ❌ | ❌ | ⚠️ |
| rarebench-hms-11 | RareBench/HMS | Familial cold inflammatory syndrome 1 | ❌ | ❌ | ⚠️ |
| rarebench-lirical-1 | RareBench/LIRICAL | Stankiewicz-Isidor syndrome | ❌ | ❌ | ❌ |
| rarebench-ramedis-11 | RareBench/RAMEDIS | Phenylketonuria | ✅ | ✅ | ⚠️ |
| rarebench-lirical-4 | RareBench/LIRICAL | Oculocerebrorenal syndrome of Lowe | ❌ | ❌ | ⚠️ |
| rarebench-hms-2 | RareBench/HMS | Systemic lupus erythematosus | ✅ | ✅ | ⚠️ |

_“Correct” means the expected diagnosis (or a known synonym) appeared anywhere in that model's board output. Matching is text-based and approximate — skim ❌ rows by hand before trusting small differences between models. ⚠️ marks a case where the API call itself failed (see `eval/comparison_results.json` for the error message)._