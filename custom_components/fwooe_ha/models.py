"""Parsing, filtering and change detection for the Upper Austria incident feed.

This module deliberately imports nothing from Home Assistant (standard library only), so
it can be tested on its own.

Shape of the feed (``json_laufend.txt``)::

    {"webext2": true, "version": "1.3.1", "title": "laufend",
     "pubDate": "Thu, 22 Oct 2026 12:51:01 +0200",
     "cnt_einsaetze": 7, "cnt_feuerwehren": 22,
     "einsaetze": {"0": {"einsatz": {...}}, "1": {"einsatz": {...}}, ...}}

An ``einsatz`` has the id ``num1``, the kind ``einsatzart`` (``BRAND``, ``SELBST`` ...), a
type and subtype (``{"id": ..., "text": ...}``), the alarm level ``alarmstufe`` (a number
as text), ``status``, ``startzeit`` (RFC 2822), the place ``einsatzort`` (``"PE - Katsdorf"``),
``adresse``, ``bezirk``, ``wgs84`` (coordinates as text) and the alarmed brigades in
``feuerwehrenarray``. ``SELBST`` is a *Selbstständiger Einsatz*: a brigade that rolled out on
its own or an exercise; most of the running list is usually made up of these.

The Bezirke (districts) are the 18 that the district filter of einsaetze.ooelfv.at offers, each
with the id the feed puts in ``bezirk.id`` and the code the website uses for it (``PE-07``:
two letters, which also start the ``einsatzort`` of its incidents, and the id). Not every feed
spells a Bezirk the same way: the JSON feed has ``{"id": 11, "text": "Steyr-Land"}``, while the
2-day XML feed has ``<bezirk id="SE-11">SE-11</bezirk>`` for the same Bezirk. :func:`find_district`
understands all of these, so a Bezirk is always recognised by what it is, not by how it is written.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
import re
from typing import Any

SELF_INITIATED_KIND = "SELBST"

_UNIT_RE = re.compile(r"^(?:Feuerwehr/)?(?P<name>.*?)(?:\s*\((?P<code>\d+)\))?$")


class FeedFormatError(ValueError):
    """The feed is not what we expect (for example an error page or a changed format)."""


def _str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _coordinate(value: Any, limit: float) -> float | None:
    try:
        number = float(str(value).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return number if -limit <= number <= limit else None


def _parse_time(value: Any) -> datetime | None:
    text = _str(value)
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if parsed.tzinfo is None:
        # The feed always names its offset; if one is ever missing it is local time.
        from zoneinfo import ZoneInfo  # noqa: PLC0415

        parsed = parsed.replace(tzinfo=ZoneInfo("Europe/Vienna"))
    return parsed


def _clean_unit(name: str) -> str:
    """``Feuerwehr/Florian Perg (42312)`` -> ``Florian Perg``."""
    name = name.strip()
    match = _UNIT_RE.match(name)
    cleaned = match["name"].strip() if match else name
    return cleaned or name


def _parse_units(value: Any) -> tuple[str, ...]:
    entries: Iterable[Any]
    if isinstance(value, Mapping):
        entries = value.values()
    elif isinstance(value, list | tuple):
        entries = value
    else:
        return ()
    units = []
    for entry in entries:
        name = _str(_mapping(entry).get("fwname"))
        if name:
            units.append(_clean_unit(name))
    return tuple(units)


@dataclass(frozen=True, slots=True)
class District:
    """A Bezirk of Upper Austria, as the district filter of einsaetze.ooelfv.at lists it."""

    id: int  # ``bezirk.id`` in the feed
    abbreviation: str  # the letters before the place of an incident ("PE - Katsdorf")
    name: str

    @property
    def code(self) -> str:
        """The value the website's district filter uses, for example ``PE-07``."""
        return f"{self.abbreviation}-{self.id:02d}"


# In the order of the website's filter list (which is the order of the ids).
DISTRICTS: tuple[District, ...] = (
    District(0, "BR", "Braunau"),
    District(1, "EF", "Eferding"),
    District(2, "FR", "Freistadt"),
    District(3, "GM", "Gmunden"),
    District(4, "GR", "Grieskirchen"),
    District(5, "KI", "Kirchdorf"),
    District(6, "LL", "Linz-Land"),
    District(7, "PE", "Perg"),
    District(8, "RI", "Ried im Innkreis"),
    District(9, "RO", "Rohrbach"),
    District(10, "SD", "Schärding"),
    District(11, "SE", "Steyr-Land"),
    District(12, "UU", "Urfahr-Umgebung"),
    District(13, "VB", "Vöcklabruck"),
    District(14, "WL", "Wels-Land"),
    District(15, "SR", "Steyr-Stadt"),
    District(16, "WE", "Wels-Stadt"),
    District(17, "LS", "Linz-Stadt"),
)

_DISTRICT_BY_ID = {district.id: district for district in DISTRICTS}
_DISTRICT_BY_CODE = {district.code: district for district in DISTRICTS}
_DISTRICT_BY_NAME = {district.name.casefold(): district for district in DISTRICTS}
_DISTRICT_CODE_RE = re.compile(r"^([A-Za-z]{2})\s*-\s*(\d{1,2})$")


