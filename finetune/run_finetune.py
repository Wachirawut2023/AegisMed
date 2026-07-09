"""Start (and watch) a supervised fine-tuning job for AegisMed on Fireworks AI.

WHAT THIS DOES (plain language)
-------------------------------
This is the step that actually teaches the model. It takes the training file
built by finetune/build_finetune_data.py and asks Fireworks AI to fine-tune the
base Gemma model on it, then it watches the job until it finishes. When it is
done, Fireworks gives you a new model id that you drop into `.env` as `MODEL`,
and the whole board runs on your tuned model.

Fireworks runs on AMD hardware — the same stack the rest of AegisMed uses — so
nothing about your deployment changes except the model name.

WHAT YOU NEED FIRST
-------------------
  1. A Fireworks API key in `.env` (FIREWORKS_API_KEY=...), same as the app.
  2. Your Fireworks account id in `.env` (FIREWORKS_ACCOUNT_ID=...). Find it in
     the Fireworks dashboard URL: app.fireworks.ai/dashboard/<ACCOUNT_ID>/...
  3. A built dataset: run `python finetune/build_finetune_data.py` first.

USAGE
-----
  python finetune/run_finetune.py                 # upload data + start + watch
  python finetune/run_finetune.py --no-wait       # start and exit (check later)
  python finetune/run_finetune.py --epochs 2      # override training epochs
  python finetune/run_finetune.py --dry-run       # validate everything, call nothing

This uses Fireworks' REST API directly (no extra dependencies beyond httpx,
which the app already needs). It is intentionally small and readable — the
Fireworks `firectl` CLI does the same thing if you prefer a command-line tool;
see docs/FINETUNE.md.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import httpx

# Make the aegismed package importable when run as `python finetune/...`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aegismed import config  # noqa: E402

FT_DIR = Path(__file__).resolve().parent
API = "https://api.fireworks.ai/v1"

# Poll cadence while waiting for the job — gentle on rate limits.
POLL_SECONDS = 20
# States that mean "stop waiting".
DONE_STATES = {"COMPLETED", "FAILED", "CANCELLED", "DELETING", "DELETED"}


class FineTuneError(Exception):
    """Any problem talking to the Fireworks fine-tuning API."""


def _account_id() -> str:
    acct = os.getenv("FIREWORKS_ACCOUNT_ID", "").strip()
    if not acct:
        raise FineTuneError(
            "FIREWORKS_ACCOUNT_ID is not set. Add it to your .env — you can find "
            "it in your Fireworks dashboard URL:\n"
            "  app.fireworks.ai/dashboard/<ACCOUNT_ID>/..."
        )
    return acct


def _client() -> httpx.Client:
    if not config.FIREWORKS_API_KEY:
        raise FineTuneError(
            "FIREWORKS_API_KEY is not set. Add it to your .env (the same key the "
            "app uses)."
        )
    return httpx.Client(
        base_url=API,
        headers={
            "Authorization": f"Bearer {config.FIREWORKS_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=300,
    )


def _base_model() -> str:
    """The model to fine-tune from — defaults to whatever the app runs (config.MODEL)."""
    return os.getenv("BASE_MODEL", config.MODEL).strip()


def _check_dataset(train: Path) -> int:
    if not train.exists():
        raise FineTuneError(
            f"{train.relative_to(ROOT)} not found — run "
            "`python finetune/build_finetune_data.py` first."
        )
    n = sum(1 for line in train.read_text(encoding="utf-8").splitlines() if line.strip())
    if n == 0:
        raise FineTuneError(f"{train.relative_to(ROOT)} is empty.")
    return n


def _example_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _dataset_state(client: httpx.Client, resource: str) -> str | None:
    """Return the dataset's state, or None if it does not exist yet."""
    r = client.get(f"/{resource}")
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise FineTuneError(f"could not read dataset ({r.status_code}): {r.text[:200]}")
    return str(r.json().get("state", "")).upper()


def upload_dataset(
    client: httpx.Client, account: str, path: Path, dataset_id: str, reupload: bool = False
) -> str:
    """Ensure the dataset exists and holds our JSONL, then return its resource name.

    Fireworks datasets are created empty (state UPLOADING) with the example
    count declared up front, then the file is uploaded (state -> READY). If the
    dataset already exists and is READY we reuse it unchanged unless `reupload`.
    """
    resource = f"accounts/{account}/datasets/{dataset_id}"
    state = _dataset_state(client, resource)

    if state == "READY" and not reupload:
        print(f"• dataset {dataset_id} already READY — reusing (use --reupload to replace)")
        return resource

    if state is None:
        count = _example_count(path)
        print(f"• creating dataset {dataset_id} ({count} examples) ...")
        r = client.post(
            f"/accounts/{account}/datasets",
            json={
                "datasetId": dataset_id,
                "dataset": {"exampleCount": str(count), "userUploaded": {}},
            },
        )
        if r.status_code not in (200, 201):
            raise FineTuneError(
                f"could not create dataset ({r.status_code}): {r.text[:300]}"
            )
    else:
        print(f"• dataset {dataset_id} exists (state {state}) — re-uploading file")

    print(f"• uploading {path.name} ...")
    with path.open("rb") as fh:
        up = client.post(
            f"/{resource}:upload",
            files={"file": (path.name, fh, "application/jsonl")},
            headers={"Authorization": f"Bearer {config.FIREWORKS_API_KEY}"},
        )
    if up.status_code not in (200, 201):
        raise FineTuneError(f"dataset upload failed ({up.status_code}): {up.text[:300]}")
    return resource


