"""
Travel Reimbursement Approval Agent - Core orchestration.

This project uses a direct LLM function-calling loop with Groq's
OpenAI-compatible API instead of a larger orchestration framework.
For a single-agent, single-turn workflow, this approach keeps the
architecture lightweight, transparent, and easier to debug.

The LLM is responsible for reasoning and tool selection, while
critical business rules are enforced in application logic. Claims
that exceed approval thresholds, have low confidence, or are flagged
as duplicates are automatically routed to Manual Review. This hybrid
approach combines the flexibility of LLM reasoning with deterministic
business rule enforcement.
"""
import json
import os
from dotenv import load_dotenv
from groq import Groq
from app.tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS, LIMITS
from app.schema import ClaimDecision

load_dotenv()
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are a Travel Reimbursement Approval Agent for a corporate travel & expense policy.

You evaluate ONE reimbursement claim at a time. You have access to tools:
- policy_lookup: retrieve relevant policy text (ALWAYS call this first for the claim's category)
- limit_checker: check claimed amount against category/city limits
- receipt_validator: check receipt presence, date match, submission window
- duplicate_detector: check for likely duplicate submissions

Process:
1. Call policy_lookup for the claim's category to ground your reasoning in actual policy text.
2. Call limit_checker, receipt_validator, and duplicate_detector as relevant to the claim.
3. Combine the tool results to decide: Approved, Partially Approved, Rejected, or Manual Review.
4. If anything is ambiguous, conflicting, a likely duplicate, missing required documents in a
   borderline way, or you are not confident — choose Manual Review. Do NOT force a confident
   decision on uncertain cases.

After you have called the tools you need, respond ONLY with a single JSON object (no markdown
fences, no prose) matching exactly this shape:
{
  "claim_id": "<string>",
  "decision": "Approved" | "Partially Approved" | "Rejected" | "Manual Review",
  "approved_amount": <number>,
  "deducted_amount": <number>,
  "missing_documents": [<string>, ...],
  "policy_reference": "<which policy section(s) this decision is based on>",
  "confidence": <number 0.0-1.0>,
  "explanation": "<2-3 sentence plain-language reasoning>",
  "tools_used": [<string>, ...]
}
"""


class TravelReimbursementAgent:
    def __init__(self, api_key: str | None = None):
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))
        self.audit_log = []

    def evaluate_claim(self, claim: dict) -> dict:
        """
        Runs the full agentic loop for a single claim. Returns a dict with
        the validated ClaimDecision plus an audit trail of tool calls.
        """
        self.audit_log = []
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Evaluate this claim:\n{json.dumps(claim, indent=2)}"},
        ]

        tools_used = []
        max_turns = 6
        final_raw = None

        for turn in range(max_turns):
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.1,
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                })
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    if fn_name == "duplicate_detector":
                        args["claim_id"] = claim.get("claim_id")
                    fn = TOOL_FUNCTIONS.get(fn_name)
                    result = fn(**args) if fn else {"error": f"unknown tool {fn_name}"}
                    tools_used.append(fn_name)
                    self.audit_log.append({"tool": fn_name, "args": args, "result": result})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": json.dumps(result),
                    })
                continue
            else:
                final_raw = msg.content
                break

        decision_dict = self._parse_decision(final_raw, claim, tools_used)
        decision_dict = self._apply_safety_overrides(decision_dict, claim)

        validated = ClaimDecision(**decision_dict)
        return {
            "decision": validated.model_dump(),
            "audit_trail": self.audit_log,
        }

    def _parse_decision(self, raw: str | None, claim: dict, tools_used: list) -> dict:
        if not raw:
            return self._fallback_manual_review(claim, tools_used, "LLM returned no content")
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        try:
            parsed = json.loads(cleaned)
            parsed.setdefault("tools_used", tools_used)
            parsed.setdefault("claim_id", claim.get("claim_id", "UNKNOWN"))
            return parsed
        except json.JSONDecodeError:
            return self._fallback_manual_review(claim, tools_used, "Could not parse LLM output as JSON")

    def _fallback_manual_review(self, claim: dict, tools_used: list, reason: str) -> dict:
        return {
            "claim_id": claim.get("claim_id", "UNKNOWN"),
            "decision": "Manual Review",
            "approved_amount": 0,
            "deducted_amount": 0,
            "missing_documents": [],
            "policy_reference": "N/A — system fallback",
            "confidence": 0.0,
            "explanation": f"Routed to Manual Review automatically: {reason}.",
            "tools_used": tools_used,
        }

    def _apply_safety_overrides(self, decision: dict, claim: dict) -> dict:
        """
        Code-enforced guardrails. The LLM's proposed decision is overridden
        to Manual Review if it violates a hard rule, regardless of what the
        LLM claims. This is what makes 'manual review handling' reliable
        rather than aspirational.
        """
        reasons = []

        amount = claim.get("amount", 0)
        if amount > LIMITS["global_manual_review_threshold"] and decision["decision"] != "Manual Review":
            reasons.append(f"Amount ₹{amount} exceeds global manual-review threshold of ₹{LIMITS['global_manual_review_threshold']}")

        confidence = decision.get("confidence", 0)
        if confidence < 0.6 and decision["decision"] != "Manual Review":
            reasons.append(f"LLM self-reported confidence ({confidence}) below 0.6 threshold")

        for entry in self.audit_log:
            if entry["tool"] == "duplicate_detector" and entry["result"].get("is_likely_duplicate"):
                if decision["decision"] != "Manual Review":
                    reasons.append("duplicate_detector flagged this as a likely duplicate claim")

        if reasons:
            decision["decision"] = "Manual Review"
            decision["explanation"] = (
                decision.get("explanation", "").strip().rstrip(".")
                + f". [System override → Manual Review: {'; '.join(reasons)}]"
            )

        return decision
