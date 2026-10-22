# Changelog

Newest first. The version in `custom_components/fwooe_ha/manifest.json` and the latest section
below always match.

## 0.1.0 - 2026-10-22

First release as a HACS custom integration (before this, the repository held loose files).

* The integration is installable through HACS: `custom_components/fwooe_ha/` layout, `hacs.json`,
  hassfest and HACS validation, tests and a release workflow in CI, icon and logo.
* Domain `fwooe_ha`.
* Setup tests the feed. Districts, keywords, minimum alarm level, the number of incidents and the
  update interval are options that can be changed later (no need to delete and add the integration).
* Districts are chosen from the list of Upper Austria's districts and matched exactly (a filter for
  "Linz" no longer also matches "Linz-Land" or any address containing "Linz").
* Self-initiated deployments and exercises (`SELBST`) are an option and hidden by default; the
  "Incidents in feed" diagnostic sensor still counts everything.
* The newest incidents are listed first (before, which ones survived the limit depended on the order
  of the feed). The alarm level is a number.
* New: *Latest incident* and *Latest incident started* sensors, *Active incident* binary sensor,
  *Incident alert* event entity (`new_incident`, `alarm_level_raised`), and a `geo_location` entity per
  incident for the map card.
* Brigade names are cleaned (`Feuerwehr/Florian Perg (42312)` is now `Florian Perg`).
* The long incident list is no longer written to the database with every state change (with many
  incidents it could exceed the 16 KB attribute limit of the recorder).
* Timeouts and connection errors are reported as one line instead of a stack trace every minute;
  the integration retries until the feed is back. Dates no longer depend on the system locale.
* German and English translations, diagnostics download.
