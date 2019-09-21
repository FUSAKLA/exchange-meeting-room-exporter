#!/usr/bin/python3
import argparse
import asyncio
import logging
import re
from datetime import datetime, timedelta
from functools import wraps

import prometheus_client
from exchangelib import Account, Credentials, Configuration, EWSDateTime
from prometheus_client.core import GaugeMetricFamily, REGISTRY, Histogram, Counter, Gauge
from sanic import Sanic, response
from sanic.exceptions import NotFound
from sanic.log import logger as sanic_logger

DEFAULT_EMAIL_ADDRESS = "meetingroom-exporter@foo.bar"

errors_total = Counter('exchange_meeting_room_errors_total',
                       'This metric exposes number of errors encountered.', labelnames=["type"])
up = Gauge('exchange_meeting_room_up',
           'This metric reports if metrics collection was successful.')
last_cache_update = Gauge('exchange_meeting_room_last_successful_cache_update_timestamp',
                          'This metric exposes timestamp of last successful cache update.',
                          )


class ExchangeMeetingRoomCollector:
    __cache = None
    __last_update = datetime.min

    def __init__(self, logger: logging.Logger, server: str, username: str, password: str, room_list_regex: str = ".*", room_name_regex: str = ".*",
                 update_interval_seconds: int = 0):
        self.__logger = logger
        credentials = Credentials(username=username, password=password)
        self.__config = Configuration(server=server, credentials=credentials)
        self.__account = self.__get_account(DEFAULT_EMAIL_ADDRESS)
        self.__room_list_regex = re.compile(room_list_regex, re.IGNORECASE)
        self.__room_name_regex = re.compile(room_name_regex, re.IGNORECASE)
        self.__update_interval_seconds = update_interval_seconds
        self.use_cache = True if update_interval_seconds > 0 else False

    def __get_account(self, email: str):
        return Account(primary_smtp_address=email, config=self.__config)

    def collect(self):
        if self.use_cache:
            if not self.__cache:
                self.__cache = self.__collect_metrics()
            return self.__cache
        return self.__collect_metrics()

    async def start_cache_update(self):
        while True:
            await asyncio.sleep(self.__update_interval_seconds)
            collected_metrics = self.__collect_metrics()
            if collected_metrics:
                last_cache_update.set(datetime.now().timestamp())
            self.__cache = collected_metrics

    def __collect_metrics(self) -> list:
        meeting_room_occupancy = GaugeMetricFamily('exchange_meeting_room_occupied', 'This metric exposes info about meeting room occupancy',
                                                   labels=["meeting_room_list_name", "meeting_room_name", "meeting_room_email"])
        meeting_room_will_be_occupied = GaugeMetricFamily('exchange_meeting_room_will_be_occupied_timestamp',
                                                          'This metric exposes timestamp of closest start of the room occupancy.',
                                                          labels=["meeting_room_list_name", "meeting_room_name", "meeting_room_email"])
        meeting_room_will_be_free = GaugeMetricFamily('exchange_meeting_room_will_be_free_timestamp',
                                                      'This metric exposes timestamp of the most recent time the room will be free.',
                                                      labels=["meeting_room_list_name", "meeting_room_name", "meeting_room_email"])
        today_meetings_left = GaugeMetricFamily('exchange_meeting_room_meetings_left_today',
                                                'This metric exposes number of the meetings till the end of this day.',
                                                labels=["meeting_room_list_name", "meeting_room_name", "meeting_room_email"])
        now = self.__account.default_timezone.localize(EWSDateTime.now())
        end = self.__account.default_timezone.localize(EWSDateTime.from_datetime(datetime.combine(now.date() + timedelta(days=1), datetime.min.time())))
        room_list_count = 0
        room_count = 0
        skipped_count = 0
        start = datetime.now()
        try:
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
                    calendar = room_account.calendar.view(start=now, end=end)
                    self.__logger.debug("checking calendar: start={} end={}".format(now, end))

                    is_occupied = False
                    will_be_free = now
                    will_be_occupied = self.__account.default_timezone.localize(datetime.max - timedelta(1))
                    events_count = 0
                    if calendar.exists():
                        for i, event in enumerate(calendar):
                            events_count += 1
                            if event.start <= now <= event.end:
                                is_occupied = True
                                will_be_free = event.end
                                continue
                            if will_be_free == event.start:
                                will_be_free = event.end
                        if not is_occupied:
                            will_be_occupied = calendar[0].start
                    self.__logger.debug("occupied: {} will_be_free={} will_be_occupied={} events: {}".format(is_occupied, will_be_free, will_be_occupied, events_count))
                    meeting_room_occupancy.add_metric(labels=[room_list.name, room.name, room.email_address], value=int(is_occupied))
                    meeting_room_will_be_occupied.add_metric(labels=[room_list.name, room.name, room.email_address], value=will_be_occupied.timestamp())
                    meeting_room_will_be_free.add_metric(labels=[room_list.name, room.name, room.email_address], value=will_be_free.timestamp())
                    today_meetings_left.add_metric(labels=[room_list.name, room.name, room.email_address], value=events_count)
            self.__logger.info("finished processing of {} room lists wit total {} rooms and {} rooms skipped, duration {}".format(
                room_list_count, room_count, skipped_count, datetime.now() - start
            ))
            self.__last_update = datetime.now()
        except Exception as e:
            self.__logger.info("failed to update meeting room data, error: {}".format(e))
            errors_total.labels(e.__class__.__name__).inc()
            up.set(0)
            return []

        up.set(1)
        return [
            meeting_room_occupancy,
            meeting_room_will_be_occupied,
            meeting_room_will_be_free,
            today_meetings_left,
        ]


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
    parser.add_argument('-i', '--update-interval-seconds', type=int, default=0, help='Update interval in seconds.')
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
        update_interval_seconds=args.update_interval_seconds,
    )

    REGISTRY.register(collector)
    if collector.use_cache:
        app.add_task(collector.start_cache_update)
    app.run(host='0.0.0.0', port=args.port)
