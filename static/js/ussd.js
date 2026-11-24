/* Simulator only: no browser SMS permissions, real phone numbers, or live gateway. */
document.addEventListener('DOMContentLoaded', () => {
  const A = window.Atlas, $ = id => document.getElementById(id);
  let call = null, busy = false, messages = [], poll = null;
  function render() {
    $('ussdScreen').textContent = call?.text || A.t('ussd_idle');
    $('ussdScreen').removeAttribute('data-i18n');
    $('ussdForm').classList.toggle('d-none', !call?.active);
    $('ussdDial').disabled = busy || Boolean(call?.active);
    $('ussdSend').disabled = busy; $('ussdCancel').disabled = busy;
    $('ussdInput').disabled = busy;
    $('ussdInput').inputMode = call?.stage === 'question' ? 'text' : 'numeric';
    $('ussdInput').maxLength = call?.stage === 'question' ? 500 : 1;
    $('smsInbox').replaceChildren();
    if (!messages.length) $('smsInbox').append(A.element('p', 'text-muted', A.t('sms_empty')));
    for (const message of messages) {
      const card = A.element('article', 'sms-card p-3 rounded-4');
      const stamp = new Date(message.created_at).toLocaleString(document.documentElement.lang);
      card.append(A.element('div', 'small text-muted mb-2', `Plotty · ${message.area} · ${stamp}`));
      const statusKey = ({ queued: 'sms_queued', processing: 'sms_processing', simulated: 'ussd_simulated', failed: 'sms_failed' })[message.status];
      card.append(A.element('span', 'badge bg-light text-dark mb-2', A.t(statusKey)));
      const body = A.element('p', 'report-text mb-2', message.body || A.t('sms_wait'));
      body.lang = message.language; card.append(body);
      if (message.segments) card.append(A.element('p', 'small mb-0 text-muted', `${A.t('sms_segments')}: ${message.segments} · ${message.encoding}`));
      if (message.source) card.append(A.element('p', 'small mb-0 text-muted', message.source));
      $('smsInbox').append(card);
    }
  }
  async function inbox() {
    try {
      const response = await fetch('/api/ussd/inbox');
      if (!response.ok) throw new Error();
      messages = await response.json(); render();
      const pending = messages.some(m => m.status === 'queued' || m.status === 'processing');
      if (pending && !poll) poll = setTimeout(() => { poll = null; inbox(); }, 1800);
    } catch { $('ussdStatus').textContent = A.t('request_error'); }
  }
  async function interact(action, text = '') {
    if (busy) return;
    busy = true; $('ussdStatus').textContent = ''; render();
    try {
      const response = await fetch('/api/ussd/session', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, text, language: A.language, session_id: call?.session_id, revision: call?.revision }) });
      const body = await response.json();
      if (body.session_id) call = body;
      if (!response.ok) throw new Error(A.t(body.error_key || 'request_error'));
      $('ussdInput').value = '';
      if (!call.active) await inbox();
    } catch (error) { $('ussdStatus').textContent = error.message || A.t('request_error'); }
    finally { busy = false; render(); if (call?.active) $('ussdInput').focus(); }
  }
  $('ussdDial').addEventListener('click', () => interact('dial'));
  $('ussdCancel').addEventListener('click', () => interact('cancel'));
  $('ussdForm').addEventListener('submit', event => { event.preventDefault(); interact('reply', $('ussdInput').value); });
  document.querySelectorAll('[data-key]').forEach(key => key.addEventListener('click', () => {
    if (busy || !call?.active) return;
    $('ussdInput').value = call.stage === 'question' ? ($('ussdInput').value + key.dataset.key).slice(0, 500) : key.dataset.key;
    $('ussdInput').focus();
  }));
  window.addEventListener('atlas:language', () => {
    // A running USSD session keeps its own chosen language, like a real handset.
    render();
  });
  window.addEventListener('pagehide', () => { if (poll) clearTimeout(poll); });
  render(); inbox();
});
