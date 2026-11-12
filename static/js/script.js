/** Field analysis, forecast actions, saved reports, and language switching. */
document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('map')) return;
  const A = window.Atlas, $ = id => document.getElementById(id);
  let report = A.storage.get('report'), selected = null, marker = null, map = null, busy = false, translationVersion = 0;
  const translatedReports = new Map();
  let savedFields = [];
  if (window.L) {
    map = L.map('map').setView([-19.0154, 29.1549], 6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap contributors' }).addTo(map);
    map.on('click', event => select(event.latlng.lat, event.latlng.lng));
  } else {
    $('map').append(A.element('p', 'alert alert-warning', A.t('request_error')));
  }
  function select(lat, lon) {
    selected = { lat, lon };
    $('manualLat').value = lat; $('manualLon').value = lon;
    if (!map) return;
    if (marker) marker.remove();
    marker = L.marker([lat, lon]).addTo(map);
    map.setView([lat, lon], 12);
  }
  function status(message, error = false) {
    $('dashboardStatus').textContent = message;
    $('dashboardStatus').className = message ? `alert ${error ? 'alert-warning' : 'alert-success'}` : 'alert d-none';
  }
  function setBusy(value) {
    busy = value;
    ['processAnalysis', 'getLocation', 'refreshPlan', 'saveField', 'useManualSoil', 'demoField'].forEach(id => { $(id).disabled = value; });
    $('uploadForm').querySelector('button').disabled = value;
    $('loader').classList.toggle('d-none', !value);
    $('languageSelect').disabled = value;
    $('savedFields').querySelectorAll('button').forEach(button => { button.disabled = value; });
  }
  function details() { return { crop: $('fieldCrop').value.trim(), planting_date: $('plantingDate').value }; }
  function persist() { A.storage.set('report', report); }
  function renderForecast() {
    const forecast = report?.forecast;
    $('forecastDays').replaceChildren(); $('actionDays').replaceChildren();
    $('forecastTime').textContent = forecast?.fetched_at ? new Date(forecast.fetched_at).toLocaleString(document.documentElement.lang) : '';
    if (!forecast || forecast.status !== 'available') {
      for (const id of ['forecastDays', 'actionDays']) $(id).append(A.element('p', 'text-muted mb-0', A.t(report ? 'weather_unavailable' : 'pending')));
      return;
    }
    for (const day of forecast.days) {
      const card = A.element('article', 'forecast-day p-3 rounded-4 bg-light');
      card.append(A.element('h3', 'h6', A.date(day.date) + (day.partial ? ' *' : '')),
        A.element('p', 'fw-bold fs-5 mb-2', `${day.temp_min}–${day.temp_max}°C`),
        A.element('p', 'small mb-1', `${A.t('rain')}: ${day.rain_mm} mm`),
        A.element('p', 'small mb-0', `${A.t('wind')}: ${day.wind_ms} m/s`));
      $('forecastDays').append(card);
      const column = A.element('div', 'col-md-6 col-xl-4');
      const plan = A.element('article', 'p-3 border rounded-4 h-100');
      plan.append(A.element('h3', 'h6 text-primary', A.date(day.date)));
      const list = A.element('ul', 'small mb-0 ps-3');
      const rules = report.action_plan?.days?.find(item => item.date === day.date)?.rules || [];
      const actions = rules.map(key => A.t(key));
      if (report.planting_date) {
        const days = Math.round((new Date(`${day.date}T00:00:00Z`) - new Date(`${report.planting_date}T00:00:00Z`)) / 86400000);
        actions.push(A.t(days < 0 ? 'before_planting' : 'after_planting', { days }));
      }
      actions.forEach(action => list.append(A.element('li', 'mb-2', action)));
      plan.append(list); column.append(plan); $('actionDays').append(column);
    }
  }
  function render() {
    if (!report) { renderForecast(); return; }
    $('locationName').removeAttribute('data-i18n');
    $('locationName').textContent = report.location || A.t('location_unavailable');
    const fields = { latitude: 'latitude', longitude: 'longitude', phLevel: 'ph', nitrogen: 'nitrogen', clay: 'clay', sand: 'sand', silt: 'silt', organic_carbon_density: 'organic_carbon_density' };
    for (const [id, key] of Object.entries(fields)) $(id).textContent = report[key] === 'N/A' ? '—' : (report[key] ?? '—');
    $('soilType').textContent = A.soil(report.soil_type);
    $('cropBadges').replaceChildren();
    (report.crops || []).forEach(crop => $('cropBadges').append(A.element('span', 'badge rounded-pill bg-white text-primary', crop)));
    $('cropsText').removeAttribute('data-i18n');
    $('cropsText').textContent = report.actionable_advice || A.t('soil_unavailable');
    $('soilProvenance').removeAttribute('data-i18n');
    const manual = report.soil_method === 'manual';
    $('soilProvenance').textContent = manual ? A.t('manual_note', { depth: report.depth, date: report.sample_date || A.t('unknown') }) : A.t('estimate_note');
    const downloads = Object.values(report.soil_fetched_at || {}).map(value => new Date(value).getTime()).filter(Number.isFinite);
    $('soilAccess').textContent = manual ? '' : [A.t(report.soil_access === 'cache' ? 'soil_cached' : report.soil_access === 'wcs' ? 'soil_wcs' : 'soil_unavailable'),
      downloads.length ? `${A.t('downloaded')}: ${new Date(Math.min(...downloads)).toLocaleString(document.documentElement.lang)}` : ''].filter(Boolean).join(' · ');
    const propertyLabels = { phh2o: 'ph', ocd: 'carbon', nitrogen: 'nitrogen', clay: 'clay', sand: 'sand', silt: 'silt' };
    $('soilMissing').textContent = report.missing_properties?.length && report.soil_status !== 'unavailable' ? `${A.t('missing_properties')}: ${report.missing_properties.map(key => A.t(propertyLabels[key] || 'unknown')).join(', ')}` : '';
    renderForecast();
  }
  function useReport(value, name = '') {
    translationVersion++;
    report = value; translatedReports.clear();
    $('fieldCrop').value = report.crop || ''; $('plantingDate').value = report.planting_date || '';
    $('fieldName').value = name;
    select(report.latitude, report.longitude); persist(); render();
  }
  async function runAnalysis(formData = null) {
    if (busy) return;
    if (!formData && !selected) { status(A.t('select_first'), true); return; }
    setBusy(true); status(A.t('working'));
    translationVersion++;
    try {
      let result;
      if (formData) {
        formData.append('language', A.language);
        for (const [key, value] of Object.entries(details())) formData.append(key, value);
        const response = await fetch('/upload', { method: 'POST', body: formData });
        let body; try { body = await response.json(); } catch { throw new Error(A.t('request_error')); }
        if (!response.ok) throw new Error(A.t(body.error_key || 'request_error'));
        result = body;
      } else result = await A.post('/process', { ...selected, ...details(), language: A.language });
      useReport(result); status(result.soil_status === 'unavailable' ? A.t('soil_unavailable') : '', result.soil_status === 'unavailable');
      if (result.soil_status === 'unavailable') $('manualSoilPanel').open = true;
    } catch (error) { status(error.message || A.t('request_error'), true); }
    finally { setBusy(false); }
  }
  $('processAnalysis').addEventListener('click', () => runAnalysis());
  $('demoField').addEventListener('click', () => {
    const demo = JSON.parse($('demoFieldCoordinates').textContent);
    select(demo.lat, demo.lon); runAnalysis();
  });
  $('uploadForm').addEventListener('submit', event => { event.preventDefault(); runAnalysis(new FormData(event.target)); });
  $('manualSoilForm').addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    const values = Object.fromEntries(new FormData(event.target));
    const { lat, lon, ...manual_soil } = values;
    setBusy(true); translationVersion++; status(A.t('working'));
    try {
      const result = await A.post('/process', { lat, lon, manual_soil, ...details(), language: A.language });
      useReport(result); status('');
    } catch (error) { status(error.message || A.t('request_error'), true); }
    finally { setBusy(false); }
  });
  $('getLocation').addEventListener('click', () => {
    if (!navigator.geolocation) { status(A.t('request_error'), true); return; }
    status(A.t('finding')); $('getLocation').disabled = true;
    navigator.geolocation.getCurrentPosition(position => {
      select(position.coords.latitude, position.coords.longitude); $('getLocation').disabled = false; status('');
    }, () => { $('getLocation').disabled = false; status(A.t('request_error'), true); }, { timeout: 10000, enableHighAccuracy: true });
  });
  async function refreshPlan() {
    if (!report) throw new Error(A.t('select_first'));
    const result = await A.post('/api/plan', { lat: report.latitude, lon: report.longitude, ...details(), language: A.language });
    report = { ...report, ...result }; persist(); renderForecast();
  }
  $('planForm').addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    setBusy(true); status(A.t('working'));
    try { await refreshPlan(); status(''); } catch (error) { status(error.message, true); }
    finally { setBusy(false); }
  });
  $('saveFieldForm').addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    if (!report) { status(A.t('select_first'), true); return; }
    setBusy(true);
    try {
      if (JSON.stringify(details()) !== JSON.stringify({ crop: report.crop || '', planting_date: report.planting_date || '' })) await refreshPlan();
      await A.post('/api/plots', { ...details(), plot_name: $('fieldName').value.trim(), latitude: report.latitude, longitude: report.longitude, report });
      status(A.t('saved')); await loadSaved();
    } catch (error) { status(error.message, true); } finally { setBusy(false); }
  });
  function renderSaved() {
    $('savedFields').replaceChildren();
    if (!savedFields.length) $('savedFields').append(A.element('p', 'text-muted', A.t('no_fields')));
    for (const field of savedFields) {
      const column = A.element('div', 'col-md-6 col-lg-4');
      const card = A.element('article', 'glass-panel p-4 bg-white h-100');
      card.append(A.element('h3', 'h5', field.plot_name),
        A.element('p', 'small text-muted', `${field.crop || A.soil(field.soil_type)} · ${new Date(field.timestamp + 'Z').toLocaleString(document.documentElement.lang)}`));
      const open = A.element('button', 'btn btn-sm btn-outline-primary rounded-pill', A.t('open'));
      open.disabled = busy;
      open.addEventListener('click', async () => {
        if (busy) return;
        useReport(field.report, field.plot_name); status(''); await translateReport(); window.scrollTo({ top: 0, behavior: 'smooth' });
      });
      card.append(open); column.append(card); $('savedFields').append(column);
    }
  }
  async function loadSaved() {
    try {
      const response = await fetch('/api/plots');
      if (!response.ok) throw new Error();
      savedFields = await response.json(); renderSaved();
    } catch { $('savedFields').replaceChildren(A.element('p', 'text-muted', A.t('request_error'))); }
  }
  async function translateReport() {
    if (!report || report.language === A.language) return;
    const version = ++translationVersion, language = A.language;
    status(A.t('working'));
    try {
      const translated = translatedReports.get(language) || await A.post('/api/report-language', { report, language });
      if (version !== translationVersion || language !== A.language) return;
      translatedReports.set(language, translated); report = { ...report, ...translated }; persist(); render(); status('');
    } catch (error) { if (version === translationVersion) status(error.message, true); }
  }
  window.addEventListener('atlas:language', () => { status(''); render(); renderSaved(); translateReport(); });
  $('discussField').addEventListener('click', () => { if (report) persist(); });
  if (report) useReport(report);
  render(); loadSaved(); translateReport();
});
