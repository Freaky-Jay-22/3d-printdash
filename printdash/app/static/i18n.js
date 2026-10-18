"use strict";
/* ---------- translations ----------
 * The German text in the code is the key (like gettext). t("Text {0}", value)
 * returns the translation for the current language, or the German text.
 * To add a language: add an object to I18N (same keys as "en") and an entry
 * in LANGUAGES. Missing entries fall back to English, then German.
 */
const LANGUAGES = { de: "Deutsch", en: "English" };
const I18N = { en: {} }; // filled by static/lang/*.js

function browserLang() {
  for (const l of navigator.languages || [navigator.language || "en"]) {
    const code = String(l).slice(0, 2).toLowerCase();
    if (LANGUAGES[code]) return code;
  }
  return "en";
}
// the language chosen in the settings is remembered in the browser, so the
// page starts in the right language before the server has answered
function detectLang() {
  let pref = "";
  try { pref = localStorage.getItem("pf-lang") || ""; } catch { /* ignore */ }
  return pref && LANGUAGES[pref] ? pref : browserLang();
}
let LANG = detectLang();

// locale for dates and numbers: the browser's own one if it matches the language
function localeFor(lang) {
  const nav = navigator.language || "";
  if (nav.slice(0, 2).toLowerCase() === lang) return nav;
  return { de: "de-CH", en: "en-GB" }[lang] || lang;
}
let LOCALE = localeFor(LANG);
document.documentElement.lang = LANG;

// called with the server setting ("" = automatic); reloads once if it differs
function syncLanguage(server) {
  const want = server && LANGUAGES[server] ? server : browserLang();
  try {
    if (server && LANGUAGES[server]) localStorage.setItem("pf-lang", server); else localStorage.removeItem("pf-lang");
  } catch { /* ignore */ }
  if (want === LANG) { try { sessionStorage.removeItem("pf-lang-reload"); } catch { /* ignore */ } return; }
  let tries = 0;
  try { tries = Number(sessionStorage.getItem("pf-lang-reload") || 0); sessionStorage.setItem("pf-lang-reload", String(tries + 1)); } catch { tries = 9; }
  if (tries < 3) location.reload();
}

function t(text, ...args) {
  let out = text;
  if (LANG !== "de") out = I18N[LANG]?.[text] ?? I18N.en?.[text] ?? text;
  // "Text|context" keys tell apart equal German words with different translations
  if (out === text && text.includes("|")) out = text.split("|")[0];
  return args.length ? out.replace(/\{(\d+)\}/g, (m, i) => (args[i] ?? "")) : out;
}

// plural: tn(n, "{0} Spule", "{0} Spulen") – the count is {0}
function tn(n, one, many, ...args) {
  return t(n === 1 ? one : many, n, ...args);
}

// static texts in the HTML: data-i18n (text), data-i18n-attr="aria-label,title"
function translateStatic(root = document) {
  root.querySelectorAll("[data-i18n]").forEach((n) => {
    if (!n.dataset.i18nSrc) n.dataset.i18nSrc = n.textContent.trim();
    n.textContent = t(n.dataset.i18nSrc);
  });
  root.querySelectorAll("[data-i18n-attr]").forEach((n) => {
    for (const a of n.dataset.i18nAttr.split(",")) {
      const key = `i18nSrc${a.replace(/[^a-z]/gi, "")}`;
      if (!n.dataset[key]) n.dataset[key] = n.getAttribute(a) || "";
      n.setAttribute(a, t(n.dataset[key]));
    }
  });
  if (document.title && !document.documentElement.dataset.titleSrc) document.documentElement.dataset.titleSrc = document.title;
  if (document.documentElement.dataset.titleSrc) document.title = t(document.documentElement.dataset.titleSrc);
}

/* ---------- currency ---------- */
const CURRENCIES = ["CHF", "EUR", "USD", "GBP", "CAD", "AUD", "NZD", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "JPY", "CNY", "INR", "BRL", "ZAR"];
const EURO_REGIONS = ["AT", "BE", "CY", "DE", "EE", "ES", "FI", "FR", "GR", "HR", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PT", "SI", "SK"];
const REGION_CURRENCY = { CH: "CHF", LI: "CHF", US: "USD", GB: "GBP", CA: "CAD", AU: "AUD", NZ: "NZD", SE: "SEK", NO: "NOK",
  DK: "DKK", PL: "PLN", CZ: "CZK", HU: "HUF", JP: "JPY", CN: "CNY", IN: "INR", BR: "BRL", ZA: "ZAR" };

// currency for "automatic": from the region of the browser language (de-CH → CHF)
function guessCurrency() {
  for (const l of navigator.languages || [navigator.language || ""]) {
    const region = String(l).split("-")[1]?.toUpperCase();
    if (!region) continue;
    if (REGION_CURRENCY[region]) return REGION_CURRENCY[region];
    if (EURO_REGIONS.includes(region)) return "EUR";
  }
  return "EUR";
}

function fmtMoney(value, currency, digits = 2) {
  const cur = (currency || guessCurrency()).trim();
  const n = Number(value) || 0;
  if (/^[A-Z]{3}$/.test(cur)) {
    try {
      return new Intl.NumberFormat(LOCALE, { style: "currency", currency: cur,
        minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
    } catch { /* unknown code: fall through */ }
  }
  return `${cur} ${n.toFixed(digits)}`;
}
