from datetime import datetime
from app.logger import format_context

class VeleroProcessor:

    def __init__(
        self,
        excel_manager,
        config,
        pagerduty_client,
        logger
    ):
        self.excel_manager = excel_manager
        self.config = config
        self.pagerduty_client = pagerduty_client
        self.logger = logger

    def process(self):

        sheet = self.excel_manager.load()

        headers = (
            self.excel_manager
            .validate_columns()
        )

        processed_count = 0
        failed_count = 0
        skipped_count = 0

        processed_value = (
            self.config["processing"]
            .get("processed_value", "Yes")
        )

        failed_value = (
            self.config["processing"]
            .get("failed_value", "No")
        )

        for row_number in range(
            2,
            sheet.max_row + 1
        ):

            namespace = sheet.cell(
                row=row_number,
                column=headers["Namespace"]
            ).value

            status = sheet.cell(
                row=row_number,
                column=headers["Status"]
            ).value

            caller = sheet.cell(
                row=row_number,
                column=headers["Caller"]
            ).value

            incident_id = sheet.cell(
                row=row_number,
                column=headers["Incident ID"]
            ).value

            processed = sheet.cell(
                row=row_number,
                column=headers["Processed"]
            ).value

            incident_date = sheet.cell(
                row=row_number,
                column=headers["Incident Date"]
            ).value

            # Empty row
            if (
                not namespace
                and not caller
                and not status
            ):
                continue

            # Already processed
            if not (
                incident_id in (None, "")
                and processed in (None, "")
                and incident_date in (None, "")
            ):

                skipped_count += 1

                self.logger.skipped(
                    "%s | Already processed on %s",
                    format_context(namespace),
                    incident_date
                )

                continue

            try:

                self.logger.info(
                    "%s | Initialized process",
                    format_context(namespace)
                )

                # Required fields
                if not namespace:
                    raise ValueError(
                        "Namespace is empty."
                    )

                if not caller:
                    raise ValueError(
                        "Caller is empty."
                    )

                if not status:
                    raise ValueError(
                        "Status is empty."
                    )

                # Create PagerDuty incident
                result = (
                    self.pagerduty_client
                    .create_incident(
                        caller=caller,
                        namespace=namespace,
                        description=status
                    )
                )

                real_incident_id = (
                    result.get("incident_id")
                )

                if not real_incident_id:
                    raise ValueError(
                        "PagerDuty did not return "
                        "an incident ID."
                    )

                current_time = datetime.now()

                # Incident ID
                sheet.cell(
                    row=row_number,
                    column=headers["Incident ID"]
                ).value = real_incident_id

                # Processed
                sheet.cell(
                    row=row_number,
                    column=headers["Processed"]
                ).value = processed_value

                # Incident Date
                sheet.cell(
                    row=row_number,
                    column=headers["Incident Date"]
                ).value = current_time

                # IMPORTANT:
                # Incident Comment is NOT updated
                # on successful processing.

                processed_count += 1

                self.logger.success(
                    "%s | Incident Triggered to %s - %s",
                    format_context(namespace),
                    caller,
                    real_incident_id
                )

                self.excel_manager.save()

                self.logger.info(
                    "%s | Updated in Sheet",
                    format_context(namespace)
                )

            except Exception as exception:

                failed_count += 1

                error_message = str(
                    exception
                )

                current_time = datetime.now()

                # Failed processing
                sheet.cell(
                    row=row_number,
                    column=headers["Processed"]
                ).value = failed_value

                sheet.cell(
                    row=row_number,
                    column=headers["Incident Date"]
                ).value = current_time

                # Comment ONLY on error
                sheet.cell(
                    row=row_number,
                    column=headers["Incident Comment"]
                ).value = error_message

                self.excel_manager.save()

                self.logger.error(
                    "%s | %s",
                    format_context(namespace),
                    error_message
                )

        return {
            "processed": processed_count,
            "failed": failed_count,
            "skipped": skipped_count
        }