import pytest

from app.services.serials import SerialError, check_quantity, parse_serials


def test_range_expands():
    assert parse_serials("SN0001~SN0003") == ["SN0001", "SN0002", "SN0003"]


def test_range_keeps_zero_padding_across_rollover():
    assert parse_serials("SN0098~SN0101") == ["SN0098", "SN0099", "SN0100", "SN0101"]


def test_mixed_separators():
    assert parse_serials("A1,A2\nA3；A4") == ["A1", "A2", "A3", "A4"]


def test_whitespace_and_blank_lines_ignored():
    assert parse_serials("  A1 \n\n ,A2\n") == ["A1", "A2"]


def test_end_before_start_rejected():
    with pytest.raises(SerialError, match="迄號小於起號"):
        parse_serials("SN0005~SN0001")


def test_prefix_mismatch_rejected():
    with pytest.raises(SerialError, match="前綴不一致"):
        parse_serials("SN0001~AB0003")


def test_duplicates_rejected_and_named():
    with pytest.raises(SerialError, match="A1"):
        parse_serials("A1,A1")


def test_duplicate_between_range_and_single():
    with pytest.raises(SerialError, match="SN0002"):
        parse_serials("SN0001~SN0003,SN0002")


def test_quantity_mismatch():
    with pytest.raises(SerialError, match="不符"):
        check_quantity(["A", "B", "C"], 4)
