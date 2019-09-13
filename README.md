# exchange-meeting-room-exporter
Prometheus exporter providing info about occupancy.

```
$ exchange-meeting-room-exporter.py --help
usage: exchange-meeting-room-exporter.py [-h] [--port PORT] -s EXCHANGE_SERVER
                                         -u USERNAME -p PASSWORD_FILE
                                         [--room-list-regex ROOM_LIST_REGEX]
                                         [--room-name-regex ROOM_NAME_REGEX]
                                         [-d]

Prometheus exporter providing info about occupancy of meeting rooms from
microsoft exchange.

optional arguments:
  -h, --help            show this help message and exit
  --port PORT           Port to use for the web server.
  -s EXCHANGE_SERVER, --exchange-server EXCHANGE_SERVER
                        Url of MS Exchange server to use.
  -u USERNAME, --username USERNAME
                        Username to used to log in (mostly in
                        `domain\username` format).
  -p PASSWORD_FILE, --password-file PASSWORD_FILE
                        File containing password.
  --room-list-regex ROOM_LIST_REGEX
                        Regular expression used to filter meeting rooms lists
                        (All rooms of the list will be skipped).
  --room-name-regex ROOM_NAME_REGEX
                        Regular expression used to filter meeting rooms.
  -d, --debug           Enable debug logging.

```
