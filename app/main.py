import logging
import sys

from app.config import default_config, load_config
from app.console import make_confirm, startup, wait_for_exit
from app.excel import ExcelManager
from app.ledger import ProcessedLedger
from app.logger import (
    attach_file_logging,
    file_only,
    format_context,
    format_label,
    setup_logger
)
from app.processor import VeleroProcessor

from app.pagerduty.client import PagerDutyClient
from app.pagerduty.incidents import PagerDutyIncidents


def main():

    logger = setup_logger()

    config = None
    exit_code = 0

    try:

        startup(logger)

        config = load_config()

        log_file = attach_file_logging(logger, config)

        confirm = make_confirm(logger)

        logger.debug(
            "%s: %s",
            format_label("Configuration file"),
            config["runtime"]["config_path"]
        )

        if log_file:

            logger.debug(
                "%s: %s",
                format_label("Log file"),
                log_file
            )

        # Excel validation
        excel_manager = ExcelManager.from_config(
            config=config,
            logger=logger,
            confirm=confirm
        )

        logger.info(
            "%s: %s",
            format_label("Using Excel file"),
            excel_manager.file_path
        )

        logger.info(
            "%s: %s",
            format_label("Excel Table"),
            excel_manager.table_name
        )

        excel_manager.preflight()

        excel_manager.validate_file()

        logger.debug(
            "Excel file, table and columns validated"
        )

        # PagerDuty validation
        pagerduty_client = PagerDutyClient(
            config=config,
            logger=logger
        )

        pagerduty_client.validate_connection()

        # PagerDuty incident manager
        pagerduty_incidents = PagerDutyIncidents(
            client=pagerduty_client,
            logger=logger
        )

        # Record of incidents already raised, kept beside the
        # workbook so a lost cell cannot become a duplicate page
        ledger = ProcessedLedger.from_config(
            config=config,
            logger=logger
        ).load()

        # Processor
        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=config,
            pagerduty_client=pagerduty_incidents,
            logger=logger,
            ledger=ledger
        )

        result = processor.process()

        backup_path = excel_manager.create_backup()

        if backup_path:

            logger.debug(
                "Workbook backed up to %s",
                backup_path,
                extra=file_only()
            )

        logger.info(
            "Velero automation completed!"
        )

        logger.info(
            "%s | Processed: %d :::: Skipped: %d :::: Failed: %d",
            format_context("Summary"),
            result["processed"],
            result["skipped"],
            result["failed"]
        )

        logger.info(
            "Bye!"
        )

    except Exception as exception:

        exit_code = 1

        # A config that failed to load left the run without a log
        # file, and that failure is exactly what needs recording.
        _ensure_file_logging(logger)

        logger.error(
            "%s",
            exception
        )

        logger.debug(
            "Run failed",
            exc_info=True,
            extra=file_only()
        )

    finally:

        wait_for_exit(
            _pause_on_exit(config)
        )

    return exit_code


def _ensure_file_logging(logger):

    for handler in logger.handlers:

        if isinstance(handler, logging.FileHandler):
            return

    try:
        attach_file_logging(logger, default_config())

    except Exception:
        pass


def _pause_on_exit(config):

    if not config:
        return True

    return (
        config
        .get("console", {})
        .get("pause_on_exit", True)
    )


if __name__ == "__main__":
    sys.exit(main())
