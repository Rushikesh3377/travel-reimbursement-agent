"""
Unit tests for tool functions — these run with zero API key / zero LLM
calls, so they can be run in CI or by a reviewer instantly to verify the
deterministic logic underneath the agent is correct.

Run with: python -m pytest tests/test_tools.py -v
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tools import policy_lookup, limit_checker, receipt_validator, duplicate_detector


def test_policy_lookup_returns_relevant_section():
    result = policy_lookup("Meals")
    assert any("Meal" in s for s in result["matched_sections"])
    assert len(result["context"]) > 0


def test_limit_checker_within_limit():
    result = limit_checker("Meals", 1500, "Pune")
    assert result["within_limit"] is True
    assert result["excess_amount"] == 0
    assert result["city_tier"] == "Tier1"


def test_limit_checker_over_limit():
    result = limit_checker("Meals", 2600, "Pune")
    assert result["within_limit"] is False
    assert result["excess_amount"] == 800


def test_limit_checker_global_threshold():
    result = limit_checker("Flight", 27500, "Bengaluru")
    assert result["exceeds_global_manual_review_threshold"] is True


def test_receipt_validator_missing_receipt():
    result = receipt_validator(4100, False, None, "2026-06-05", "2026-06-20")
    assert result["passed"] is False
    assert "Receipt required but not attached" in result["issues"]


def test_receipt_validator_late_submission():
    result = receipt_validator(1500, True, "2026-06-12", "2026-06-12", "2026-08-01")
    assert result["late_submission"] is True


def test_receipt_validator_clean_claim():
    result = receipt_validator(1500, True, "2026-06-12", "2026-06-12", "2026-06-15")
    assert result["passed"] is True


def test_duplicate_detector_flags_known_duplicate():
    result = duplicate_detector("EMP-118", 2580, "Hotel Grand Court Restaurant", "2026-06-10")
    assert result["is_likely_duplicate"] is True
    assert "CLM-1002" in result["matched_claims"]


def test_duplicate_detector_no_false_positive():
    result = duplicate_detector("EMP-204", 1500, "The Spice Route Restaurant", "2026-06-12")
    assert result["is_likely_duplicate"] is False


if __name__ == "__main__":
    import subprocess
    subprocess.run(["python", "-m", "pytest", __file__, "-v"])
