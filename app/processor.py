from datetime import datetime

from app import console


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
        headers = self.excel_manager.validate_columns()

        processed_count = 0
        failed_count = 0
        skipped_count = 0

        processed_value = self.config[
            "processing"
        ].get("processed_value", "Yes")

        failed_value = self.config[
            "processing"
        ].get("failed_value", "No")

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

            # Skip completely empty rows
            if not namespace and not caller and not status:
                continue

            # Only process new rows
            if (
                incident_id in (None, "")
                and processed in (None, "")
                and incident_date in (None, "")
            ):

                try:

                    console.processing(
                        namespace=namespace
                    )

                    self.logger.info(
                        "Processing namespace: %s",
                        namespace
                    )

                    # Validate required fields
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

                    real_incident_id = result.get(
                        "incident_id"
                    )

                    if not real_incident_id:
                        raise ValueError(
                            "PagerDuty did not return an incident ID."
                        )

                    current_time = datetime.now()

                    # Update Incident ID
                    sheet.cell(
                        row=row_number,
                        column=headers["Incident ID"]
                    ).value = real_incident_id

                    # Update Processed
                    sheet.cell(
                        row=row_number,
                        column=headers["Processed"]
                    ).value = processed_value

                    # Update Incident Date
                    sheet.cell(
                        row=row_number,
                        column=headers["Incident Date"]
                    ).value = current_time

                    # Update Incident Comment
                    sheet.cell(
                        row=row_number,
                        column=headers["Incident Comment"]
                    ).value = (
                        "PagerDuty incident created successfully."
                    )

                    processed_count += 1

                    console.processed(
                        namespace=namespace,
                        status=status,
                        incident_id=real_incident_id,
                        incident_date=current_time
                    )

                    self.logger.info(
                        "Processed successfully: %s | Incident ID: %s",
                        namespace,
                        real_incident_id
                    )

                except Exception as exception:

                    failed_count += 1

                    error_message = str(exception)
                    current_time = datetime.now()

                    # Update failure information
                    sheet.cell(
                        row=row_number,
                        column=headers["Processed"]
                    ).value = failed_value

                    sheet.cell(
                        row=row_number,
                        column=headers["Incident Date"]
                    ).value = current_time

                    sheet.cell(
                        row=row_number,
                        column=headers["Incident Comment"]
                    ).value = error_message

                    console.failed(
                        namespace=namespace,
                        reason=error_message,
                        comment=error_message
                    )

                    self.logger.exception(
                        "Failed processing namespace: %s",
                        namespace
                    )

            else:

                skipped_count += 1

                console.skipped(
                    namespace=namespace,
                    reason=(
                        "Already processed or required "
                        "fields are populated."
                    )
                )

                self.logger.info(
                    "Skipped namespace: %s",
                    namespace
                )

        # Save Excel after all rows are processed
        self.excel_manager.save()

        return {
            "processed": processed_count,
            "failed": failed_count,
            "skipped": skipped_count
        }