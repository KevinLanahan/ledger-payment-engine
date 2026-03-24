from fastapi import HTTPException, status

def validate_balanced(entries: list[dict]) -> None:
    total = sum(e["amount_cents"] for e in entries)
    if total != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transaction is not balanced. Sum(amount_cents) = {total}, expected 0."
        )