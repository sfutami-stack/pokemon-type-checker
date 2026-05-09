'use strict';

let DATA = null;
let TYPES = null;
let CHART = null;
let ABILITIES = null;
let POKEMON = null;

const $ = (id) => document.getElementById(id);


// --- Input normalization ------------------------------------------------
function toKatakana(s) {
  let out = '';
  for (const c of s) {
    const code = c.codePointAt(0);
    // Hiragana ぁ(0x3041) .. ゖ(0x3096)  →  shift to katakana
    if (code >= 0x3041 && code <= 0x3096) {
      out += String.fromCodePoint(code + 0x60);
    } else {
      out += c;
    }
  }
  return out;
}


// --- Data load ----------------------------------------------------------
async function loadData() {
  const r = await fetch('data.json');
  if (!r.ok) {
    $('loading').textContent = `データの読み込みに失敗しました (${r.status})`;
    return;
  }
  DATA = await r.json();
  TYPES = DATA.types;
  CHART = DATA.type_chart;
  ABILITIES = DATA.abilities;
  POKEMON = DATA.pokemon;
  $('loading').hidden = true;
  $('hint').hidden = false;
  $('q').focus();
}


// --- Search -------------------------------------------------------------
function findMatches(query) {
  const q = toKatakana(query.trim());
  if (!q) return [];
  return POKEMON.filter(p => p.name_ja.startsWith(q));
}

function renderSuggestions(matches) {
  const ul = $('suggestions');
  ul.innerHTML = '';
  if (matches.length === 0 || matches.length > 4) {
    ul.hidden = true;
    return;
  }
  for (const p of matches) {
    const li = document.createElement('li');
    li.className = 'suggestion';
    const id = document.createElement('span');
    id.className = 'sugg-id';
    id.textContent = `#${String(p.id).padStart(3, '0')}`;
    const name = document.createElement('span');
    name.className = 'sugg-name';
    name.textContent = p.name_ja;
    li.append(id, name);
    li.addEventListener('click', () => selectPokemon(p));
    ul.appendChild(li);
  }
  ul.hidden = false;
}

function selectPokemon(p) {
  $('q').value = p.name_ja;
  $('clear').hidden = false;
  $('suggestions').hidden = true;
  $('hint').hidden = true;
  $('nomatch').hidden = true;
  renderResult(p);
}


// --- Type matchup -------------------------------------------------------
function formatMult(m) {
  if (m === 0) return '×0';
  if (m === 0.25) return '×1/4';
  return `×${m}`;
}

function computeMatchups(p) {
  const baseMults = {};
  for (const atk of Object.keys(TYPES)) {
    let m = CHART[atk][p.types[0]];
    if (p.types[1]) m *= CHART[atk][p.types[1]];
    baseMults[atk] = m;
  }
  // ability key -> { type: effectiveMult }
  const annotations = {};  // type -> [ {abName, eff} ]
  for (const abKey of p.abilities) {
    const ab = ABILITIES[abKey];
    if (ab.negates) {
      const t = ab.negates;
      (annotations[t] ||= []).push({ abName: ab.name_ja, eff: 0 });
    }
    if (ab.halves) {
      for (const t of ab.halves) {
        (annotations[t] ||= []).push({
          abName: ab.name_ja,
          eff: baseMults[t] * 0.5,
        });
      }
    }
  }
  return { baseMults, annotations };
}

// Decide which section a row belongs to.
// Strict spec: only show rows with base != 1.
// Exception: if the base is 1 but an ability changes the multiplier,
// expose the row so the player still sees the ability's effect.
function classifyRow(base, anns) {
  if (base === 4 || base === 2) return 'super';
  if (base === 0.5 || base === 0.25) return 'resist';
  if (base === 0) return 'immune';
  // base === 1: only show if an ability changes things
  if (anns && anns.length) {
    const minEff = Math.min(...anns.map(a => a.eff));
    if (minEff === 0) return 'immune';
    if (minEff < 1) return 'resist';
  }
  return null;
}

function typeBadge(typeKey) {
  const t = TYPES[typeKey];
  const span = document.createElement('span');
  span.className = 'type-badge';
  span.style.backgroundColor = t.color;
  span.style.color = t.text;
  span.textContent = t.it;
  return span;
}

function renderMatchupRow(typeKey, base, anns) {
  const li = document.createElement('li');
  li.className = 'matchup-row';

  const badge = typeBadge(typeKey);
  li.appendChild(badge);

  const mult = document.createElement('span');
  mult.className = 'mult';
  mult.textContent = formatMult(base);
  li.appendChild(mult);

  if (anns && anns.length) {
    for (const a of anns) {
      const note = document.createElement('div');
      note.className = 'annotation';
      note.textContent = `※${a.abName}持ちなら${formatMult(a.eff)}`;
      li.appendChild(note);
    }
  }

  return li;
}

