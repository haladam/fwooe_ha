# Feuerwehr OÖ Einsätze for Home Assistant

A Home Assistant integration that shows the **currently running fire brigade incidents in
Upper Austria**, from the public feed behind [einsaetze.ooelfv.at](https://einsaetze.ooelfv.at)
(Oö. Landes-Feuerwehrverband). Filter by district, keyword and alarm level, see incidents on the
map, and trigger automations when a new one starts or its alarm level goes up.

* **Sensors:** number of incidents, the latest incident (with all details as attributes), when it
  started, and diagnostics about the feed.
* **Binary sensor:** *Active incident*, on while something passes your filters.
* **Event entity:** *Incident alert* fires `new_incident` and `alarm_level_raised`, with the whole
  incident as event data: the trigger for notifications.
* **Map entities:** one `geo_location` entity per incident, with the distance to your home as its
  state. They appear on the map card, and disappear again when the incident ends.
* Filters you can change at any time under *Configure*; several feeds can run side by side (for
  example "home district" and "work district").

> **Unofficial.** This is not an alerting service and is not affiliated with the
> Oö. Landes-Feuerwehrverband. The feed is delayed and can be wrong or unavailable: never rely on
> this integration for anything safety-relevant. The incident data belongs to the
> Oö. Landes-Feuerwehrverband; the website states no terms for re-using it, so please keep the
> update interval modest (default 60 s, minimum 30 s) and check with them if you plan more than
> private use.

> **Status:** written against the feed as it was on 2026-10-22 (a fire with 16 brigades and six
> self-initiated deployments) and tested against recorded copies of it. Other incident kinds
> should parse the same way, but have not been seen. If an incident looks wrong, open an issue
> and attach the *Download diagnostics* file of the integration.

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/haladam/fwooe_ha`, category
   **Integration**.
2. Install **Feuerwehr OÖ Einsätze** and restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *Feuerwehr OÖ Einsätze*.

Updates then appear in HACS whenever a new release is published here.

### Manual

Copy `custom_components/fwooe_ha` into the `custom_components` folder of your Home Assistant
configuration (or unpack the `fwooe_ha.zip` of a release into `custom_components/fwooe_ha`) and
restart. Declared minimum: Home Assistant 2024.12 (the APIs used exist there). CI only tests
the current release.

## Setup

When adding the integration you choose a **name**, optionally one or more **districts**
(empty = all of Upper Austria) and whether to include self-initiated deployments.

### Options (Configure)

| Option | Meaning |
|---|---|
| Districts | Only incidents in these districts (Bezirke), exact name as on einsaetze.ooelfv.at. |
| Keywords | Only incidents whose type, subtype or place contains one of these words, for example `Brand`, `Verkehr`, `Wald`. Not case sensitive. |
| Include self-initiated deployments and exercises | See below. Off by default. |
| Minimum alarm level | Hide incidents below this level (`alarmstufe`). 0 shows all. |
| Maximum number of incidents | How many of the newest matches are listed in the attributes and get a map entity (1 to 100, default 20). |
| Update interval | Seconds between reads of the feed (30 to 600, default 60). |

An incident is shown when it passes **all** filters that are set.

**Self-initiated deployments.** Most of the running list is usually made up of entries of type
`SELBST` (*Selbstständiger Einsatz*, "Einsatz od. Einsatzübung"): a brigade that rolled out on its
own, or an exercise. They are hidden by default so that the sensors show real incidents; switch
them on if you want to see everything the feed contains.

## Entities

| Entity | What it is |
|---|---|
| `sensor.<name>_incidents` | Number of incidents that pass the filters. Attributes: `incidents` (the newest, as a list with all details) and `incidents_by_kind`. |
| `sensor.<name>_latest_incident` | Type and subtype of the newest incident, for example *Brand Industrie - Brand Gewerbe*. Attributes: `id`, `kind`, `alarm_level`, `status`, `place`, `location`, `district`, `start_time`, `latitude`, `longitude`, `units` (the alarmed brigades), `unit_count`. |
| `sensor.<name>_latest_incident_started` | When the newest incident started. |
| `sensor.<name>_incidents_in_feed` | Diagnostic: every running incident in the feed, filtered or not. |
| `sensor.<name>_feed_updated` | Diagnostic: when the feed says it was generated. |
| `binary_sensor.<name>_active_incident` | On while at least one incident passes the filters. |
| `event.<name>_incident_alert` | `new_incident` and `alarm_level_raised`. Incidents that are already running when Home Assistant starts do not fire an event. |
| `geo_location.<incident>` | One per incident (source `fwooe_ha`); the state is the distance to home in km. |

The entity ids depend on the name you chose and on the language of your Home Assistant.

## Examples

### Notification when a fire starts

```yaml
alias: Fire in Upper Austria
triggers:
  - trigger: state
    entity_id: event.feuerwehr_oo_incident_alert
conditions:
  - condition: template
    value_template: >
      {{ trigger.to_state.attributes.event_type == 'new_incident'
         and trigger.to_state.attributes.kind == 'BRAND' }}
actions:
  - action: notify.mobile_app_my_phone
    data:
      title: "🚒 {{ trigger.to_state.attributes.description }}"
      message: >
        {{ trigger.to_state.attributes.place }},
        alarm level {{ trigger.to_state.attributes.alarm_level }},
        {{ trigger.to_state.attributes.unit_count }} brigades
```

### Incidents on the map

```yaml
type: map
geo_location_sources:
  - fwooe_ha
default_zoom: 9
```

### Only incidents within 15 km

```yaml
triggers:
  - trigger: numeric_state
    entity_id: geo_location.brand_industrie_brand_gewerbe_katsdorf
    below: 15
```

(For all incidents at once, use a template on `states.geo_location` filtered by
`attributes.source == 'fwooe_ha'`.)

## Development

```
custom_components/fwooe_ha/   the integration (what HACS installs)
  models.py                   feed parsing, filters, change detection (standard library only)
  api.py                      HTTP client
  coordinator.py              polling, filtering, new/escalated incidents
  config_flow.py              setup and options
  sensor.py binary_sensor.py event.py geo_location.py   the platforms
  translations/               English and German
  brand/                      icon and logo (shipped with the integration)
tests/                        tests; fixtures/feed.json is a recorded feed
scripts/                      run_tests.sh, release.sh
```

* **Tests:** `./scripts/run_tests.sh`. The feed model (`tests/test_models.py`) needs only Python.
  The rest runs against a real Home Assistant:
  `python3.14 -m venv .venv && . .venv/bin/activate && pip install -r requirements_test.txt && pytest`.
* **Lint:** `ruff check . && ruff format --check .`
* **Version:** the single source is `version` in `manifest.json`.

### Releasing an update

1. Add a `## x.y.z - date` section to `CHANGELOG.md`.
2. `./scripts/release.sh x.y.z` bumps the manifest, runs the tests, commits and tags `vx.y.z`.
3. `git push && git push --tags`. The *Release* workflow checks that the tag matches the manifest,
   zips the integration and publishes the GitHub release; HACS offers it as an update.

CI (`.github/workflows`) runs hassfest and the HACS validation, lint, all tests, and the release.
The HACS validation needs the repository to be public and to have a description and topics.

## Licence

[MIT](LICENSE). Incident data: Oö. Landes-Feuerwehrverband.