def create_job(
    client: httpx.Client,
    account: str,
    dataset_resource: str,
    base_model: str,
    epochs: int,
    output_model: str,
) -> dict:
    """Kick off the supervised fine-tuning job and return the created job object."""
    # Fireworks requires the fully-qualified resource name here.
    output_resource = (
        output_model
        if output_model.startswith("accounts/")
        else f"accounts/{account}/models/{output_model}"
    )
    body = {
        "baseModel": base_model,
        "dataset": dataset_resource,
        "outputModel": output_resource,
        "epochs": epochs,
    }
    print(f"• starting fine-tuning job (base: {base_model}, epochs: {epochs}) ...")
    r = client.post(f"/accounts/{account}/supervisedFineTuningJobs", json=body)
    if r.status_code not in (200, 201):
        raise FineTuneError(
            f"could not start fine-tuning job ({r.status_code}): {r.text[:400]}"
        )
    return r.json()


def _job_state(job: dict) -> str:
    # Fireworks reports states like "JOB_STATE_RUNNING" / "JOB_STATE_COMPLETED";
    # normalise to the bare word (RUNNING, COMPLETED, ...) for readable output.
    raw = str(job.get("state") or job.get("status") or "UNKNOWN").upper()
    return raw[len("JOB_STATE_"):] if raw.startswith("JOB_STATE_") else raw


def watch_job(client: httpx.Client, job_name: str) -> dict:
    """Poll the job until it reaches a terminal state, printing progress."""
    print(f"• watching {job_name} (every {POLL_SECONDS}s; Ctrl-C to stop watching)")
    last = None
    while True:
        r = client.get(f"/{job_name}")
        if r.status_code != 200:
            raise FineTuneError(f"could not read job ({r.status_code}): {r.text[:200]}")
        job = r.json()
        state = _job_state(job)
        if state != last:
            print(f"  state: {state}")
            last = state
        if state in DONE_STATES:
            return job
        time.sleep(POLL_SECONDS)


def main() -> None:
    ap = argparse.ArgumentParser(description="Fine-tune AegisMed's model on Fireworks AI.")
    ap.add_argument("--train", default=str(FT_DIR / "train.jsonl"),
                    help="training JSONL (default: finetune/train.jsonl)")
    ap.add_argument("--dataset-id", default="aegismed-synthesis",
                    help="Fireworks dataset id to create/reuse")
    ap.add_argument("--output-model", default="aegismed-gemma-tuned",
                    help="name for the resulting fine-tuned model")
    ap.add_argument("--epochs", type=int, default=1, help="training epochs (default: 1)")
    ap.add_argument("--reupload", action="store_true",
                    help="re-upload the training file even if the dataset already exists")
    ap.add_argument("--no-wait", action="store_true",
                    help="start the job and exit instead of watching it")
    ap.add_argument("--dry-run", action="store_true",
                    help="validate config and dataset, but make no API calls")
    args = ap.parse_args()

    train = Path(args.train)

    try:
        n = _check_dataset(train)
        base_model = _base_model()

        if args.dry_run:
            account = os.getenv("FIREWORKS_ACCOUNT_ID", "<FIREWORKS_ACCOUNT_ID>").strip()
            print("── Dry run — nothing was sent to Fireworks ──")
            print(f"training examples : {n}  ({train.relative_to(ROOT)})")
            print(f"base model        : {base_model}")
            print(f"output model      : accounts/{account}/models/{args.output_model}")
            print(f"epochs            : {args.epochs}")
            print("Remove --dry-run to actually launch the job.")
            return

        account = _account_id()
        with _client() as client:
            dataset_resource = upload_dataset(
                client, account, train, args.dataset_id, reupload=args.reupload
            )
            job = create_job(
                client, account, dataset_resource, base_model,
                args.epochs, args.output_model,
            )
            job_name = job.get("name") or job.get("id") or ""
            print(f"✓ job created: {job_name or '(unnamed)'}")

            if args.no_wait or not job_name:
                print("\nNot waiting (--no-wait). Check status later in the Fireworks "
                      "dashboard or re-run without --no-wait.")
                return

            final = watch_job(client, job_name)
            state = _job_state(final)
            if state == "COMPLETED":
                model = final.get("outputModel") or f"accounts/{account}/models/{args.output_model}"
                print("\n✓ Fine-tuning complete!")
                print(f"  Your tuned model: {model}")
                print("\nTo use it, set this in your .env and restart the app:")
                print(f"  MODEL={model}")
                print("Then re-run `python eval/run_eval.py` to measure the lift.")
            else:
                print(f"\n✗ Job ended in state {state}.")
                if final.get("statusMessage"):
                    print(f"  {final['statusMessage']}")
                sys.exit(1)

    except FineTuneError as err:
        sys.exit(f"Fine-tuning error: {err}")
    except httpx.HTTPError as err:
        sys.exit(f"Network error talking to Fireworks: {err}")
    except KeyboardInterrupt:
        sys.exit("\nStopped watching. The job keeps running on Fireworks; "
                 "check the dashboard for its status.")


if __name__ == "__main__":
    main()
