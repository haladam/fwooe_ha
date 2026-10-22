// Tests of the dashboard card's logic. Plain Node, no packages:  node --test tests/card.test.mjs
//
// They cover everything that does not need a browser: what is rendered for which sensor state,
// that nothing from the feed can inject HTML, distances, relative times, the language.
// tests/fixtures/card_state.json is the Incidents sensor as the integration writes it (a Python
// test keeps it equal to what the model produces).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const card = await import(
  new URL("../custom_components/fwooe_ha/frontend/fwooe-incidents-card.js", import.meta.url)
);
const SENSOR = JSON.parse(readFileSync(`${here}fixtures/card_state.json`, "utf-8"));

const NOW = new Date("2026-10-22T14:30:00+02:00");
const LINZ = { latitude: 48.3069, longitude: 14.2858 };
const FIRE = "E261004261";

function render(overrides = {}) {
  return card.renderBody({
    config: { entity: SENSOR.entity_id },
    entityId: SENSOR.entity_id,
    stateObj: SENSOR,
    lang: "en",
    home: LINZ,
    now: NOW,
    ...overrides,
  });
}

function sensorWith(incidents, state = String(incidents.length)) {
  return { ...SENSOR, state, attributes: { ...SENSOR.attributes, incidents } };
}

const fireOnly = () => sensorWith(SENSOR.attributes.incidents.filter((i) => i.id === FIRE));

test("importing the card in Node defines nothing global", () => {
  assert.equal(typeof customElements, "undefined");
  assert.equal(card.CARD_TYPE, "fwooe-incidents-card");
});

test("the fire is shown with its details", () => {
  const { html, count } = render({ stateObj: fireOnly() });
  assert.equal(count, 1);
  assert.match(html, /Brand Industrie - Brand Gewerbe/);
  assert.match(html, /Katsdorf · Perg/);
  assert.match(html, /Alarm level 3/);
  assert.match(html, /class="incident fire"/);
  assert.match(html, /<summary>16 brigades<\/summary>/);
  assert.match(html, /<li>Florian Katsdorf<\/li>/);
  assert.match(html, /8 hours ago/); // 06:28 to 14:30
  assert.match(html, /<span class="count">1<\/span>/);
});

test("the distance is the great-circle distance from home", () => {
  // Linz to Katsdorf: 0.2233 degrees of longitude at 48.3 degrees north, about 16.5 km
  const km = card.distanceKm(48.3069, 14.2858, 48.3122, 14.5091);
  assert.ok(Math.abs(km - 16.5) < 0.1, km);
  assert.equal(card.distanceKm(48, 14, 48, 14), 0);
  // one degree of latitude is about 111 km
  assert.ok(Math.abs(card.distanceKm(48, 14, 49, 14) - 111.2) < 0.5);
  assert.match(render({ stateObj: fireOnly() }).html, /<span>16\.5 km<\/span>/);
});

test("the distance can be switched off, and is left out without a home", () => {
  assert.doesNotMatch(
    render({ stateObj: fireOnly(), config: { show_distance: false } }).html,
    / km</,
  );
  assert.doesNotMatch(render({ stateObj: fireOnly(), home: null }).html, / km</);
});

test("the brigades can be reduced to a count", () => {
  const { html } = render({ stateObj: fireOnly(), config: { show_units: false } });
  assert.doesNotMatch(html, /<details/);
  assert.match(html, /<span>16 brigades<\/span>/);
});

test("a brigade list that was opened stays open when the card is drawn again", () => {
  const closed = render({ stateObj: fireOnly() }).html;
  const open = render({ stateObj: fireOnly(), openIds: new Set([FIRE]) }).html;
  assert.match(closed, /<details data-id="E261004261">/);
  assert.match(open, /<details data-id="E261004261" open>/);
});

test("self-initiated deployments are muted and have no alarm level chip", () => {
  const { html } = render();
  assert.match(html, /class="incident self"/);
  assert.match(html, /<div class="badge"><ha-icon icon="mdi:fire-truck">/);
  assert.match(html, /<summary>1 brigade<\/summary>/);
  assert.doesNotMatch(html, /Alarm level 0/);
});

