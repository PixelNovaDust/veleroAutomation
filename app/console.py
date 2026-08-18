import os
import sys

from app.logger import format_label
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

    logger.info(
        "Starting Velero Automation..."
    )

    logger.info(
        "%s: %s",
        format_label("Started by"),
        get_current_user()
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
