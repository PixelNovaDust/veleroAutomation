from datetime import datetime


DATE_PATTERNS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y",
    "%d/%m/%Y",
)


def normalize_date(value):
    """
    Return a comparable YYYY-MM-DD string for sheet dates,
    ledger keys and PagerDuty custom details.
    """

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")

    if value:

        text = str(value).strip()

        for pattern in DATE_PATTERNS:
            try:
                return datetime.strptime(
                    text,
                    pattern
                ).strftime("%Y-%m-%d")

            except ValueError:
                pass

        if len(text) >= 10:
            return text[:10]

    return None


def dates_match(left, right):
    """Compare two sheet or config dates after normalisation."""

    left_normalized = normalize_date(left)
    right_normalized = normalize_date(right)

    if not left_normalized or not right_normalized:
        return False

    return left_normalized == right_normalized


def format_display_date(value):
    """Present a sheet date as DD-MM-YYYY in console output."""

    normalized = normalize_date(value)

    if not normalized:
        return str(value or "")

    try:
        return datetime.strptime(
            normalized,
            "%Y-%m-%d"
        ).strftime("%d-%m-%Y")

    except ValueError:
        return normalized


def as_datetime(value):
    """Restore a stored date string as a datetime for Excel cells."""

    if isinstance(value, datetime):
        return value

    if not value:
        return value

    normalized = normalize_date(value)

    if not normalized:
        return value

    try:
        return datetime.strptime(
            normalized,
            "%Y-%m-%d"
        )

    except ValueError:
        return value
