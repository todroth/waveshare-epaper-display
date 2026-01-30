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
- Implementations: Brightsky (DWD), Met Office RSS Feed, Weather.gov, Met Éireann
- Displays severe weather warnings if configured
- Brightsky alerts use language from LANG variable (headline_de vs headline_en)

### SVG Template System

Templates are in `screen-template.{1-7}.svg` corresponding to SCREEN_LAYOUT values.

The `update_svg()` function (utility.py) performs simple string replacement:
- Takes template filename, output filename, and dictionary of replacements
- Keys in dictionary (e.g., `'TIME_NOW'`, `'CAL_DESC_1'`) are replaced in SVG
- Multiple scripts update the same output SVG sequentially
- **Important architectural principle**: All scripts generate ALL possible tokens, and templates use only what they need. This keeps scripts template-agnostic and maintainable.

Common tokens:
- Weather: `LOW_ONE`, `HIGH_ONE`, `ICON_ONE`, `WEATHER_DESC_1/2`, `DAY_ONE`, `DAY_NAME`, `ALERT_MESSAGE`
- Calendar: `CAL_DATETIME_1` through `CAL_DATETIME_10`, `CAL_DESC_1` through `CAL_DESC_10`
- Time (digital): `TIME_NOW`, `TIME_NOW_FONT_SIZE`, `HOUR_NOW` - used by templates 1-5
- Time (word clock): `WORD_TIME_LINE1`, `WORD_TIME_LINE2` - used by template 6
- Sunrise/Sunset: `SUNRISE_TIME`, `SUNSET_TIME` - used by template 7
- Custom: User-defined in screen-custom.svg and screen-custom-get.py

**Note on token naming**: Word clock tokens use `WORD_TIME_` prefix instead of `TIME_NOW_` to avoid string replacement collisions (e.g., if `TIME_NOW` is replaced first, `TIME_NOW_LINE1` would become `22:03_LINE1`).

**Template Independence**: Scripts like `screen-weather-get.py` always output both digital time (`TIME_NOW`) and word clock time (`TIME_NOW_LINE1`, `TIME_NOW_LINE2`). Each template simply ignores the tokens it doesn't use. This means:
- No conditional logic based on template selection in scripts
- Easy to add new templates without modifying scripts
- Scripts remain clean and maintainable

#### Layout 6: German Word Clock

Template 6 (`screen-template.6.svg`) features a German word clock display that:
- Shows time in words with 5-minute resolution (e.g., "Es ist halb eins")
- Only requires updates every 5 minutes instead of every minute
- Uses two-line display for better readability (`WORD_TIME_LINE1`, `WORD_TIME_LINE2`)
- Implements traditional German time expressions using "halb", "viertel", "nach", "vor"
- Function: `utility.get_word_clock_time()` converts datetime to German word format

#### Layout 7: Sunrise/Sunset Times

Template 7 (`screen-template.7.svg`) shows sunrise and sunset times instead of current time:
- Based on layout 1 but replaces the time display with sunrise/sunset information
- Uses `astral` library to calculate daily sunrise/sunset times based on location coordinates
- Displays sun icon and times with up/down arrows (↑ sunrise, ↓ sunset)
- Avoids frequent updates and screen flickering throughout the day
- Function: `screen-weather-get.get_sunrise_sunset()` calculates times using astral library
- Tokens: `SUNRISE_TIME`, `SUNSET_TIME`

When adding new templates:
1. Create new `screen-template.N.svg` with desired layout
2. Use any combination of existing tokens
3. No need to modify any Python scripts - all tokens are already generated
4. Unused tokens in SVG are simply left as-is (will be ignored)

### Configuration (env.sh)

All configuration is environment-based:
- **Required**: WAVESHARE_EPD75_VERSION (1, 2, or 2B), WEATHER_LATITUDE, WEATHER_LONGITUDE
- **Weather provider**: One of the *_APIKEY or *_SELF_IDENTIFICATION variables
- **Calendar provider**: One of GOOGLE_CALENDAR_ID, OUTLOOK_CALENDAR_ID, ICS_CALENDAR_URL, or CALDAV_* variables
- **Optional**: Alert providers, cache TTLs, SCREEN_LAYOUT, LOG_LEVEL, LANG, WEATHER_FORMAT, privacy modes

### Caching Strategy

Files are cached with TTL-based staleness checking (utility.py `is_stale()`):
- Weather: `cache_weather.json` or `cache_weather.xml` (WEATHER_TTL, default 3600s)
- Calendar: `cache_calendar.pickle` or `cache_outlookcalendar.pickle` (CALENDAR_TTL, default 3600s)
- OAuth tokens: `token.pickle` (Google), `outlooktoken.bin` (Outlook)

To force refresh, delete the relevant cache file.

### Localization

The application supports localization through a single environment variable:

- **LANG**: Controls ALL language-related functionality (e.g., `de_DE.UTF-8`, `en_US.UTF-8`)

  **Date/Time formatting:**
  - Used by `utility.get_formatted_time()`, `utility.get_formatted_date()`, and `utility.get_formatted_full_date()`
  - Uses `babel.dates.format_date()` for locale-aware date formatting (e.g., "30. Jan 2026" in German vs "Jan 30, 2026" in English)
  - Uses `babel.dates.format_time()` for time formatting
  - Uses `humanize` for natural language dates (Heute/Morgen vs Today/Tomorrow)

  **Weather descriptions:**
  - Language code is extracted from LANG (e.g., "de_DE.UTF-8" → "de")
  - Passed to weather providers that support language parameters
  - OpenWeatherMap: Uses native `lang` parameter in API requests
  - Brightsky: Uses translation dictionaries for condition descriptions
  - Other providers: May or may not support language selection

When adding new weather providers:
- Extract language code from LANG in screen-weather-get.py (already implemented)
- Accept `language` parameter in provider's `__init__()` method
- If the provider API supports a language parameter, add it to the API request URL
- If not, create translation dictionaries like in `brightsky.py`

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
