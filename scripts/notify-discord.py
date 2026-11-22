#!/usr/bin/env python3
"""Send a Nagios notification to Discord without exposing the webhook."""

import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


WEBHOOK_FILE = Path("/etc/nagios-secrets/discord_webhook")


def clean(value, limit=700):
    """Keep notification text short and safe for Discord formatting."""
    return " ".join(value.replace("`", "'").split())[:limit]


def main():
    """Build either a host or service message from Nagios environment macros."""
    if len(sys.argv) != 2 or sys.argv[1] not in {"host", "service"}:
        print("Usage: notify-discord.py host|service", file=sys.stderr)
        return 2

    kind = sys.argv[1]
    notification_type = clean(os.getenv("NAGIOS_NOTIFICATIONTYPE", "UNKNOWN"))
    host = clean(os.getenv("NAGIOS_HOSTNAME", "unknown"))
    event_time = clean(os.getenv("NAGIOS_LONGDATETIME", "unknown time"))

    # Recovery messages use a green check. Other state changes use an alarm.
    icon = "✅" if notification_type == "RECOVERY" else "🚨"

    if kind == "host":
        state = clean(os.getenv("NAGIOS_HOSTSTATE", "UNKNOWN"))
        output = clean(os.getenv("NAGIOS_HOSTOUTPUT", "No check output"))
        subject = f"Host {host} is {state}"
    else:
        service = clean(os.getenv("NAGIOS_SERVICEDESC", "unknown service"))
        state = clean(os.getenv("NAGIOS_SERVICESTATE", "UNKNOWN"))
        output = clean(os.getenv("NAGIOS_SERVICEOUTPUT", "No check output"))
        subject = f"{host} / {service} is {state}"

    content = (
        f"{icon} **{subject}**\n"
        f"Notification: `{notification_type}`\n"
        f"Time: `{event_time}`\n"
        f"Output: {output}"
    )

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
            "content": content[:1900],
            "allowed_mentions": {"parse": []},
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
