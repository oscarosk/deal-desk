"""Deal Desk pricing check for the fictional company Lumen Analytics.

The agents never do pricing arithmetic themselves. They run this script and
quote its output, so every number in the room comes from one tested place.

Usage:
    python tools/pricing.py data/deals/northwind.json
    python tools/pricing.py data/deals/northwind.json --verdict-only

--verdict-only prints accept / reject / counter without the margin floor or
the cost figures. It is the mode for anything the customer's side can see.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PRICE_LIST = ROOT / "data" / "price_list.json"

# Who can approve, from the lowest authority to the highest.
APPROVERS = ["rep", "sales_manager", "finance_lead"]


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def automatic_discount(prices: dict, seats: int, term_months: int) -> int:
    """Discount every deal gets for its size and length, in whole percent."""
    volume = 0
    for tier in prices["volume_discount_pct"]:
        if seats >= tier["min_seats"]:
            volume = max(volume, tier["pct"])
    term = prices["term_discount_pct"].get(str(term_months))
    if term is None:
        raise ValueError(f"term_months must be one of {sorted(prices['term_discount_pct'])}, got {term_months}")
    return volume + term


def approver_for_discount(prices: dict, extra_pct: float) -> str | None:
    """Lowest role allowed to approve this extra discount, or None if nobody can."""
    for role in APPROVERS:
        if extra_pct <= prices["extra_discount_limit_pct"][role]:
            return role
    return None


def approver_for_terms(prices: dict, payment_terms: str) -> str | None:
    if payment_terms in prices["payment_terms"]["standard"]:
        return "rep"
    if payment_terms in prices["payment_terms"]["finance_lead"]:
        return "finance_lead"
    return None


def higher(a: str, b: str) -> str:
    return a if APPROVERS.index(a) >= APPROVERS.index(b) else b


def check_deal(deal: dict, prices: dict) -> dict:
    plan_name = deal["plan"]
    if plan_name not in prices["plans"]:
        raise ValueError(f"unknown plan {plan_name!r}")
    plan = prices["plans"][plan_name]
    seats = int(deal["seats"])
    term = int(deal["term_months"])
    requested = float(deal["discount_pct"])
    terms = deal.get("payment_terms", "net30")
    if seats <= 0:
        raise ValueError("seats must be positive")
    if not 0 <= requested < 100:
        raise ValueError("discount_pct must be between 0 and 100")

    list_price = plan["list_per_seat_year"]
    cost = plan["cost_per_seat_year"]
    years = term / 12
    auto = automatic_discount(prices, seats, term)
    extra = max(0.0, requested - auto)

    net_per_seat = list_price * (1 - requested / 100)
    margin = (net_per_seat - cost) / net_per_seat * 100

    floor_pct = prices["margin_floor_pct"]
    # Largest whole-percent discount that still keeps the margin floor.
    floor_price = cost / (1 - floor_pct / 100)
    max_discount = math.floor((1 - floor_price / list_price) * 100)

    reasons: list[str] = []
    discount_role = approver_for_discount(prices, extra)
    terms_role = approver_for_terms(prices, terms)

    if margin < floor_pct:
        reasons.append(f"margin {margin:.1f}% is below the {floor_pct}% floor")
    if discount_role is None:
        reasons.append(f"extra discount {extra:g}% is above anyone's approval limit")
    if terms_role is None:
        reasons.append(f"payment terms {terms} are not allowed")

    if reasons:
        verdict = "reject"
        approver = None
    else:
        approver = higher(discount_role, terms_role)
        verdict = "accept" if approver == "rep" else "needs_approval"

    counter = None
    if verdict == "reject":
        counter_pct = max(0, max_discount - prices["counter_buffer_pct"])
        counter_extra = max(0, counter_pct - auto)
        counter_role = approver_for_discount(prices, counter_extra)
        counter_terms = terms if terms_role else "net30"
        counter = {
            "discount_pct": counter_pct,
            "term_months": term,
            "payment_terms": counter_terms,
            "approver": higher(counter_role, approver_for_terms(prices, counter_terms))
            if counter_role
            else None,
        }

    return {
        "company": prices["company"],
        "deal_id": deal.get("deal_id"),
        "customer": deal.get("customer"),
        "plan": plan_name,
        "seats": seats,
        "term_months": term,
        "payment_terms": terms,
        "requested_discount_pct": requested,
        "automatic_discount_pct": auto,
        "extra_discount_pct": extra,
        "list_total": round(list_price * seats * years, 2),
        "net_total": round(net_per_seat * seats * years, 2),
        "net_per_seat_year": round(net_per_seat, 2),
        "margin_pct": round(margin, 1),
        "margin_floor_pct": floor_pct,
        "max_discount_pct": max_discount,
        "verdict": verdict,
        "approver": approver,
        "reasons": reasons,
        "counter": counter,
    }


def verdict_only(result: dict) -> dict:
    """What the customer's side may see: no costs, margins, floor or approver."""
    out = {"deal_id": result["deal_id"], "verdict": result["verdict"]}
    if result["verdict"] == "needs_approval":
        out["verdict"] = "pending_internal_review"
    if result["counter"]:
        out["counter"] = {
            k: result["counter"][k] for k in ("discount_pct", "term_months", "payment_terms")
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("deal", type=Path, help="deal JSON file")
    parser.add_argument("--prices", type=Path, default=DEFAULT_PRICE_LIST)
    parser.add_argument("--verdict-only", action="store_true",
                        help="hide costs, margins and the floor")
    args = parser.parse_args(argv)
    try:
        result = check_deal(load_json(args.deal), load_json(args.prices))
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(verdict_only(result) if args.verdict_only else result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
