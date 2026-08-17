from datetime import datetime

from app.config import load_config
from app.excel import ExcelManager
from app.processor import VeleroProcessor
from app.console import startup, wait_for_exit
from app.logger import setup_logger, format_context

from app.pagerduty.client import PagerDutyClient
from app.pagerduty.incidents import PagerDutyIncidents


def main():

    logger = setup_logger()

    try:

        startup(logger)

        execution_time = datetime.now()

        logger.info(
            "Started at  : %s",
            execution_time.strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        )

        config = load_config()

        file_path = config["excel"]["file_path"]
        table_name = config["excel"]["table_name"]

        logger.info(
            "Using Excel file   : %s",
            file_path
        )

        logger.info(
            "Excel Table        : %s",
            table_name
        )
        
        # Excel validation
        excel_manager = ExcelManager(
            file_path=file_path,
            table_name=table_name
        )

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

        logger.debug(
            "PagerDuty API is accessible"
        )
        
        # PagerDuty incident manager
        pagerduty_incidents = PagerDutyIncidents(
            client=pagerduty_client,
            logger=logger
        )
        
        # Processor
        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=config,
            pagerduty_client=pagerduty_incidents,
            logger=logger
        )

        result = processor.process()
        
        # Summary
        logger.debug(
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

        logger.error(
            "%s",
            exception
        )

    finally:

        wait_for_exit()


if __name__ == "__main__":
    main()