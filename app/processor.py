from datetime import datetime

from app.logger import file_only, format_context


def _as_date(value):
    """Keep a restored date a real date so the cell format holds."""

    if isinstance(value, datetime):
        return value

    if not value:
        return value

    try:
        return datetime.strptime(
            str(value),
            "%Y-%m-%d %H:%M:%S"
        )

    except ValueError:
        return value


class VeleroProcessor:

    def __init__(
        self,
        excel_manager,
        config,
        pagerduty_client,
        logger,
        ledger=None
    ):
        self.excel_manager = excel_manager
        self.config = config
        self.pagerduty_client = pagerduty_client
        self.logger = logger
        self.ledger = ledger

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

            environment = sheet.cell(
                row=row_number,
                column=headers["Prod/Non-Prod"]
            ).value

            status = sheet.cell(
                row=row_number,
                column=headers["Status"]
            ).value

            caller = sheet.cell(
                row=row_number,
                column=headers["Caller"]
            ).value

            backup_date = sheet.cell(
                row=row_number,
                column=headers["Date"]
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

            incident_comment = sheet.cell(
                row=row_number,
                column=headers["Incident Comment"]
            ).value

            context = format_context(namespace)

            # Empty row
            if (
                not namespace
                and not caller
                and not status
                and not environment
            ):
                continue

            # Skip decom rows
            if (
                incident_comment
                and "decom" in str(
                    incident_comment
                ).lower()
            ):

                skipped_count += 1

                self.logger.skipped(
                    "%s | Decom mentioned in comment",
                    context
                )

                continue

            # Already processed
            if not (
                incident_id in (None, "")
                and processed in (None, "")
                and incident_date in (None, "")
            ):

                skipped_count += 1

                self._remember(
                    namespace,
                    backup_date,
                    incident_id,
                    incident_date,
                    source="sheet"
                )

                self.logger.skipped(
                    "%s | Already processed on %s",
                    context,
                    incident_date
                )

                continue

            # Processed in an earlier run whose values were lost
            # from the sheet, most likely by another engineer's
            # open session overwriting them.
            recovered = self._recover(
                sheet,
                headers,
                row_number,
                namespace,
                backup_date,
                processed_value,
                context
            )

            if recovered:

                skipped_count += 1

                continue

            try:

                self.logger.info(
                    "%s | Initialized process",
                    context
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

                # Recorded before the workbook is touched, so a
                # failure to write the sheet can never turn into
                # a duplicate incident on the next run.
                self._remember(
                    namespace,
                    backup_date,
                    real_incident_id,
                    current_time
                )

                processed_count += 1

                self.logger.success(
                    "%s | Incident Triggered to %s - %s",
                    context,
                    caller,
                    real_incident_id
                )

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

                # Save successful processing
                try:

                    self.excel_manager.save()

                    self.logger.info(
                        "%s | Sheet updated",
                        context
                    )

                except Exception as save_error:

                    self.logger.error(
                        "%s | Incident %s was raised but the "
                        "sheet could not be updated: %s",
                        context,
                        real_incident_id,
                        save_error
                    )

            except Exception as exception:

                failed_count += 1

                error_message = str(
                    exception
                )

                current_time = datetime.now()

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

                self.logger.error(
                    "%s | %s",
                    context,
                    error_message
                )

                self.logger.debug(
                    "%s | Failure detail",
                    context,
                    exc_info=True,
                    extra=file_only()
                )

                try:
                    self.excel_manager.save()

                except Exception as save_error:

                    self.logger.error(
                        "%s | Failure could not be written to "
                        "the sheet: %s",
                        context,
                        save_error
                    )

        return {
            "processed": processed_count,
            "failed": failed_count,
            "skipped": skipped_count
        }

    def _remember(
        self,
        namespace,
        backup_date,
        incident_id,
        incident_date,
        source="automation"
    ):

        if not self.ledger or not incident_id:
            return

        self.ledger.record(
            namespace=namespace,
            date_value=backup_date,
            incident_id=incident_id,
            incident_date=incident_date,
            source=source
        )

        self.ledger.save()

    def _recover(
        self,
        sheet,
        headers,
        row_number,
        namespace,
        backup_date,
        processed_value,
        context
    ):
        """
        Put back the incident details of a row this automation
        already handled, and report it as skipped.
        """

        if not self.ledger:
            return False

        entry = self.ledger.find(namespace, backup_date)

        if not entry:
            return False

        known_id = entry.get("incident_id")
        known_date = entry.get("incident_date")

        if not self.ledger.restore_missing:

            self.logger.skipped(
                "%s | Already triggered as %s on %s, "
                "sheet no longer shows it",
                context,
                known_id,
                known_date
            )

            return True

        sheet.cell(
            row=row_number,
            column=headers["Incident ID"]
        ).value = known_id

        sheet.cell(
            row=row_number,
            column=headers["Processed"]
        ).value = processed_value

        sheet.cell(
            row=row_number,
            column=headers["Incident Date"]
        ).value = _as_date(known_date)

        self.logger.skipped(
            "%s | Already triggered as %s on %s, "
            "restored into the sheet",
            context,
            known_id,
            known_date
        )

        try:
            self.excel_manager.save()

        except Exception as save_error:

            self.logger.error(
                "%s | Restored details could not be written: %s",
                context,
                save_error
            )

        return True
