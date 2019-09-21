# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2019-09-21

### Changed
- Cache is now optional and by default disabled, only if `--update-interval-seconds` is higher than zero cache is enabled.

### Added
- Handle errors during metrics collection and expose `exchange_meeting_room_errors_total` to report errors.
- Expose `exchange_meeting_room_up` to representing metrics collection success/failure.

## [0.2.1] - 2019-09-17

### Added
- additional `meeting_room_list` label with name of the list the room belongs to. 

## [0.2.0] - 2019-09-16

### Added
- `exchange_meeting_room_will_be_occupied_timestamp` metric with timestamp of next occupancy start.
- `exchange_meeting_room_will_be_free_timestamp` metric with timestamp of current occupancy end.
- `exchange_meeting_room_meetings_left_today` metric with number of events left this day.
- Cache and `--update-interval-seconds` flag to set interval of it's data update.

## [0.1.0] - 2019-09-13

Initial release
