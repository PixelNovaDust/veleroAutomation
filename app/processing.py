def is_processed(value, processed_value="Yes"):
    """A row is eligible only when it is not already marked processed."""

    if value is None or value == "":
        return False

    return (
        str(value).strip().lower()
        == str(processed_value).strip().lower()
    )
