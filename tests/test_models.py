"""Tests of the feed model: parsing, filtering, ordering, change detection.

The model imports nothing from Home Assistant, so these run on plain Python:
    python3 -B -m unittest tests.test_models
"""

from __future__ import annotations

import copy
from datetime import timedelta
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent


def _load_models():
    """Load models.py by path (importing the package would import Home Assistant)."""
    name = "fwooe_models_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "custom_components" / "fwooe_ha" / "models.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses needs the module to be registered
    spec.loader.exec_module(module)
    return module


models = _load_models()
RAW = json.loads((ROOT / "tests" / "fixtures" / "feed.json").read_text(encoding="utf-8"))


def feed():
    return models.parse_feed(copy.deepcopy(RAW))


def by_id(parsed, incident_id):
    return next(i for i in parsed.incidents if i.id == incident_id)


class ParseFeedTests(unittest.TestCase):
    def test_reads_every_incident_and_the_feed_header(self):
        parsed = feed()
        self.assertEqual(len(parsed.incidents), 7)
        self.assertEqual(parsed.version, "1.3.1")
        self.assertEqual(parsed.published.isoformat(), "2026-10-22T12:51:01+02:00")

    def test_fire_incident_fields(self):
        fire = by_id(feed(), "E261004261")
        self.assertEqual(fire.kind, "BRAND")
        self.assertEqual(fire.type_id, "B1-GEB-INDUSTRIE")
        self.assertEqual(fire.description, "Brand Industrie - Brand Gewerbe")
        self.assertEqual(fire.alarm_level, 3)
        self.assertEqual(fire.status, "offen")
        self.assertEqual(fire.place, "PE - Katsdorf")
        self.assertEqual(fire.location, "Katsdorf")
        self.assertEqual((fire.district_id, fire.district), (7, "Perg"))
        self.assertEqual((fire.latitude, fire.longitude), (48.3122, 14.5091))
        self.assertEqual(fire.start.isoformat(), "2026-10-22T06:28:48+02:00")
        self.assertFalse(fire.self_initiated)

    def test_units_are_cleaned_and_counted(self):
        fire = by_id(feed(), "E261004261")
        self.assertEqual(fire.unit_count, 16)
        self.assertEqual(len(fire.units), 16)
        self.assertEqual(fire.units[0], "Florian Wartberg ob der Aist")
        # a "(PE)" that is not the numeric code stays in the name
        self.assertIn("Florian Haid (PE)", fire.units)
        self.assertTrue(
            all("/" not in unit and not unit.endswith(")") or "(PE)" in unit for unit in fire.units)
        )
        traun = by_id(feed(), "E261004298")
        self.assertEqual(traun.units, ("Florian Dr. Franz Feurstein Ges.m.b.H.",))

    def test_self_initiated_flag(self):
        self.assertTrue(by_id(feed(), "E261004313").self_initiated)
        self.assertEqual(sum(i.self_initiated for i in feed().incidents), 6)

    def test_as_dict_is_json_serialisable(self):
        for incident in feed().incidents:
            data = incident.as_dict()
            self.assertEqual(json.loads(json.dumps(data)), data)
        self.assertEqual(by_id(feed(), "E261004261").as_dict()["units"][5], "Florian Katsdorf")

    def test_empty_feed_is_fine(self):
        for empty in ({}, [], None):
            raw = {"webext2": True, "cnt_einsaetze": 0, "einsaetze": empty}
            self.assertEqual(models.parse_feed(raw).incidents, ())

    def test_list_instead_of_object_is_accepted(self):
        raw = copy.deepcopy(RAW)
        raw["einsaetze"] = list(raw["einsaetze"].values())
        self.assertEqual(len(models.parse_feed(raw).incidents), 7)

    def test_not_a_feed_raises(self):
        for bad in ([], "html", None, 5, {}, {"error": "nope"}):
            with self.assertRaises(models.FeedFormatError, msg=repr(bad)):
                models.parse_feed(bad)

    def test_malformed_entries_are_skipped_not_fatal(self):
        raw = copy.deepcopy(RAW)
        raw["einsaetze"]["7"] = "garbage"
        raw["einsaetze"]["8"] = {"einsatz": {"einsatzart": "BRAND"}}  # no id
        raw["einsaetze"]["9"] = {"einsatz": []}
        raw["einsaetze"]["10"] = {"other": {}}
        self.assertEqual(len(models.parse_feed(raw).incidents), 7)

    def test_odd_field_values_do_not_break_parsing(self):
        raw = {
            "num1": "E1",
            "startzeit": "not a date",
            "alarmstufe": "x",
            "wgs84": {"lat": "abc", "lng": "14"},
            "bezirk": "Perg",
            "cntfeuerwehren": None,
            "feuerwehrenarray": "none",
        }
        incident = models.parse_incident(raw)
        self.assertEqual(incident.id, "E1")
        self.assertIsNone(incident.start)
        self.assertIsNone(incident.alarm_level)
        self.assertEqual((incident.latitude, incident.longitude), (None, None))
        self.assertEqual(incident.district, "")
        self.assertEqual((incident.units, incident.unit_count), ((), 0))
        self.assertEqual(incident.description, "Unknown")

    def test_zero_zero_and_out_of_range_coordinates_are_dropped(self):
        for lat, lng in (("0", "0"), ("95", "14"), ("48", "200")):
            incident = models.parse_incident({"num1": "E1", "wgs84": {"lat": lat, "lng": lng}})
            self.assertIsNone(incident.latitude, (lat, lng))
            self.assertIsNone(incident.longitude, (lat, lng))

    def test_time_without_offset_is_vienna_time(self):
        incident = models.parse_incident(
            {"num1": "E1", "startzeit": "Thu, 22 Oct 2026 12:00:00 -0000"}
        )
        self.assertEqual(incident.start.utcoffset(), timedelta(hours=2))  # CEST in October


