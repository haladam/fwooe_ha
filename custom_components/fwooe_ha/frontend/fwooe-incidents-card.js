/*
 * Feuerwehr OÖ Einsätze: dashboard card for the fwooe_ha integration.
 *
 * Shows the running incidents of a feed from the attributes of its "Incidents" sensor.
 * Shipped with the integration and registered by it: no resource to add, no build step, no
 * dependencies. The functions below that do not touch the page are exported so that they can be
 * tested with plain Node (tests/card.test.mjs).
 */

export const CARD_TYPE = "fwooe-incidents-card";

const DEFAULT_MAX_ITEMS = 5;
const ATTRIBUTION_MARK = "Feuerwehrverband";
const REFRESH_MS = 60 * 1000; // the relative times ("12 minutes ago") move on

const STRINGS = {
  en: {
    title: "Fire brigade incidents",
    empty: "No incidents right now",
    alarm_level: "Alarm level {n}",
    brigades_one: "{n} brigade",
    brigades_other: "{n} brigades",
    map: "Open on map",
    more: "+{n} more",
    no_entity:
      "No sensor of Feuerwehr OÖ Einsätze found. Choose its “Incidents” sensor in the card settings.",
    missing: "{entity} was not found.",
    wrong: "{entity} has no incident list. Choose the “Incidents” sensor of Feuerwehr OÖ Einsätze.",
    unavailable: "The incident feed is not available.",
    label_entity: "Incidents sensor",
    label_title: "Title",
    label_max_items: "Maximum number of incidents",
    label_show_units: "Show the alarmed brigades",
    label_show_distance: "Show the distance from home",
    helper_entity: "The “Incidents” sensor of the feed. Leave empty to use the first one found.",
    helper_title: "Leave empty for the default title.",
    description: "The running fire brigade incidents of a feed, with alarm level, distance and brigades.",
  },
  de: {
    title: "Feuerwehreinsätze",
    empty: "Derzeit keine Einsätze",
    alarm_level: "Alarmstufe {n}",
    brigades_one: "{n} Feuerwehr",
    brigades_other: "{n} Feuerwehren",
    map: "Auf der Karte öffnen",
    more: "+{n} weitere",
    no_entity:
      "Kein Sensor von Feuerwehr OÖ Einsätze gefunden. Wähle in den Karteneinstellungen den Sensor „Einsätze“.",
    missing: "{entity} wurde nicht gefunden.",
    wrong:
      "{entity} enthält keine Einsatzliste. Wähle den Sensor „Einsätze“ von Feuerwehr OÖ Einsätze.",
    unavailable: "Die Einsatzliste ist nicht erreichbar.",
    label_entity: "Sensor „Einsätze“",
    label_title: "Titel",
    label_max_items: "Höchstzahl der Einsätze",
    label_show_units: "Alarmierte Feuerwehren anzeigen",
    label_show_distance: "Entfernung von zuhause anzeigen",
    helper_entity: "Der Sensor „Einsätze“ des Feeds. Leer lassen, um den ersten gefundenen zu verwenden.",
    helper_title: "Leer lassen für den Standardtitel.",
    description:
      "Die laufenden Feuerwehreinsätze eines Feeds, mit Alarmstufe, Entfernung und Feuerwehren.",
  },
};

/** The strings for a language tag such as "de", "de-AT" or "en-GB" (English if unknown). */
export function strings(lang) {
  return String(lang || "").toLowerCase().startsWith("de") ? STRINGS.de : STRINGS.en;
}

function format(text, values = {}) {
  return text.replace(/\{(\w+)\}/g, (_, key) => (key in values ? String(values[key]) : ""));
}

