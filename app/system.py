import getpass
import os
import socket


def get_user_name():
    """Bare login name of the engineer running the automation."""

    for variable in ("USERNAME", "USER", "LOGNAME"):

        value = os.environ.get(variable)

        if value:
            return value.strip()

    try:
        return getpass.getuser()

    except Exception:
        return "unknown"


def get_domain_name():

    domain = os.environ.get("USERDOMAIN")

    if domain:
        return domain.strip()

    return None


def get_host_name():

    host = os.environ.get("COMPUTERNAME")

    if host:
        return host.strip()

    try:
        return socket.gethostname()

    except Exception:
        return "unknown"


def get_current_user():
    """
    Qualified account name, for example PTC\\jdoe, falling
    back to the bare login name off the Windows domain.
    """

    user = get_user_name()
    domain = get_domain_name()

    if domain and "\\" not in user:
        return "{}\\{}".format(domain, user)

    return user


def is_same_user(candidate):
    """
    Compare a name found outside the process, such as the one
    Excel writes into its owner lock file, against the current
    account. Excel records the Office display name rather than
    the login, so only a loose match is possible.
    """

    if not candidate:
        return False

    candidate = str(candidate).strip().lower()

    if not candidate:
        return False

    known = [
        get_user_name(),
        get_current_user()
    ]

    for name in known:

        if not name:
            continue

        name = name.strip().lower()

        if candidate == name:
            return True

        if "\\" in name and candidate == name.split("\\")[-1]:
            return True

    return False
