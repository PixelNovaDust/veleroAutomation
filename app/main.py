import msvcrt
from datetime import datetime

from app.config import load_config
from app.excel import ExcelManager
from app.processor import VeleroProcessor
from app.console import startup, error, summary
from app.logger import setup_logger

from app.pagerduty.client import PagerDutyClient
from app.pagerduty.incidents import PagerDutyIncidents


def wait_for_exit():

    print()
    print("Press any key to exit...")
    msvcrt.getch()


def main():

    logger = setup_logger()

    try:

        startup()

        logger.info(
            "Velero automation started."
        )

        execution_time = datetime.now()

        config = load_config()

        file_path = config["excel"]["file_path"]
        table_name = config["excel"]["table_name"]

        print(
            "Last performed at : {}".format(
                execution_time.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )
        )

        print(
            "Excel file        : {}".format(
                file_path
            )
        )

        print(
            "Excel table       : {}".format(
                table_name
            )
        )

        print()

        excel_manager = ExcelManager(
            file_path=file_path,
            table_name=table_name
        )

        print("Validating Excel file...")

        excel_manager.validate_file()

        print("  ✓ Excel file, table and columns validated.")

        logger.info(
            "Excel file validated successfully: %s",
            file_path
        )

        pagerduty_client = PagerDutyClient(
            config=config,
            logger=logger
        )

        print("Validating PagerDuty API...")

        pagerduty_client.validate_connection()

        print("  ✓ PagerDuty API is accessible.")

        logger.info(
            "PagerDuty API validated successfully."
        )

        pagerduty_incidents = PagerDutyIncidents(
            client=pagerduty_client,
            logger=logger
        )

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=config,
            pagerduty_client=pagerduty_incidents,
            logger=logger
        )


        result = processor.process()

        summary(
            processed_count=result["processed"],
            failed_count=result["failed"],
            skipped_count=result["skipped"]
        )

        logger.info(
            "Velero automation completed. "
            "Processed=%s Failed=%s Skipped=%s",
            result["processed"],
            result["failed"],
            result["skipped"]
        )

        wait_for_exit()

    except Exception as exception:

        logger.exception(
            "Velero automation failed."
        )

        error(str(exception))

        wait_for_exit()


if __name__ == "__main__":
    main()