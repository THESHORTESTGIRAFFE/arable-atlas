/* Shared language preference, safe storage, and plain-text rendering. */
(() => {
  const catalogs = JSON.parse(document.getElementById('translationCatalogs').textContent);
  const storage = {
    get(key, fallback = null) { try { const raw = localStorage.getItem(`arable.${key}`); return raw ? JSON.parse(raw) : fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(`arable.${key}`, JSON.stringify(value)); } catch { /* Browser storage is optional. */ } }
  };
  let language = storage.get('language', 'en');
  if (!catalogs[language]) language = 'en';
  function t(key, values = {}) {
    let value = catalogs[language][key] || catalogs.en[key] || key;
    Object.entries(values).forEach(([key, replacement]) => { value = value.replaceAll(`{${key}}`, String(replacement)); });
    return value;
  }
  function apply() {
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : language;
    document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = t(el.dataset.i18nPlaceholder); });
    document.querySelectorAll('[data-i18n-title]').forEach(el => { el.title = t(el.dataset.i18nTitle); el.setAttribute('aria-label', el.title); });
    document.getElementById('languageSelect').value = language;
  }
  const element = (tag, className = '', text = '') => {
    const el = document.createElement(tag); el.className = className; el.textContent = text; return el;
  };
  async function post(url, data) {
    const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
    let body;
    try { body = await response.json(); } catch { throw new Error(t('request_error')); }
    if (!response.ok || body.error) throw new Error(body.error_key ? t(body.error_key) : t('request_error'));
    return body;
  }
  window.Atlas = { t, storage, element, post, get language() { return language; },
    date(value) { return new Intl.DateTimeFormat(document.documentElement.lang, { month: 'short', day: 'numeric' }).format(new Date(`${value}T12:00:00Z`)); },
    soil(value) { return t(({ 'Clayey Soil': 'clay_soil', 'Sandy Soil': 'sand_soil', 'Silty Soil': 'silt_soil', 'Loamy Soil': 'loam_soil', 'Mixed Soil': 'mixed_soil' })[value] || 'unknown'); }
  };
  document.getElementById('languageSelect').addEventListener('change', event => {
    language = event.target.value; storage.set('language', language); apply();
    window.dispatchEvent(new CustomEvent('atlas:language'));
  });
  apply();
})();
