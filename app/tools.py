"""
Tool functions available to the LLM agent.
Each tool is a pure Python function, independently testable, with no LLM
dependency. The LLM only decides WHEN and WHICH tools to call; the tools
themselves are deterministic so results are trustworthy and auditable.
"""
import json
import re
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher

DATA_DIR = Path(__file__).parent.parent / "data"

with open(DATA_DIR / "policy.md", encoding="utf-8") as f:
    POLICY_TEXT = f.read()

with open(DATA_DIR / "limits.json", encoding="utf-8") as f:
    LIMITS = json.load(f)

with open(DATA_DIR / "claim_history.json", encoding="utf-8") as f:
    CLAIM_HISTORY = json.load(f)

# Split policy into sections for lightweight retrieval (no vector DB needed
# for a document this size — keyword/section matching is the right-sized
# tool here; swapping in embeddings later is a drop-in change, noted in README).
_SECTION_PATTERN = re.compile(r"^## (Section \d+: .+)$", re.MULTILINE)


def _split_policy_sections():
    matches = list(_SECTION_PATTERN.finditer(POLICY_TEXT))
    sections = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(POLICY_TEXT)
        sections.append({"title": m.group(1), "text": POLICY_TEXT[start:end].strip()})
    return sections


POLICY_SECTIONS = _split_policy_sections()


def policy_lookup(query: str) -> dict:
    """
    Retrieve the most relevant policy section(s) for a free-text query
    (e.g. category name, 'duplicate', 'receipt requirements').
    Simple relevance scoring via substring + sequence similarity —
    sufficient for a single-page mock policy; would upgrade to embedding
    similarity for a larger real policy corpus.
    """
    query_l = query.lower()
    scored = []
    for sec in POLICY_SECTIONS:
        text_l = sec["text"].lower()
        score = 0.0
        if query_l in text_l:
            score += 2.0
        score += SequenceMatcher(None, query_l, sec["title"].lower()).ratio()
        scored.append((score, sec))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for score, s in scored[:2] if score > 0.15]
    if not top:
        top = [scored[0][1]]
    return {
        "query": query,
        "matched_sections": [s["title"] for s in top],
        "context": "\n\n".join(s["text"] for s in top),
    }


def limit_checker(category: str, amount: float, city: str) -> dict:
    """
    Check a claimed amount against the policy limit table for the
    claim's category and city tier. Returns whether it's within limit
    and the excess amount if not.
    """
    tier = None
    for tier_name, cities in LIMITS["city_tiers"].items():
        if city in cities:
            tier = tier_name
            break
    if tier is None:
        tier = "Tier3"  # conservative default for unknown cities

    cat_limits = LIMITS["limits"].get(category)
    if cat_limits is None:
        return {
            "category": category,
            "found": False,
            "reason": f"No limit table entry for category '{category}'",
        }

    limit = cat_limits.get(tier)
    within_limit = amount <= limit
    excess = max(0, amount - limit)

    return {
        "category": category,
        "city": city,
        "city_tier": tier,
        "limit": limit,
        "claimed_amount": amount,
        "within_limit": within_limit,
        "excess_amount": excess,
        "global_manual_review_threshold": LIMITS["global_manual_review_threshold"],
        "exceeds_global_manual_review_threshold": amount > LIMITS["global_manual_review_threshold"],
    }


def receipt_validator(amount: float, receipt_attached: bool, receipt_date: str | None,
                       claim_date: str, submitted_date: str) -> dict:
    """
    Validate receipt presence/requirement and check date consistency
    and submission window per policy.
    """
    issues = []
    receipt_required = amount > LIMITS["receipt_required_above"]

    if receipt_required and not receipt_attached:
        issues.append("Receipt required but not attached")

    date_mismatch = False
    if receipt_attached and receipt_date:
        try:
            d1 = datetime.fromisoformat(claim_date)
            d2 = datetime.fromisoformat(receipt_date)
            if abs((d1 - d2).days) > 1:
                date_mismatch = True
                issues.append(f"Receipt date {receipt_date} differs from claim date {claim_date} by more than 1 day")
        except ValueError:
            issues.append("Could not parse claim_date or receipt_date")

    late_submission = False
    try:
        d_claim = datetime.fromisoformat(claim_date)
        d_sub = datetime.fromisoformat(submitted_date)
        days_to_submit = (d_sub - d_claim).days
        if days_to_submit > 30:
            late_submission = True
            issues.append(f"Submitted {days_to_submit} days after expense date (>30 day policy window)")
    except ValueError:
        issues.append("Could not parse submitted_date")

    return {
        "receipt_required": receipt_required,
        "receipt_attached": receipt_attached,
        "date_mismatch": date_mismatch,
        "late_submission": late_submission,
        "issues": issues,
        "passed": len(issues) == 0,
    }


def duplicate_detector(employee_id: str, amount: float, vendor: str, date: str, claim_id: str | None = None) -> dict:
    """
    Check the claim against historical claims for likely duplicates:
    same employee, similar amount (+/-1%), same/similar vendor, date
    within 2 days. Excludes the claim's own claim_id from matches so a
    claim already present in history doesn't flag itself as a duplicate.
    """
    try:
        claim_date = datetime.fromisoformat(date)
    except ValueError:
        return {"checked": False, "reason": "invalid date format", "is_likely_duplicate": False}

    matches = []
    for hist in CLAIM_HISTORY:
        if hist["employee_id"] != employee_id:
            continue
        if claim_id is not None and hist.get("claim_id") == claim_id:
            continue
        try: hist_date = datetime.fromisoformat(hist["date"])
        except ValueError:
            continue
        date_close = abs((claim_date - hist_date).days) <= 2
        amount_close = abs(hist["amount"] - amount) <= 0.01 * max(hist["amount"], amount)
        vendor_sim = SequenceMatcher(None, vendor.lower(), hist["vendor"].lower()).ratio() > 0.8
        if date_close and amount_close and vendor_sim:
            matches.append(hist)

    return {
        "is_likely_duplicate": len(matches) > 0,
        "matched_claims": [m["claim_id"] for m in matches],
        "checked_against_history_size": len(CLAIM_HISTORY),
    }


# Tool schema definitions for LLM function calling (Groq/OpenAI-style)
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "policy_lookup",
            "description": "Retrieve relevant travel reimbursement policy text for a category or topic (e.g. 'Meals', 'Lodging', 'duplicate', 'receipt requirements'). Use this before deciding on any claim to ground the decision in actual policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or category to search policy for"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "limit_checker",
            "description": "Check a claimed amount against the policy limit table for its category and city. Returns whether within limit, and excess amount if over.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "amount": {"type": "number"},
                    "city": {"type": "string"},
                },
                "required": ["category", "amount", "city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "receipt_validator",
            "description": "Validate whether a claim has the required receipt, whether receipt date matches claim date, and whether it was submitted within the policy window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "receipt_attached": {"type": "boolean"},
                    "receipt_date": {"type": ["string", "null"]},
                    "claim_date": {"type": "string"},
                    "submitted_date": {"type": "string"},
                },
                "required": ["amount", "receipt_attached", "claim_date", "submitted_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "duplicate_detector",
            "description": "Check if a claim is a likely duplicate of a previously submitted/approved claim by the same employee.",
            "parameters": {
                "type": "object",
                "properties": {
                    "employee_id": {"type": "string"},
                    "amount": {"type": "number"},
                    "vendor": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["employee_id", "amount", "vendor", "date"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "policy_lookup": policy_lookup,
    "limit_checker": limit_checker,
    "receipt_validator": receipt_validator,
    "duplicate_detector": duplicate_detector,
}
