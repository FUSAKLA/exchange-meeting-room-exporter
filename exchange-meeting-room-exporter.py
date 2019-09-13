#!/usr/bin/python3
import argparse
import logging
import re
from datetime import datetime
from functools import wraps

import prometheus_client
from exchangelib import Account, Credentials, Configuration, EWSDateTime
from prometheus_client.core import GaugeMetricFamily, REGISTRY, Histogram
from sanic import Sanic, response
from sanic.exceptions import NotFound
from sanic.log import logger as sanic_logger

DEFAULT_EMAIL_ADDRESS = "meetingroom-exporter@foo.bar"


class ExchangeMeetingRoomCollector:

    def __init__(self, logger: logging.Logger, server: str, username: str, password: str, room_list_regex: str = ".*", room_name_regex: str = ".*"):
        self.__logger = logger
        credentials = Credentials(username=username, password=password)
        self.__config = Configuration(server=server, credentials=credentials)
        self.__account = self.__get_account(DEFAULT_EMAIL_ADDRESS)
        self.__room_list_regex = re.compile(room_list_regex, re.IGNORECASE)
        self.__room_name_regex = re.compile(room_name_regex, re.IGNORECASE)

    def __get_account(self, email: str):
        return Account(primary_smtp_address=email, config=self.__config)

    def collect(self):
        meeting_room_occupancy = GaugeMetricFamily('exchange_meeting_room_occupied', 'This metric exposes info about meeting room occupancy',
                                                   labels=["meeting_room_name", "meeting_room_email"])
        now = self.__account.default_timezone.localize(EWSDateTime.now())
        room_list_count = 0
        room_count = 0
        skipped_count = 0
        start = datetime.now()
        for room_list in self.__account.protocol.get_roomlists():
            self.__logger.debug("processing room list: {}".format(room_list.name))
            if not self.__room_list_regex.search(room_list.name):
                self.__logger.debug("processing room list {} skipped, not matching regular expression".format(room_list.name))
                continue
            room_list_count += 1
            for room in self.__account.protocol.get_rooms(room_list.email_address):
                self.__logger.debug("processing room: {}".format(room.name))
                if not self.__room_name_regex.search(room.name):
                    self.__logger.debug("processing room {} skipped, not matching regular expression".format(room.name))
                    skipped_count += 1
                    continue
                room_count += 1
                room_account = self.__get_account(room.email_address)
                meeting_room_occupancy.add_metric(labels=[room.name, room.email_address],
                                                  value=int(room_account.calendar.view(start=now, end=now, max_items=1).exists())
                                                  )
        self.__logger.info("finished processing of {} room lists wit total {} rooms and {} rooms skipped, duration {}".format(
            room_list_count, room_count, skipped_count, datetime.now() - start
        ))
        yield meeting_room_occupancy


app = Sanic()

request_histogram = Histogram("request_duration_seconds", "Histogram or request duration.",
                              labelnames=["type", "status_code", "endpoint", "method"])


def observe_latency():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            start = datetime.now()
            r = await f(request, *args, **kwargs)
            request_histogram.labels("REST", r.status, request.uri_template, request.method).observe((datetime.now() - start).seconds)
            return r

        return decorated_function

    return decorator


@app.route('/liveness')
async def liveness(request):
    return response.text("OK")


@app.route('/readiness')
async def readiness(request):
    return response.text("OK")


@app.route('/metrics')
@observe_latency()
async def metrics(request):
    return response.raw(prometheus_client.generate_latest(), content_type="text/plain; version=0.0.4; charset=utf-8")


@app.exception(NotFound)
async def ignore_404s(request, exception):
    return response.text("NOPE", status=404)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Prometheus exporter providing info about occupancy of meeting rooms from microsoft exchange.')
    parser.add_argument('--port', type=int, default=8000, help='Port to use for the web server.')
    parser.add_argument('-s', '--exchange-server', type=str, required=True, help='Url of MS Exchange server to use.')
    parser.add_argument('-u', '--username', type=str, required=True, help='Username to used to log in (mostly in `domain\\username` format).')
    parser.add_argument('-p', '--password-file', type=argparse.FileType('r'), required=True, help='File containing password.')
    parser.add_argument('--room-list-regex', type=str, default=".*",
                        help='Regular expression used to filter meeting rooms lists (All rooms of the list will be skipped).')
    parser.add_argument('--room-name-regex', type=str, default=".*", help='Regular expression used to filter meeting rooms.')
    parser.add_argument('-d', '--debug', action='store_true', default=False, help='Enable debug logging.')

    args = parser.parse_args()
    if args.debug:
        sanic_logger.setLevel(logging.DEBUG)

    sanic_logger.info("Starting exchange-meeting-room-exporter...")
    collector = ExchangeMeetingRoomCollector(
        logger=sanic_logger,
        server=args.exchange_server,
        username=args.username,
        password=args.password_file.read().strip(),
        room_name_regex=args.room_name_regex,
        room_list_regex=args.room_list_regex,
    )

    REGISTRY.register(collector)

    app.run(host='0.0.0.0', port=args.port)
