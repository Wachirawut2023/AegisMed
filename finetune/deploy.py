"""Spin up (and tear down) a dedicated Fireworks deployment for A/B testing.

WHY THIS EXISTS (plain language)
--------------------------------
The base model `gemma-3-27b-it` is NOT served on Fireworks' free "serverless"
tier, and a fine-tuned LoRA adapter is never serverless on its own. So every
inference call 404s until the model is actually hosted somewhere. This script
rents a GPU (an on-demand deployment), loads the base model onto it, and loads
your tuned LoRA adapter onto the *same* GPU ("Multi-LoRA"). Now both the base
model and the tuned model answer requests — on identical hardware — which is
exactly what a fair A/B test needs.

This spends Fireworks credit for as long as the GPU is up, so always run the
`down` command when you are finished (the A/B script does this automatically).

USAGE
-----
  python finetune/deploy.py up      # rent H100, load base + LoRA, write eval/ab_models.json
  python finetune/deploy.py down     # release the GPU (stop the credit meter)
  python finetune/deploy.py status   # show the current deployment, if any

WHAT YOU NEED FIRST
-------------------
  1. FIREWORKS_API_KEY in .env (same key the app uses).
  2. FIREWORKS_ACCOUNT_ID in .env (e.g. wachirawut2002-fqt88).
  3. A finished tuned model (run finetune/run_finetune.py first).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Make the aegismed package importable when run as `python finetune/...`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aegismed import config  # noqa: E402

# The tuned LoRA adapter produced by finetune/run_finetune.py.
TUNED_MODEL = "accounts/{account}/models/aegismed-gemma-tuned"
# The base model the adapter was trained on.
BASE_MODEL = "accounts/fireworks/models/gemma-3-27b-it"

# One 80GB H100 comfortably holds the ~28B base weights plus the small adapter.
ACCELERATOR = "NVIDIA_H100_80GB"

# Name for the underlying base-model deployment the SDK creates. "on-demand-lora"
# requires this id; the SDK creates a deployment with this name if it doesn't
# already exist, then loads the LoRA addon onto it.
BASE_DEPLOYMENT_ID = "aegismed-ab-base"

INFERENCE_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
CONTROL_PLANE = "https://api.fireworks.ai/v1"

# Where we record the resolved model ids for the A/B harness, and the
# deployment name so `down` can find it again.
AB_MODELS_FILE = ROOT / "eval" / "ab_models.json"


class DeployError(Exception):
    """Any problem creating or tearing down the deployment."""


def _account_id() -> str:
    acct = os.getenv("FIREWORKS_ACCOUNT_ID", "").strip()
    if not acct:
        raise DeployError(
            "FIREWORKS_ACCOUNT_ID is not set. Add it to your .env — find it in "
            "your Fireworks dashboard URL: app.fireworks.ai/dashboard/<ACCOUNT_ID>/..."
        )
    return acct


def _require_key() -> str:
    if not config.FIREWORKS_API_KEY:
        raise DeployError(
            "FIREWORKS_API_KEY is not set. Add it to your .env (the same key the app uses)."
        )
    return config.FIREWORKS_API_KEY


def _lora_llm(account: str):
    """SDK handle for the tuned adapter as an on-demand LoRA deployment.

    Passing the *adapter* as the model with deployment_type="on-demand-lora" tells
    the SDK to provision the base model (auto-detected from the adapter's PEFT
    metadata) on a GPU under `base_id`, then load the adapter onto that same
    deployment — this is what makes it a true Multi-LoRA (base + tuned, same host).
    `apply()`/`delete_deployment()` on *this* handle only manage the LoRA addon
    layer, not the underlying GPU deployment — see `_base_llm` for that.
    """
    from fireworks import LLM  # imported lazily so `status`/errors stay fast

    return LLM(
        model=TUNED_MODEL.format(account=account),
        deployment_type="on-demand-lora",
        base_id=BASE_DEPLOYMENT_ID,
        accelerator_type=ACCELERATOR,
        enable_addons=True,
        api_key=config.FIREWORKS_API_KEY,
    )


def _base_llm(account: str):
    """SDK handle for the underlying base-model GPU deployment itself.

    Same `id` as `base_id` above, so this addresses the identical deployment.
    Needed because `scale_to_zero`/`delete_deployment` on the LoRA handle only
    touch the addon — deleting the actual GPU deployment (what stops billing)
    requires a handle with deployment_type="on-demand" for the base model.
    """
    from fireworks import LLM

    return LLM(
        model=BASE_MODEL,
        deployment_type="on-demand",
        id=BASE_DEPLOYMENT_ID,
        accelerator_type=ACCELERATOR,
        enable_addons=True,
        api_key=config.FIREWORKS_API_KEY,
    )


def _smoke_test(model_id: str) -> tuple[bool, str]:
    """Send one tiny chat request. Returns (ok, detail)."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
        "max_tokens": 8,
        "temperature": 0.0,
    }
    headers = {
        "Authorization": f"Bearer {config.FIREWORKS_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        r = httpx.post(INFERENCE_URL, json=payload, headers=headers, timeout=120)
    except httpx.HTTPError as err:
        return False, f"request failed: {err}"
    if r.status_code != 200:
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    try:
        content = r.json()["choices"][0]["message"]["content"].strip()
    except Exception as err:  # noqa: BLE001
        return False, f"unexpected response shape: {err}"
    return bool(content), content or "(empty)"


def _first_working(candidates: list[str], label: str) -> str:
    """Try each candidate model id against the live endpoint; return the first that answers."""
    print(f"\n  Resolving working '{label}' model id:")
    for cid in candidates:
        ok, detail = _smoke_test(cid)
        mark = "✓" if ok else "✗"
        print(f"    {mark} {cid}\n        -> {detail}")
        if ok:
            return cid
    raise DeployError(
        f"None of the candidate ids for '{label}' answered. The deployment may still "
        f"be warming up, or the adapter is not loaded. Candidates tried:\n  "
        + "\n  ".join(candidates)
    )


def cmd_up() -> None:
    account = _account_id()
    _require_key()

    tuned = TUNED_MODEL.format(account=account)
    print("Provisioning a dedicated on-demand deployment (this spends credit)…")
    print(f"  base model : {BASE_MODEL}")
    print(f"  adapter    : {tuned}")
    print(f"  accelerator: {ACCELERATOR}")
    print("  This can take several minutes while the GPU warms up.\n")

    # Create the base GPU deployment explicitly first, with accelerator_type set.
    # (The SDK's on-demand-lora path creates this internally too, but its internal
    # call omits accelerator_type and fails with "accelerator_type must be
    # specified" — creating it ourselves first means the LoRA step below finds an
    # existing, already-READY deployment and just reuses it.)
    print("  Step A: creating base deployment…")
    _base_llm(account).apply(wait=True)

    print("  Step B: loading tuned LoRA adapter onto it…")
    _lora_llm(account).apply(wait=True)

    # Deterministic — we chose BASE_DEPLOYMENT_ID ourselves, no need to introspect protos.
    dep_name = f"accounts/{account}/deployments/{BASE_DEPLOYMENT_ID}"
    print(f"\nDeployment ready: {dep_name}")

    # Resolve the exact `model` strings the raw inference endpoint accepts.
    # A dedicated deployment is addressed by suffixing the model with #<deployment>.
    base_id = _first_working(
        [f"{BASE_MODEL}#{dep_name}", BASE_MODEL],
        "base",
    )
    tuned_id = _first_working(
        [tuned, f"{tuned}#{dep_name}"],
        "tuned",
    )

    AB_MODELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    AB_MODELS_FILE.write_text(
        json.dumps(
            {
                "gemma3_base": base_id,
                "gemma3_tuned": tuned_id,
                "_deployment": dep_name,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n✓ Wrote {AB_MODELS_FILE.relative_to(ROOT)}")
    print(f"    gemma3_base  = {base_id}")
    print(f"    gemma3_tuned = {tuned_id}")
    print("\nReady for A/B testing. Remember to run `python finetune/deploy.py down` when done.")


def cmd_down() -> None:
    account = _account_id()
    _require_key()

    dep_name = f"accounts/{account}/deployments/{BASE_DEPLOYMENT_ID}"

    # Layer 1: unload the LoRA addon (harmless if already gone / never loaded).
    try:
        _lora_llm(account).delete_deployment(wait=True)
        print("✓ LoRA addon unloaded.")
    except Exception as err:  # noqa: BLE001
        print(f"(LoRA unload skipped: {err})")

    # Layer 2: delete the base GPU deployment itself — this is what actually stops billing.
    base_deleted = False
    try:
        _base_llm(account).delete_deployment(wait=True)
        base_deleted = True
        print(f"✓ Base deployment {dep_name} deleted via SDK — the credit meter has stopped.")
    except Exception as err:  # noqa: BLE001
        print(f"SDK base-deployment teardown did not complete ({err}).")

    # Fallback: delete the deployment directly via REST.
    if not base_deleted:
        headers = {"Authorization": f"Bearer {config.FIREWORKS_API_KEY}"}
        r = httpx.delete(f"{CONTROL_PLANE}/{dep_name}", headers=headers, timeout=120)
        if r.status_code in (200, 204, 404):
            print(f"✓ Base deployment {dep_name} deleted via REST — the credit meter has stopped.")
            base_deleted = True
        else:
            print(f"✗ REST delete returned HTTP {r.status_code}: {r.text[:200]}")

    if not base_deleted:
        print(
            "\n⚠ Could not confirm teardown automatically. Check the Fireworks dashboard "
            "(Deployments) and delete any running deployment to stop credit usage."
        )

    if AB_MODELS_FILE.exists():
        AB_MODELS_FILE.unlink()
        print(f"✓ Removed {AB_MODELS_FILE.relative_to(ROOT)}")


def cmd_status() -> None:
    account = _account_id()
    _require_key()
    headers = {"Authorization": f"Bearer {config.FIREWORKS_API_KEY}"}
    r = httpx.get(f"{CONTROL_PLANE}/accounts/{account}/deployments", headers=headers, timeout=60)
    if r.status_code != 200:
        print(f"Could not list deployments (HTTP {r.status_code}): {r.text[:200]}")
        return
    deployments = r.json().get("deployments", [])
    if not deployments:
        print("No active deployments — you are not being charged for a GPU.")
        return
    print(f"{len(deployments)} deployment(s):")
    for d in deployments:
        print(f"  {d.get('name')}  state={d.get('state')}  model={d.get('baseModel', d.get('model',''))}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Manage the A/B testing deployment on Fireworks.")
    ap.add_argument("command", choices=["up", "down", "status"], help="what to do")
    args = ap.parse_args()

    try:
        {"up": cmd_up, "down": cmd_down, "status": cmd_status}[args.command]()
    except DeployError as err:
        sys.exit(f"\nError: {err}")


if __name__ == "__main__":
    main()
