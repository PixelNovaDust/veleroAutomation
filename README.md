# Velero Automation

Reads the Velero tracking workbook, finds the matching PagerDuty
user and service for each pending row, raises the incident and
writes the result back into the sheet.

## Layout

Everything the automation reads or writes lives next to the entry
point, which is the repository root when run from source with
`VeleroAutomation.py` and the folder holding `VeleroAutomation.exe`
once built.

```
VeleroAutomation.exe      the automation
config/config.json        settings, edited by hand
logs/                     one log file per day
data/                     record of incidents already raised
backups/                  timestamped copies of the workbook
```

## Running

From source:

```bash
pip install -r requirements.txt
python VeleroAutomation.py
```

As an executable (Windows):

```bash
pyinstaller velero.spec
```

Copy `dist/VeleroAutomation.exe` and the `config` folder into the
shared OneDrive folder. `logs`, `data` and `backups` are created
on first run.

## Configuration

`config/config.json` is searched for in this order, first match
wins:

1. the path in the `VELERO_CONFIG_FILE` environment variable
2. `config/config.json` next to the executable
3. `config.json` next to the executable
4. the copy bundled inside the executable

Any value may reference an environment variable as `%NAME%`, which
is how the PagerDuty token stays out of the file. Relative paths
are resolved against the folder holding the executable. Missing
keys fall back to the defaults in `app/config.py`.

| Key | Meaning |
| --- | --- |
| `excel.file_path` | Workbook to process |
| `excel.table_name` | Named table inside the workbook |
| `excel.save_retry_attempts` | Retries while the file is locked |
| `excel.save_retry_delay_seconds` | Wait between those retries |
| `excel.safe_save` | Build the workbook outside the synced folder, then copy it over the original |
| `excel.close_local_workbook` | Offer to close the workbook if it is open on this machine |
| `excel.confirm_before_close` | Ask before closing it |
| `excel.warn_when_opened_by_others` | Warn when a colleague has it open |
| `excel.backup.*` | Post-run copy of the workbook and how long to keep it |
| `processing.processed_value` | Value written to `Processed` on success |
| `processing.failed_value` | Value written to `Processed` on failure |
| `processing.ledger.*` | Record of raised incidents, see below |
| `logging.directory` | Where log files are written |
| `logging.file_name` | Name of the active log file |
| `logging.level` | Level written to the log file |
| `logging.console_level` | Level shown on screen |
| `logging.retention_days` | How long dated log files are kept |
| `console.pause_on_exit` | Wait for a key press before closing |
| `pagerduty.*` | Endpoint, token, urgency, priority and retry behaviour |

## Sharing the workbook

The workbook sits on OneDrive and several engineers keep it open,
so a run has to survive that.

- **Open on the machine running the automation.** This blocks the
  update. The run offers to save and close that workbook through
  Excel and then continues. Declining stops the run before any
  incident is raised.
- **Open on a colleague's machine.** The run warns and continues.
  Their Excel still holds the version they opened, so saving it
  later can overwrite the cells this run wrote. Ask them to close
  it without saving.
- **Recovery.** Every raised incident is recorded in
  `data/processed-ledger.json` before the sheet is touched. If the
  cells are lost, the next run recognises the row from the ledger,
  writes the incident details back and skips it, so an incident is
  never raised twice. A copy of the workbook is also kept under
  `backups/`.

## Log output

```
Enter the date:

YYYY-MM-DD HH:MM:SS | INFO    | Validating the sheet
YYYY-MM-DD HH:MM:SS | INFO    | Starting Velero Automation for DD-MM-YYYY...
YYYY-MM-DD HH:MM:SS | INFO    | Using Excel file   : FILE_PATH
YYYY-MM-DD HH:MM:SS | INFO    | Excel Table        : TABLE_NAME
YYYY-MM-DD HH:MM:SS | DEBUG   | Excel file, table and columns validated
YYYY-MM-DD HH:MM:SS | INFO    | NAMESPACE | Initialized process
YYYY-MM-DD HH:MM:SS | SUCCESS | NAMESPACE | Incident Triggered
YYYY-MM-DD HH:MM:SS | INFO    | NAMESPACE | Sheet updated
YYYY-MM-DD HH:MM:SS | SKIPPED | NAMESPACE | Already processed on INCIDENT_DATE
YYYY-MM-DD HH:MM:SS | ERROR   | NAMESPACE | REASON
YYYY-MM-DD HH:MM:SS | INFO    | Summary   | Processed: XX :::: Skipped: XX :::: Failed: XX
YYYY-MM-DD HH:MM:SS | INFO    | Velero automation completed!
YYYY-MM-DD HH:MM:SS | INFO    | Bye!



Enter the date:

YYYY-MM-DD HH:MM:SS | INFO    | Validating the sheet
YYYY-MM-DD HH:MM:SS | ERROR   | No event found for DD-MM-YYYY
YYYY-MM-DD HH:MM:SS | INFO    | Velero automation completed!
YYYY-MM-DD HH:MM:SS | INFO    | Bye!
```

The log file keeps the same lines plus tracebacks and a few
details left off the console. Yesterday's file is renamed to
`velero-automation-YYYY-MM-DD.log` on the first run of a new day.


Enter the date:
Info      | Running veloro backup for DD-MM-YYYY
prod-ns   | Initialized process
prod-ns   | Incident Triggered - prod-ns-velero-backup-issue
prod-ns   | Sheet updated
Summary   | Processed: 3 :::: Skipped: 1 :::: Failed: 0

778b8e1d472f4001c034a316b7e7b912
a4357af44fd24c00d055b70b9ad11893