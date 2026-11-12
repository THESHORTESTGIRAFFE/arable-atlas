/** Stateful multilingual chat; all user and model content is rendered as text. */
document.addEventListener('DOMContentLoaded', () => {
  if (!document.getElementById('chatBody')) return;
  const A = window.Atlas, $ = id => document.getElementById(id);
  const codes = { en: 'en-US', sn: 'sn-ZW', nd: 'nd-ZW', fr: 'fr-FR', es: 'es-ES', zh: 'zh-CN' };
  let history = [], busy = false, recognition = null, listening = false;
  try {
    const stored = JSON.parse(sessionStorage.getItem('arable.chat') || '[]');
    history = Array.isArray(stored) ? stored.filter(m => ['user', 'assistant'].includes(m.role) && typeof m.content === 'string').slice(-24) : [];
  } catch { /* A new conversation works without storage. */ }
  function saveHistory() { try { sessionStorage.setItem('arable.chat', JSON.stringify(history.slice(-24))); } catch { /* optional */ } }
  function speechVoice(language) {
    return window.speechSynthesis?.getVoices().find(voice => voice.lang.toLowerCase().split('-')[0] === language);
  }
  function renderMessage(message) {
    const box = A.element('article', message.role === 'user' ? 'atlas-message atlas-user' : 'atlas-message atlas-bot');
    box.lang = message.language === 'zh' ? 'zh-CN' : (message.language || 'en');
    box.append(A.element('div', 'report-text', message.content));
    const voice = speechVoice(message.language || 'en');
    if (message.role === 'assistant' && voice) {
      const read = A.element('button', 'btn btn-sm btn-link p-0 mt-2', A.t('read'));
      read.type = 'button';
      read.addEventListener('click', () => {
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(message.content);
        utterance.voice = voice; utterance.lang = voice.lang; speechSynthesis.speak(utterance);
      });
      box.append(read);
    }
    $('chatBody').append(box);
  }
  function renderContext() {
    const report = A.storage.get('report');
    $('fieldContext').removeAttribute('data-i18n');
    $('fieldContext').textContent = report ?
      `${report.location || `${report.latitude}, ${report.longitude}`} · ${A.soil(report.soil_type)} · pH ${report.ph ?? '—'}${report.crop ? ` · ${report.crop}` : ''}` : A.t('no_context');
    $('clearContext').hidden = !report;
  }
  function render() {
    $('chatBody').replaceChildren();
    if (!history.length) renderMessage({ role: 'assistant', language: A.language, content: A.t('welcome') });
    history.forEach(renderMessage);
    $('suggestedQuestions').replaceChildren();
    ['question_crop', 'question_plan', 'question_water'].forEach(key => {
      const button = A.element('button', 'btn btn-sm btn-outline-primary rounded-pill', A.t(key));
      button.type = 'button'; button.disabled = busy;
      button.addEventListener('click', () => { $('chatInput').value = A.t(key); $('chatInput').focus(); });
      $('suggestedQuestions').append(button);
    });
    renderContext();
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    // Browser recognition does not expose a portable list of supported languages.
    // Enable common locales only; unsupported-language errors fall back to typing.
    $('voiceBtn').hidden = !SpeechRecognition || ['sn', 'nd'].includes(A.language);
    $('chatStatus').textContent = busy ? A.t('thinking') : $('voiceBtn').hidden ? A.t('speech_unavailable') : '';
    $('chatBody').scrollTop = $('chatBody').scrollHeight;
  }
  async function send(event) {
    event?.preventDefault();
    const query = $('chatInput').value.trim();
    if (!query || busy) return;
    const language = A.language, context = A.storage.get('report');
    const previous = history.slice(-12).map(({role, content}) => ({role, content: content.slice(0, 8000)}));
    history.push({ role: 'user', content: query, language });
    $('chatInput').value = ''; busy = true; $('sendChat').disabled = true;
    $('clearChat').disabled = true; $('clearContext').disabled = true; $('voiceBtn').disabled = true;
    saveHistory(); render();
    try {
      const result = await A.post('/ask', { query, language, history: previous, context });
      history.push({ role: 'assistant', content: result.response, language: result.language });
      saveHistory();
      busy = false; render();
    } catch (error) {
      // Failed messages do not enter the model's conversation history.
      history.pop(); $('chatInput').value = query; saveHistory(); busy = false; render();
      $('chatStatus').textContent = error.message || A.t('chat_error');
    } finally {
      busy = false; $('sendChat').disabled = false; $('clearChat').disabled = false;
      $('clearContext').disabled = false; $('voiceBtn').disabled = false; $('chatInput').focus();
    }
  }
  $('chatForm').addEventListener('submit', send);
  $('chatInput').addEventListener('keydown', event => { if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) send(event); });
  $('clearChat').addEventListener('click', () => { history = []; saveHistory(); window.speechSynthesis?.cancel(); render(); });
  $('clearContext').addEventListener('click', () => {
    A.storage.set('report', null); history = []; saveHistory(); render();
  });
  $('voiceBtn').addEventListener('click', () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;
    if (listening) { recognition.stop(); return; }
    recognition = new SpeechRecognition(); recognition.lang = codes[A.language];
    recognition.interimResults = false; recognition.maxAlternatives = 1;
    recognition.onstart = () => { listening = true; $('voiceBtn').classList.add('text-danger'); };
    recognition.onresult = event => { $('chatInput').value = event.results[0][0].transcript; $('chatInput').focus(); };
    recognition.onerror = () => { $('chatStatus').textContent = A.t('voice_error'); };
    recognition.onend = () => { listening = false; $('voiceBtn').classList.remove('text-danger'); };
    try { recognition.start(); } catch { $('chatStatus').textContent = A.t('voice_error'); }
  });
  window.addEventListener('atlas:language', () => {
    recognition?.abort(); window.speechSynthesis?.cancel(); render();
  });
  if (window.speechSynthesis) speechSynthesis.addEventListener('voiceschanged', render);
  window.addEventListener('storage', renderContext);
  render();
});
