def startup(logger):
    logger.info(
        "Starting Velero Automation..."
    )


def wait_for_exit():
    import msvcrt

    print()
    print("Press any key to exit...")
    msvcrt.getch()