/** Text for HTML: everything that comes from the feed goes through this. */
export function esc(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** The configuration with defaults; never throws. */
export function normalizeConfig(config) {
  const raw = config && typeof config === "object" ? config : {};
  const max = Math.floor(Number(raw.max_items));
  return {
    entity: typeof raw.entity === "string" ? raw.entity.trim() : "",
    title: typeof raw.title === "string" ? raw.title.trim() : "",
    max_items: Number.isFinite(max) && max >= 1 ? Math.min(max, 100) : DEFAULT_MAX_ITEMS,
    show_units: raw.show_units !== false,
    show_distance: raw.show_distance !== false,
  };
}

function hasIncidentList(stateObj) {
  return Boolean(stateObj) && Array.isArray(stateObj.attributes?.incidents);
}

/** The first "Incidents" sensor of the integration, for a card that was not given one. */
export function findIncidentsEntity(states) {
  return Object.keys(states || {})
    .sort()
    .find(
      (entityId) =>
        entityId.startsWith("sensor.") &&
        hasIncidentList(states[entityId]) &&
        String(states[entityId].attributes.attribution || "").includes(ATTRIBUTION_MARK),
    );
}

/** Great-circle distance in kilometres. */
export function distanceKm(lat1, lon1, lat2, lon2) {
  const rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad;
  const dLon = (lon2 - lon1) * rad;
  const a =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 6371.0088 * 2 * Math.asin(Math.min(1, Math.sqrt(a)));
}

function number(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** "12 minutes ago" / "vor 12 Minuten"; a start in the future counts as now. */
export function relativeTime(date, now, lang) {
  let formatter;
  try {
    formatter = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  } catch {
    formatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  }
  const seconds = Math.min(0, Math.round((date.getTime() - now.getTime()) / 1000));
  const abs = -seconds;
  if (abs < 45) return formatter.format(0, "second");
  if (abs < 45 * 60) return formatter.format(Math.round(seconds / 60), "minute");
  if (abs < 36 * 3600) return formatter.format(Math.round(seconds / 3600), "hour");
  return formatter.format(Math.round(seconds / 86400), "day");
}

function formatDistance(km, lang) {
  const digits = km < 100 ? 1 : 0;
  try {
    return `${new Intl.NumberFormat(lang, { maximumFractionDigits: digits }).format(km)} km`;
  } catch {
    return `${km.toFixed(digits)} km`;
  }
}

function toneOf(incident) {
  if (incident.self_initiated) return "self";
  return String(incident.kind || "").toUpperCase() === "BRAND" ? "fire" : "other";
}

const ICONS = { fire: "mdi:fire", self: "mdi:fire-truck", other: "mdi:alarm-light" };

function renderIncident(incident, options) {
  const { text, lang, now, home, config, openIds } = options;
  const tone = toneOf(incident);
  const place = [incident.location || incident.place, incident.district]
    .filter((part, index, parts) => part && parts.indexOf(part) === index)
    .join(" · ");

  const meta = [];
  const started = incident.start_time ? new Date(incident.start_time) : null;
  if (started && !Number.isNaN(started.getTime())) {
    meta.push(
      `<span title="${esc(started.toLocaleString(lang))}">${esc(relativeTime(started, now, lang))}</span>`,
    );
  }
  const level = number(incident.alarm_level);
  if (level !== null && level > 0) {
    meta.push(`<span class="chip">${esc(format(text.alarm_level, { n: level }))}</span>`);
  }

  const lat = number(incident.latitude);
  const lon = number(incident.longitude);
  const located = lat !== null && lon !== null;
  if (config.show_distance && located && home) {
    meta.push(`<span>${esc(formatDistance(distanceKm(home.latitude, home.longitude, lat, lon), lang))}</span>`);
  }

  const units = Array.isArray(incident.units) ? incident.units.map(String) : [];
  const count = number(incident.unit_count) ?? units.length;
  const countText = format(count === 1 ? text.brigades_one : text.brigades_other, { n: count });
  let brigades = "";
  if (config.show_units && units.length) {
    const id = esc(incident.id);
    brigades = `<details data-id="${id}"${openIds.has(String(incident.id)) ? " open" : ""}>
        <summary>${esc(countText)}</summary>
        <ul>${units.map((unit) => `<li>${esc(unit)}</li>`).join("")}</ul>
      </details>`;
  } else if (count > 0) {
    meta.push(`<span>${esc(countText)}</span>`);
  }

  const link = located
    ? `<a class="map" href="https://www.openstreetmap.org/?mlat=${lat.toFixed(5)}&amp;mlon=${lon.toFixed(5)}#map=15/${lat.toFixed(5)}/${lon.toFixed(5)}"
          target="_blank" rel="noopener noreferrer" title="${esc(text.map)}" aria-label="${esc(text.map)}">
         <ha-icon icon="mdi:map-marker"></ha-icon>
       </a>`
    : "";

  return `<article class="incident ${tone}">
      <div class="badge"><ha-icon icon="${ICONS[tone]}"></ha-icon></div>
      <div class="body">
        <div class="what">${esc(incident.description || incident.kind || "")}</div>
        ${place ? `<div class="where">${esc(place)}</div>` : ""}
        ${meta.length ? `<div class="meta">${meta.join("")}</div>` : ""}
        ${brigades}
      </div>
      ${link}
    </article>`;
}

function message(kind, content) {
  return `<div class="message ${kind}">${esc(content)}</div>`;
}

/**
 * The inside of the card as HTML.
 *
 * `context`: config (as given), entityId, stateObj, lang, home ({latitude, longitude}),
 * now (Date), openIds (Set of incident ids whose brigade list is open).
 * Returns {html, count}.
 */
export function renderBody(context) {
  const { entityId, stateObj, lang } = context;
  const config = normalizeConfig(context.config);
  const text = strings(lang);
  const now = context.now || new Date();
  const openIds = context.openIds || new Set();
  const title = config.title || text.title;

  const header = (count) =>
    `<div class="header"><span class="title">${esc(title)}</span>${
      count === null ? "" : `<span class="count${count ? "" : " none"}">${esc(count)}</span>`
    }</div>`;

  if (!entityId) return { html: header(null) + message("error", text.no_entity), count: 0 };
  if (!stateObj) {
    return { html: header(null) + message("error", format(text.missing, { entity: entityId })), count: 0 };
  }
  if (!hasIncidentList(stateObj)) {
    const unavailable = ["unavailable", "unknown"].includes(stateObj.state);
    return {
      html:
        header(null) +
        message("error", unavailable ? text.unavailable : format(text.wrong, { entity: entityId })),
      count: 0,
    };
  }

  const incidents = stateObj.attributes.incidents.filter((item) => item && typeof item === "object");
  const shown = incidents.slice(0, config.max_items);
  const hidden = incidents.length - shown.length;
  // The sensor's state is the number of matches, which may exceed what its list holds.
  const total = number(stateObj.state) ?? incidents.length;

  if (!incidents.length) return { html: header(0) + message("empty", text.empty), count: 0 };

  const options = { text, lang, now, home: context.home, config, openIds };
  const more = Math.max(hidden, total - shown.length);
  return {
    html:
      header(total) +
      `<div class="list">${shown.map((incident) => renderIncident(incident, options)).join("")}</div>` +
      (more > 0 ? `<div class="more">${esc(format(text.more, { n: more }))}</div>` : ""),
    count: shown.length,
  };
}

export const STYLE = `
  :host { display: block; }
  ha-card { overflow: hidden; }
  .header { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 16px 16px 8px; }
  .title { font-size: var(--ha-card-header-font-size, 24px); line-height: 1.2;
    letter-spacing: -0.012em; color: var(--ha-card-header-color, var(--primary-text-color)); }
  .count { min-width: 24px; box-sizing: border-box; padding: 2px 8px; border-radius: 12px;
    text-align: center; font-size: 14px; font-weight: 500;
    background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .count.none { background: var(--secondary-background-color); color: var(--secondary-text-color); }
  .list { padding-bottom: 4px; }
  .incident { --tone: var(--warning-color, #ffa600); display: grid;
    grid-template-columns: 40px minmax(0, 1fr) auto; gap: 12px; padding: 12px 16px;
    border-top: 1px solid var(--divider-color); }
  .incident.fire { --tone: var(--error-color, #db4437); }
  .incident.self { --tone: var(--secondary-text-color); }
  .badge { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
    color: var(--tone); background: color-mix(in srgb, var(--tone) 16%, transparent);
    --mdc-icon-size: 22px; }
  .what { font-weight: 500; color: var(--primary-text-color); overflow-wrap: anywhere; }
  .where { font-size: 14px; color: var(--secondary-text-color); overflow-wrap: anywhere; }
  .meta { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; margin-top: 6px;
    font-size: 13px; color: var(--secondary-text-color); }
  .chip { padding: 1px 8px; border-radius: 10px; font-weight: 500; color: var(--tone);
    background: color-mix(in srgb, var(--tone) 16%, transparent); }
  details { margin-top: 6px; font-size: 13px; color: var(--secondary-text-color); }
  summary { cursor: pointer; width: fit-content; }
  summary:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }
  ul { margin: 6px 0 0; padding-left: 18px; columns: 2 14em; }
  li { break-inside: avoid; overflow-wrap: anywhere; }
  .map { align-self: start; display: grid; place-items: center; width: 40px; height: 40px;
    margin: -8px -8px -8px 0; border-radius: 50%; color: var(--secondary-text-color);
    text-decoration: none; }
  .map:hover, .map:focus-visible { background: var(--secondary-background-color); outline: none; }
  .message { padding: 8px 16px 16px; color: var(--secondary-text-color); }
  .message.error { color: var(--error-color, #db4437); }
  .more { padding: 4px 16px 12px; font-size: 13px; color: var(--secondary-text-color); }
`;

/* ---- the custom element (only where there is a page) ---- */

let currentLanguage = "en";

function languageOf(hass) {
  return hass?.locale?.language || hass?.language || "en";
}

if (typeof HTMLElement !== "undefined" && typeof customElements !== "undefined") {
  class FwooeIncidentsCard extends HTMLElement {
    constructor() {
      super();
      this._config = normalizeConfig({});
      this._rawConfig = {};
      this._open = new Set();
      this._rendered = null;
      this._count = 0;
      this.attachShadow({ mode: "open" });
      // "toggle" does not bubble: listen while it travels down.
      this.shadowRoot.addEventListener(
        "toggle",
        (event) => {
          const id = event.target?.dataset?.id;
          if (id === undefined) return;
          if (event.target.open) this._open.add(id);
          else this._open.delete(id);
        },
        true,
      );
    }

    static getConfigForm() {
      const text = () => strings(currentLanguage);
      return {
        schema: [
          {
            name: "entity",
            selector: { entity: { filter: { domain: "sensor", integration: "fwooe_ha" } } },
          },
          { name: "title", selector: { text: {} } },
          { name: "max_items", selector: { number: { min: 1, max: 20, mode: "box" } } },
          {
            type: "grid",
            name: "",
            schema: [
              { name: "show_units", selector: { boolean: {} } },
              { name: "show_distance", selector: { boolean: {} } },
            ],
          },
        ],
        computeLabel: (schema) => text()[`label_${schema.name}`] ?? schema.name,
        computeHelper: (schema) => text()[`helper_${schema.name}`] ?? undefined,
      };
    }

    static getStubConfig(hass) {
      const entity = findIncidentsEntity(hass?.states);
      return entity ? { entity } : {};
    }

    setConfig(config) {
      if (!config || typeof config !== "object") throw new Error("Invalid configuration");
      this._rawConfig = config;
      this._config = normalizeConfig(config);
      this._render(true);
    }

    set hass(hass) {
      this._hass = hass;
      currentLanguage = languageOf(hass);
      this._render(false);
    }

    connectedCallback() {
      this._timer = setInterval(() => this._render(true), REFRESH_MS);
      this._render(true);
    }

    disconnectedCallback() {
      clearInterval(this._timer);
      this._timer = undefined;
    }

    getCardSize() {
      return 1 + 2 * Math.max(1, this._count);
    }

    getGridOptions() {
      return { columns: 12, min_columns: 6, rows: "auto" };
    }

    _render(force) {
      const hass = this._hass;
      if (!hass) return;
      const entityId = this._config.entity || findIncidentsEntity(hass.states);
      const stateObj = entityId ? hass.states[entityId] : undefined;
      const lang = languageOf(hass);
      const home = Number.isFinite(hass.config?.latitude)
        ? { latitude: hass.config.latitude, longitude: hass.config.longitude }
        : null;

      const signature = [entityId, stateObj, lang, home?.latitude, home?.longitude, this._config];
      if (
        !force &&
        this._rendered &&
        signature.every((value, index) => value === this._rendered[index])
      ) {
        return;
      }
      this._rendered = signature;

      const { html, count } = renderBody({
        config: this._config,
        entityId,
        stateObj,
        lang,
        home,
        now: new Date(),
        openIds: this._open,
      });
      this._count = count;
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>${html}</ha-card>`;
    }
  }

  if (!customElements.get(CARD_TYPE)) customElements.define(CARD_TYPE, FwooeIncidentsCard);

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
    window.customCards.push({
      type: CARD_TYPE,
      name: "Feuerwehr OÖ Einsätze",
      description: strings(typeof navigator === "undefined" ? "en" : navigator.language).description,
      preview: true,
      documentationURL: "https://github.com/haladam/fwooe_ha#dashboard-card",
    });
  }
}
