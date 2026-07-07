# Travel Reimbursement Approval Agent

A personal project exploring agentic GenAI design — an agent that reads a travel reimbursement claim, checks it against policy and limits using real tools, and returns a decision: Approved, Partially Approved, Rejected, or Manual Review.

---

## 1. Quick Start

```bash
# 1. Clone/unzip and enter the project
cd travel-reimbursement-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your free Groq API key (https://console.groq.com/keys)
cp .env.example .env
# edit .env and paste your key, then:
export GROQ_API_KEY=your_key_here

# 4. Run the unit tests for the deterministic tool layer (no API key needed)
python -m pytest tests/test_tools.py -v

# 5. Run the batch demo — evaluates all 5 sample claims end-to-end
python run_demo.py
# results saved to outputs/sample_results.json

# 6. (Optional) Run the API + simple UI
uvicorn app.main:app --reload --port 8000
# then open frontend.html in a browser (serve it via `python -m http.server`
# from the project root so it can load data/claims.json, e.g.:
python -m http.server 5500
# then visit http://localhost:5500/frontend.html
```

No paid services are required — Groq's free tier is used for the LLM, and
all "RAG" context grounding is done against a local markdown file (no vector
DB / no paid embeddings needed for a policy doc this size).

---

## 2. Architecture

```
Claim (JSON) ──> Agent (LLM + tool-calling loop)
                     │
                     ├── policy_lookup        (context grounding)
                     ├── limit_checker        (per-diem / category limits)
                     ├── receipt_validator    (missing docs, date mismatch, late submission)
                     └── duplicate_detector   (claim history match)
                     │
                     ▼
            LLM proposes: decision + amounts + confidence + explanation
                     │
                     ▼
       Code-enforced safety overrides (cannot be talked around by the LLM):
         - amount > ₹25,000  → forced Manual Review
         - confidence < 0.6  → forced Manual Review
         - duplicate flagged → forced Manual Review
                     │
                     ▼
         Pydantic-validated structured JSON output + audit trail
```

### Why a direct tool-calling loop instead of LangChain/CrewAI/AutoGen?

This is a single-agent, single-turn-per-claim workflow — there's no need for
multi-agent orchestration, memory chains, or a planning framework. A
transparent function-calling loop against Groq's OpenAI-compatible API is:
- Easier to **audit** (every tool call and result is logged, see `audit_trail`)
- Easier to **debug and explain** in an interview
- Fewer moving parts that could fail or behave unpredictably

This was a deliberate trade-off in line with the assignment's call to remove
"avoidable over-engineering." A framework would be justified if this grew
into a multi-agent system (e.g., a separate agent negotiating with a finance
system), but isn't needed here.

### Why is policy grounding not a vector database?

The mock policy is a single short markdown file. A section-based lookup
(`policy_lookup` in `app/tools.py`) gives accurate, citable context without
the overhead of embeddings/vector storage. For a real, much larger policy
corpus, the same function signature would just swap its internals for
embedding similarity search (e.g., `sentence-transformers` + FAISS) — the
rest of the agent is unaffected.

### Why are safety overrides code-enforced rather than trusted to the LLM?

LLMs can be confidently wrong. The assignment explicitly asks for reliability
("manual review for uncertain cases") — so the three hardest rules (global
amount threshold, low confidence, duplicate detection) are enforced in plain
Python after the LLM responds, not just instructed via the prompt. The LLM
can still recommend Manual Review on its own judgement for other ambiguous
cases (conflicting info, missing receipt context, suite upgrades needing
sign-off, etc.) — the overrides are a backstop, not a replacement for its
reasoning.

---

## 3. Sample Data

| File | Purpose |
|---|---|
| `data/policy.md` | Mock 8-section travel policy |
| `data/limits.json` | Per-diem/limit table by category and city tier |
| `data/claims.json` | 5 sample claims covering all 4 outcomes |
| `data/claim_history.json` | Prior claims used for duplicate detection |

Sample claims were deliberately designed to hit each decision bucket:

| Claim | Scenario | Expected outcome |
|---|---|---|
| CLM-1001 | Clean meal claim, within limit, receipt attached | Approved |
| CLM-1002 | Meal claim over per-diem limit, includes alcohol | Partially Approved |
| CLM-1003 | Lodging claim with no receipt, late submission | Rejected / Manual Review |
| CLM-1004 | Flight over ₹25,000 + unauthorized business-class upgrade | Manual Review (global threshold) |
| CLM-1005 | Near-identical resubmission of CLM-1002 | Manual Review (duplicate flagged) |

---

## 4. Structured Output Schema

Every decision is validated against a strict Pydantic schema
(`app/schema.py`) before being returned — invalid/incomplete LLM output
cannot pass through silently:

```json
{
  "claim_id": "CLM-1002",
  "decision": "Partially Approved",
  "approved_amount": 1800,
  "deducted_amount": 800,
  "missing_documents": [],
  "policy_reference": "Section 2: Per Diem & Meal Allowance",
  "confidence": 0.88,
  "explanation": "Claim exceeds the Tier1 meal per-diem limit and includes alcohol, which is never reimbursable; approved at the policy cap.",
  "tools_used": ["policy_lookup", "limit_checker", "receipt_validator"]
}
```

---

## 5. Assumptions & Limitations

**Assumptions**
- All claim data is mock/synthetic; no real employee or company information.
- A single LLM call per tool decision is sufficient (no retries/voting needed
  for this scope).
- City tiers are hardcoded into `limits.json` rather than looked up from an
  external HR system.

**Known limitations**
- Policy retrieval is section/keyword-based, not semantic embedding search —
  fine for one short policy doc, would need upgrading for a larger real
  policy corpus with more nuanced phrasing.
- Duplicate detection is a deterministic exact-ish match (employee + amount
  ±1% + vendor similarity + date proximity). It would miss more disguised
  duplicates (e.g., split into two smaller claims) — flagged as a "what I'd
  improve next."
- No persistent database — claim history is a static JSON file, not a live
  store of past decisions.
- No authentication/authorization layer (out of scope per assignment).

**What I'd improve with more time**
- Swap policy_lookup for embedding-based retrieval to scale to a full real
  policy handbook.
- Add a feedback loop where Manual Review human decisions are logged and
  used to refine prompt/tool logic over time.
- Add an evaluation harness that scores agent decisions against a larger
  labeled claim set automatically (precision/recall on each decision class).
- Add MCP-based tool exposure so the same tools could be reused by other
  internal agents (noted as optional in the assignment).

---

## 6. Project Structure

```
travel-reimbursement-agent/
├── app/
│   ├── agent.py        # Core agentic loop + safety overrides
│   ├── tools.py         # 4 deterministic tool functions + LLM tool schemas
│   ├── schema.py         # Pydantic output schema
│   └── main.py            # FastAPI endpoint
├── data/
│   ├── policy.md
│   ├── limits.json
│   ├── claims.json
│   └── claim_history.json
├── tests/
│   └── test_tools.py     # Unit tests, no API key required
├── outputs/
│   └── sample_results.json   # generated by run_demo.py
├── frontend.html          # Minimal demo UI
├── run_demo.py             # Batch evaluator for all sample claims
├── requirements.txt
└── README.md
```