def find_district(value: Any) -> District | None:
    """Recognise a Bezirk by its id (``7``), code (``PE-07``) or name (``Perg``).

    Returns None for anything that is none of the 18 (including the empty string).
    """
    text = _str(value)
    if not text:
        return None
    if (number := _int(text)) is not None:
        return _DISTRICT_BY_ID.get(number)
    if match := _DISTRICT_CODE_RE.match(text):
        return _DISTRICT_BY_CODE.get(f"{match[1].upper()}-{int(match[2]):02d}")
    return _DISTRICT_BY_NAME.get(text.casefold())


@dataclass(frozen=True, slots=True)
class Incident:
    """One running incident."""

    id: str
    kind: str
    type_id: str
    type_text: str
    subtype_id: str
    subtype_text: str
    alarm_level: int | None
    status: str
    place: str
    location: str
    municipality: str
    district_id: int | None
    district: str
    start: datetime | None
    latitude: float | None
    longitude: float | None
    units: tuple[str, ...]
    unit_count: int

    @property
    def self_initiated(self) -> bool:
        """True for a *Selbstständiger Einsatz* (own deployment or exercise)."""
        return self.kind.upper() == SELF_INITIATED_KIND

    @property
    def description(self) -> str:
        """Type and subtype as one line, for example ``Brand Industrie - Brand Gewerbe``."""
        parts = [part for part in (self.type_text, self.subtype_text) if part]
        return " - ".join(parts) or self.kind or "Unknown"

    @property
    def start_timestamp(self) -> float:
        """Start as a POSIX timestamp; -inf when unknown, for sorting."""
        return self.start.timestamp() if self.start else float("-inf")

    @property
    def search_text(self) -> str:
        """Everything a keyword is matched against, lower case."""
        return " ".join(
            (
                self.kind,
                self.type_id,
                self.type_text,
                self.subtype_id,
                self.subtype_text,
                self.place,
                self.location,
            )
        ).casefold()

    def as_dict(self) -> dict[str, Any]:
        """The incident as plain JSON-able data (state attributes, event data)."""
        return {
            "id": self.id,
            "description": self.description,
            "kind": self.kind,
            "type": self.type_text,
            "type_id": self.type_id,
            "subtype": self.subtype_text,
            "subtype_id": self.subtype_id,
            "alarm_level": self.alarm_level,
            "status": self.status,
            "place": self.place,
            "location": self.location,
            "municipality": self.municipality,
            "district": self.district,
            "start_time": self.start.isoformat() if self.start else None,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "units": list(self.units),
            "unit_count": self.unit_count,
            "self_initiated": self.self_initiated,
        }


@dataclass(frozen=True, slots=True)
class Feed:
    """The whole feed: every running incident, filtered or not."""

    incidents: tuple[Incident, ...]
    published: datetime | None
    version: str


def parse_incident(raw: Any) -> Incident | None:
    """Turn one ``einsatz`` object into an :class:`Incident`; None if it has no id."""
    if not isinstance(raw, Mapping):
        return None
    incident_id = _str(raw.get("num1"))
    if not incident_id:
        return None

    kind = _str(raw.get("einsatzart"))
    incident_type = _mapping(raw.get("einsatztyp"))
    subtype = _mapping(raw.get("einsatzsubtyp"))
    address = _mapping(raw.get("adresse"))
    district_data = _mapping(raw.get("bezirk"))
    coordinates = _mapping(raw.get("wgs84"))
    # By id, else by the text; either may be a code like "SE-11" instead of id or name.
    district = find_district(district_data.get("id")) or find_district(district_data.get("text"))

    latitude = _coordinate(coordinates.get("lat"), 90)
    longitude = _coordinate(coordinates.get("lng"), 180)
    if latitude is None or longitude is None or (latitude == 0 and longitude == 0):
        latitude = longitude = None

    units = _parse_units(raw.get("feuerwehrenarray"))
    unit_count = _int(raw.get("cntfeuerwehren"))

    return Incident(
        id=incident_id,
        kind=kind,
        type_id=_str(incident_type.get("id")),
        type_text=_str(incident_type.get("text")),
        subtype_id=_str(subtype.get("id")),
        subtype_text=_str(subtype.get("text")),
        alarm_level=_int(raw.get("alarmstufe")),
        status=_str(raw.get("status")),
        place=_str(raw.get("einsatzort")),
        location=_str(address.get("default")),
        municipality=_str(address.get("emun")),
        district_id=district.id if district else _int(district_data.get("id")),
        district=district.name if district else _str(district_data.get("text")),
        start=_parse_time(raw.get("startzeit")),
        latitude=latitude,
        longitude=longitude,
        units=units,
        unit_count=unit_count if unit_count is not None else len(units),
    )


