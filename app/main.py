import logging
import sys

from app.config import default_config, load_config
from app.console import (
    log_run_start,
    make_confirm,
    prompt_target_date,
    startup,
    wait_for_exit
)
from app.dates import format_display_date
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
    excel_manager = None
    target_date = None
    row_count = 0
    result = {
        "processed": 0,
        "skipped": 0,
        "failed": 0
    }

    try:

        config = load_config()

        log_file = attach_file_logging(logger, config)

        startup(logger)

        target_date = prompt_target_date(config)

        logger.info(
            "Validating the sheet"
        )

        confirm = make_confirm(logger)

        logger.debug(
            "%s: %s",
            format_label("Configuration file"),
            config["runtime"]["config_path"],
            extra=file_only()
        )

        if log_file:

            logger.debug(
                "%s: %s",
                format_label("Log file"),
                log_file,
                extra=file_only()
            )

        excel_manager = ExcelManager.from_config(
            config=config,
            logger=logger,
            confirm=confirm
        )

        log_run_start(logger, target_date)

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

        row_count = excel_manager.count_rows_for_date(
            target_date
        )

        if row_count == 0:

            exit_code = 1

            logger.error(
                "No event found for {}".format(
                    format_display_date(target_date)
                )
            )

        else:

            try:

                pagerduty_client = PagerDutyClient(
                    config=config,
                    logger=logger
                )

                pagerduty_client.validate_connection()

                pagerduty_incidents = PagerDutyIncidents(
                    client=pagerduty_client,
                    logger=logger
                )

                ledger = ProcessedLedger.from_config(
                    config=config,
                    logger=logger
                ).load()

                processor = VeleroProcessor(
                    excel_manager=excel_manager,
                    config=config,
                    pagerduty_client=pagerduty_incidents,
                    logger=logger,
                    ledger=ledger
                )

                result = processor.process(target_date)

            except Exception as pre_process_error:

                exit_code = 1

                _write_pre_pagerduty_failure(
                    excel_manager=excel_manager,
                    config=config,
                    logger=logger,
                    target_date=target_date,
                    error_message=str(pre_process_error)
                )

                logger.error(
                    "%s",
                    pre_process_error
                )

                logger.debug(
                    "Run failed before row processing",
                    exc_info=True,
                    extra=file_only()
                )

            backup_path = excel_manager.create_backup()

            if backup_path:

                logger.debug(
                    "Workbook backed up to %s",
                    backup_path,
                    extra=file_only()
                )

            logger.info(
                "%s | Processed: %d :::: Skipped: %d :::: Failed: %d",
                format_context("Summary"),
                result["processed"],
                result["skipped"],
                result["failed"]
            )

        logger.info(
            "Velero automation completed!"
        )

        logger.info(
            "Bye!"
        )

    except Exception as exception:

        exit_code = 1

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

        logger.info(
            "Velero automation completed!"
        )

        logger.info(
            "Bye!"
        )

    finally:

        wait_for_exit(
            _pause_on_exit(config)
        )

    return exit_code


def _write_pre_pagerduty_failure(
    excel_manager,
    config,
    logger,
    target_date,
    error_message
):

    if not excel_manager or not target_date or not config:
        return

    try:

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=config,
            pagerduty_client=None,
            logger=logger,
            ledger=None
        )

        processor.mark_unprocessed_failed(
            target_date,
            error_message
        )

    except Exception as write_error:

        logger.error(
            "Failure could not be written to the sheet: %s",
            write_error
        )


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
