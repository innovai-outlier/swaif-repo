import pytest
from estoque.adapters.parsers import parse_quantidade_raw

@pytest.mark.parametrize(
    "txt,exp_num,exp_unit,exp_desc",
    [
        ("5.00 MG - MILIGRAMAs", 5.0, "MG", "MILIGRAMAs"),
        ("2 FR - Frascos", 2.0, "FR", "Frascos"),
        ("5,5 ml - mililitro", 5.5, "ML", "mililitro"),
        ("10 AMP", 10.0, "AMP", None),
        ("", None, None, None),
        (None, None, None, None),
    ],
)
def test_parse_quantidade_raw(txt, exp_num, exp_unit, exp_desc):
    num, unit, desc = parse_quantidade_raw(txt)
    assert (num == exp_num) or (num is None and exp_num is None)
    assert unit == exp_unit
    assert desc == exp_desc
