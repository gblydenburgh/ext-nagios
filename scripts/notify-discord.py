#!/usr/bin/env python3
"""Send a Nagios notification to Discord without exposing the webhook."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


WEBHOOK_FILE = Path("/etc/nagios-secrets/discord_webhook")

# A Discord webhook can have a broad name such as "Monitoring-Alerts." Repeat
# the real sender in every message so readers know which monitor raised it.
SOURCE_NAME = "Nagios on ext.blydenburgh.com"

# This is the Discord user who should receive a pop-up for each alert. Discord
# user IDs are public identifiers, not passwords or webhook secrets.
MENTION_ID = "155801919133188096"

# Match the colors used by the home Icinga notifications. Problems are red,
# recoveries are green, and manual or other messages are yellow.
COLOR_RED = 13632027
COLOR_YELLOW = 16098851
COLOR_GREEN = 8311585

NAGIOS_DETAILS_URL = "https://ext.blydenburgh.com/nagios/cgi-bin/extinfo.cgi"


def clean(value, limit=700):
    """Keep notification text short and safe for Discord formatting."""
    return " ".join(value.replace("`", "'").split())[:limit]


def format_event_time():
    """Show Nagios event time in the same simple format used by Icinga."""
    raw_time = os.getenv("NAGIOS_SHORTDATETIME") or os.getenv(
        "NAGIOS_LONGDATETIME", "unknown time"
    )

    # Nagios versions can export either a short numeric date or a longer date
    # with the weekday and timezone. Try both before keeping the original text.
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%m-%d-%Y %H:%M:%S",
        "%a %b %d %H:%M:%S %Z %Y",
    )
    for date_format in formats:
        try:
            parsed_time = datetime.strptime(raw_time, date_format)
            return parsed_time.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    return clean(raw_time, 100)


def main():
    """Build either a host or service message from Nagios environment macros."""
    if len(sys.argv) != 2 or sys.argv[1] not in {"host", "service"}:
        print("Usage: notify-discord.py host|service", file=sys.stderr)
        return 2

    kind = sys.argv[1]
    notification_type = clean(os.getenv("NAGIOS_NOTIFICATIONTYPE", "UNKNOWN"))
    host = clean(os.getenv("NAGIOS_HOSTNAME", "unknown"))
    address = clean(os.getenv("NAGIOS_HOSTADDRESS", "unknown"), 100)
    event_time = format_event_time()

    # Use the same color choices as Icinga so alerts look familiar at a glance.
    color = COLOR_YELLOW
    if notification_type == "PROBLEM":
        color = COLOR_RED
    elif notification_type == "RECOVERY":
        color = COLOR_GREEN

    if kind == "host":
        state = clean(os.getenv("NAGIOS_HOSTSTATE", "UNKNOWN"))
        output = clean(os.getenv("NAGIOS_HOSTOUTPUT", "No check output"))
        title = f"Alert: {host} is {state} ({notification_type})"
        output_label = "Host Output"
        details_query = urlencode({"type": "1", "host": host})
    else:
        service = clean(os.getenv("NAGIOS_SERVICEDESC", "unknown service"))
        state = clean(os.getenv("NAGIOS_SERVICESTATE", "UNKNOWN"))
        output = clean(os.getenv("NAGIOS_SERVICEOUTPUT", "No check output"))
        title = f"Alert: {host} – {service} is {state} ({notification_type})"
        output_label = "Service Output"
        details_query = urlencode({"type": "2", "host": host, "service": service})

    # Discord renders an embed as the same colored card used by Icinga. The
    # title links to the matching host or service page in the Nagios website.
    embed = {
        "title": title[:256],
        "description": f"**Address:** `{address}`",
        "url": f"{NAGIOS_DETAILS_URL}?{details_query}",
        "color": color,
        "fields": [
            {"name": output_label, "value": output},
            {"name": "Date", "value": event_time},
        ],
        # The sender name already identifies Nagios. Repeat it in the footer so
        # copied screenshots and forwarded embeds still show their source.
        "footer": {"text": f"Source: {SOURCE_NAME}"},
    }

    try:
        webhook = WEBHOOK_FILE.read_text(encoding="utf-8").strip()
    except OSError as error:
        print(f"Cannot read Discord webhook file: {error}", file=sys.stderr)
        return 1

    # Reject unexpected URLs without ever printing the secret.
    valid_prefixes = (
        "https://discord.com/api/webhooks/",
        "https://discordapp.com/api/webhooks/",
    )
    if not webhook.startswith(valid_prefixes):
        print("Discord webhook file does not contain a valid HTTPS webhook.", file=sys.stderr)
        return 1

    payload = json.dumps(
        {
            # Mention only the intended user so Discord creates a pop-up. The
            # allowed_mentions list prevents plugin output from pinging others.
            "content": f"<@{MENTION_ID}>",
            "username": SOURCE_NAME,
            "embeds": [embed],
            "allowed_mentions": {"parse": [], "users": [MENTION_ID]},
        }
    ).encode("utf-8")

    request = Request(
        webhook,
        data=payload,
        headers={
            "Content-Type": "application/json",
            # Discord may block requests that do not identify their sender.
            "User-Agent": "Nagios-Discord-Notifier/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            if not 200 <= response.status < 300:
                print(
                    f"Discord returned HTTP {response.status}.",
                    file=sys.stderr,
                )
                return 1
    except HTTPError as error:
        print(f"Discord returned HTTP {error.code}.", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Discord connection failed: {error.reason}", file=sys.stderr)
        return 1

    print("Discord notification sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
