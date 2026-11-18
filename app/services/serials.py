"""Serial list parsing (FR-02). Pure functions, no database access."""
import re

MAX_RANGE = 5000
_SPLIT = re.compile(r"[\n,，;；\t]+")
_RANGE = re.compile(r"^(.*?)(\d+)\s*~\s*(.*?)(\d+)(.*)$")


class SerialError(ValueError):
    pass


def _expand(token: str) -> list[str]:
    m = _RANGE.match(token)
    if not m:
        raise SerialError(f"無法解析範圍「{token}」")
    p1, a, p2, b, suffix = m.groups()
    if p2 and p2 != p1:
        raise SerialError(f"範圍「{token}」前後前綴不一致")
    start, end = int(a), int(b)
    if end < start:
        raise SerialError(f"範圍「{token}」迄號小於起號")
    if end - start >= MAX_RANGE:
        raise SerialError(f"範圍「{token}」超過 {MAX_RANGE} 台，請分批")
    return [f"{p1}{i:0{len(a)}d}{suffix}" for i in range(start, end + 1)]


def parse_serials(text: str) -> list[str]:
    """Expand a pasted serial list. Raises SerialError on malformed ranges or duplicates."""
    out: list[str] = []
    for token in (t.strip() for t in _SPLIT.split(text or "")):
        if not token:
            continue
        out.extend(_expand(token) if "~" in token else [token])
    seen, dup = set(), []
    for s in out:
        if s in seen and s not in dup:
            dup.append(s)
        seen.add(s)
    if dup:
        more = " …" if len(dup) > 5 else ""
        raise SerialError(f"序號重複：{', '.join(dup[:5])}{more}")
    return out


def check_quantity(serials: list[str], qty: int) -> None:
    if len(serials) != qty:
        raise SerialError(f"序號數量（{len(serials)}）與出貨數量（{qty}）不符")