test("only max_items are listed, the rest is counted", () => {
  const { html, count } = render({ config: { max_items: 2 } });
  assert.equal(count, 2);
  assert.equal(html.match(/<article/g).length, 2);
  assert.match(html, /\+5 more/);
  assert.match(html, /<span class="count">7<\/span>/);
});

test("a state that is higher than the list adds to the remainder", () => {
  // the sensor lists at most its own limit but counts all matches
  const sensor = sensorWith(SENSOR.attributes.incidents.slice(0, 3), "9");
  assert.match(render({ stateObj: sensor, config: { max_items: 3 } }).html, /\+6 more/);
});

test("max_items is made sensible", () => {
  assert.equal(card.normalizeConfig({}).max_items, 5);
  assert.equal(card.normalizeConfig({ max_items: "3" }).max_items, 3);
  assert.equal(card.normalizeConfig({ max_items: 0 }).max_items, 5);
  assert.equal(card.normalizeConfig({ max_items: -2 }).max_items, 5);
  assert.equal(card.normalizeConfig({ max_items: 5000 }).max_items, 100);
  assert.equal(card.normalizeConfig(null).show_units, true);
  assert.equal(card.normalizeConfig({ show_units: false }).show_units, false);
  assert.equal(card.normalizeConfig({ title: "  Home  " }).title, "Home");
});

test("no incident gives a calm message and a grey count", () => {
  const { html, count } = render({ stateObj: sensorWith([]) });
  assert.equal(count, 0);
  assert.match(html, /No incidents right now/);
  assert.match(html, /class="count none">0</);
});

test("the title can be changed", () => {
  assert.match(render({ config: { title: "Perg" } }).html, /<span class="title">Perg<\/span>/);
  assert.match(render().html, /<span class="title">Fire brigade incidents<\/span>/);
});

test("German", () => {
  const { html } = render({ stateObj: fireOnly(), lang: "de" });
  assert.match(html, /Feuerwehreinsätze/);
  assert.match(html, /Alarmstufe 3/);
  assert.match(html, /16 Feuerwehren/);
  assert.match(html, /vor 8 Stunden/);
  assert.match(html, /16,5 km/);
  assert.match(render({ stateObj: sensorWith([]), lang: "de-AT" }).html, /Derzeit keine Einsätze/);
  assert.match(render({ stateObj: sensorWith([]), lang: "fr" }).html, /No incidents right now/);
});

test("singular and plural of brigades", () => {
  const one = sensorWith([{ ...SENSOR.attributes.incidents[0], units: [], unit_count: 1 }]);
  assert.match(render({ stateObj: one }).html, /1 brigade</);
  const none = sensorWith([{ ...SENSOR.attributes.incidents[0], units: [], unit_count: 0 }]);
  assert.doesNotMatch(render({ stateObj: none }).html, /\d brigade/);
});

test("the map link opens the position on OpenStreetMap", () => {
  const { html } = render({ stateObj: fireOnly() });
  assert.match(html, /href="https:\/\/www\.openstreetmap\.org\/\?mlat=48\.31220&amp;mlon=14\.50910#map=15\/48\.31220\/14\.50910"/);
  assert.match(html, /rel="noopener noreferrer"/);
});

test("an incident without a position has no map link and no distance", () => {
  const sensor = sensorWith([{ ...SENSOR.attributes.incidents[3], latitude: null, longitude: null }]);
  const { html } = render({ stateObj: sensor });
  assert.doesNotMatch(html, /openstreetmap/);
  assert.doesNotMatch(html, / km</);
});

