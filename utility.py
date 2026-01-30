import base64
import codecs
import logging
import os
import time
from http.client import HTTPConnection
import requests
import datetime
import pytz
import json
import xml.etree.ElementTree as ET
from astral import LocationInfo
from astral.sun import sun
import humanize
import locale
from babel.dates import format_time, format_date


def configure_locale():
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        logging.debug("Could not set locale")


def configure_logging():
    """
    Sets up logging with a specific logging format.
    Call this at the beginning of a script.
    Then using logging methods as normal
    """
    log_level = os.getenv("LOG_LEVEL", "INFO")
    log_format = "%(asctime)s %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s"
    log_dateformat = "%Y-%m-%d:%H:%M:%S"
    logging.basicConfig(level=log_level, format=log_format, datefmt=log_dateformat)
    logger = logging.getLogger()
    logger.setLevel(level=log_level)

    # Adds debug logging to python requests
    # https://stackoverflow.com/a/24588289/974369
    HTTPConnection.debuglevel = 1 if log_level == "DEBUG" else 0
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(level=log_level)
    requests_log.propagate = True

    formatter = logging.Formatter(fmt=log_format, datefmt=log_dateformat)
    handler = logger.handlers[0]
    handler.setFormatter(formatter)


# utilize a template svg as a base for output of values
def update_svg(template_svg_filename, output_svg_filename, output_dict):
    """
    Update the `template_svg_filename` SVG.
    Replaces keys with values from `output_dict`
    Writes the output to `output_svg_filename`
    """
    # replace tags with values in SVG
    output = codecs.open(template_svg_filename, 'r', encoding='utf-8').read()

    for output_key in output_dict:
        logging.debug("update_svg() - {} -> {}"
                      .format(output_key, output_dict[output_key]))
        output = output.replace(output_key, output_dict[output_key])

    logging.debug("update_svg() - Write to SVG {}".format(output_svg_filename))

    codecs.open(output_svg_filename, 'w', encoding='utf-8').write(output)


def is_stale(filepath, ttl):
    """
    Checks if the specified `filepath` is older than the `ttl` in seconds
    Returns true if the file doesn't exist.
    """

    verdict = True
    if (os.path.isfile(filepath)):
        verdict = time.time() - os.path.getmtime(filepath) > ttl

    logging.debug(
        "is_stale({}) - {}"
        .format(filepath, str(verdict)))

    return verdict


def get_json_from_url(url, headers, cache_file_name, ttl):
    """
    Perform an HTTP GET for a `url` with optional `headers`.
    Caches the response in `cache_file_name` for `ttl` seconds.
    Returns the response as JSON
    """
    response_json = False

    if (is_stale(cache_file_name, ttl)):
        logging.info("Cache file is stale. Fetching from source.")
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_data = response.text
            response_json = json.loads(response_data)
            with open(cache_file_name, 'w') as text_file:
                json.dump(response_json, text_file, indent=4)
        except Exception as error:
            logging.error(error)
            logging.error(response.text)
            logging.error(response.headers)
            raise
    else:
        logging.info("Found in cache.")
        with open(cache_file_name, 'r') as file:
            return json.loads(file.read())
    return response_json


def get_xml_from_url(url, headers, cache_file_name, ttl):
    """
    Perform an HTTP GET for a `url` with optional `headers`.
    Caches the response in `cache_file_name` for `ttl` seconds.
    Returns the response as an XML ElementTree object
    """
    logging.info(url)

    if (is_stale(cache_file_name, ttl)):
        logging.info("Cache file is stale. Fetching from source.")
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_data = response.text

            with open(cache_file_name, 'w') as text_file:
                text_file.write(response_data)
        except Exception as error:
            logging.error(error)
            logging.error(response.text)
            logging.error(response.headers)
            raise
    else:
        logging.info("Found in cache.")
        with open(cache_file_name, 'r') as file:
            response_data = file.read()
    response_xml = ET.fromstring(response_data)
    return response_xml


