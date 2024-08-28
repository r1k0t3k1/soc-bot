# soc-bot

## Install

Install dependencies.

```bash
python -m pip install -r requirements.txt
```

## Usage

Register the url of the webhook.

```bash
python soc-bot.py --add-webhook-url https://xxxxx
```

Register the URL to be monitored.

```bash
python soc-bot.py --add-url https://xxxxx
```

Access the monitored URL and take a screenshots.
After that, merge the images and upload it to the webhook.

```bash
python soc-bot.py
```

## Use SOCKS5 Proxy

If SOCKS5 Proxy cannot go out to the external network, you may need to add the following to proxychains4.conf.

```bash
# discordapp.com
localnet 162.159.0.0/16
```

```bash
proxychains python soc-bot.py
```

## Create systemd timer

Make service file.

`/etc/systemd/system/soc-bot.service`

```bash
#!/bin/bash

cat << EOF > /etc/systemd/system/soc-bot.service
[Unit]
Description=soc-bot service

[Service]
Type=simple
User={USERNAME}
WorkingDirectory=/home/rikoteki/Desktop/Repost/soc-bot
ExecStart=/usr/bin/python soc-bot.py --filename urls.txt

[Install]
WantedBy=multi-user.target
EOF
```

Enable service.

```bash
systemctl enable soc-bot
```

Make Timer file.

```bash
#!/bin/bash

cat << EOF > /etc/systemd/system/soc-bot.timer
[Unit]
Description=soc-bot service timer

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Unit=soc-bot.service

[Install]
WantedBy=multi-user.target
EOF

```
