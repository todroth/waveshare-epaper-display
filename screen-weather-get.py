#!/usr/bin/python

import datetime
import sys
import os
import logging
from weather_providers import climacell, openweathermap, metofficedatahub, metno, meteireann, accuweather, visualcrossing, weathergov, smhi, brightsky
from alert_providers import metofficerssfeed, weathergovalerts, brightsky as brightskyalerts
from alert_providers import meteireann as meteireannalertprovider
from utility import get_formatted_time, get_formatted_full_date, get_word_clock_time, update_svg, configure_logging, configure_locale
import textwrap
import html
from astral import LocationInfo
from astral.sun import sun

configure_locale()
configure_logging()


def format_weather_description(weather_description):
    if len(weather_description) < 20:
        return {1: weather_description, 2: ''}

    splits = textwrap.fill(weather_description, 20, break_long_words=False,
                           max_lines=2, placeholder='...').split('\n')
    weather_dict = {1: splits[0]}
    weather_dict[2] = splits[1] if len(splits) > 1 else ''
    return weather_dict


def get_weather(location_lat, location_long, units):

    # gather relevant environment configs
    climacell_apikey = os.getenv("CLIMACELL_APIKEY")
    openweathermap_apikey = os.getenv("OPENWEATHERMAP_APIKEY")
    metoffice_apikey = os.getenv("METOFFICEDATAHUB_API_KEY")
    accuweather_apikey = os.getenv("ACCUWEATHER_APIKEY")
    accuweather_locationkey = os.getenv("ACCUWEATHER_LOCATIONKEY")
    metno_self_id = os.getenv("METNO_SELF_IDENTIFICATION")
    visualcrossing_apikey = os.getenv("VISUALCROSSING_APIKEY")
    use_met_eireann = os.getenv("WEATHER_MET_EIREANN")
    weathergov_self_id = os.getenv("WEATHERGOV_SELF_IDENTIFICATION")
    smhi_self_id = os.getenv("SMHI_SELF_IDENTIFICATION")
    brightsky_self_id = os.getenv("BRIGHTSKY_SELF_IDENTIFICATION")

    # Extract language code from LANG environment variable (e.g., "de_DE.UTF-8" -> "de")
    lang_env = os.getenv("LANG", "en_US.UTF-8")
    weather_language = lang_env.split("_")[0] if "_" in lang_env else lang_env.split(".")[0]
    logging.debug(f"Detected language from LANG: {weather_language}")

    if (
        not climacell_apikey
        and not openweathermap_apikey
        and not metoffice_apikey
        and not accuweather_apikey
        and not metno_self_id
        and not visualcrossing_apikey
        and not use_met_eireann
        and not weathergov_self_id
        and not smhi_self_id
        and not brightsky_self_id
    ):
        logging.error("No weather provider has been configured (Climacell, OpenWeatherMap, Weather.gov, MetOffice, AccuWeather, Met.no, Met Eireann, VisualCrossing, SMHI, Brightsky...)")
        sys.exit(1)

    if visualcrossing_apikey:
        logging.info("Getting weather from Visual Crossing")
        weather_provider = visualcrossing.VisualCrossing(visualcrossing_apikey, location_lat, location_long, units)

    elif use_met_eireann:
        logging.info("Getting weather from Met Eireann")
        weather_provider = meteireann.MetEireann(location_lat, location_long, units)

    elif weathergov_self_id:
        logging.info("Getting weather from Weather.gov")
        weather_provider = weathergov.WeatherGov(weathergov_self_id, location_lat, location_long, units)

    elif metno_self_id:
        logging.info("Getting weather from Met.no")
        weather_provider = metno.MetNo(metno_self_id, location_lat, location_long, units)

    elif accuweather_apikey:
        logging.info("Getting weather from Accuweather")
        weather_provider = accuweather.AccuWeather(accuweather_apikey, location_lat,
                                                   location_long,
                                                   accuweather_locationkey,
                                                   units)

    elif metoffice_apikey:
        logging.info("Getting weather from Met Office Weather Datahub")
        weather_provider = metofficedatahub.MetOffice(metoffice_apikey,
                                                      location_lat,
                                                      location_long,
                                                      units)

    elif openweathermap_apikey:
        logging.info("Getting weather from OpenWeatherMap")
        weather_provider = openweathermap.OpenWeatherMap(openweathermap_apikey,
                                                         location_lat,
                                                         location_long,
                                                         units,
                                                         weather_language)

    elif climacell_apikey:
        logging.info("Getting weather from Climacell")
        weather_provider = climacell.Climacell(climacell_apikey, location_lat, location_long, units)

    elif smhi_self_id:
        logging.info("Getting weather from SMHI")
        weather_provider = smhi.SMHI(smhi_self_id, location_lat, location_long, units)

    elif brightsky_self_id:
        logging.info("Getting weather from Brightsky")
        weather_provider = brightsky.Brightsky(brightsky_self_id, location_lat, location_long, units, weather_language)

    weather = weather_provider.get_weather()
    logging.info("weather - {}".format(weather))
    return weather