def parse_feed(raw: Any) -> Feed:
    """Parse the decoded JSON of the feed.

    Raises :class:`FeedFormatError` when it does not look like the incident feed at all.
    An empty list of incidents is fine (it is what a quiet moment looks like).
    """
    if not isinstance(raw, Mapping):
        raise FeedFormatError("the feed is not a JSON object")
    if "einsaetze" not in raw and "cnt_einsaetze" not in raw:
        raise FeedFormatError("the feed has no 'einsaetze'")

    entries = raw.get("einsaetze")
    if isinstance(entries, Mapping):
        entries = list(entries.values())
    elif not isinstance(entries, list | tuple):
        entries = []

    incidents = []
    for entry in entries:
        wrapped = entry.get("einsatz") if isinstance(entry, Mapping) else None
        if (incident := parse_incident(wrapped)) is not None:
            incidents.append(incident)

    return Feed(
        incidents=tuple(incidents),
        published=_parse_time(raw.get("pubDate")),
        version=_str(raw.get("version")),
    )


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.split(",")
    return [text for item in value if (text := _str(item))]


def _clamp(value: Any, default: int, low: int, high: int) -> int:
    number = _int(value) if not isinstance(value, float) else int(value)
    if number is None:
        number = default
    return max(low, min(high, number))


def normalize_districts(value: Any) -> list[str]:
    """The chosen Bezirke as stored: the website's code (``PE-07``) of every Bezirk we know.

    Version 0.1.0 stored names (``Perg``), and ids or codes are accepted too; anything that is
    none of the 18 stays as it is, so nothing the user chose silently disappears.
    """
    result: dict[str, str] = {}  # casefolded -> value, because matching ignores case
    for item in _as_list(value):
        district = find_district(item)
        normalized = district.code if district else item
        result.setdefault(normalized.casefold(), normalized)
    return list(result.values())


@dataclass(frozen=True, slots=True)
class Selection:
    """The incidents that pass the filter, newest first."""

    matching: tuple[Incident, ...]
    shown: tuple[Incident, ...]


@dataclass(frozen=True, slots=True)
class IncidentFilter:
    """Which incidents the user wants to see."""

    districts: frozenset[int] = frozenset()  # ids of the chosen Bezirke
    other_districts: frozenset[str] = frozenset()  # chosen names that are no known Bezirk
    keywords: tuple[str, ...] = ()
    include_self_initiated: bool = False
    min_alarm_level: int = 0
    max_incidents: int = 20

    @classmethod
    def create(
        cls,
        *,
        districts: Any = (),
        keywords: Any = (),
        include_self_initiated: bool = False,
        min_alarm_level: Any = 0,
        max_incidents: Any = 20,
    ) -> IncidentFilter:
        """Build a filter from raw option values (lists, or comma separated text).

        A Bezirk may be given as code, id or name (see :func:`find_district`); a value that is
        none of the known Bezirke is matched as an exact, case-insensitive name.
        """
        chosen = [(item, find_district(item)) for item in _as_list(districts)]
        return cls(
            districts=frozenset(district.id for _, district in chosen if district),
            other_districts=frozenset(item.casefold() for item, district in chosen if not district),
            keywords=tuple(dict.fromkeys(word.casefold() for word in _as_list(keywords))),
            include_self_initiated=bool(include_self_initiated),
            min_alarm_level=_clamp(min_alarm_level, 0, 0, 99),
            max_incidents=_clamp(max_incidents, 20, 1, 1000),
        )

    def matches(self, incident: Incident) -> bool:
        """True if the incident passes every active filter."""
        if incident.self_initiated and not self.include_self_initiated:
            return False
        if self.min_alarm_level and (incident.alarm_level or 0) < self.min_alarm_level:
            return False
        if (self.districts or self.other_districts) and not (
            incident.district_id in self.districts
            or incident.district.casefold() in self.other_districts
        ):
            return False
        if self.keywords:
            text = incident.search_text
            if not any(keyword in text for keyword in self.keywords):
                return False
        return True

    def select(self, incidents: Iterable[Incident]) -> Selection:
        """Filter, sort newest first, and cut to ``max_incidents``."""
        matching = sorted(
            (incident for incident in incidents if self.matches(incident)),
            key=lambda incident: (incident.start_timestamp, incident.id),
            reverse=True,
        )
        return Selection(matching=tuple(matching), shown=tuple(matching[: self.max_incidents]))


def detect_changes(
    known: Mapping[str, int] | None, incidents: Iterable[Incident]
) -> tuple[tuple[Incident, ...], tuple[Incident, ...]]:
    """Compare against the previous update.

    ``known`` maps the id of every previously matching incident to its alarm level;
    ``None`` means this is the first update, which never reports anything (incidents that
    were already running when Home Assistant started are not "new").

    Returns ``(new, raised)``: incidents not seen before, and known incidents whose alarm
    level went up.
    """
    if known is None:
        return (), ()
    new = []
    raised = []
    for incident in incidents:
        if incident.id not in known:
            new.append(incident)
        elif (incident.alarm_level or 0) > known[incident.id]:
            raised.append(incident)
    return tuple(new), tuple(raised)
