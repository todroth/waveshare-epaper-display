# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python application for displaying weather, calendar events, and custom data on a Waveshare 7.5" e-Paper HAT connected to a Raspberry Pi Zero WH. The display runs as a scheduled job and shows formatted information via SVG templates rendered to 1-bit BMP images.

## Development Setup

### Local Development (Mac/Linux)

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Copy and configure environment variables
cp env.sh.sample env.sh
# Edit env.sh with your API keys and settings
```

### Running the Application

```bash
# Main entry point - runs the full pipeline
./run.sh

# Individual components can be run separately:
.venv/bin/python3 screen-weather-get.py    # Fetch weather data
.venv/bin/python3 screen-calendar-get.py   # Fetch calendar events
.venv/bin/python3 screen-calendar-month.py # Generate month calendar (layout 5 only)
.venv/bin/python3 display.py screen-output.png  # Display on e-paper (requires Pi hardware)
```

Note: The display.py step will fail on non-Raspberry Pi systems, but the PNG generation steps work fine for testing layouts.

### OAuth Setup

```bash
# Google Calendar - initiates OAuth flow
.venv/bin/python3 screen-calendar-get.py

# Outlook Calendar - gets available calendars and their IDs
.venv/bin/python3 outlook_util.py
```

## Architecture

### Execution Pipeline (run.sh)

The main script follows this flow:

1. **Privacy modes** (mutually exclusive):
   - XKCD comic mode: Fetches and displays a comic strip
   - Literature clock mode: Generates SVG with literary quotes for current time

2. **Normal mode** (default):
   - **Weather**: Fetches from configured provider → Updates SVG template
   - **Calendar**: Fetches events → Updates SVG with calendar data
   - **Month view**: Generates calendar month (layout 5 only)
   - **Custom data**: Optional user-defined script (screen-custom-get.py)
   - **Rendering**: Converts SVG → PNG → BMP → e-paper display

Each step updates the same SVG file by replacing placeholder tokens.

### Provider Architecture

The codebase uses a **provider pattern** with base classes that define contracts:

#### Weather Providers (`weather_providers/`)
- Base: `BaseWeatherProvider` (defines `get_weather()` returning dict with temperatureMin, temperatureMax, icon, description)
- Implementations: OpenWeatherMap, MetOffice, AccuWeather, Met.no, Met Éireann, Weather.gov, Climacell, VisualCrossing, SMHI
- All providers cache responses for WEATHER_TTL seconds in `cache_weather.json`
- Priority order determined by env.sh (first configured provider wins)

#### Calendar Providers (`calendar_providers/`)
- Base: `BaseCalendarProvider` (defines `get_calendar_events()` returning list of `CalendarEvent`)
- Implementations: Google, Outlook, ICS, CalDav
- Cache responses in `cache_calendar.pickle` or `cache_outlookcalendar.pickle` for CALENDAR_TTL seconds
- Priority: Outlook > CalDav > ICS > Google (if multiple are configured)

#### Alert Providers (`alert_providers/`)
- Base: `BaseAlertProvider` (defines `get_alert()` returning string)
- Implementations: Met Office RSS Feed, Weather.gov, Met Éireann
- Displays severe weather warnings if configured

### SVG Template System

Templates are in `screen-template.{1-5}.svg` corresponding to SCREEN_LAYOUT values.

The `update_svg()` function (utility.py) performs simple string replacement:
- Takes template filename, output filename, and dictionary of replacements
- Keys in dictionary (e.g., `'TIME_NOW'`, `'CAL_DESC_1'`) are replaced in SVG
- Multiple scripts update the same output SVG sequentially

Common tokens:
- Weather: `LOW_ONE`, `HIGH_ONE`, `ICON_ONE`, `WEATHER_DESC_1/2`, `TIME_NOW`, `DAY_ONE`, `ALERT_MESSAGE`
- Calendar: `CAL_DATETIME_1` through `CAL_DATETIME_10`, `CAL_DESC_1` through `CAL_DESC_10`
- Custom: User-defined in screen-custom.svg and screen-custom-get.py

### Configuration (env.sh)

All configuration is environment-based:
- **Required**: WAVESHARE_EPD75_VERSION (1, 2, or 2B), WEATHER_LATITUDE, WEATHER_LONGITUDE
- **Weather provider**: One of the *_APIKEY or *_SELF_IDENTIFICATION variables
- **Calendar provider**: One of GOOGLE_CALENDAR_ID, OUTLOOK_CALENDAR_ID, ICS_CALENDAR_URL, or CALDAV_* variables
- **Optional**: Alert providers, cache TTLs, SCREEN_LAYOUT, LOG_LEVEL, LANG, WEATHER_LANGUAGE, WEATHER_FORMAT, privacy modes

### Caching Strategy

Files are cached with TTL-based staleness checking (utility.py `is_stale()`):
- Weather: `cache_weather.json` or `cache_weather.xml` (WEATHER_TTL, default 3600s)
- Calendar: `cache_calendar.pickle` or `cache_outlookcalendar.pickle` (CALENDAR_TTL, default 3600s)
- OAuth tokens: `token.pickle` (Google), `outlooktoken.bin` (Outlook)

To force refresh, delete the relevant cache file.

### Localization

The application supports localization through two environment variables:

- **LANG**: Controls date/time formatting via Python's locale system (e.g., `de_DE.UTF-8`, `en_US.UTF-8`)
  - Used by `utility.get_formatted_time()` and `utility.get_formatted_date()`
  - Uses `babel` for time formatting and `humanize` for natural language dates

- **WEATHER_LANGUAGE**: Controls weather description language (e.g., `en`, `de`)
  - Passed to weather providers that support language parameters
  - OpenWeatherMap: Uses native `lang` parameter in API requests
  - Brightsky: Uses translation dictionaries for condition descriptions
  - Other providers: May or may not support language selection

When adding new weather providers, consider:
- If the provider API supports a language parameter, add it to the API request URL
- If not, create translation dictionaries like in `brightsky.py`
- Always accept `language` parameter in `__init__()` method

## Git Submodule

The Waveshare display driver is a git submodule at `lib/e-Paper`:
```bash
# If missing after clone:
git submodule update --init --recursive
```

## Display Hardware Details

- **Version 1**: 640x384 pixels (older SKU: 13504)
- **Version 2**: 800x480 pixels (current version)
- **Version 2B**: 800x480 pixels with red color support (SKU: 13505)

The display.py script:
- Imports the correct driver based on WAVESHARE_EPD75_VERSION
- Performs full screen clear at 2 AM daily
- Displays 1-bit BMP for fast refresh (~6 seconds vs ~35 seconds for high-quality renders)

## Adding New Providers

### New Weather Provider
1. Create `weather_providers/newprovider.py` extending `BaseWeatherProvider`
2. Implement `get_weather()` returning `{"temperatureMin": float, "temperatureMax": float, "icon": str, "description": str}`
3. Use `self.get_response_json()` or `self.get_response_xml()` for caching
4. Add import and conditional logic to `screen-weather-get.py`
5. Document in README.md with env.sh.sample example

### New Calendar Provider
1. Create `calendar_providers/newprovider.py` extending `BaseCalendarProvider`
2. Implement `get_calendar_events()` returning `list[CalendarEvent]`
3. Add import and conditional logic to `screen-calendar-get.py`
4. Document in README.md with env.sh.sample example

## Custom Data Extension

Users can add custom data by:
1. Copying `screen-custom-get.py.sample` to `screen-custom-get.py`
2. Setting values in `output_dict` (custom_value_1, custom_value_2, etc.)
3. Modifying `screen-custom.svg` to position the custom elements
4. run.sh automatically detects and runs the custom script

## Troubleshooting

- Set `LOG_LEVEL=DEBUG` in env.sh for verbose output
- Check `run.log` when running via cron
- Delete cache files to force fresh data fetches
- The final display.py step requires Pi hardware and will fail on development machines (this is expected)