function renderResult(p) {
  hideAbilityPopup();
  $('result').hidden = false;
  $('poke-id').textContent = `#${String(p.id).padStart(3, '0')}`;
  $('poke-name').textContent = p.name_ja;

  const typesEl = $('poke-types');
  typesEl.innerHTML = '';
  for (const t of p.types) typesEl.appendChild(typeBadge(t));

  const abEl = $('poke-abilities');
  abEl.innerHTML = '';
  for (const k of p.abilities) {
    const ab = ABILITIES[k];
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'ability-btn';
    btn.dataset.key = k;
    btn.textContent = ab.name_ja;
    abEl.appendChild(btn);
  }

  const { baseMults, annotations } = computeMatchups(p);
  const buckets = { super: [], resist: [], immune: [] };
  for (const t of Object.keys(baseMults)) {
    const sec = classifyRow(baseMults[t], annotations[t]);
    if (sec) buckets[sec].push(t);
  }
  // Order:
  //   super: ×4 first, then ×2
  //   resist: ×1/4 first, then ×0.5 (and base-1+ability rows last)
  //   immune: as-is
  buckets.super.sort((a, b) => baseMults[b] - baseMults[a]);
  buckets.resist.sort((a, b) => baseMults[a] - baseMults[b]);

  for (const sec of ['super', 'resist', 'immune']) {
    const types = buckets[sec];
    const list = $(`list-${sec}`);
    const wrap = $(`sec-${sec}`);
    list.innerHTML = '';
    if (types.length === 0) {
      wrap.hidden = true;
      continue;
    }
    wrap.hidden = false;
    for (const t of types) {
      list.appendChild(renderMatchupRow(t, baseMults[t], annotations[t]));
    }
  }

  // Scroll the result into view on mobile so it's visible after typing
  $('result').scrollIntoView({ behavior: 'smooth', block: 'start' });
}


// --- Ability popup ------------------------------------------------------
function showAbilityPopup(key, anchor) {
  const ab = ABILITIES[key];
  const popup = $('ability-popup');
  popup.innerHTML = '';
  const name = document.createElement('div');
  name.className = 'popup-name';
  name.textContent = ab.name_ja;
  const desc = document.createElement('div');
  desc.className = 'popup-desc';
  desc.textContent = ab.desc_ja || '(説明テキストなし)';
  popup.append(name, desc);
  popup.hidden = false;

  // Position: center popup horizontally on the button, then clamp to
  // viewport so it never escapes the screen on a narrow phone. The arrow
  // is repositioned to still point at the button center.
  const rect = anchor.getBoundingClientRect();
  const vw = window.innerWidth;
  const popupWidth = Math.min(340, vw - 24);
  const buttonCenter = rect.left + rect.width / 2;
  let left = buttonCenter - popupWidth / 2;
  left = Math.max(12, Math.min(vw - popupWidth - 12, left));
  const arrowLeft = buttonCenter - left;
  popup.style.width = `${popupWidth}px`;
  popup.style.left = `${left + window.scrollX}px`;
  popup.style.top = `${rect.bottom + window.scrollY + 10}px`;
  popup.style.setProperty(
    '--arrow-left',
    `${Math.max(14, Math.min(popupWidth - 14, arrowLeft))}px`,
  );
}

function hideAbilityPopup() {
  $('ability-popup').hidden = true;
}


// --- Wire up ------------------------------------------------------------
// Register service worker for offline support. Failures are non-fatal —
// the app still works as a regular page if SW registration is rejected.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('service-worker.js').catch((err) => {
      console.warn('Service worker registration failed:', err);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadData();

  const input = $('q');
  const clearBtn = $('clear');

  input.addEventListener('input', (e) => {
    const v = e.target.value;
    clearBtn.hidden = v.length === 0;

    if (v.trim() === '') {
      $('suggestions').hidden = true;
      $('result').hidden = true;
      $('nomatch').hidden = true;
      $('hint').hidden = false;
      return;
    }

    const matches = findMatches(v);
    const normalized = toKatakana(v.trim());
    const exact = matches.find(m => m.name_ja === normalized);

    if (exact) {
      $('hint').hidden = true;
      $('suggestions').hidden = true;
      $('nomatch').hidden = true;
      renderResult(exact);
      return;
    }

    if (matches.length === 0) {
      $('hint').hidden = true;
      $('suggestions').hidden = true;
      $('result').hidden = true;
      $('nomatch').hidden = false;
      return;
    }

    $('result').hidden = true;
    $('nomatch').hidden = true;
    if (matches.length > 4) {
      $('suggestions').hidden = true;
      $('hint').hidden = false;
    } else {
      $('hint').hidden = true;
      renderSuggestions(matches);
    }
  });

  // Enter on a single match selects it
  input.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') return;
    const matches = findMatches(input.value);
    if (matches.length === 1) {
      e.preventDefault();
      selectPokemon(matches[0]);
    }
  });

  clearBtn.addEventListener('click', () => {
    input.value = '';
    input.dispatchEvent(new Event('input'));
    input.focus();
  });

  // Ability button taps + dismiss popup on outside click
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.ability-btn');
    if (btn) {
      e.stopPropagation();
      const popup = $('ability-popup');
      const sameOpen = !popup.hidden && popup.dataset.key === btn.dataset.key;
      if (sameOpen) {
        hideAbilityPopup();
      } else {
        popup.dataset.key = btn.dataset.key;
        showAbilityPopup(btn.dataset.key, btn);
      }
      return;
    }
    if (!e.target.closest('.ability-popup')) hideAbilityPopup();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') hideAbilityPopup();
  });
});
