# finetune/

Fine-tune AegisMed's model so the board chair reliably surfaces rare diagnoses.

```bash
python data/build_dataset.py            # 1. get the data (free, no API key)
python finetune/build_finetune_data.py  # 2. shape it into training conversations (free)
python finetune/run_finetune.py         # 3. launch the job on Fireworks (needs your key)
```

| File | What it does |
|---|---|
| `build_finetune_data.py` | Turns `data/eval_cases.jsonl` into chat-format `train.jsonl` / `val.jsonl`. Runs offline. |
| `run_finetune.py` | Uploads the data and starts + watches a supervised fine-tuning job on Fireworks AI. |
| `train.jsonl`, `val.jsonl` | Generated locally (gitignored). |

Full beginner-friendly walkthrough: [`../docs/FINETUNE.md`](../docs/FINETUNE.md).
