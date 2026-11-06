# Pairing the Sony speaker to the Pi

All of Botfia's audio — narration and music — plays through the Sony Bluetooth
speaker. The Pi 5 has no headphone jack, so this pairing is required. You do this
once; after that the speaker reconnects on its own.

Run these steps on the Pi (over SSH or with a keyboard and screen).

## 1. Put the speaker in pairing mode

Turn the speaker on and hold its Bluetooth button until it announces it is ready to
pair or its light blinks. Keep it close to the Pi for the first pairing.

## 2. Pair with bluetoothctl

Start the Bluetooth control tool:

```
bluetoothctl
```

At the `[bluetooth]#` prompt, run these in order:

```
power on
agent on
default-agent
scan on
```

Wait a few seconds. Devices appear as lines like
`[NEW] Device 00:11:22:33:44:55 SRS-XB...`. Find your Sony speaker and copy its MAC
address (the `00:11:22:33:44:55` part). Then:

```
scan off
pair 00:11:22:33:44:55
trust 00:11:22:33:44:55
connect 00:11:22:33:44:55
```

- `pair` does the one-time handshake.
- `trust` lets the speaker reconnect later without asking.
- `connect` connects it now.

When it reports `Connection successful`, leave the tool:

```
exit
```

Write the MAC address down. You will reuse it below.

## 3. Make it the default audio output

Pi OS uses PipeWire with WirePlumber. List the outputs:

```
wpctl status
```

Under "Sinks" you should see the Sony speaker with a number in front of it (its ID).
Set it as the default:

```
wpctl set-default <id>
```

Set a sane volume (0.6 is 60%):

```
wpctl set-volume <id> 0.6
```

## 4. Confirm sound plays

```
speaker-test -c2 -twav -l1
```

You should hear the test tone from the speaker. If you hear nothing, recheck that the
speaker shows as connected (`bluetoothctl` then `info <mac>` shows `Connected: yes`)
and that it is the default sink in `wpctl status`.

## 5. Reconnect on boot

Because you ran `trust`, the speaker will try to reconnect when both it and the Pi
are on. To make it reliable:

- Turn the speaker on before (or as) you power the Pi.
- Keep the speaker from auto-sleeping during a game, or it drops the connection.

If it does not reconnect on its own, a one-line helper that runs at boot fixes it.
Create `/etc/systemd/system/botfia-speaker.service`:

```
[Unit]
Description=Reconnect the Sony speaker
After=bluetooth.target
Wants=bluetooth.target

[Service]
Type=oneshot
ExecStart=/usr/bin/bluetoothctl connect 00:11:22:33:44:55
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Replace the MAC with your speaker's. Then enable it:

```
sudo systemctl daemon-reload
sudo systemctl enable botfia-speaker.service
```

The host screen's health panel shows the speaker status, so you can confirm it is
connected before a game without any of this.
