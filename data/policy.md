# Corporate Travel & Expense Reimbursement Policy (Mock)
Version 1.0 — For demo/assignment purposes only. No real company data.

## Section 1: General Eligibility
1.1 Reimbursement applies only to pre-approved business travel (client visits, conferences, training, inter-office travel).
1.2 Personal travel, leisure add-ons, or travel for dependents is never reimbursable.
1.3 Claims must be submitted within 30 days of the expense date. Claims submitted later are routed to Manual Review.

## Section 2: Per Diem & Meal Allowance
2.1 Meal per-diem limits by city tier (see limits.json for exact values):
    - Tier 1 (Metro: Mumbai, Bengaluru, Delhi, Pune): higher allowance
    - Tier 2 (other state capitals): medium allowance
    - Tier 3 (other cities): lower allowance
2.2 Alcohol is never reimbursable under meal per-diem, regardless of city tier.
2.3 Amounts exceeding the per-diem limit are Partially Approved — the excess is deducted, not auto-rejected, unless receipts are also missing.

## Section 3: Lodging / Hotel
3.1 Hotel stays must not exceed the nightly cap for the relevant city tier.
3.2 Only standard/business category rooms are covered. Suite or premium upgrades require Manual Review with written justification.
3.3 Lodging claims without an itemized hotel invoice are Rejected unless the amount is under ₹1,500, in which case Manual Review may apply.

## Section 4: Flight & Transportation
4.1 Economy class is the default for trips under 6 hours; Premium Economy is allowed for flights over 6 hours with manager pre-approval.
4.2 Business class requires VP-level sign-off and is otherwise Rejected.
4.3 Local transportation (cabs, ride-hailing) is reimbursable up to a daily cap; amounts above the cap require a trip log and are otherwise Partially Approved.

## Section 5: Receipt & Documentation Requirements
5.1 All claims above ₹500 require an attached receipt/invoice.
5.2 Claims missing required receipts are Rejected for the unreceipted portion, or routed to Manual Review if the claim is otherwise borderline (e.g., near a limit, ambiguous category).
5.3 Receipts must match the claimed date within +/- 1 day and the claimed vendor/category. Mismatches trigger Manual Review.

## Section 6: Approval Thresholds & Manual Review Triggers
6.1 Any single claim above ₹25,000 is automatically routed to Manual Review regardless of category.
6.2 Claims with conflicting information (e.g., category mismatch with description, date inconsistencies) are routed to Manual Review.
6.3 Claims with low-confidence policy interpretation (ambiguous category, missing context) must not be auto-approved or auto-rejected — route to Manual Review.

## Section 7: Duplicate Claims
7.1 A claim is considered a likely duplicate if the same employee, amount (+/- 1%), vendor, and a date within 2 days already exists in claim history.
7.2 Suspected duplicates are never auto-rejected outright — they are routed to Manual Review for human verification, since duplicate detection can have false positives (e.g., split billing).

## Section 8: Currency & Rounding
8.1 All amounts in this policy and in claims are in INR (₹) unless otherwise stated.
8.2 Final approved amounts are rounded down to the nearest whole rupee.
