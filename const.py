"""Constants for the Upper Austria Fire Brigade integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "ooelfv_incidents"
DEFAULT_NAME: Final = "OÖ Fire Brigade"

# API Configuration
API_URL: Final = "https://cf-einsaetze.ooelfv.at/webext2/rss/json_laufend.txt"
API_TIMEOUT: Final = 30

# Update interval (every 1 minute as per documentation)
UPDATE_INTERVAL: Final = timedelta(minutes=1)

# Configuration
CONF_NAME: Final = "name"
CONF_FILTER_DISTRICTS: Final = "filter_districts"
CONF_FILTER_KEYWORDS: Final = "filter_keywords"
CONF_MAX_INCIDENTS: Final = "max_incidents"

# Incident types mapping (German to English)
INCIDENT_TYPES: Final = {
    "Brand": "fire",
    "Technischer Einsatz": "technical",
    "Verkehrsunfall": "traffic_accident",
    "Person in Not": "person_in_danger",
    "Fehlalarm": "false_alarm",
    "Ölaustritt": "oil_spill",
    "Tier in Not": "animal_rescue",
    "Unwetter": "storm",
    "Sturmschaden": "storm_damage",
}

# Alarm levels
ALARM_LEVELS: Final = {
    "B0": "small_fire",
    "B1": "fire_level_1",
    "B2": "fire_level_2",
    "B3": "fire_level_3",
    "B4": "fire_level_4",
    "T0": "technical_small",
    "T1": "technical_level_1",
    "T2": "technical_level_2",
    "T3": "technical_level_3",
}
