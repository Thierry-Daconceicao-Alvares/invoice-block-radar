from datetime import date

import pytest

from radar.detective import CAUSE_TEXT, CaseFile, Note, TemplateWriter, check, diagnose


def case(**changes) -> CaseFile:
    facts = dict(
        case_id="4508000001_00010",
        po_document="4508000001",
        vendor="vendorID_0042",
        buyer="user_116",
        company="companyID_0000",
        spend_area="Packaging",
        line_value_eur=12450,
        blocked_on=date(2018, 9, 20),
        days_open=25,
        goods_received=True,
        cause="likely_mismatch",
        cause_text=CAUSE_TEXT["likely_mismatch"],
        owner="Buyer user_116",
        action="Compare the invoice with the order.",
        contact_vendor=True,
        vendor_blocks_before=40,
        vendor_corrections_before=9,
        buyer_blocks_before=120,
        buyer_corrections_before=14,
    )
    return CaseFile(**(facts | changes))


def note(**changes) -> Note:
    text = dict(
        summary="Purchase order 4508000001 from vendorID_0042 (12,450 EUR) is blocked.",
        next_step="Buyer user_116 compares the invoice with the order.",
        email_subject="Invoice check for purchase order 4508000001",
        email_body="Hello, please check the invoice for order 4508000001. Accounts Payable",
    )
    return Note(**(text | changes))


def test_a_note_using_only_the_facts_passes():
    assert check(note(), case()) == []


def test_an_invented_amount_is_caught():
    problems = check(note(summary="Order 4508000001 is blocked for 13,000 EUR."), case())
    assert problems == ["numbers not in the facts: 13000"]


def test_the_email_must_follow_the_rules():
    assert check(note(email_subject=None, email_body=None), case()) == ["email missing"]
    assert check(note(), case(contact_vendor=False)) == ["email present but not asked for"]


def test_internal_rates_never_reach_the_vendor():
    body = "Hello, 9 of your 40 invoices needed a fix. Please check order 4508000001, 22% of cases."
    assert "internal rates shown to the vendor" in check(note(email_body=body), case())


@pytest.mark.parametrize(
    "goods, score, cause, vendor_email",
    [(False, 0.9, "waiting_for_goods", False), (True, 0.2, "likely_mismatch", True), (True, 0.01, "routine_check", False)],
)
def test_rules(goods, score, cause, vendor_email):
    diagnosis = diagnose(goods, score, threshold=0.1, buyer="user_1")
    assert (diagnosis.cause, diagnosis.contact_vendor) == (cause, vendor_email)


def test_the_template_writer_passes_its_own_checks():
    for facts in (case(), case(contact_vendor=False, cause="routine_check")):
        assert check(TemplateWriter().write(facts), facts) == []


# Attempts to get past the checks, taken from an independent review.
@pytest.mark.parametrize(
    "body, problem",
    [
        ("7 of your 40 invoices needed a fix. Please check order 4508000001.", "numbers the vendor should not see: 40, 7"),
        ("user_116 flagged order 4508000001. Please check it.", "internal user id shown to the vendor"),
        ("Your invoice for order 4508000001 is wrong.", "the email accuses or presses the vendor"),
        ("Order 4508000001: a penalty of twelve thousand euros applies.", "a number written in words"),
        ("Please answer by 20/09/2018 or we cancel order 4508000001.", "the email accuses or presses the vendor"),
        ("Order 4508000001 is on hold, 22% of cases need a fix.", "internal rates shown to the vendor"),
        ("Order 4508000001: 13000EUR were invoiced.", "numbers the vendor should not see: 13000"),
        ("Order 4508000001: about 13k EUR.", "numbers the vendor should not see: 13"),
        ("Order 4508000001: we received 40pcs.", "numbers the vendor should not see: 40"),
        ("Please reply about order 4508000001 by Friday, otherwise payment stays withheld.", "the email accuses or presses the vendor"),
    ],
)
def test_the_vendor_email_cannot_leak_or_threaten(body, problem):
    assert problem in check(note(email_body=body), case())


def test_digits_inside_an_id_are_not_a_figure():
    summary = "Order 4508000001 from vendorID_0042 is blocked; 116 EUR at stake."
    assert check(note(summary=summary), case()) == ["numbers not in the facts: 116"]
