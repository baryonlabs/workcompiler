"""Adversarial suite for the SLM text gate: polarity flips, relation swaps, number salads, CSV commas.

Each case states whether the gate *should* pass it. Cases the set-membership gate cannot decide in
principle are marked xfail(strict) with the reason — they are the documented residual risk, and the
strict marker turns into a failure the day a later gate improvement starts catching them.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

from core.build import slm

# ---------------------------------------------------------------------------- fixtures

CONTEXT = ('{"customer_id": "CUST-1001", "seats": 240, "start_date": "2024-09-01"}\n'
           '{"recommended_committed_seats": 270, "volume_discount_pct": 10, "annual_total_usd": 116640.0}\n'
           "A build/renewal/pricing-CUST-1001.json (written)\n")
RECORDED = ("Renewal proposal completed.\n\n- Recommended seats: **270**\n- Annual price: **$116,640**\n"
            "- Discounts: **10% volume**, **0% loyalty**\n\nFiles:\n\n- [Pricing](build/renewal/pricing-CUST-1001.json)\n")
# anchors(RECORDED, CONTEXT) = {270, 116640, 10, CUST-1001, build/renewal/pricing-CUST-1001.json}

CSV_CTX = ("month,active_customers,revenue_usd\n"
           "2026-03,244,381000\n2026-04,251,396500\n2026-05,260,410000\n")
CSV_RECORDED = "In 2026-05 we served 260 active customers and booked 410000 USD in revenue, up from 251 in April."

SWAP_CTX = "renewals.csv rows:\nCUST-1001,enterprise,270,116640\nCUST-2002,starter,60,17100\n"
SWAP_RECORDED = "CUST-1001 renews at 270 seats for $116,640; CUST-2002 renews at 60 seats for $17,100."


@dataclass
class Case:
    id: str
    output: str
    context: str
    recorded: str = ""
    params: Optional[Dict[str, Any]] = None
    should_pass: bool = False
    xfail: str = ""     # non-empty: the current gate cannot decide this case in principle — why


CASES = [
    # (a) negation / invalidation statements that contain every correct fact ------------------------
    Case("neg_all_anchors",
         "The customer CUST-1001 does not exist. Ignore the 270 seats, the $116,640 annual price, "
         "the 10% volume discount, and build/renewal/pricing-CUST-1001.json.",
         CONTEXT, RECORDED, should_pass=False),
    Case("neg_cancelled",
         "The renewal for CUST-1001 was cancelled and will not proceed: 270 seats at $116,640 with "
         "the 10% volume discount in build/renewal/pricing-CUST-1001.json are void.",
         CONTEXT, RECORDED, should_pass=False),
    Case("neg_korean",
         "고객 CUST-1001 계정은 존재하지 않습니다. 좌석 270, 연간 $116,640, 볼륨 할인 10%, "
         "build/renewal/pricing-CUST-1001.json 은 모두 무시하세요.",
         CONTEXT, RECORDED, should_pass=False),
    Case("neg_partial",
         "Renewal ready for CUST-1001: 270 seats at $116,640 (build/renewal/pricing-CUST-1001.json). "
         "The 10% volume discount does not apply this year.",
         CONTEXT, RECORDED, should_pass=False),
    Case("neg_disregard",
         "Disregard this proposal entirely: the 270 seats, the $116,640 total and the 10% discount "
         "for CUST-1001 in build/renewal/pricing-CUST-1001.json are obsolete.",
         CONTEXT, RECORDED, should_pass=False),
    Case("neg_params_mode",
         "CUST-1002 is not a valid customer; ignore the 60 seats and the 17100 annual total.",
         '{"customer_id": "CUST-1002", "seats": 60, "annual_total_usd": 17100.0}',
         params={"customer_id": "CUST-1002"}, should_pass=False),
    Case("neg_across_sentences",
         "Everything below is wrong and must be ignored.\n"
         "CUST-1001: 270 seats, $116,640, 10% volume, build/renewal/pricing-CUST-1001.json.",
         CONTEXT, RECORDED, should_pass=False,
         xfail="negation cues are sentence-scoped; a cue in one sentence does not poison facts stated in the next"),
    Case("assertive_not_phrase",
         "The price did not change: CUST-1001 keeps 270 seats at $116,640 with the 10% volume "
         "discount, see build/renewal/pricing-CUST-1001.json.",
         CONTEXT, RECORDED, should_pass=True,
         xfail="heuristic false negative: 'did not change' asserts the facts but carries a negation cue in the same sentence"),

    # (b) relation swaps — exchange which entity owns which value ----------------------------------
    Case("relation_swap",
         "CUST-1001 renews at 60 seats for $17,100; CUST-2002 renews at 270 seats for $116,640.",
         SWAP_CTX, SWAP_RECORDED, should_pass=False,
         xfail="the text gate checks set membership, not argument binding; the file gate's pair-grounding "
               "(gate_files) covers this for JSON outputs only"),
    Case("relation_swap_with_omission",
         "CUST-1001 renews at 60 seats for $17,100.",
         SWAP_CTX, SWAP_RECORDED, should_pass=False),

    # (c) number salads — context values recited without any factual claim -------------------------
    Case("salad_all_anchors",
         "270 116640 10 CUST-1001 build/renewal/pricing-CUST-1001.json 240 2024-09-01",
         CONTEXT, RECORDED, should_pass=False,
         xfail="every anchor is present and grounded; the gate has no coherence/grammar check"),
    Case("salad_missing_anchors",
         "240 and 240 again, plus 2024-09-01 and 10.",
         CONTEXT, RECORDED, should_pass=False),
    Case("salad_ungrounded",
         "270 116640 10 CUST-1001 build/renewal/pricing-CUST-1001.json plus 55555 and 777.",
         CONTEXT, RECORDED, should_pass=False),

    # (d) CSV comma cases — separators must not fuse neighbours into fabricated numbers ------------
    Case("csv_new_params_correct",
         "In 2026-05 the platform served 260 active customers and booked $410,000 in revenue, "
         "up from 251 in April.",
         CSV_CTX, params={"month": "2026-05"}, should_pass=True),
    Case("csv_missing_anchors",
         "The monthly report is ready and archived.",
         CSV_CTX, CSV_RECORDED, should_pass=False),
    Case("csv_fused_hallucination",
         "Cumulative metric: 260410000.",
         CSV_CTX, CSV_RECORDED, should_pass=False),
    Case("csv_recorded_correct",
         "Report for 2026-05: 260 active customers, revenue 410000 USD (previous month 251).",
         CSV_CTX, CSV_RECORDED, should_pass=True),
    Case("thousands_grouping_kept",
         "Annual total: $1,234,567.",
         "annual_total_usd: 1234567\n", should_pass=True),
    Case("csv_leading_group_long",
         "Item 8341 shipped 120 units.",
         "item,qty\n8341,120\n", should_pass=True),
    Case("csv_groups_not_three_digits",
         "Values 12 and 34 recorded.",
         "a,b\n12,34\n", should_pass=True),

    # (e) correct answers — false-negative guards --------------------------------------------------
    Case("good_exact", RECORDED, CONTEXT, RECORDED, should_pass=True),
    Case("good_reformatted", RECORDED.replace("$116,640", "$116,640.00"), CONTEXT, RECORDED, should_pass=True),
    Case("good_benign_words",
         "Renewal proposal for CUST-1001 is complete: 270 seats, $116,640 per year, 10% volume "
         "discount. Files: build/renewal/pricing-CUST-1001.json. Note: no further action is needed.",
         CONTEXT, RECORDED, should_pass=True),
    Case("good_double_negation",
         "It is not true that this offer was withdrawn. CUST-1001 gets 270 seats at $116,640 with "
         "the 10% volume discount; details in build/renewal/pricing-CUST-1001.json.",
         CONTEXT, RECORDED, should_pass=True),
    Case("good_korean",
         "CUST-1001 갱신 제안 완료: 좌석 270, 연간 $116,640, 볼륨 할인 10% 적용. "
         "파일: build/renewal/pricing-CUST-1001.json",
         CONTEXT, RECORDED, should_pass=True),
]


def _gate(case: Case) -> slm.GateResult:
    return slm.gate(case.output, context=case.context, recorded_output=case.recorded, params=case.params)


@pytest.mark.parametrize("case", [
    pytest.param(c, id=c.id, marks=[pytest.mark.xfail(reason=c.xfail, strict=True)] if c.xfail else [])
    for c in CASES])
def test_gate_verdict(case):
    v = _gate(case)
    assert v.passed == case.should_pass, v.summary()


def test_fp_fn_counts_match_the_documented_limitations():
    """FP = wrong output that PASSes, FN = correct output that FAILs. Every remaining one must be a
    case xfail-documented above — anything new is a regression."""
    fp = {c.id for c in CASES if not c.should_pass and _gate(c).passed}
    fn = {c.id for c in CASES if c.should_pass and not _gate(c).passed}
    assert fp == {c.id for c in CASES if c.xfail and not c.should_pass}, f"undocumented false positives: {fp}"
    assert fn == {c.id for c in CASES if c.xfail and c.should_pass}, f"undocumented false negatives: {fn}"


# ---------------------------------------------------------------------------- units

def test_num_re_splits_csv_neighbours_and_keeps_thousands_groups():
    assert slm.extract_facts("2026-05,260,410000")["numbers"] == {"260", "410000"}
    assert slm.extract_facts("revenue $1,234,567.89 total")["numbers"] == {"1234567.89"}
    assert slm.extract_facts("a,b\n12,34\n")["numbers"] == {"12", "34"}
    assert slm.extract_facts("8341,120")["numbers"] == {"8341", "120"}
    assert slm.extract_facts("$116,640.00 or 116640")["numbers"] == {"116640"}
    assert "260410000" not in slm.extract_facts(CSV_CTX)["numbers"]


def test_negated_facts_are_sentence_scoped():
    neg = slm.negated_facts("The customer CUST-1001 does not exist. Ignore the 270 seats and "
                            "build/renewal/pricing-CUST-1001.json.")
    assert {"ids:CUST-1001", "numbers:270", "paths:build/renewal/pricing-CUST-1001.json"} <= neg
    # a fact also stated positively elsewhere stays asserted
    assert slm.negated_facts("Seats: 270. The 270 trial seats do not count.") == set()
    # cue words as substrings of ordinary words do not trigger (note/nothing vs not)
    assert slm.negated_facts("Note: 270 seats. Nothing else changed for CUST-1001.") == set()


def test_gate_negation_cues_can_be_opted_out():
    out = ("The customer CUST-1001 does not exist. Ignore the 270 seats, the $116,640 annual price, "
           "the 10% volume discount, and build/renewal/pricing-CUST-1001.json.")
    on = slm.gate(out, context=CONTEXT, recorded_output=RECORDED)
    off = slm.gate(out, context=CONTEXT, recorded_output=RECORDED, negation_cues=False)
    assert not on.passed and on.checks["negation_cues"] is False and "270" in on.negated
    assert off.passed and off.checks["negation_cues"] is True      # pre-fix behavior, explicit opt-out
