'use strict';
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem('havie-token') || '';
let state = null;
let busy = false;
let pending = null;
const noticed = new Set();
function status(text, error = false) { $('status').textContent = text; $('status').classList.toggle('error', error); }
async function api(path, data) {
  const response = await fetch(path, { method: data ? 'POST' : 'GET', headers: { 'Authorization': 'Bearer ' + token, ...(data ? {'Content-Type': 'application/json'} : {}) }, ...(data ? {body: JSON.stringify(data)} : {}) });
  const value = await response.json();
  if (response.status === 401) disconnect();
  if (!response.ok) throw new Error(value.error || 'Request failed.');
  return value;
}
function disconnect() {
  token = ''; sessionStorage.removeItem('havie-token'); state = null; noticed.clear();
  $('connected').hidden = true; $('pair').hidden = false; $('disconnect').hidden = true;
  $('messages').replaceChildren();
}
function message(text, user = false) {
  const node = document.createElement('div'); node.className = 'message' + (user ? ' user' : ''); node.textContent = text;
  $('messages').append(node); node.scrollIntoView({block:'nearest'});
}
function item(container, text, detail, command, label = 'Remove') {
  const node = document.createElement('div'); node.className = 'item';
  const content = document.createElement('div'); content.className = 'item-text'; content.textContent = text;
  if (detail) { const small = document.createElement('small'); small.textContent = detail; content.append(small); }
  node.append(content);
  if (command) { const button = document.createElement('button'); button.className = 'ghost'; button.textContent = label; button.addEventListener('click', () => act(command)); node.append(button); }
  container.append(node);
}
function empty(container, text) { if (!container.childElementCount) { const node = document.createElement('p'); node.className = 'empty'; node.textContent = text; container.append(node); } }
function render() {
  const today = state.server_time.slice(0,10);
  $('date').textContent = today + ' · YOUR SPACE';
  $('connection-state').textContent = 'Connected · PC timezone: ' + state.timezone;
  $('pc-status').textContent = state.pc_controls ? 'PC controls enabled. Approved computer actions run on your PC.' : 'Personal assistant mode. Computer controls are disabled on the phone.';
  const byKind = kind => state.items.filter(i => i.kind === kind);
  $('task-count').textContent = byKind('task').length;
  $('event-count').textContent = byKind('event').filter(i => i.due.slice(0,10) === today).length;
  $('reminder-count').textContent = byKind('reminder').length;
  const sections = [ ['task','tasks-list','done ','Done'], ['note','notes-list','delete note ','Remove'], ['event','events-list','cancel event ','Remove'], ['reminder','reminders-list','cancel reminder ','Dismiss'] ];
  for (const [kind, id, command, label] of sections) {
    const container = $(id); container.replaceChildren();
    const items = byKind(kind).sort((a,b) => (a.due || '').localeCompare(b.due || ''));
    for (const value of items) {
      const due = value.due && value.due <= state.server_time;
      item(container, value.text, value.due ? (due && kind === 'reminder' ? 'Due now · ' : '') + value.due.replace('T',' ') : '', command + value.id, label);
      if (due && kind === 'reminder' && !noticed.has(value.id)) { noticed.add(value.id); status('Reminder: ' + value.text); }
    }
    empty(container, 'Nothing here yet.');
  }
  const agenda = $('agenda-list'); agenda.replaceChildren();
  for (const value of state.items.filter(i => i.kind === 'task' || (i.due && i.due.slice(0,10) === today)).sort((a,b) => (a.due || '').localeCompare(b.due || ''))) {
    item(agenda, value.text, value.kind + (value.due ? ' · ' + value.due.slice(11,16) : ''));
  }
  empty(agenda, 'A clear day. Add a task or plan something good.');
  const memory = $('memory-list'); memory.replaceChildren();
  for (const value of state.memory) item(memory, value.name + ': ' + value.value, '', 'forget ' + value.name, 'Forget');
  empty(memory, 'Save your name, preferences or personal goals.');
}
async function refresh() {
  if (!token) return;
  state = await api('/api/state');
  $('pair').hidden = true; $('connected').hidden = false; $('disconnect').hidden = false;
  render();
}
function review(value) {
  return new Promise(resolve => {
    pending = {id: value.id, resolve}; $('preview').textContent = value.preview; $('review').showModal();
  });
}
function finishReview(approved) {
  if (!pending) return;
  const value = pending; pending = null; $('review').close(); value.resolve(approved);
}
async function act(request, chat = false) {
  if (busy) { status('Wait for the current action to finish.'); return false; }
  busy = true;
  document.querySelectorAll('form button').forEach(b => b.disabled = true);
  status('Working…');
  try {
    const prepared = await api('/api/prepare', {request});
    let result = prepared;
    if (prepared.confirmation_required) {
      const approved = await review(prepared);
      result = await api(approved ? '/api/execute' : '/api/cancel', {id: prepared.id});
      if (!approved) { status('Cancelled.'); return false; }
    }
    if (chat) message(result.result);
    status(result.result || 'Done.');
    await refresh();
    return true;
  } catch (error) { status(error.message, true); if (chat) message(error.message); return false; }
  finally { busy = false; document.querySelectorAll('form button').forEach(b => b.disabled = false); }
}
$('pair-form').addEventListener('submit', async event => {
  event.preventDefault(); token = $('code').value.trim();
  try { await refresh(); sessionStorage.setItem('havie-token', token); $('code').value = ''; status('Connected. Welcome to Havie.'); }
  catch(error) { status(error.message, true); }
});
$('disconnect').addEventListener('click', () => { disconnect(); status('Disconnected.'); });
$('confirm').addEventListener('click', () => finishReview(true));
$('cancel').addEventListener('click', () => finishReview(false));
$('review').addEventListener('cancel', event => { event.preventDefault(); finishReview(false); });
for (const button of document.querySelectorAll('[data-tab]')) button.addEventListener('click', () => {
  document.querySelectorAll('.panel').forEach(p => p.hidden = p.id !== button.dataset.tab);
  document.querySelectorAll('[data-tab]').forEach(b => b.classList.toggle('active', b === button));
});
for (const [form, input, prefix] of [['task-form','task-text','task '], ['note-form','note-text','note ']]) {
  $(form).addEventListener('submit', async event => { event.preventDefault(); if (await act(prefix + $(input).value.trim())) $(input).value = ''; });
}
$('reminder-form').addEventListener('submit', async event => { event.preventDefault(); if (await act('remind ' + $('minutes').value + ' ' + $('reminder-text').value.trim())) $('reminder-text').value = ''; });
$('event-form').addEventListener('submit', async event => { event.preventDefault(); if (await act('event ' + $('event-date').value.replace('T',' ') + ' ' + $('event-text').value.trim())) $('event-text').value = ''; });
$('memory-form').addEventListener('submit', async event => { event.preventDefault(); if (await act('remember ' + $('memory-key').value.trim() + ' = ' + $('memory-value').value.trim())) { $('memory-key').value = ''; $('memory-value').value = ''; } });
$('message-form').addEventListener('submit', async event => { event.preventDefault(); const text = $('message').value.trim(); message(text, true); if (await act(($('mode').value === 'chat' ? 'chat ' : '') + text, true)) $('message').value = ''; });
if (token) refresh().catch(error => status(error.message, true));
setInterval(() => { if (token && !busy) refresh().catch(error => status('Connection lost: ' + error.message, true)); }, 15000);
