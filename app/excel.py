import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta

from openpyxl import load_workbook

from app.excel_lock import (
    close_local_workbook,
    describe_owner,
    wait_until_writable
)
from app.dates import dates_match, normalize_date
from app.paths import ensure_directory, resolve_path
from app.processing import is_processed


REQUIRED_COLUMNS = [
    "Namespace",
    "Environment Version",
    "Environment Type",
    "Date",
    "Prod/Non-Prod",
    "Caller",
    "Status",
    "Final Status",
    "Processed",
    "Incident Date",
    "Incident Comment"
]


class ExcelLockedError(RuntimeError):
    pass


class ExcelManager:

    def __init__(
        self,
        file_path,
        table_name,
        logger=None,
        settings=None,
        base_directory=None,
        confirm=None
    ):
        self.file_path = file_path
        self.table_name = table_name
        self.logger = logger
        self.settings = settings or {}
        self.base_directory = base_directory
        self.confirm = confirm

        self.workbook = None
        self.sheet = None
        self.table = None
        self.headers = None

    @classmethod
    def from_config(cls, config, logger, confirm=None):

        excel_settings = config.get("excel", {})

        base_directory = (
            config
            .get("runtime", {})
            .get("base_directory")
        )

        return cls(
            file_path=resolve_path(
                excel_settings.get("file_path"),
                base_directory
            ),
            table_name=excel_settings.get("table_name"),
            logger=logger,
            settings=excel_settings,
            base_directory=base_directory,
            confirm=confirm
        )

    def _log(self, level, message, *args):

        if self.logger:
            getattr(self.logger, level)(message, *args)

    def _setting(self, name, default):

        value = self.settings.get(name, default)

        if value is None:
            return default

        return value

    def preflight(self):
        """
        Make sure the workbook can be written before any incident
        is raised, and report anybody else holding it open.
        """

        if not os.path.exists(self.file_path):

            raise FileNotFoundError(
                "Excel file not found: {}".format(
                    self.file_path
                )
            )

        if not os.access(self.file_path, os.W_OK):

            raise ExcelLockedError(
                "Excel file is read only for this account: "
                "{}".format(self.file_path)
            )

        holder, owner = describe_owner(self.file_path)

        if holder == "other":

            if self._setting("warn_when_opened_by_others", True):

                self._log(
                    "warning",
                    "Workbook is currently open by %s. "
                    "Updates written now can be overwritten when "
                    "that session saves, so ask them to close it "
                    "without saving.",
                    owner
                )

            return

        if holder != "self":
            return

        self._log(
            "warning",
            "Workbook is open on this machine%s, "
            "which blocks the update.",
            " by {}".format(owner) if owner else ""
        )

        if not self._setting("close_local_workbook", True):
            self._raise_locked()

        if self._setting("confirm_before_close", True):

            question = (
                "Close '{}' in Excel now? "
                "Unsaved changes will be saved first".format(
                    os.path.basename(self.file_path)
                )
            )

            if not self._ask(question):
                self._raise_locked()

        if not close_local_workbook(self.file_path, self.logger):
            self._raise_locked()

        if not wait_until_writable(self.file_path):
            self._raise_locked()

        self._log(
            "info",
            "Workbook was saved and closed in Excel."
        )

    def _ask(self, question):

        if not self.confirm:
            return False

        return bool(self.confirm(question))

    def _raise_locked(self):

        raise ExcelLockedError(
            "Excel file is open on this machine and cannot be "
            "updated: {}. Close it in Excel and run again.".format(
                self.file_path
            )
        )

    def validate_file(self):

        if not os.path.exists(self.file_path):

            raise FileNotFoundError(
                "Excel file not found: {}".format(
                    self.file_path
                )
            )

        try:

            self.load()

            self.validate_columns()

        except Exception as error:

            raise RuntimeError(
                "Excel validation failed: {}".format(
                    error
                )
            )

    def load(self, force=False):
        """
        Open the workbook once and reuse it. Parsing a large
        workbook repeatedly is the slowest part of a run.
        """

        if self.sheet is not None and not force:
            return self.sheet

        if not os.path.exists(self.file_path):
            raise FileNotFoundError(
                "Excel file not found: {}".format(self.file_path)
            )

        self.workbook = load_workbook(self.file_path)
        self.sheet = None
        self.table = None
        self.headers = None

        for worksheet in self.workbook.worksheets:
            for table in worksheet.tables.values():

                if table.name == self.table_name:
                    self.sheet = worksheet
                    self.table = table
                    return self.sheet

        raise ValueError(
            "Excel table '{}' was not found.".format(
                self.table_name
            )
        )

    def get_headers(self):

        headers = {}

        for cell in self.sheet[1]:
            if cell.value:
                headers[str(cell.value).strip()] = cell.column

        return headers

    def validate_columns(self):

        if self.headers:
            return self.headers

        headers = self.get_headers()

        missing = [
            column
            for column in REQUIRED_COLUMNS
            if column not in headers
        ]

        if missing:
            raise ValueError(
                "Missing required Excel columns: {}".format(
                    ", ".join(missing)
                )
            )

        self.headers = headers

        return headers

    def count_rows_for_date(self, target_date):
        """
        Return how many rows exist for the selected date,
        regardless of processed status.
        """

        sheet = self.load()
        headers = self.validate_columns()

        date_column = headers["Date"]
        count = 0

        for row_number in range(2, sheet.max_row + 1):

            date_value = sheet.cell(
                row=row_number,
                column=date_column
            ).value

            if dates_match(date_value, target_date):
                count += 1

        return count

    def collect_unprocessed_dates(self, processed_value="Yes"):
        """
        Return distinct normalised dates that still have at least
        one row not marked as processed.
        """

        sheet = self.load()
        headers = self.validate_columns()

        date_column = headers["Date"]
        processed_column = headers["Processed"]

        dates = set()

        for row_number in range(2, sheet.max_row + 1):

            processed = sheet.cell(
                row=row_number,
                column=processed_column
            ).value

            if is_processed(processed, processed_value):
                continue

            date_value = sheet.cell(
                row=row_number,
                column=date_column
            ).value

            normalized = normalize_date(date_value)

            if normalized:
                dates.add(normalized)

        return sorted(dates)

    def save(self):
        """
        Write the workbook, retrying while the file is locked.

        A lock here is usually a sync client or a virus scanner
        holding the file for a moment, so a short retry loop
        avoids losing a row that was already raised in
        PagerDuty.
        """

        attempts = max(
            1,
            int(self._setting("save_retry_attempts", 5))
        )

        delay_seconds = max(
            0,
            float(self._setting("save_retry_delay_seconds", 3))
        )

        last_error = None

        for attempt in range(1, attempts + 1):

            try:

                self._write()

                return True

            except PermissionError as error:

                last_error = error

                if attempt < attempts:

                    self._log(
                        "warning",
                        "Excel file is locked, retrying in %ss "
                        "(attempt %d of %d)",
                        int(delay_seconds),
                        attempt,
                        attempts
                    )

                    time.sleep(delay_seconds)

        raise ExcelLockedError(
            "Excel file could not be saved after {} attempts, "
            "it is open or locked: {} ({})".format(
                attempts,
                self.file_path,
                last_error
            )
        )

    def _write(self):

        if not self._setting("safe_save", True):

            self.workbook.save(self.file_path)

            return

        # The workbook is built outside the synced folder and
        # then copied over the original. Copying keeps the
        # existing file identity, which matters for a shared
        # OneDrive workbook, and keeps a partial write from
        # being the only copy of the data.
        temp_path = os.path.join(
            tempfile.gettempdir(),
            ".velero-{}-{}".format(
                os.getpid(),
                os.path.basename(self.file_path)
            )
        )

        self.workbook.save(temp_path)

        try:

            shutil.copyfile(temp_path, self.file_path)

        finally:

            try:
                os.remove(temp_path)

            except OSError:
                pass

    def create_backup(self):
        """
        Keep a timestamped copy of the updated workbook so a run
        can be recovered if a stale session overwrites the file.
        """

        backup_settings = self._setting("backup", {}) or {}

        if not backup_settings.get("enabled", True):
            return None

        directory = resolve_path(
            backup_settings.get("directory") or "backups",
            self.base_directory
        )

        stem, extension = os.path.splitext(
            os.path.basename(self.file_path)
        )

        backup_path = os.path.join(
            directory,
            "{}-{}{}".format(
                stem,
                datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                extension
            )
        )

        try:

            ensure_directory(directory)

            shutil.copy2(self.file_path, backup_path)

        except OSError as error:

            self._log(
                "warning",
                "Backup copy could not be created: %s",
                error
            )

            return None

        self._prune_backups(
            directory,
            stem,
            extension,
            backup_settings.get("retention_days")
        )

        return backup_path

    def _prune_backups(self, directory, stem, extension, retention_days):

        try:
            retention_days = int(retention_days)

        except (TypeError, ValueError):
            return

        if retention_days <= 0:
            return

        cutoff = datetime.now() - timedelta(
            days=retention_days
        )

        try:
            entries = os.listdir(directory)

        except OSError:
            return

        for entry in entries:

            if not entry.startswith(stem + "-"):
                continue

            if not entry.endswith(extension):
                continue

            path = os.path.join(directory, entry)

            try:

                modified = datetime.fromtimestamp(
                    os.path.getmtime(path)
                )

                if modified < cutoff:
                    os.remove(path)

            except OSError:
                continue
