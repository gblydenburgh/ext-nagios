# External Nagios monitoring

This repository is the configuration for Nagios Core on `ext.blydenburgh.com`. The server is outside the home network, so it can report when the home Internet connection or firewall becomes unreachable.

The live checkout is `/usr/local/nagios/etc` on `ext`. Nagios reads its configuration directly from that directory.

## Discord alerts

[scripts/notify-discord.py](scripts/notify-discord.py) sends host and service notifications to Discord. Every message identifies its source in two places:

- The Discord sender name is `Nagios on ext.blydenburgh.com`.
- The first line of the message says `Source: Nagios on ext.blydenburgh.com`.

The source is repeated because a Discord webhook can be renamed. A person reading an alert should not have to guess whether it came from the home Icinga server or the external Nagios server.

Nagios passes notification details to the script through environment variables. [objects/discord.cfg](objects/discord.cfg) connects Nagios to the script, and [objects/templates.cfg](objects/templates.cfg) enables the commands for host and service notifications.

The Discord webhook is stored only in `/etc/nagios-secrets/discord_webhook`. It must be readable by the `nagios` account and must never be committed to this repository.

## Validate a change

Compile the Python script and ask Nagios to check the full configuration before reloading the service:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -c \
  'compile(open("scripts/notify-discord.py", "rb").read(), "scripts/notify-discord.py", "exec")'
sudo /usr/local/nagios/bin/nagios -v /usr/local/nagios/etc/nagios.cfg
```

The first command checks the Python syntax without leaving an `__pycache__` directory. The Nagios check must end with zero errors. After updating the live checkout, reload Nagios and confirm it remains active:

```sh
sudo systemctl reload nagios
sudo systemctl is-active nagios
```

## Test an alert

This command sends a real test message to Discord without exposing the webhook:

```sh
sudo -u nagios env \
  NAGIOS_NOTIFICATIONTYPE=CUSTOM \
  NAGIOS_HOSTNAME=firewall \
  NAGIOS_HOSTSTATE=UP \
  NAGIOS_HOSTOUTPUT='Manual notification test from ext.blydenburgh.com' \
  NAGIOS_LONGDATETIME="$(date -u '+%a %b %d %H:%M:%S UTC %Y')" \
  /usr/local/nagios/etc/scripts/notify-discord.py host
```

The Discord sender and the message's first line should both identify `Nagios on ext.blydenburgh.com`.