def get_sunrise_sunset(location_lat, location_long):
    """Calculate sunrise and sunset times for the current day"""
    try:
        location = LocationInfo(latitude=float(location_lat), longitude=float(location_long))
        s = sun(location.observer, date=datetime.date.today())

        # Format times as HH:MM
        sunrise_time = s['sunrise'].strftime("%-H:%M")
        sunset_time = s['sunset'].strftime("%-H:%M")

        logging.debug(f"Sunrise: {sunrise_time}, Sunset: {sunset_time}")
        return sunrise_time, sunset_time
    except Exception as e:
        logging.error(f"Error calculating sunrise/sunset: {e}")
        return "—", "—"


def format_alert_description(alert_message):
    return html.escape(alert_message)


def get_alert_message(location_lat, location_long):
    alert_message = ""
    alert_metoffice_feed_url = os.getenv("ALERT_METOFFICE_FEED_URL")
    alert_weathergov_self_id = os.getenv("ALERT_WEATHERGOV_SELF_IDENTIFICATION")
    alert_meteireann_feed_url = os.getenv("ALERT_MET_EIREANN_FEED_URL")
    alert_brightsky_self_id = os.getenv("ALERT_BRIGHTSKY_SELF_IDENTIFICATION")

    if alert_brightsky_self_id:
        logging.info("Getting weather alert from Brightsky (DWD)")
        alert_provider = brightskyalerts.BrightskyAlerts(location_lat, location_long, alert_brightsky_self_id)
        alert_message = alert_provider.get_alert()

    elif alert_weathergov_self_id:
        logging.info("Getting weather alert from Weather.gov API")
        alert_provider = weathergovalerts.WeatherGovAlerts(location_lat, location_long, alert_weathergov_self_id)
        alert_message = alert_provider.get_alert()

    elif alert_metoffice_feed_url:
        logging.info("Getting weather alert from Met Office RSS Feed")
        alert_provider = metofficerssfeed.MetOfficeRssFeed(alert_metoffice_feed_url)
        alert_message = alert_provider.get_alert()

    elif alert_meteireann_feed_url:
        logging.info("Getting weather alert from Met Eireann")
        alert_provider = meteireannalertprovider.MetEireannAlertProvider(alert_meteireann_feed_url)
        alert_message = alert_provider.get_alert()

    logging.info("alert - {}".format(alert_message))
    return alert_message


def main():

    template_name = os.getenv("SCREEN_LAYOUT", "1")
    location_lat = os.getenv("WEATHER_LATITUDE", "51.5077")
    location_long = os.getenv("WEATHER_LONGITUDE", "-0.1277")
    weather_format = os.getenv("WEATHER_FORMAT", "CELSIUS")

    if (weather_format == "CELSIUS"):
        units = "metric"
        degrees = "°C"
    else:
        units = "imperial"
        degrees = "°F"

    weather = get_weather(location_lat, location_long, units)

    if not weather:
        logging.error("Unable to fetch weather payload. SVG will not be updated.")
        return

    weather_desc = format_weather_description(weather["description"])

    alert_message = get_alert_message(location_lat, location_long)
    alert_message = format_alert_description(alert_message)

    # Prepare all time formats - templates use what they need
    now = datetime.datetime.now()

    # Digital time format (for templates 1-5)
    time_now = get_formatted_time(now)
    time_now_font_size = "100px"
    if len(time_now) > 6:
        time_now_font_size = str(100 - (len(time_now)-5) * 5) + "px"

    # Word clock format (for template 6)
    word_time_line1, word_time_line2 = get_word_clock_time(now)

    # Sunrise/sunset times (for template 7)
    sunrise_time, sunset_time = get_sunrise_sunset(location_lat, location_long)

    # Single output dictionary with all possible values
    # Templates will use what they need and ignore the rest
    output_dict = {
        'LOW_ONE': "{}{}".format(str(round(weather['temperatureMin'])), degrees),
        'HIGH_ONE': "{}{}".format(str(round(weather['temperatureMax'])), degrees),
        'ICON_ONE': weather["icon"],
        'WEATHER_DESC_1': weather_desc[1],
        'WEATHER_DESC_2': weather_desc[2],
        # Digital time (templates 1-5)
        'TIME_NOW_FONT_SIZE': time_now_font_size,
        'TIME_NOW': time_now,
        # Word clock time (template 6) - different prefix to avoid collision with TIME_NOW
        'WORD_TIME_LINE1': word_time_line1,
        'WORD_TIME_LINE2': word_time_line2,
        # Sunrise/sunset times (template 7)
        'SUNRISE_TIME': sunrise_time,
        'SUNSET_TIME': sunset_time,
        # Common fields
        'HOUR_NOW': now.strftime("%-I %p"),
        'DAY_ONE': get_formatted_full_date(now),
        'DAY_NAME': now.strftime("%A"),
        'ALERT_MESSAGE_VISIBILITY': "visible" if alert_message else "hidden",
        'ALERT_MESSAGE': alert_message
    }

    logging.info(output_dict)

    logging.info("Updating SVG")

    template_svg_filename = f'screen-template.{template_name}.svg'
    output_svg_filename = 'screen-output-weather.svg'
    update_svg(template_svg_filename, output_svg_filename, output_dict)


if __name__ == "__main__":
    main()
