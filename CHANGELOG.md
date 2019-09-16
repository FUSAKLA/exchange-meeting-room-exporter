# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Added `exchange_meeting_room_will_be_occupied_timestamp` metric with timestamp of next occupancy start.
- Added `exchange_meeting_room_will_be_free_timestamp` metric with timestamp of current occupancy end.
- Added `exchange_meeting_room_meetings_left_today` metric with number of events left this day.
- Added cache and `--update-interval-seconds` flag to set interval of it's data update.

## [0.1.0] - 2019-09-13

Initial release
