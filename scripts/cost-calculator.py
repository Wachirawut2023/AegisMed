#!/usr/bin/env python3
"""
AegisMed Deployment Cost Calculator

Calculate total cost of ownership for each deployment option based on:
- Expected diagnosis volume
- Geographic region
- Reserved vs on-demand pricing
"""

import sys
from typing import Tuple

# Pricing (as of 2024)
PRICING = {
    "option_a": {
        "name": "Fireworks API (CPU Droplet)",
        "droplet": 12,  # DigitalOcean basic, /month
        "api_per_diagnosis": 0.003,  # Gemma-3-27B on Fireworks, ~$0.001-0.005
        "storage": 5,  # /month for basic storage
    },
    "option_b": {
        "name": "AMD Developer Cloud (GPU + Fireworks)",
        "gpu_instance": 500,  # MI210 or MI250, /month (sustained)
        "api_per_diagnosis": 0.003,  # Still using Fireworks
        "bandwidth": 50,  # /month estimate
    },
    "option_c": {
        "name": "Self-Hosted Gemma (vLLM + ROCm)",
        "gpu_instance": 500,  # MI210+ GPU, /month
        "power_cooling": 100,  # Estimated power & cooling overhead
        "storage": 50,  # Large NVMe for model & results
        "admin_time": 200,  # Estimated monthly maintenance/monitoring
    },
}

def format_money(amount: float) -> str:
    """Format number as USD."""
    return f"${amount:,.2f}"

def calculate_option_a(diagnoses_per_month: int) -> Tuple[float, dict]:
    """Calculate Option A costs."""
    p = PRICING["option_a"]
    monthly_cost = p["droplet"] + p["storage"] + (diagnoses_per_month * p["api_per_diagnosis"])
    return monthly_cost, {
        "Droplet (DigitalOcean)": p["droplet"],
        "API calls": diagnoses_per_month * p["api_per_diagnosis"],
        "Storage": p["storage"],
    }

def calculate_option_b(diagnoses_per_month: int) -> Tuple[float, dict]:
    """Calculate Option B costs."""
    p = PRICING["option_b"]
    monthly_cost = p["gpu_instance"] + p["bandwidth"] + (diagnoses_per_month * p["api_per_diagnosis"])
    return monthly_cost, {
        "GPU Instance (AMD MI210)": p["gpu_instance"],
        "API calls": diagnoses_per_month * p["api_per_diagnosis"],
        "Bandwidth": p["bandwidth"],
    }

def calculate_option_c(diagnoses_per_month: int) -> Tuple[float, dict]:
    """Calculate Option C costs."""
    p = PRICING["option_c"]
    monthly_cost = p["gpu_instance"] + p["power_cooling"] + p["storage"] + p["admin_time"]
    # Note: Option C has NO per-diagnosis costs
    return monthly_cost, {
        "GPU Instance": p["gpu_instance"],
        "Power/Cooling": p["power_cooling"],
        "Storage": p["storage"],
        "Admin/Monitoring": p["admin_time"],
    }

def find_breakeven(option_a_base: float, option_c_base: float, cost_per_diagnosis: float) -> float:
    """Find breakeven point where Option C becomes cheaper."""
    if cost_per_diagnosis <= 0:
        return float('inf')
    return (option_c_base - option_a_base) / cost_per_diagnosis

