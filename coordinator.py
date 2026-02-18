"""DataUpdateCoordinator for Upper Austria Fire Brigade."""
from __future__ import annotations

from datetime import datetime, timedelta
import json
import logging
from typing import Any

import aiohttp
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    API_TIMEOUT,
    API_URL,
    CONF_FILTER_DISTRICTS,
    CONF_FILTER_KEYWORDS,
    CONF_MAX_INCIDENTS,
    DOMAIN,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class OOELFVDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Upper Austria Fire Brigade data."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.session = session
        self.entry = entry
        
        # Get filter settings
        self.filter_districts = [
            d.strip() 
            for d in entry.data.get(CONF_FILTER_DISTRICTS, "").split(",") 
            if d.strip()
        ]
        self.filter_keywords = [
            k.strip().lower() 
            for k in entry.data.get(CONF_FILTER_KEYWORDS, "").split(",") 
            if k.strip()
        ]
        self.max_incidents = entry.data.get(CONF_MAX_INCIDENTS, 20)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(API_TIMEOUT):
                async with self.session.get(API_URL) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        _LOGGER.error("API error %s: %s", response.status, response_text)
                        raise UpdateFailed(f"API error {response.status}")
                    
                    # Read as text and parse manually
                    response_text = await response.text()
                    
                    if not response_text:
                        raise UpdateFailed("Empty response from API")
                    
                    try:
                        data = json.loads(response_text)
                    except json.JSONDecodeError as err:
                        _LOGGER.error("Failed to parse JSON: %s", err)
                        raise UpdateFailed(f"Invalid JSON response: {err}") from err
                    
                    return self._process_data(data)
                    
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _process_data(self, raw_data: dict) -> dict[str, Any]:
        """Process raw API data."""
        try:
            # Extract metadata
            metadata = {
                "title": raw_data.get("title", "OÖ Fire Brigade"),
                "pubDate": raw_data.get("pubDate", ""),
                "version": raw_data.get("version", ""),
                "cnt_einsaetze": raw_data.get("cnt_einsaetze", 0),
                "cnt_feuerwehren": raw_data.get("cnt_feuerwehren", 0),
            }
            
            # Get einsaetze dict
            einsaetze_dict = raw_data.get("einsaetze", {})
            
            if not isinstance(einsaetze_dict, dict):
                _LOGGER.warning("einsaetze is not a dict: %s", type(einsaetze_dict))
                einsaetze_dict = {}
            
            # Extract incidents from the nested structure
            # Structure: einsaetze -> {"0": {"einsatz": {...}}, "1": {"einsatz": {...}}, ...}
            incidents = []
            for key, value in einsaetze_dict.items():
                if isinstance(value, dict) and "einsatz" in value:
                    incident = value["einsatz"]
                    if isinstance(incident, dict):
                        incidents.append(incident)
                    else:
                        _LOGGER.debug("Incident under key %s is not a dict", key)
                else:
                    _LOGGER.debug("No 'einsatz' key found under %s", key)
            
            _LOGGER.info("Extracted %s incidents from API", len(incidents))
            
            # Apply filters
            filtered_incidents = []
            for incident in incidents:
                # 1. Filter out 'SELBST' (administrative/maintenance) incidents
                if incident.get("einsatzart", "").upper() == "SELBST":
                    continue

                # 2. Filter by district
                if self.filter_districts:
                    bezirk_dict = incident.get("bezirk", {})
                    bezirk_text = bezirk_dict.get("text", "") if isinstance(bezirk_dict, dict) else ""
                    
                    adresse_dict = incident.get("adresse", {})
                    location = adresse_dict.get("default", "") if isinstance(adresse_dict, dict) else ""
                    
                    if not any(d.lower() in bezirk_text.lower() or d.lower() in location.lower() 
                              for d in self.filter_districts):
                        continue
                
                # 3. Filter by keywords
                if self.filter_keywords:
                    einsatzart = incident.get("einsatzart", "").lower()
                    einsatztyp_dict = incident.get("einsatztyp", {})
                    einsatztyp_text = einsatztyp_dict.get("text", "").lower() if isinstance(einsatztyp_dict, dict) else ""
                    alarmstufe = incident.get("alarmstufe", "").lower()
                    
                    if not any(k in einsatzart or k in einsatztyp_text or k in alarmstufe 
                              for k in self.filter_keywords):
                        continue
                
                filtered_incidents.append(incident)
            
            # Limit number of incidents
            filtered_incidents = filtered_incidents[:self.max_incidents]
            
            # Process each incident
            processed_incidents = []
            for incident in filtered_incidents:
                processed = self._process_incident(incident)
                if processed:
                    processed_incidents.append(processed)
            
            _LOGGER.info("Successfully processed %s incidents (filtered from %s)", 
                        len(processed_incidents), len(incidents))
            
            return {
                "incidents": processed_incidents,
                "total_count": len(incidents),
                "filtered_count": len(processed_incidents),
                "last_update": dt_util.utcnow().isoformat(),
                "source": metadata["title"],
                "pub_date": metadata["pubDate"],
                "version": metadata["version"],
            }
            
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.exception("Error processing data")
            raise UpdateFailed(f"Error processing data: {err}") from err

    def _process_incident(self, incident: dict) -> dict[str, Any] | None:
        """Process a single incident."""
        try:
            # Parse start time
            startzeit_str = incident.get("startzeit", "")
            startzeit = None
            
            if startzeit_str:
                try:
                    # Format: "Thu, 05 Feb 2026 11:32:09 +0100"
                    startzeit = datetime.strptime(startzeit_str, "%a, %d %b %Y %H:%M:%S %z")
                except (ValueError, TypeError) as err:
                    _LOGGER.debug("Could not parse date '%s': %s", startzeit_str, err)
            
            # Get address details
            adresse_dict = incident.get("adresse", {})
            location = adresse_dict.get("default", "") if isinstance(adresse_dict, dict) else ""
            municipality = adresse_dict.get("emun", "") if isinstance(adresse_dict, dict) else ""
            
            # Get district
            bezirk_dict = incident.get("bezirk", {})
            district = bezirk_dict.get("text", "") if isinstance(bezirk_dict, dict) else ""
            
            # Get incident type details
            einsatztyp_dict = incident.get("einsatztyp", {})
            einsatztyp_text = einsatztyp_dict.get("text", "") if isinstance(einsatztyp_dict, dict) else ""
            
            einsatzsubtyp_dict = incident.get("einsatzsubtyp", {})
            einsatzsubtyp_text = einsatzsubtyp_dict.get("text", "") if isinstance(einsatzsubtyp_dict, dict) else ""
            
            # Get coordinates
            wgs84_dict = incident.get("wgs84", {})
            lat = wgs84_dict.get("lat") if isinstance(wgs84_dict, dict) else None
            lng = wgs84_dict.get("lng") if isinstance(wgs84_dict, dict) else None
            
            # Get fire brigades
            units = []
            feuerwehren_array = incident.get("feuerwehrenarray", {})
            if isinstance(feuerwehren_array, dict):
                for key, fw_data in feuerwehren_array.items():
                    if isinstance(fw_data, dict):
                        fw_name = fw_data.get("fwname", "")
                        if fw_name:
                            units.append(fw_name)
            
            # Build description text
            description_parts = []
            if einsatztyp_text:
                description_parts.append(einsatztyp_text)
            if einsatzsubtyp_text:
                description_parts.append(einsatzsubtyp_text)
            description = " - ".join(description_parts) if description_parts else incident.get("einsatzart", "")
            
            # Build processed incident
            processed = {
                "id": incident.get("num1", "unknown"),
                "incident_type": incident.get("einsatzart", "Unknown"),
                "incident_type_detail": einsatztyp_text,
                "incident_subtype": einsatzsubtyp_text,
                "alarm_level": incident.get("alarmstufe", ""),
                "status": incident.get("status", ""),
                "location": location,
                "municipality": municipality,
                "district": district,
                "einsatzort": incident.get("einsatzort", ""),
                "text": description,
                "start_time": startzeit.isoformat() if startzeit else startzeit_str,
                "start_time_obj": startzeit,
                "units": units,
                "unit_count": incident.get("cntfeuerwehren", len(units)),
                "lat": float(lat) if lat else None,
                "lon": float(lng) if lng else None,
            }
            
            return processed
            
        except Exception as err:
            _LOGGER.warning("Error processing incident: %s", err)
            _LOGGER.debug("Incident data: %s", incident)
            return None
