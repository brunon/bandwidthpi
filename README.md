# Internet Bandwidth Monitor using Raspberry Pi

Monitor Internet bandwidth using SpeedTest.net and display on Inky wHAT e-paper display connected to a Raspberry Pi

> This project is based on [these instructions](https://www.instructables.com/Bandwidth-Monitor/) with simplified hardware requirements.

This is a SpeedTest module designed to update a [400x300 Inky wHAT e-paper display](https://shop.pimoroni.com/products/inky-what?variant=21214020436051) connected to a RaspberryPi computer (of any variant, though I've only tested a Pi3b)

It will keep 120 rows of previous test values and display a homegrown chart, and is designed to be run every 12 minutes in cron (so 5x per hour), making it 120x per 24h period. Therefore the charts would show a trailing 24h period if configured that way.

The history file can be stored in a RAM disk if desired by adding this entry to /etc/fstab:

```
tmpfs   /var/ram        tmpfs   nodev,nosuid,size=1M    0       0
```

Then launch the Python process with `--history /var/ram/speedtest.json`

These lines can be added to crontab to run the process every 12 minutes (5x / hour, 120x / day):

```
SHELL=/bin/bash

# Run SpeedTest 5x per hour
*/12 * * * * python3 /home/pi/bandwidth_monitor/bandwidth_monitor.py --history /var/ram/speedtest.json &>>/var/ram/speedtest.log

# Prune log file daily to avoid filling up RAM disk
0 0 * * * rm -f /var/ram/speedtest.log
```

The script also supports a `--csv` parameter to append each test result to a CSV file (which I store on an NFS file server and use outside of the Pi).

For testing purposes, the `--mock` argument uses a `TkInter` GUI window to simulate what the output would look like (without needing the e-paper display being connected).

Likewise, the `--fake` argument will skip the comparatively slow SpeedTest.net test and output some random values, this is useful in testing.