def main():
    print("=" * 70)
    print("🧮 AegisMed Deployment Cost Calculator")
    print("=" * 70)
    print()

    # Get monthly diagnosis volume
    if len(sys.argv) > 1:
        try:
            diagnoses = int(sys.argv[1])
        except ValueError:
            diagnoses = 1000
    else:
        print("Enter expected diagnoses per month (or press Enter for 1000):")
        try:
            input_val = input().strip()
            diagnoses = int(input_val) if input_val else 1000
        except (ValueError, EOFError):
            diagnoses = 1000

    print()
    print(f"📊 Analysis for {diagnoses:,} diagnoses/month")
    print()
    print("-" * 70)

    # Calculate costs
    cost_a, breakdown_a = calculate_option_a(diagnoses)
    cost_b, breakdown_b = calculate_option_b(diagnoses)
    cost_c, breakdown_c = calculate_option_c(diagnoses)

    # Display results
    options = [
        ("Option A", cost_a, breakdown_a, "Fireworks API (cheapest for low volume)"),
        ("Option B", cost_b, breakdown_b, "AMD GPU + Fireworks (balanced)"),
        ("Option C", cost_c, breakdown_c, "Self-Hosted vLLM (best for high volume)"),
    ]

    for name, cost, breakdown, description in options:
        print()
        print(f"📌 {name}: {description}")
        print(f"   Total: {format_money(cost)}/month")
        print()
        for item, value in breakdown.items():
            print(f"      {item:.<40} {format_money(value):>12}")

    # Find breakeven points
    print()
    print("-" * 70)
    print("📈 Cost Comparison & Breakeven Analysis")
    print()

    # A vs B breakeven (when API costs exceed GPU cost difference)
    be_a_to_b = find_breakeven(
        PRICING["option_a"]["droplet"] + PRICING["option_a"]["storage"],
        PRICING["option_b"]["gpu_instance"],
        PRICING["option_b"]["api_per_diagnosis"] - PRICING["option_a"]["api_per_diagnosis"],
    )
    # For A vs B, the API cost is the same, so focus is on droplet vs GPU
    be_a_to_b = (PRICING["option_b"]["gpu_instance"] - PRICING["option_a"]["droplet"] - PRICING["option_a"]["storage"]) / PRICING["option_a"]["api_per_diagnosis"]

    # A vs C breakeven
    api_cost_a = PRICING["option_a"]["droplet"] + PRICING["option_a"]["storage"]
    be_a_to_c = find_breakeven(
        api_cost_a,
        PRICING["option_c"]["gpu_instance"] + PRICING["option_c"]["power_cooling"] +
        PRICING["option_c"]["storage"] + PRICING["option_c"]["admin_time"],
        PRICING["option_a"]["api_per_diagnosis"],
    )

    # B vs C breakeven
    api_cost_b = PRICING["option_b"]["gpu_instance"] + PRICING["option_b"]["bandwidth"]
    be_b_to_c = find_breakeven(
        api_cost_b,
        PRICING["option_c"]["gpu_instance"] + PRICING["option_c"]["power_cooling"] +
        PRICING["option_c"]["storage"] + PRICING["option_c"]["admin_time"],
        PRICING["option_b"]["api_per_diagnosis"],
    )

    if be_a_to_c > 0:
        print(f"🔄 Option A ↔ Option C breakeven: {be_a_to_c:,.0f} diagnoses/month")
        print(f"   At that volume, both cost ≈ {format_money(max(cost_a, cost_c))}/month")
        print()

    if be_b_to_c > 0:
        print(f"🔄 Option B ↔ Option C breakeven: {be_b_to_c:,.0f} diagnoses/month")
        print()

    # Recommendation
    print("-" * 70)
    print("💡 Recommendation:")
    print()

    min_cost = min(cost_a, cost_b, cost_c)

    if min_cost == cost_a:
        print(f"   ✅ Use Option A (Fireworks API)")
        print(f"      Cost: {format_money(cost_a)}/month")
        print(f"      Best for: <{int(be_a_to_c):,} diagnoses/month")
        print()
        print(f"   Upgrade to Option C when volume reaches ~{int(be_a_to_c):,} diagnoses/month")
    elif min_cost == cost_b:
        print(f"   ✅ Use Option B (AMD GPU + Fireworks)")
        print(f"      Cost: {format_money(cost_b)}/month")
        print(f"      Best for: {int(be_a_to_c):,}-{int(be_b_to_c):,} diagnoses/month")
    else:
        print(f"   ✅ Use Option C (Self-Hosted vLLM)")
        print(f"      Cost: {format_money(cost_c)}/month")
        print(f"      Best for: >{int(be_a_to_c):,} diagnoses/month")
        print(f"      Benefit: Unlimited diagnoses, no API costs, full privacy")

    print()
    print("-" * 70)
    print()

    # Cost per diagnosis
    print("💰 Cost Per Diagnosis:")
    print(f"   Option A: {format_money(cost_a / max(1, diagnoses))}")
    print(f"   Option B: {format_money(cost_b / max(1, diagnoses))}")
    print(f"   Option C: {format_money(cost_c / max(1, diagnoses))}")
    print()

    # Annual costs
    print("📅 Annual Costs:")
    print(f"   Option A: {format_money(cost_a * 12)}")
    print(f"   Option B: {format_money(cost_b * 12)}")
    print(f"   Option C: {format_money(cost_c * 12)}")
    print()

if __name__ == "__main__":
    main()
