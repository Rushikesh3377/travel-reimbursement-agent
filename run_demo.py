"""
Runs the agent against all sample claims in data/claims.json and saves
results to outputs/ — this is what generates the 'sample outputs' deliverable
and what you'd narrate over in the demo video.

Usage:
    export GROQ_API_KEY=your_key_here
    python run_demo.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from app.agent import TravelReimbursementAgent

DATA_DIR = Path(__file__).parent / "data"
OUT_DIR = Path(__file__).parent / "outputs"
OUT_DIR.mkdir(exist_ok=True)


def main():
    with open(DATA_DIR / "claims.json") as f:
        claims = json.load(f)

    agent = TravelReimbursementAgent()
    all_results = []

    for claim in claims:
        print(f"\n{'='*70}\nEvaluating {claim['claim_id']} ({claim['category']}, ₹{claim['amount']})...")
        result = agent.evaluate_claim(claim)
        all_results.append({"claim": claim, **result})

        d = result["decision"]
        print(f"  Decision: {d['decision']}")
        print(f"  Approved: ₹{d['approved_amount']}  |  Deducted: ₹{d['deducted_amount']}")
        print(f"  Confidence: {d['confidence']}")
        print(f"  Tools used: {d['tools_used']}")
        print(f"  Explanation: {d['explanation']}")

    out_path = OUT_DIR / "sample_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'='*70}\nSaved {len(all_results)} results to {out_path}")


if __name__ == "__main__":
    main()
