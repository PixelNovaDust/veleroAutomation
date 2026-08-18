import os
import time

from app.system import is_same_user


OWNER_PREFIX = "~$"

ALLOWED_OWNER_CHARACTERS = set(
    " .-_'\\@()"
)


def get_owner_file_path(file_path):
    """Path of the ~$ owner file Excel writes next to a workbook."""

    directory, file_name = os.path.split(
        os.path.abspath(file_path)
    )

    return os.path.join(
        directory,
        OWNER_PREFIX + file_name
    )


def _is_plausible_name(text):

    if not text:
        return False

    if len(text) > 64:
        return False

    has_letter = False

    for character in text:

        if character.isalnum():

            has_letter = True

            continue

        if character in ALLOWED_OWNER_CHARACTERS:
            continue

        return False

    return has_letter


def _decode(raw, encoding):

    try:
        text = raw.decode(encoding, "ignore")

    except (LookupError, UnicodeDecodeError):
        return None

    text = text.split("\x00")[0].strip()

    return text


def _decode_owner(raw):
    """
    Excel stores a length byte followed by the owner name. The
    encoding depends on the Office version that opened the file,
    so every candidate is decoded and the most name-like result
    wins.

    Reading a single byte name as UTF-16 yields characters that
    still pass as letters, so an all-ASCII reading is preferred
    over one that is not.
    """

    if not raw:
        return None

    length = raw[0]

    candidates = []

    if 0 < length < 64:

        candidates.append((raw[2:2 + length * 2], "utf-16-le"))
        candidates.append((raw[1:1 + length], "cp1252"))

    candidates.append((raw[1:], "utf-16-le"))
    candidates.append((raw[1:], "cp1252"))

    plausible = []

    for chunk, encoding in candidates:

        text = _decode(chunk, encoding)

        if _is_plausible_name(text) and text not in plausible:
            plausible.append(text)

    for text in plausible:

        if text.isascii():
            return text

    if plausible:
        return plausible[0]

    return None


def read_owner(file_path):
    """
    Name recorded in the owner file, or None when the workbook
    is not open anywhere that syncs to this folder.
    """

    owner_file = get_owner_file_path(file_path)

    if not os.path.exists(owner_file):
        return None

    try:

        with open(owner_file, "rb") as handle:
            raw = handle.read(512)

    except OSError:
        # The owner file exists but is locked, which still means
        # somebody has the workbook open.
        return None

    return _decode_owner(raw)


def is_locked_locally(file_path):
    """
    True when this machine cannot write the workbook, which is
    what Excel causes while it has the file open here.
    """

    if not os.path.exists(file_path):
        return False

    try:

        with open(file_path, "r+b"):
            return False

    except PermissionError:
        return True

    except OSError:
        return False


def describe_owner(file_path):
    """
    Report who holds the workbook.

    'self' means this machine cannot write the file, which only
    a local Excel session causes. 'other' means a colleague has
    it open, seen through the owner file their Excel synced into
    the folder. A leftover owner file naming the current user is
    ignored, because the file is still writable here.
    """

    owner = read_owner(file_path)

    if is_locked_locally(file_path):
        return "self", owner

    if owner and not is_same_user(owner):
        return "other", owner

    return None, owner


def wait_until_writable(file_path, attempts=5, delay_seconds=1):
    """
    Give the sync client and Excel a moment to release the file
    after it has been closed.
    """

    for attempt in range(max(1, attempts)):

        if not is_locked_locally(file_path):
            return True

        if attempt + 1 < attempts:
            time.sleep(max(0, delay_seconds))

    return not is_locked_locally(file_path)


def close_local_workbook(file_path, logger):
    """
    Save and close the workbook in the Excel instance running on
    this machine.

    Returns True only when a matching workbook was found and
    closed. Anything missing, such as pywin32 or Excel itself,
    is reported and treated as 'not closed' rather than fatal.
    """

    try:
        import pythoncom
        import win32com.client

    except ImportError:

        logger.debug(
            "Excel automation is unavailable "
            "(pywin32 is not installed).",
        )

        return False

    target_name = os.path.basename(file_path).lower()

    pythoncom.CoInitialize()

    try:

        try:
            excel = win32com.client.GetActiveObject(
                "Excel.Application"
            )

        except Exception:

            logger.debug(
                "No running Excel instance was found on "
                "this machine."
            )

            return False

        closed = False

        try:
            workbooks = list(excel.Workbooks)

        except Exception as error:

            logger.debug(
                "Open workbooks could not be listed: %s",
                error
            )

            return False

        for workbook in workbooks:

            try:
                name = str(workbook.Name).lower()

            except Exception:
                continue

            if name != target_name:
                continue

            try:

                excel.DisplayAlerts = False

                workbook.Save()
                workbook.Close(True)

                closed = True

            except Exception as error:

                logger.error(
                    "Excel refused to close %s: %s",
                    workbook_display_name(workbook),
                    error
                )

            finally:

                try:
                    excel.DisplayAlerts = True

                except Exception:
                    pass

        return closed

    finally:

        try:
            pythoncom.CoUninitialize()

        except Exception:
            pass


def workbook_display_name(workbook):

    try:
        return str(workbook.Name)

    except Exception:
        return "workbook"
