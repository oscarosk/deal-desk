import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from order_form import ApprovalError, render, validate  # noqa: E402
from pricing import check_deal, load_json, verdict_only  # noqa: E402

PRICES = load_json(ROOT / "data" / "price_list.json")
NORTHWIND = load_json(ROOT / "data" / "deals" / "northwind.json")


def deal(**changes):
    return {**NORTHWIND, **changes}


def approval(role="finance_lead", **terms):
    return {
        "deal_id": "D-1042",
        "approved_by": "maya",
        "role": role,
        "approved_at": "2026-11-07T15:00:00+05:30",
        "terms": terms or {"discount_pct": 25, "term_months": 24, "payment_terms": "net60"},
    }


class PricingTest(unittest.TestCase):
    def test_demo_request_is_rejected_for_margin_and_authority(self):
        r = check_deal(NORTHWIND, PRICES)
        self.assertEqual(r["verdict"], "reject")
        self.assertEqual(r["margin_pct"], 60.7)
        self.assertTrue(any("floor" in x for x in r["reasons"]))
        self.assertTrue(any("approval limit" in x for x in r["reasons"]))

    def test_counter_stays_inside_the_floor_with_a_buffer(self):
        r = check_deal(NORTHWIND, PRICES)
        self.assertEqual(r["max_discount_pct"], 26)
        self.assertEqual(r["counter"]["discount_pct"], 24)
        countered = check_deal(deal(**{k: r["counter"][k] for k in
                                       ("discount_pct", "term_months", "payment_terms")}), PRICES)
        self.assertNotEqual(countered["verdict"], "reject")

    def test_finance_counter_needs_finance_lead(self):
        r = check_deal(deal(discount_pct=25, term_months=24), PRICES)
        self.assertEqual(r["automatic_discount_pct"], 10)
        self.assertEqual(r["extra_discount_pct"], 15)
        self.assertEqual(r["verdict"], "needs_approval")
        self.assertEqual(r["approver"], "finance_lead")

    def test_small_discount_on_standard_terms_needs_nobody(self):
        r = check_deal(deal(discount_pct=8, payment_terms="net30"), PRICES)
        self.assertEqual((r["verdict"], r["approver"]), ("accept", "rep"))

    def test_long_payment_terms_alone_need_finance(self):
        r = check_deal(deal(discount_pct=0, payment_terms="net60"), PRICES)
        self.assertEqual(r["approver"], "finance_lead")

    def test_net90_is_never_allowed(self):
        r = check_deal(deal(discount_pct=0, payment_terms="net90"), PRICES)
        self.assertEqual(r["verdict"], "reject")

    def test_unknown_term_is_an_error(self):
        with self.assertRaises(ValueError):
            check_deal(deal(term_months=18), PRICES)

    def test_verdict_only_hides_internal_numbers(self):
        out = verdict_only(check_deal(NORTHWIND, PRICES))
        text = json.dumps(out)
        for secret in ("margin", "floor", "cost", "max_discount", "approver", "26"):
            self.assertNotIn(secret, text)
        self.assertEqual(out["verdict"], "reject")

    def test_verdict_only_does_not_reveal_who_approves(self):
        out = verdict_only(check_deal(deal(discount_pct=25, term_months=24), PRICES))
        self.assertEqual(out["verdict"], "pending_internal_review")


class OrderFormTest(unittest.TestCase):
    def test_finance_approval_produces_an_order_form(self):
        result = validate(NORTHWIND, approval(), PRICES)
        text = render(NORTHWIND, approval(), result, "USD")
        # 25% off 900 = 675 per seat per year, x 300 seats x 2 years.
        self.assertIn("Total contract value | USD 405,000.00", text)
        self.assertIn("maya", text)

    def test_rep_cannot_approve_finance_terms(self):
        with self.assertRaisesRegex(ApprovalError, "need finance_lead"):
            validate(NORTHWIND, approval(role="rep"), PRICES)

    def test_nobody_can_approve_terms_below_the_floor(self):
        with self.assertRaisesRegex(ApprovalError, "floor"):
            validate(NORTHWIND, approval(discount_pct=35, term_months=24,
                                         payment_terms="net60"), PRICES)

    def test_approval_for_another_deal_is_refused(self):
        a = approval()
        a["deal_id"] = "D-9999"
        with self.assertRaisesRegex(ApprovalError, "not D-1042"):
            validate(NORTHWIND, a, PRICES)

    def test_missing_fields_are_refused(self):
        a = approval()
        del a["approved_by"]
        with self.assertRaisesRegex(ApprovalError, "approved_by"):
            validate(NORTHWIND, a, PRICES)


if __name__ == "__main__":
    unittest.main()
