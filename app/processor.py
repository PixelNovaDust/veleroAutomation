import time
from datetime import datetime

from app.dates import as_datetime, dates_match, normalize_date
from app.logger import file_only, format_context
from app.processing import is_processed


def _read_setting(processing, key, default):

    value = processing.get(key, default)

    if value is None or value == "":
        return default

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

    def process(self, target_date):

        sheet = self.excel_manager.load()

        headers = (
            self.excel_manager
            .validate_columns()
        )

        processing = self.config.get("processing", {})

        processed_value = processing.get(
            "processed_value",
            "Yes"
        )

        failed_value = processing.get(
            "failed_value",
            "No"
        )

        target_date = normalize_date(target_date)

        if not target_date:
            raise ValueError(
                "Target date is not valid."
            )

        processed_count = 0
        failed_count = 0
        skipped_count = 0
        failed_rows = []

        matching_rows = self._matching_rows(
            sheet,
            headers,
            target_date
        )

        for row_number in matching_rows:

            outcome = self._handle_row(
                sheet,
                headers,
                row_number,
                target_date,
                processed_value,
                failed_value
            )

            if outcome == "processed":
                processed_count += 1

            elif outcome == "failed":
                failed_count += 1
                failed_rows.append(row_number)

            elif outcome == "skipped":
                skipped_count += 1

        retry_attempts = int(
            _read_setting(
                processing,
                "failed_retry_attempts",
                1
            )
        )

        retry_delay_seconds = float(
            _read_setting(
                processing,
                "failed_retry_delay_seconds",
                2
            )
        )

        for attempt in range(1, retry_attempts + 1):

            if not failed_rows:
                break

            self.logger.info(
                "Retrying %d failed row(s) "
                "(attempt %d of %d)",
                len(failed_rows),
                attempt,
                retry_attempts
            )

            if retry_delay_seconds > 0:
                time.sleep(retry_delay_seconds)

            still_failed = []

            for row_number in failed_rows:

                outcome = self._handle_row(
                    sheet,
                    headers,
                    row_number,
                    target_date,
                    processed_value,
                    failed_value,
                    is_retry=True
                )

                if outcome == "processed":
                    processed_count += 1
                    failed_count -= 1

                elif outcome == "failed":
                    still_failed.append(row_number)

                elif outcome == "skipped":
                    skipped_count += 1

            failed_rows = still_failed

        return {
            "processed": processed_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "target_date": target_date
        }

    def _matching_rows(self, sheet, headers, target_date):

        rows = []

        for row_number in range(
            2,
            sheet.max_row + 1
        ):

            backup_date = sheet.cell(
                row=row_number,
                column=headers["Date"]
            ).value

            if dates_match(backup_date, target_date):
                rows.append(row_number)

        return rows

    def _handle_row(
        self,
        sheet,
        headers,
        row_number,
        target_date,
        processed_value,
        failed_value,
        is_retry=False
    ):
        """
        Process one row and return processed, failed, or skipped.
        """

        namespace = sheet.cell(
            row=row_number,
            column=headers["Namespace"]
        ).value

        backup_date = sheet.cell(
            row=row_number,
            column=headers["Date"]
        ).value

        processed = sheet.cell(
            row=row_number,
            column=headers["Processed"]
        ).value

        incident_date = sheet.cell(
            row=row_number,
            column=headers["Incident Date"]
        ).value

        context = format_context(namespace or row_number)

        if not dates_match(backup_date, target_date):
            return "skipped"

        if is_retry:

            if is_processed(processed, processed_value):
                return "skipped"

        else:

            if is_processed(processed, processed_value):

                self.logger.skipped(
                    "%s | Already processed on %s",
                    context,
                    incident_date
                )

                return "skipped"

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
                return "skipped"

        try:

            if is_retry:

                self.logger.info(
                    "%s | Retrying failed row",
                    context
                )

            else:

                self.logger.info(
                    "%s | Initialized process",
                    context
                )

            if not self.pagerduty_client:

                raise ValueError(
                    "PagerDuty client is not configured."
                )

            result = (
                self.pagerduty_client
                .create_incident(
                    namespace=namespace,
                    event_date=backup_date
                )
            )

            current_time = datetime.now()
            response_status = result.get("status")
            response_message = result.get("message", "")
            dedup_key = result.get("dedup_key")

            if (
                response_status == "success"
                and dedup_key
            ):

                self._remember(
                    namespace,
                    backup_date,
                    dedup_key,
                    current_time
                )

                self.logger.success(
                    "%s | Incident Triggered",
                    context
                )

                sheet.cell(
                    row=row_number,
                    column=headers["Processed"]
                ).value = processed_value

                sheet.cell(
                    row=row_number,
                    column=headers["Incident Date"]
                ).value = current_time

                sheet.cell(
                    row=row_number,
                    column=headers["Incident Comment"]
                ).value = (
                    response_message
                    or "PagerDuty event was not accepted."
                )

            else:

                failure_message = (
                    response_message
                    or "PagerDuty event was not accepted."
                )

                self._write_row_failure(
                    sheet,
                    headers,
                    row_number,
                    failed_value,
                    current_time,
                    failure_message
                )

                self.logger.error(
                    "%s | %s",
                    context,
                    failure_message
                )

                self._save_row(context)

                return "failed"

            self._save_row(context)

            return "processed"

        except Exception as exception:

            error_message = str(exception)

            current_time = datetime.now()

            self._write_row_failure(
                sheet,
                headers,
                row_number,
                failed_value,
                current_time,
                error_message
            )

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

            self._save_row(context)

            return "failed"

    def _save_row(self, context):

        try:

            self.excel_manager.save()

            self.logger.info(
                "%s | Sheet updated",
                context
            )

        except Exception as save_error:

            self.logger.error(
                "%s | Row update could not be saved: %s",
                context,
                save_error
            )

    def mark_unprocessed_failed(self, target_date, error_message):
        """
        Write a run-level failure to every unprocessed row for
        the selected date, for example when PagerDuty cannot be
        initialised before row processing starts.
        """

        sheet = self.excel_manager.load()

        headers = (
            self.excel_manager
            .validate_columns()
        )

        processing = self.config.get("processing", {})

        processed_value = processing.get(
            "processed_value",
            "Yes"
        )

        failed_value = processing.get(
            "failed_value",
            "No"
        )

        target_date = normalize_date(target_date)

        if not target_date:
            return 0

        current_time = datetime.now()
        updated_count = 0

        for row_number in range(
            2,
            sheet.max_row + 1
        ):

            backup_date = sheet.cell(
                row=row_number,
                column=headers["Date"]
            ).value

            processed = sheet.cell(
                row=row_number,
                column=headers["Processed"]
            ).value

            if not dates_match(backup_date, target_date):
                continue

            if is_processed(processed, processed_value):
                continue

            namespace = sheet.cell(
                row=row_number,
                column=headers["Namespace"]
            ).value

            context = format_context(namespace or row_number)

            self._write_row_failure(
                sheet,
                headers,
                row_number,
                failed_value,
                current_time,
                error_message
            )

            updated_count += 1

            self.logger.error(
                "%s | %s",
                context,
                error_message
            )

        if updated_count:

            try:
                self.excel_manager.save()

            except Exception as save_error:

                self.logger.error(
                    "Pre-PagerDuty failure could not be written "
                    "to the sheet: %s",
                    save_error
                )

        return updated_count

    def _write_row_failure(
        self,
        sheet,
        headers,
        row_number,
        failed_value,
        incident_date,
        error_message
    ):

        sheet.cell(
            row=row_number,
            column=headers["Processed"]
        ).value = failed_value

        sheet.cell(
            row=row_number,
            column=headers["Incident Date"]
        ).value = incident_date

        sheet.cell(
            row=row_number,
            column=headers["Incident Comment"]
        ).value = error_message

    def _remember(
        self,
        namespace,
        backup_date,
        dedup_key,
        incident_date,
        source="automation"
    ):

        if not self.ledger or not dedup_key:
            return

        self.ledger.record(
            namespace=namespace,
            date_value=backup_date,
            dedup_key=dedup_key,
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
        Put back processing details of a row this automation
        already handled, and report it as skipped.
        """

        if not self.ledger:
            return False

        entry = self.ledger.find(namespace, backup_date)

        if not entry:
            return False

        known_dedup_key = (
            entry.get("dedup_key")
            or entry.get("incident_id")
        )
        known_date = entry.get("incident_date")

        if not self.ledger.restore_missing:

            self.logger.skipped(
                "%s | Already triggered as %s on %s, "
                "sheet no longer shows it",
                context,
                known_dedup_key,
                known_date
            )

            return True

        sheet.cell(
            row=row_number,
            column=headers["Processed"]
        ).value = processed_value

        sheet.cell(
            row=row_number,
            column=headers["Incident Date"]
        ).value = as_datetime(known_date)

        self.logger.skipped(
            "%s | Already triggered as %s on %s, "
            "restored into the sheet",
            context,
            known_dedup_key,
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
