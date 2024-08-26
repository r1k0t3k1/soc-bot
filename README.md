# soc-bot

## Install

Install dependencies.

```bash
python -m pip install -r requirements.txt
```

Create `.env`

```bash

echo {WEBHOOK_URL} > .env
```


## Usage

```bash
python soc-bot.py --filename urls.txt`
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
