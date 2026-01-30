from alert_providers.base_provider import BaseAlertProvider
import logging
import os
import locale


class BrightskyAlerts(BaseAlertProvider):
    def __init__(self, location_lat, location_long, self_identification):
        self.location_lat = location_lat
        self.location_long = location_long
        self.self_identification = self_identification

    def get_alert(self):
        """
        Get weather alerts from Brightsky (DWD) API
        Returns a string with the alert headline in the appropriate language
        """
        try:
            url = f"https://api.brightsky.dev/alerts?lat={self.location_lat}&lon={self.location_long}"
            headers = {"User-Agent": self.self_identification}

            response = self.get_response_json(url, headers)
            logging.debug(f"get_alert - {response}")

            # Check if there are any alerts
            if "alerts" in response and len(response["alerts"]) > 0:
                # Get the first (most recent/relevant) alert
                alert = response["alerts"][0]

                # Determine language from LANG environment variable
                lang_env = os.getenv("LANG", "en_US.UTF-8")
                language = lang_env.split("_")[0] if "_" in lang_env else lang_env.split(".")[0]

                # Use German headline if language is German, otherwise English
                if language.lower() == "de":
                    headline = alert.get("headline_de", alert.get("event_de", ""))
                else:
                    headline = alert.get("headline_en", alert.get("event_en", ""))

                # Add severity level if available for context
                severity = alert.get("severity", "")
                if severity and severity in ["extreme", "severe"]:
                    severity_prefix = "⚠️ " if severity == "extreme" else "! "
                    headline = severity_prefix + headline

                logging.info(f"Brightsky alert found: {headline}")
                return headline

        except Exception as error:
            logging.debug(f"Error fetching Brightsky alerts: {error}")
            pass

        return ""