class FilterTests(unittest.TestCase):
    def ids(self, selection):
        return [incident.id for incident in selection.shown]

    def test_default_hides_self_initiated(self):
        selection = models.IncidentFilter.create().select(feed().incidents)
        self.assertEqual(self.ids(selection), ["E261004261"])
        self.assertEqual(len(selection.matching), 1)

    def test_include_self_initiated_gives_all_newest_first(self):
        selection = models.IncidentFilter.create(include_self_initiated=True).select(
            feed().incidents
        )
        self.assertEqual(
            self.ids(selection),
            [
                "E261004313",
                "E261004298",
                "E261004275",
                "E261004261",
                "E261004229",
                "E261004227",
                "E261004210",
            ],
        )

    def test_sorting_does_not_depend_on_feed_order(self):
        incidents = list(reversed(feed().incidents))
        selection = models.IncidentFilter.create(include_self_initiated=True).select(incidents)
        self.assertEqual(self.ids(selection)[0], "E261004313")
        self.assertEqual(self.ids(selection)[-1], "E261004210")

    def test_limit_keeps_the_newest_and_reports_all_matches(self):
        selection = models.IncidentFilter.create(
            include_self_initiated=True, max_incidents=2
        ).select(feed().incidents)
        self.assertEqual(self.ids(selection), ["E261004313", "E261004298"])
        self.assertEqual(len(selection.matching), 7)

    def test_district_is_an_exact_case_insensitive_match(self):
        everything = feed().incidents
        only = lambda districts: self.ids(  # noqa: E731
            models.IncidentFilter.create(districts=districts, include_self_initiated=True).select(
                everything
            )
        )
        self.assertEqual(only(["perg"]), ["E261004261"])
        self.assertEqual(only(["Linz-Land"]), ["E261004298"])
        self.assertEqual(only(["Linz"]), [])  # no substring matching: not Linz-Land
        self.assertEqual(only(["Freistadt", "Braunau"]), ["E261004313", "E261004275"])
        self.assertEqual(only("Perg, Weyer"), ["E261004261"])  # comma separated text

    def test_keywords_match_type_subtype_and_place(self):
        everything = feed().incidents
        only = lambda keywords: self.ids(  # noqa: E731
            models.IncidentFilter.create(keywords=keywords, include_self_initiated=True).select(
                everything
            )
        )
        self.assertEqual(only(["brand"]), ["E261004261"])
        self.assertEqual(only(["GEWERBE"]), ["E261004261"])
        self.assertEqual(only(["katsdorf"]), ["E261004261"])
        self.assertEqual(len(only(["einsatzübung"])), 6)
        self.assertEqual(only(["nothing-like-this"]), [])

    def test_minimum_alarm_level(self):
        everything = feed().incidents
        level = lambda n: self.ids(  # noqa: E731
            models.IncidentFilter.create(min_alarm_level=n, include_self_initiated=True).select(
                everything
            )
        )
        self.assertEqual(level(3), ["E261004261"])
        self.assertEqual(level(4), [])
        self.assertEqual(len(level(0)), 7)

    def test_options_are_normalised(self):
        flt = models.IncidentFilter.create(
            districts=[" Perg ", "", "PERG"],
            keywords="Brand, brand ,Unfall",
            min_alarm_level=-5,
            max_incidents=99999,
        )
        self.assertEqual(flt.districts, frozenset({"perg"}))
        self.assertEqual(flt.keywords, ("brand", "unfall"))
        self.assertEqual(flt.min_alarm_level, 0)
        self.assertEqual(flt.max_incidents, 1000)
        self.assertEqual(models.IncidentFilter.create(max_incidents="x").max_incidents, 20)
        self.assertEqual(models.IncidentFilter.create(max_incidents=5.0).max_incidents, 5)


class ChangeDetectionTests(unittest.TestCase):
    def test_first_update_reports_nothing(self):
        self.assertEqual(models.detect_changes(None, feed().incidents), ((), ()))

    def test_new_incident(self):
        incidents = feed().incidents
        known = {i.id: i.alarm_level or 0 for i in incidents if i.id != "E261004261"}
        new, raised = models.detect_changes(known, incidents)
        self.assertEqual([i.id for i in new], ["E261004261"])
        self.assertEqual(raised, ())

    def test_alarm_level_raised_but_not_lowered(self):
        incidents = feed().incidents
        known = {i.id: i.alarm_level or 0 for i in incidents}
        known["E261004261"] = 2
        new, raised = models.detect_changes(known, incidents)
        self.assertEqual(new, ())
        self.assertEqual([i.id for i in raised], ["E261004261"])
        known["E261004261"] = 5  # now lower than before
        self.assertEqual(models.detect_changes(known, incidents), ((), ()))

    def test_nothing_changed(self):
        incidents = feed().incidents
        known = {i.id: i.alarm_level or 0 for i in incidents}
        self.assertEqual(models.detect_changes(known, incidents), ((), ()))


class TimeTests(unittest.TestCase):
    def test_start_ordering_uses_real_instants_across_offsets(self):
        early = models.parse_incident({"num1": "A", "startzeit": "Thu, 22 Oct 2026 10:00:00 +0200"})
        late = models.parse_incident({"num1": "B", "startzeit": "Thu, 22 Oct 2026 08:30:00 +0000"})
        self.assertEqual(late.start - early.start, timedelta(minutes=30))
        ordered = models.IncidentFilter.create(include_self_initiated=True).select([early, late])
        self.assertEqual([i.id for i in ordered.shown], ["B", "A"])


if __name__ == "__main__":
    unittest.main()
