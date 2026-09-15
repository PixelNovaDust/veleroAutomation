import json
import os
import tempfile
from datetime import datetime, timedelta

from app.paths import ensure_directory, resolve_path
from app.system import get_current_user


LEDGER_VERSION = 1

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ProcessedLedger:
    """
    Record of every incident this automation has raised.

    The workbook is the source of truth, but it lives on a
    shared folder where a stale Excel session can wipe freshly
    written cells. This ledger is a second copy of the same
    facts, so a lost cell costs a value in the sheet instead of
    a duplicate page to the on-call engineer.
    """

    def __init__(
        self,
        file_path,
        logger,
        enabled=True,
        restore_missing=True,
        retention_days=90
    ):
        self.file_path = file_path
        self.logger = logger
        self.enabled = enabled
        self.restore_missing = restore_missing
        self.retention_days = retention_days

        self.entries = {}
        self.dirty = False

    @classmethod
    def from_config(cls, config, logger):

        settings = (
            config
            .get("processing", {})
            .get("ledger", {})
        )

        base_directory = (
            config
            .get("runtime", {})
            .get("base_directory")
        )

        return cls(
            file_path=resolve_path(
                settings.get("file_path")
                or "data/processed-ledger.json",
                base_directory
            ),
            logger=logger,
            enabled=settings.get("enabled", True),
            restore_missing=settings.get("restore_missing", True),
            retention_days=settings.get("retention_days", 90)
        )

    @staticmethod
    def build_key(namespace, date_value):
        """
        Identify a row by namespace and its backup date so a
        namespace that comes back next week is still processed.
        """

        namespace = str(namespace or "").strip().lower()

        if isinstance(date_value, datetime):
            date_part = date_value.strftime("%Y-%m-%d")

        else:
            date_part = str(date_value or "").strip().lower()

        return "{}|{}".format(namespace, date_part)

    def load(self):

        if not self.enabled:
            return self

        if not os.path.exists(self.file_path):
            return self

        try:

            with open(self.file_path, "r", encoding="utf-8") as file:
                payload = json.load(file)

        except (OSError, ValueError) as error:

            self.logger.warning(
                "Processed ledger could not be read, "
                "starting a new one: %s",
                error
            )

            return self

        entries = payload.get("entries")

        if isinstance(entries, dict):
            self.entries = entries

        self._prune()

        return self

    def find(self, namespace, date_value):

        if not self.enabled:
            return None

        return self.entries.get(
            self.build_key(namespace, date_value)
        )

    def record(
        self,
        namespace,
        date_value,
        dedup_key,
        incident_date,
        source="automation"
    ):

        if not self.enabled or not dedup_key:
            return

        key = self.build_key(namespace, date_value)

        if key in self.entries:
            return

        if isinstance(incident_date, datetime):
            incident_date = incident_date.strftime(DATE_FORMAT)

        self.entries[key] = {
            "namespace": str(namespace or "").strip(),
            "date": str(date_value or "").strip(),
            "dedup_key": str(dedup_key),
            "incident_date": str(incident_date or ""),
            "recorded_at": datetime.now().strftime(DATE_FORMAT),
            "recorded_by": get_current_user(),
            "source": source
        }

        self.dirty = True

    def save(self):
        """
        Persist the ledger. A failure here is logged and never
        stops the run, because the workbook is still updated.
        """

        if not self.enabled or not self.dirty:
            return False

        payload = {
            "version": LEDGER_VERSION,
            "updated_at": datetime.now().strftime(DATE_FORMAT),
            "entries": self.entries
        }

        try:

            ensure_directory(
                os.path.dirname(self.file_path)
            )

            handle, temp_path = tempfile.mkstemp(
                prefix=".velero-ledger-",
                dir=os.path.dirname(self.file_path)
            )

            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)

            # The ledger sits on the shared folder, so every
            # engineer has to be able to read it. A temp file is
            # created private to its owner.
            os.chmod(temp_path, 0o644)

            os.replace(temp_path, self.file_path)

            self.dirty = False

            return True

        except OSError as error:

            self.logger.warning(
                "Processed ledger could not be saved: %s",
                error
            )

            return False

    def _prune(self):

        try:
            retention_days = int(self.retention_days)

        except (TypeError, ValueError):
            return

        if retention_days <= 0:
            return

        cutoff = datetime.now() - timedelta(days=retention_days)

        for key in list(self.entries.keys()):

            entry = self.entries.get(key) or {}

            recorded_at = entry.get("recorded_at")

            if not recorded_at:
                continue

            try:
                recorded = datetime.strptime(
                    recorded_at,
                    DATE_FORMAT
                )

            except ValueError:
                continue

            if recorded < cutoff:

                del self.entries[key]

                self.dirty = True
