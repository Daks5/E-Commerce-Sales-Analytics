import pytest
from assistant.gemini import normalize_currency_display, numeric_claims_supported


@pytest.mark.parametrize('original,expected', [
    ('Sales: ₹31,980,39 [D1].', 'Sales: ₹3,198,039 [D1].'),
    ('₹31,98,039.50 and ₹-1000.25', '₹3,198,039.50 and ₹-1,000.25'),
    ('₹3,198,039, across 6,580 orders', '₹3,198,039, across 6,580 orders'),
    ('₹6.97 crore; ₹31.98 lakh', '₹6.97 crore; ₹31.98 lakh'),
])
def test_grouping_preserves_amount_scale_decimals_and_citations(original, expected):
    assert normalize_currency_display(original) == expected


def test_formatter_does_not_bypass_numeric_evidence_validation():
    evidence = [{'rows':[{'shipped_value':3198039}], 'filters':{'row_limit':200}}]
    assert numeric_claims_supported(normalize_currency_display('₹31,980,39'), evidence)
    assert not numeric_claims_supported(normalize_currency_display('₹31,980,40'), evidence)
