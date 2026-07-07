"""
FastAPI entrypoint.
Run with: uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.agent import TravelReimbursementAgent

app = FastAPI(title="Travel Reimbursement Approval Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = TravelReimbursementAgent()


class ClaimInput(BaseModel):
    claim_id: str
    employee_id: str
    employee_name: str
    category: str
    city: str
    date: str
    amount: float
    vendor: str
    description: str
    receipt_attached: bool
    receipt_date: str | None = None
    submitted_date: str


@app.get("/")
def root():
    return {"status": "ok", "service": "travel-reimbursement-approval-agent"}


@app.post("/evaluate-claim")
def evaluate_claim(claim: ClaimInput):
    try:
        result = agent.evaluate_claim(claim.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