def get_formatted_time(dt):
    try:
        formatted_time = format_time(dt, format='short', locale=locale.getlocale()[0])
    except Exception:
        logging.debug("Locale not found for Babel library.")
        formatted_time = dt.strftime("%-I:%M %p")
    return formatted_time


def get_word_clock_time(dt):
    """
    Convert time to German word clock format with 5-minute resolution.
    Returns a tuple of (line1, line2) for multi-line display.

    Examples:
        12:00 -> ("Es ist", "zwölf Uhr")
        12:05 -> ("Es ist fünf", "nach zwölf")
        12:30 -> ("Es ist", "halb eins")
        12:45 -> ("Es ist viertel", "vor eins")
    """
    # Round to nearest 5 minutes
    minute = dt.minute
    hour = dt.hour
    rounded_minute = 5 * round(minute / 5)

    # If rounded to 60, move to next hour
    if rounded_minute == 60:
        rounded_minute = 0
        hour = (hour + 1) % 24

    # Convert 24h to 12h format
    hour_12 = hour % 12
    if hour_12 == 0:
        hour_12 = 12

    # Next hour for "halb" and "vor" expressions
    next_hour = (hour_12 % 12) + 1
    if next_hour == 13:
        next_hour = 1

    # German hour names
    hours = {
        1: "eins", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs",
        7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwölf"
    }

    # Special case: "ein Uhr" not "eins Uhr"
    def hour_name(h, is_oclock=False):
        if h == 1 and is_oclock:
            return "ein"
        return hours[h]

    # Generate word clock string based on minutes
    if rounded_minute == 0:
        # Full hour: "Es ist zwölf Uhr"
        line1 = "Es ist"
        line2 = f"{hour_name(hour_12, True)} Uhr"

    elif rounded_minute == 5:
        # 5 after: "Es ist fünf nach zwölf"
        line1 = "Es ist fünf"
        line2 = f"nach {hour_name(hour_12)}"

    elif rounded_minute == 10:
        # 10 after: "Es ist zehn nach zwölf"
        line1 = "Es ist zehn"
        line2 = f"nach {hour_name(hour_12)}"

    elif rounded_minute == 15:
        # Quarter after: "Es ist viertel nach zwölf"
        line1 = "Es ist viertel"
        line2 = f"nach {hour_name(hour_12)}"

    elif rounded_minute == 20:
        # 20 after = 10 before half: "Es ist zehn vor halb eins"
        line1 = "Es ist zehn vor"
        line2 = f"halb {hour_name(next_hour)}"

    elif rounded_minute == 25:
        # 25 after = 5 before half: "Es ist fünf vor halb eins"
        line1 = "Es ist fünf vor"
        line2 = f"halb {hour_name(next_hour)}"

    elif rounded_minute == 30:
        # Half: "Es ist halb eins"
        line1 = "Es ist"
        line2 = f"halb {hour_name(next_hour)}"

    elif rounded_minute == 35:
        # 35 after = 5 after half: "Es ist fünf nach halb eins"
        line1 = "Es ist fünf nach"
        line2 = f"halb {hour_name(next_hour)}"

    elif rounded_minute == 40:
        # 40 after = 10 after half: "Es ist zehn nach halb eins"
        line1 = "Es ist zehn nach"
        line2 = f"halb {hour_name(next_hour)}"

    elif rounded_minute == 45:
        # Quarter before: "Es ist viertel vor eins"
        line1 = "Es ist viertel"
        line2 = f"vor {hour_name(next_hour)}"

    elif rounded_minute == 50:
        # 10 before: "Es ist zehn vor eins"
        line1 = "Es ist zehn"
        line2 = f"vor {hour_name(next_hour)}"

    elif rounded_minute == 55:
        # 5 before: "Es ist fünf vor eins"
        line1 = "Es ist fünf"
        line2 = f"vor {hour_name(next_hour)}"

    else:
        # Fallback (should not happen with proper rounding)
        line1 = "Es ist"
        line2 = f"{hour_name(hour_12, True)} Uhr"

    return (line1, line2)


