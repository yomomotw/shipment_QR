from datetime import date

import pytest

from app.services.qr_payload import (MAX_PAYLOAD_BYTES, SCAN_ALPHABET, PayloadTooLarge,
                                     build_payload, new_scan_code)

BASE = dict(model="XYZ-200", serial="SN0001", service_tel="0800-123-456",
            spec="電壓 24V\n黑色外殼", ship_date=date(2026, 11, 16), cust_po="PO-1", int_po="SO-1",
            warranty_start=date(2026, 11, 16), warranty_end=date(2027, 11, 16), scan_code="7KQ2M9XA")


def test_minimum_is_three_offline_lines():
    assert build_payload(**BASE) == "型號:XYZ-200\n序號:SN0001\n叫修電話:0800-123-456"


def test_matches_spec_example_exactly():
    got = build_payload(**BASE, qr_fields=["spec", "ship_date"],
                        public_base_url="https://service.example.com")
    assert got == ("型號:XYZ-200\n序號:SN0001\n叫修電話:0800-123-456\n規格:\n電壓 24V\n黑色外殼\n"
                   "出貨日期:2026-11-16\n線上報修:https://service.example.com/d/7KQ2M9XA")


def test_all_fields_order():
    got = build_payload(**BASE, qr_fields=["warranty", "int_po", "cust_po", "ship_date", "spec"])
    assert got.split("\n")[3:] == ["規格:", "電壓 24V", "黑色外殼", "出貨日期:2026-11-16",
                                    "客戶訂單:PO-1", "內部訂單:SO-1", "保固:2026-11-16~2027-11-16"]


def test_empty_spec_omitted_even_if_checked():
    assert "規格" not in build_payload(**{**BASE, "spec": "  \n"}, qr_fields=["spec"])


def test_spec_outer_blank_lines_trimmed_inner_kept():
    got = build_payload(**{**BASE, "spec": "\n\nA\n\nB\n\n"}, qr_fields=["spec"])
    assert got.endswith("規格:\nA\n\nB")


def test_base_url_trailing_slash():
    got = build_payload(**BASE, public_base_url="https://s.example.com/")
    assert got.endswith("線上報修:https://s.example.com/d/7KQ2M9XA")


def test_url_line_is_last_without_trailing_newline():
    got = build_payload(**BASE, qr_fields=["warranty"], public_base_url="https://s.example.com")
    assert got.split("\n")[-1].startswith("線上報修:") and not got.endswith("\n")


def test_no_url_line_without_base_url():
    assert "線上報修" not in build_payload(**BASE, qr_fields=["spec"])


def test_too_large_rejected():
    with pytest.raises(PayloadTooLarge):
        build_payload(**{**BASE, "spec": "規" * MAX_PAYLOAD_BYTES}, qr_fields=["spec"])


def test_scan_codes():
    codes = {new_scan_code() for _ in range(1000)}
    assert len(codes) == 1000
    assert all(len(c) == 8 and set(c) <= set(SCAN_ALPHABET) for c in codes)
