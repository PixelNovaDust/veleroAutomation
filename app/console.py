from colorama import Fore, Style, just_fix_windows_console


just_fix_windows_console()


def startup():
    print()
    print(
        Fore.MAGENTA +
        Style.BRIGHT +
        "Starting Velero Automation...." +
        Style.RESET_ALL
    )
    print()

def processing(namespace):

    print(
        Fore.CYAN +
        "Processing: {}".format(namespace) +
        Style.RESET_ALL
    )

    print()


def processed(namespace, status, incident_id, incident_date):

    print(
        Fore.GREEN +
        "✓ {}".format(namespace) +
        Style.RESET_ALL
    )

    print("  Status        : {}".format(status))

    print(
        Fore.GREEN +
        "  Result        : PROCESSED" +
        Style.RESET_ALL
    )

    print("  Incident ID   : {}".format(incident_id))
    print("  Incident Date : {}".format(incident_date))
    print()


def skipped(namespace, reason):

    print(
        Fore.YELLOW +
        "• {}".format(namespace) +
        Style.RESET_ALL
    )

    print(
        Fore.YELLOW +
        "  Result        : SKIPPED" +
        Style.RESET_ALL
    )

    print("  Reason        : {}".format(reason))
    print()


def failed(namespace, reason, comment=None):

    print(
        Fore.RED +
        "✗ {}".format(namespace) +
        Style.RESET_ALL
    )

    print(
        Fore.RED +
        "  Result        : FAILED" +
        Style.RESET_ALL
    )

    print("  Reason        : {}".format(reason))

    if comment:
        print("  Comment       : {}".format(comment))

    print()


def error(message):

    print()
    print(
        Fore.RED +
        Style.BRIGHT +
        "ERROR" +
        Style.RESET_ALL
    )

    print(
        Fore.RED +
        message +
        Style.RESET_ALL
    )

    print()


def summary(processed_count, failed_count, skipped_count):

    total = (
        processed_count +
        failed_count +
        skipped_count
    )

    print(
        Fore.CYAN +
        Style.BRIGHT +
        "AUTOMATION SUMMARY" +
        Style.RESET_ALL
    )

    print()

    print(
        Fore.GREEN +
        "Processed : {}".format(processed_count) +
        Style.RESET_ALL
    )

    print(
        Fore.RED +
        "Failed    : {}".format(failed_count) +
        Style.RESET_ALL
    )

    print(
        Fore.YELLOW +
        "Skipped   : {}".format(skipped_count) +
        Style.RESET_ALL
    )

    print(
        "Total     : {}".format(total)
    )

    print()

    if failed_count == 0:

        print(
            Fore.GREEN +
            Style.BRIGHT +
            "✓ Velero automation completed!" +
            Style.RESET_ALL
        )

    else:

        print(
            Fore.YELLOW +
            Style.BRIGHT +
            "⚠ Velero automation completed with failures." +
            Style.RESET_ALL
        )

    print()