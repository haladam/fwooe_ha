# Fixtures

`feed.json` is the running-incident feed (`json_laufend.txt`) as it looked on 2026-10-22 around
12:50: six self-initiated deployments (`SELBST`) and one industrial fire (`BRAND`, alarm level 3,
16 brigades). It was rebuilt from the values read from the live feed, so the field names and
the shape (`einsaetze` -> `"0"` -> `einsatz` ...) are the real ones.

`card_state.json` is the *Incidents* sensor (state and attributes) with all seven incidents of
`feed.json` shown, as the dashboard card receives it. `tests/test_models.py` checks that it equals
what the model produces, so the card test (`tests/card.test.mjs`) works on real data.

`website_bezirke.html` is the district filter of einsaetze.ooelfv.at (the `<select name="bezirk">`)
as copied from the page. The tests check that the list of Bezirke in `models.py` is exactly this one.
