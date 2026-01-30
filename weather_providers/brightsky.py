import logging
from weather_providers.base_provider import BaseWeatherProvider
import datetime


class Brightsky(BaseWeatherProvider):
    def __init__(self, self_identification, location_lat, location_long, units):
        self.self_identification = self_identification
        self.location_lat = location_lat
        self.location_long = location_long
        self.units = units

    # Map Brightsky icon names to local icons
    # Reference: https://brightsky.dev/docs/
    def get_icon_from_brightsky_icon(self, icon_name):
        icon_dict = {
            "clear-day": "clear_sky_day",
            "clear-night": "clearnight",
            "partly-cloudy-day": "few_clouds",
            "partly-cloudy-night": "partlycloudynight",
            "cloudy": "mostly_cloudy",
            "fog": "climacell_fog",
            "wind": "wind",
            "rain": "climacell_rain",
            "sleet": "sleet",
            "snow": "snow",
            "hail": "sleet",
            "thunderstorm": "thundershower_rain",
        }

        # Default to the original icon name if not found in mapping
        icon = icon_dict.get(icon_name, "mostly_cloudy")
        logging.debug(
            "get_icon_from_brightsky_icon({}) - {}"
            .format(icon_name, icon))

        return icon

    # Map Brightsky condition to description
    def get_description_from_condition(self, condition):
        condition_dict = {
            "dry": "Clear",
            "fog": "Foggy",
            "rain": "Rainy",
            "sleet": "Sleet",
            "snow": "Snowy",
            "hail": "Hail",
            "thunderstorm": "Thunderstorm",
        }

        description = condition_dict.get(condition, condition.title())
        return description

    # Get weather from Brightsky
    # https://brightsky.dev/docs/
    def get_weather(self):
        # Get today's date for the API request
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        # Brightsky API endpoint
        url = ("https://api.brightsky.dev/weather?lat={}&lon={}&date={}"
               .format(self.location_lat, self.location_long, today))

        headers = {"User-Agent": self.self_identification}
        response_data = self.get_response_json(url, headers)
        logging.debug(response_data)

        # The API returns hourly data for the day
        # We need to aggregate to get min/max temperatures
        weather_records = response_data.get("weather", [])

        if not weather_records:
            logging.error("No weather data returned from Brightsky API")
            return None

        # Extract temperatures and find min/max
        temperatures = [record["temperature"] for record in weather_records if record.get("temperature") is not None]

        if not temperatures:
            logging.error("No temperature data in Brightsky response")
            return None

        temp_min = min(temperatures)
        temp_max = max(temperatures)

        # Get current or next available weather record for icon and description
        # Use the first record that has icon and condition data
        current_weather = None
        for record in weather_records:
            if record.get("icon") and record.get("condition"):
                current_weather = record
                break

        if not current_weather:
            # Fallback to first record
            current_weather = weather_records[0]

        # Convert Celsius to Fahrenheit if needed
        if self.units == "imperial":
            temp_min = self.c_to_f(temp_min)
            temp_max = self.c_to_f(temp_max)

        # Build weather dictionary
        weather = {}
        weather["temperatureMin"] = temp_min
        weather["temperatureMax"] = temp_max
        weather["icon"] = self.get_icon_from_brightsky_icon(current_weather.get("icon", "cloudy"))
        weather["description"] = self.get_description_from_condition(current_weather.get("condition", "dry"))

        logging.debug("get_weather() - {}".format(weather))
        return weather