test("nothing from the feed can inject HTML", () => {
  const evil = {
    ...SENSOR.attributes.incidents[3],
    id: '"><script>alert(1)</script>',
    description: "<img src=x onerror=alert(1)>",
    location: "<b>Katsdorf</b>",
    district: "Perg\"'&",
    units: ["<script>alert(2)</script>", "Florian & Co"],
    start_time: '"><svg onload=alert(3)>',
    alarm_level: "<i>3</i>",
    latitude: "48.3\"><script>",
    longitude: "14.5",
  };
  const { html } = render({ stateObj: sensorWith([evil]), openIds: new Set([evil.id]) });
  assert.doesNotMatch(html, /<script/i);
  assert.doesNotMatch(html, /<img/i);
  assert.doesNotMatch(html, /<svg/i);
  assert.doesNotMatch(html, /<b>/);
  assert.doesNotMatch(html, /<i>/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /&lt;script&gt;alert\(2\)&lt;\/script&gt;/);
  assert.match(html, /Florian &amp; Co/);
  assert.doesNotMatch(html, /openstreetmap/); // the garbled latitude is not a number
});

test("odd values do not break the card", () => {
  const odd = [
    null,
    "text",
    42,
    { id: 1 },
    { id: 2, start_time: "not a date", units: "x", unit_count: "many", alarm_level: null },
  ];
  const { html, count } = render({ stateObj: sensorWith(odd, "5") });
  assert.equal(count, 2);
  assert.equal(html.match(/<article/g).length, 2);
});

test("messages for a missing, wrong or unavailable sensor", () => {
  assert.match(render({ entityId: undefined, stateObj: undefined }).html, /No sensor of Feuerwehr/);
  assert.match(
    render({ entityId: "sensor.nope", stateObj: undefined }).html,
    /sensor\.nope was not found/,
  );
  const wrong = { entity_id: "sensor.other", state: "5", attributes: {} };
  assert.match(render({ entityId: "sensor.other", stateObj: wrong }).html, /has no incident list/);
  const unavailable = { entity_id: SENSOR.entity_id, state: "unavailable", attributes: {} };
  assert.match(render({ stateObj: unavailable }).html, /not available/);
  assert.match(render({ stateObj: unavailable, lang: "de" }).html, /nicht erreichbar/);
});

test("the sensor of the integration is found among all entities", () => {
  const states = {
    "sensor.temperature": { state: "21", attributes: {} },
    "sensor.somebody_elses_incidents": {
      state: "1",
      attributes: { incidents: [{}], attribution: "Another service" },
    },
    "sensor.latest": { state: "x", attributes: { attribution: SENSOR.attributes.attribution } },
    [SENSOR.entity_id]: SENSOR,
    "sensor.zz_second_feed": { ...SENSOR, entity_id: "sensor.zz_second_feed" },
  };
  assert.equal(card.findIncidentsEntity(states), SENSOR.entity_id);
  assert.equal(card.findIncidentsEntity({}), undefined);
  assert.equal(card.findIncidentsEntity(undefined), undefined);
});

test("relative times", () => {
  const at = (iso) => card.relativeTime(new Date(iso), NOW, "en");
  assert.equal(at("2026-10-22T14:29:50+02:00"), "now");
  assert.equal(at("2026-10-22T14:00:00+02:00"), "30 minutes ago");
  assert.equal(at("2026-10-22T06:28:48+02:00"), "8 hours ago");
  assert.equal(at("2026-10-20T14:30:00+02:00"), "2 days ago");
  assert.equal(at("2026-10-22T15:30:00+02:00"), "now"); // a clock that is ahead is not "in 1 hour"
  assert.equal(card.relativeTime(new Date("2026-10-22T14:00:00+02:00"), NOW, "de"), "vor 30 Minuten");
  assert.equal(card.relativeTime(new Date("2026-10-22T14:00:00+02:00"), NOW, "??"), "30 minutes ago");
});

test("esc escapes the five characters that matter", () => {
  assert.equal(card.esc(`<a href="x">'&'</a>`), "&lt;a href=&quot;x&quot;&gt;&#39;&amp;&#39;&lt;/a&gt;");
  assert.equal(card.esc(null), "");
  assert.equal(card.esc(0), "0");
});

test("the strings of both languages have the same keys", () => {
  const en = Object.keys(card.strings("en")).sort();
  const de = Object.keys(card.strings("de")).sort();
  assert.deepEqual(en, de);
});
