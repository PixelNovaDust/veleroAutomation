import os
import re
import sys


WINDOWS_VARIABLE_PATTERN = re.compile(
    r"%([A-Za-z_][A-Za-z0-9_]*)%"
)


def is_frozen():
    return bool(
        getattr(sys, "frozen", False)
    )


def get_base_directory():
    """
    Directory that owns config, logs, data and backups.

    Frozen builds keep these next to the executable so an
    engineer can edit config.json without a rebuild. Source
    runs keep using the repository root.
    """

    if is_frozen():
        return os.path.dirname(
            os.path.abspath(sys.executable)
        )

    return os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )


def get_bundle_directory():
    """
    Directory holding read-only resources packed into the
    executable by PyInstaller.
    """

    bundle = getattr(sys, "_MEIPASS", None)

    if bundle:
        return bundle

    return get_base_directory()


def expand(value):
    """
    Expand environment variables and the user home marker.

    Windows style %VARIABLE% is handled on every platform so
    one config file stays portable between an engineer's
    machine and a build host.
    """

    if value is None:
        return None

    text = str(value)

    if not text:
        return text

    def replace(match):
        return os.environ.get(
            match.group(1),
            match.group(0)
        )

    text = WINDOWS_VARIABLE_PATTERN.sub(replace, text)

    text = os.path.expandvars(text)

    return os.path.expanduser(text)


def has_unresolved_variable(value):

    if value is None:
        return False

    return bool(
        WINDOWS_VARIABLE_PATTERN.search(str(value))
    )


def resolve_path(value, base_directory=None):
    """
    Turn a config path into an absolute path, treating
    relative values as relative to the base directory.
    """

    expanded = expand(value)

    if not expanded:
        return expanded

    expanded = expanded.replace("\\", os.sep)

    if os.path.isabs(expanded):
        return os.path.normpath(expanded)

    base = base_directory or get_base_directory()

    return os.path.normpath(
        os.path.join(base, expanded)
    )


def ensure_directory(path):

    if path:
        os.makedirs(path, exist_ok=True)

    return path


def is_directory_writable(path):

    if not path or not os.path.isdir(path):
        return False

    probe = os.path.join(
        path,
        ".velero-write-test-{}".format(os.getpid())
    )

    try:

        with open(probe, "w"):
            pass

        os.remove(probe)

        return True

    except OSError:
        return False