def get_formatted_full_date(dt):
    """
    Format a date for display in header (e.g., "30. Jan 2026" in German, "Jan 30, 2026" in English)
    """
    try:
        current_locale = locale.getlocale()[0]  # de_DE, en_GB, etc.
        short_locale = current_locale.split("_")[0] if current_locale else "en"

        if short_locale == "de":
            # German format: "30. Jan 2026"
            return format_date(dt, format="d. MMM yyyy", locale=current_locale)
        else:
            # English format: "Jan 30, 2026"
            return format_date(dt, format="MMM d, yyyy", locale=current_locale)
    except Exception as e:
        logging.debug(f"Babel full date formatting failed: {e}, falling back to strftime")
        # Fallback to strftime
        return dt.strftime("%b %-d, %Y")


def get_formatted_date(dt, include_time=True):
    today = datetime.datetime.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    next_week = today + datetime.timedelta(days=7)

    # Display the time in the locale format, if possible
    if include_time:
        formatted_time = get_formatted_time(dt)
    else:
        formatted_time = " "

    try:
        current_locale = locale.getlocale()[0]  # de_DE, en_GB, etc.
        short_locale = current_locale.split("_")[0] if current_locale else "en"  # de, en, etc.
        if short_locale != "en":
            humanize.activate(short_locale)
        has_locale = True
    except Exception:
        logging.debug("Locale not found for humanize")
        has_locale = False
        current_locale = None
        short_locale = "en"

    # Check if this is today/tomorrow/yesterday
    if (has_locale and
            (dt.date() == today.date()
             or dt.date() == tomorrow.date()
             or dt.date() == yesterday.date())):
        # Show today/tomorrow/yesterday in the appropriate language
        formatter_day = humanize.naturalday(dt.date(), "%A").title()
    elif dt.date() < next_week.date():
        # Just show the day name if it's in the next few days
        formatter_day = dt.strftime("%A")
    else:
        # For dates further out, use babel for proper locale formatting
        try:
            # Use babel to format the date in the user's locale
            # Format: "EEE, d. MMM" for German (e.g., "Fr, 6. Feb")
            # Format: "EEE MMM d" for English (e.g., "Fri Feb 6")
            if short_locale == "de":
                # German format: "Fr, 6. Feb"
                formatter_day = format_date(dt, format="EEE, d. MMM", locale=current_locale)
            else:
                # English and other locales: "Fri Feb 6"
                formatter_day = format_date(dt, format="EEE MMM d", locale=current_locale)
        except Exception as e:
            logging.debug(f"Babel date formatting failed: {e}, falling back to strftime")
            # Fallback to strftime if babel fails
            formatter_day = dt.strftime("%a %b %-d")

    return formatter_day + " " + formatted_time


def get_sunset_time():
    """
    Return the time at which darkness begins, aka 'tonight'
    """
    location_lat = os.getenv("WEATHER_LATITUDE", "51.5077")
    location_long = os.getenv("WEATHER_LONGITUDE", "-0.1277")
    dt = datetime.datetime.now(pytz.utc)
    city = LocationInfo(location_lat, location_long)
    s = sun(city.observer, date=dt)
    return s['sunset']


def xor_encode(data, key):
    """XOR encode/decode the input data with a key."""
    # Repeat the key to match the length of data
    extended_key = (key * (len(data) // len(key) + 1))[:len(data)]

    # XOR each byte
    xored = bytes(a ^ b for a, b in zip(data.encode(), extended_key.encode()))

    return base64.b64encode(xored).decode()


def xor_decode(encoded_data, key):
    """XOR decode the input data with a key.
       Completely pointless and lightweight obfuscation, accomplishes nothing.
    """
    # Decode base64 first
    decoded_bytes = base64.b64decode(encoded_data.encode())

    # Repeat the key to match the length of data
    extended_key = (key * (len(decoded_bytes) // len(key) + 1))[:len(decoded_bytes)]

    # XOR each byte back
    xored = bytes(a ^ b for a, b in zip(decoded_bytes, extended_key.encode()))

    return xored.decode()
