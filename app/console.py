import os
import sys

from app.dates import format_display_date, normalize_date
from app.logger import file_only, format_label
from app.system import get_current_user


def is_interactive():
    """
    A frozen build launched by a scheduler has no usable stdin,
    and blocking on input there would hang the run forever.
    """

    stream = sys.stdin

    if stream is None or stream.closed:
        return False

    try:
        return bool(stream.isatty())

    except (OSError, ValueError):
        return False


def startup(logger):

    logger.debug(
        "Starting Velero Automation..."
    )

    logger.debug(
        "%s: %s",
        format_label("Started by"),
        get_current_user(),
        extra=file_only()
    )


def make_confirm(logger, default=False):
    """
    Build the yes/no prompt used before Excel is closed.

    The question and the answer both reach the log, so a run
    that stopped early can be explained afterwards.
    """

    def confirm(question):

        if not is_interactive():

            logger.warning(
                "%s? No console is available to answer, "
                "assuming %s.",
                question,
                "yes" if default else "no"
            )

            return default

        prompt = "{}? [{}]: ".format(
            question,
            "Y/n" if default else "y/N"
        )

        print()

        try:
            answer = input(prompt).strip().lower()

        except (EOFError, KeyboardInterrupt):

            print()

            answer = ""

        print()

        if not answer:
            decision = default

        else:
            decision = answer in ("y", "yes")

        logger.info(
            "%s? Answered %s",
            question,
            "yes" if decision else "no"
        )

        return decision

    return confirm


def prompt_target_date(config=None):
    """
    Ask the engineer which workbook date to process before the
    sheet is validated or any PagerDuty events are raised.
    """

    config = config or {}

    fallback = (
        config
        .get("processing", {})
        .get("default_date")
    )

    if not is_interactive():

        normalized = normalize_date(fallback)

        if not normalized:
            raise ValueError(
                "No console is available to enter a date and "
                "processing.default_date is not configured."
            )

        return normalized

    print()
    print("Enter the date:")
    print()

    while True:

        try:
            answer = input().strip()

        except (EOFError, KeyboardInterrupt):

            print()

            raise ValueError(
                "Date entry was cancelled."
            )

        if not answer:
            print("A date is required.")
            continue

        normalized = normalize_date(answer)

        if normalized:
            return normalized

        print(
            "Enter a valid date, for example 15-03-2026 or "
            "2026-03-15."
        )


def log_run_start(logger, target_date):

    logger.info(
        "Starting Velero Automation for {}...".format(
            format_display_date(target_date)
        )
    )


def wait_for_exit(enabled=True):

    if not enabled or not is_interactive():
        return

    print()
    print("Press any key to exit...")

    if os.name == "nt":

        try:
            import msvcrt

            msvcrt.getch()

            return

        except ImportError:
            pass

    try:
        input()

    except (EOFError, KeyboardInterrupt):
        pass
