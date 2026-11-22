#!/usr/bin/env python3
"""Alert when the installed Nagios Core version is not the latest release."""

import json
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


# Nagios is installed from source, so the program itself is the most reliable
# place to read the installed version. The GitHub project is the official
# source for stable Nagios Core releases.
NAGIOS_BINARY = "/usr/local/nagios/bin/nagios"
LATEST_RELEASE_URL = (
    "https://api.github.com/repos/NagiosEnterprises/nagioscore/releases/latest"
)
VERSION_PATTERN = re.compile(r"^(?:nagios-)?(\d+)\.(\d+)\.(\d+)$")


def parse_version(value):
    """Turn a version such as 4.5.14 into numbers that Python can compare."""
    match = VERSION_PATTERN.fullmatch(value.strip())
    if not match:
        raise ValueError(f"unsupported version value: {value!r}")
    return tuple(int(part) for part in match.groups())


def installed_version():
    """Read the version from the same Nagios program used by the service."""
    result = subprocess.run(
        [NAGIOS_BINARY, "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    first_line = result.stdout.splitlines()[0]
    match = re.fullmatch(r"Nagios Core (\S+)", first_line.strip())
    if not match:
        raise ValueError("Nagios returned an unexpected version line")
    return match.group(1)


def latest_version():
    """Ask the official GitHub project for its newest stable release."""
    request = Request(
        LATEST_RELEASE_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ext-nagios-version-check/1.0",
        },
    )
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)

    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str):
        raise ValueError("release response did not include a version tag")
    return tag_name


def result_for_versions(installed, latest):
    """Return the Nagios status code and message for two valid versions."""
    installed_parts = parse_version(installed)
    latest_parts = parse_version(latest)

    if installed_parts < latest_parts:
        return (
            1,
            f"NAGIOS VERSION WARNING - installed {installed}; "
            f"latest stable is {latest.removeprefix('nagios-')}",
        )

    if installed_parts > latest_parts:
        return (
            0,
            f"NAGIOS VERSION OK - installed {installed} is newer than "
            f"latest stable {latest.removeprefix('nagios-')}",
        )

    return 0, f"NAGIOS VERSION OK - installed {installed} is the latest stable release"


def main():
    """Run the version lookup and print one standard Nagios plugin result."""
    try:
        installed = installed_version()
        latest = latest_version()
        status, message = result_for_versions(installed, latest)
    except subprocess.TimeoutExpired:
        status, message = 3, "NAGIOS VERSION UNKNOWN - installed version check timed out"
    except subprocess.SubprocessError as error:
        status, message = 3, f"NAGIOS VERSION UNKNOWN - cannot run Nagios: {error}"
    except HTTPError as error:
        status, message = 3, f"NAGIOS VERSION UNKNOWN - release lookup returned HTTP {error.code}"
    except URLError as error:
        status, message = 3, f"NAGIOS VERSION UNKNOWN - release lookup failed: {error.reason}"
    except (IndexError, OSError, ValueError, json.JSONDecodeError) as error:
        status, message = 3, f"NAGIOS VERSION UNKNOWN - {error}"

    print(message)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
