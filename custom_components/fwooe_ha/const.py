"""Constants for the Feuerwehr OÖ Einsätze integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "fwooe_ha"

MANUFACTURER: Final = "Oö. Landes-Feuerwehrverband"
CONFIGURATION_URL: Final = "https://einsaetze.ooelfv.at"
ATTRIBUTION: Final = "Data: Oö. Landes-Feuerwehrverband (einsaetze.ooelfv.at)"

# The public JSON feed behind einsaetze.ooelfv.at: the currently running incidents.
API_URL: Final = "https://cf-einsaetze.ooelfv.at/webext2/rss/json_laufend.txt"
API_TIMEOUT: Final = 30

# Config entry data
CONF_NAME: Final = "name"

# Config entry options (the filters and the polling interval)
CONF_DISTRICTS: Final = "districts"
CONF_KEYWORDS: Final = "keywords"
CONF_INCLUDE_SELF_INITIATED: Final = "include_self_initiated"
CONF_MIN_ALARM_LEVEL: Final = "min_alarm_level"
CONF_MAX_INCIDENTS: Final = "max_incidents"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_NAME: Final = "Feuerwehr OÖ"
DEFAULT_MIN_ALARM_LEVEL: Final = 0
MAX_ALARM_LEVEL: Final = 10
DEFAULT_MAX_INCIDENTS: Final = 20
MIN_MAX_INCIDENTS: Final = 1
MAX_MAX_INCIDENTS: Final = 100
DEFAULT_SCAN_INTERVAL: Final = 60  # seconds
MIN_SCAN_INTERVAL: Final = 30
MAX_SCAN_INTERVAL: Final = 600

# The districts (Bezirke) of Upper Austria as the filter list of einsaetze.ooelfv.at spells them;
# the feed's `bezirk.text` uses the same spelling.
DISTRICTS: Final = (
    "Braunau",
    "Eferding",
    "Freistadt",
    "Gmunden",
    "Grieskirchen",
    "Kirchdorf",
    "Linz-Land",
    "Perg",
    "Ried im Innkreis",
    "Rohrbach",
    "Schärding",
    "Steyr-Land",
    "Urfahr-Umgebung",
    "Vöcklabruck",
    "Wels-Land",
    "Steyr-Stadt",
    "Wels-Stadt",
    "Linz-Stadt",
)

# Event types of the event entity
EVENT_NEW_INCIDENT: Final = "new_incident"
EVENT_ALARM_RAISED: Final = "alarm_level_raised"
EVENT_TYPES: Final = [EVENT_NEW_INCIDENT, EVENT_ALARM_RAISED]
