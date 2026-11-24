from decimal import ROUND_HALF_UP, Decimal

TWO = Decimal("0.01")

_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve",
         "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def q2(x) -> Decimal:
    return Decimal(x).quantize(TWO, rounding=ROUND_HALF_UP)


def _below_hundred(n: int) -> str:
    return _ONES[n] if n < 20 else (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else ""))


def _below_thousand(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n:
        parts.append(_below_hundred(n))
    return " ".join(parts)


def amount_in_words(amount: Decimal) -> str:
    """Indian numbering: 1,23,45,678.50 -> 'One Crore Twenty Three Lakh ... Rupees and Fifty Paise Only'."""
    amount = q2(amount)
    rupees = int(amount)
    paise = int((amount - rupees) * 100)
    if rupees == 0:
        words = "Zero"
    else:
        parts = []
        for div, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
            if rupees >= div:
                parts.append(f"{_below_thousand(rupees // div) if rupees // div < 1000 else amount_in_words(Decimal(rupees // div)).replace(' Rupees Only', '')} {name}")
                rupees %= div
        if rupees:
            parts.append(_below_thousand(rupees))
        words = " ".join(parts)
    out = f"{words} Rupees"
    if paise:
        out += f" and {_below_hundred(paise)} Paise"
    return out + " Only"


def fmt_inr(amount) -> str:
    """12345678.5 -> '1,23,45,678.50'"""
    amount = q2(amount)
    sign = "-" if amount < 0 else ""
    s = f"{abs(amount):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}{whole}.{frac}"


def mask_account(acc: str | None) -> str | None:
    if not acc:
        return None
    return "X" * max(0, len(acc) - 4) + acc[-4:]
