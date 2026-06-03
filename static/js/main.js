// ═══════════════════════════════════════════════════════════════════
//  PCAdvisor — main.js
//  Handles: Chat (with conversation memory), SAGE voice assistant,
//           Quiz modal, Compare UI, Upgrade advice, Laptop cards
// ═══════════════════════════════════════════════════════════════════

// ── Global state ─────────────────────────────────────────────────
let currentBudget  = '';
let currentUseCase = 'general use';

// ── Utility: typewriter effect ────────────────────────────────────
function typewriterEffect(element, html, speedMs = 8) {
  const stripped = html.replace(/<[^>]*>/g, '');
  element.innerHTML = '';
  let i = 0;
  // For performance use full HTML after a short delay on long responses
  if (stripped.length > 600) {
    setTimeout(() => { element.innerHTML = html; }, 50);
    return;
  }
  const timer = setInterval(() => {
    if (i < stripped.length) {
      element.textContent += stripped[i++];
    } else {
      clearInterval(timer);
      element.innerHTML = html; // swap to rich HTML once done
    }
  }, speedMs);
}

// ── Utility: render markdown (uses marked.js if available) ────────
function renderMarkdown(text) {
  if (typeof marked !== 'undefined') {
    return marked.parse(text);
  }
  return text.replace(/\n/g, '<br>');
}

// ── Chatbot ───────────────────────────────────────────────────────

function openChatbot() {
  document.getElementById('chatbot-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
  setTimeout(() => document.getElementById('chat-input').focus(), 100);
}

function closeChatbot() {
  document.getElementById('chatbot-overlay').style.display = 'none';
  document.body.style.overflow = '';
}

function playChatbotOpenSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [523, 659, 784].forEach((freq, i) => {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime + i * 0.15);
      gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.15);
      gain.gain.linearRampToValueAtTime(0.3,  ctx.currentTime + i * 0.15 + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.15 + 0.4);
      osc.start(ctx.currentTime + i * 0.15);
      osc.stop(ctx.currentTime + i * 0.15 + 0.4);
    });
  } catch(e) {}
}

function clearChatHistory() {
  fetch('/clear-history', { method: 'POST' });
  const messages = document.getElementById('chat-messages');
  // Keep only the welcome message
  while (messages.children.length > 1) messages.lastChild.remove();
  addBotMessage('✅ Conversation cleared! I\'ve forgotten our chat history. What would you like to explore?');
}

async function sendChatMessage() {
  const input  = document.getElementById('chat-input');
  const msg    = input.value.trim();
  if (!msg) return;

  input.value = '';
  addUserMessage(msg);

  const typingId = addTypingIndicator();

  try {
    const res = await fetch('/chat', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        message:  msg,
        budget:   currentBudget  || '500000',
        use_case: currentUseCase || 'general use',
      }),
    });

    removeTypingIndicator(typingId);

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      addBotMessage(`⚠️ ${err.error || 'Server error. Please try again.'}`);
      return;
    }

    const data = await res.json();

    // Render AI reply
    if (data.reply) addBotMessage(data.reply, true);

    // Render comparison result if present
    if (data.comparison && data.laptops && data.laptops.length >= 2) {
      renderComparisonCards(
        data.laptops[0], data.laptops[1],
        data.comparison,
        data.score_pct  || { a: 0, b: 0 },
        data.near_tie   || false,
        data.use_case   || currentUseCase
      );
    } else if (data.laptops && data.laptops.length > 0) {
      renderLaptopCards(data.laptops);
    }

  } catch (err) {
    removeTypingIndicator(typingId);
    addBotMessage('⚠️ Could not reach the server. Make sure the backend is running on port 5000.');
  }
}

// ── Message rendering ─────────────────────────────────────────────

function addUserMessage(text) {
  const messages = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.style.cssText = 'display:flex;gap:10px;align-items:flex-start;flex-direction:row-reverse;';
  div.innerHTML = `
    <div style="width:32px;height:32px;border-radius:8px;background:rgba(124,58,237,0.2);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;">👤</div>
    <div style="background:rgba(0,212,255,0.15);border-radius:12px 12px 4px 12px;padding:12px 16px;font-size:14px;max-width:85%;line-height:1.6;color:#e6edf3;text-align:right;">${text}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function addBotMessage(text, useMarkdown = false) {
  const messages = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.style.cssText = 'display:flex;gap:10px;align-items:flex-start;';

  const bubble = document.createElement('div');
  bubble.style.cssText = 'background:#1e2535;border-radius:12px 12px 12px 4px;padding:12px 16px;font-size:14px;max-width:85%;line-height:1.6;color:#e6edf3;';
  bubble.classList.add('bot-bubble');

  div.innerHTML = `<div style="width:32px;height:32px;border-radius:8px;background:rgba(0,212,255,0.12);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;">🤖</div>`;
  div.appendChild(bubble);
  messages.appendChild(div);

  if (useMarkdown) {
    const html = renderMarkdown(text);
    typewriterEffect(bubble, html);
  } else {
    bubble.innerHTML = text;
  }

  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function addTypingIndicator() {
  const messages = document.getElementById('chat-messages');
  const id  = 'typing-' + Date.now();
  const div = document.createElement('div');
  div.id = id;
  div.style.cssText = 'display:flex;gap:10px;align-items:flex-start;';
  div.innerHTML = `
    <div style="width:32px;height:32px;border-radius:8px;background:rgba(0,212,255,0.12);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;">🤖</div>
    <div style="background:#1e2535;border-radius:12px 12px 12px 4px;padding:12px 16px;">
      <span style="display:flex;gap:4px;align-items:center;">
        <span style="width:6px;height:6px;border-radius:50%;background:#00d4ff;animation:bounce 1s infinite 0s"></span>
        <span style="width:6px;height:6px;border-radius:50%;background:#00d4ff;animation:bounce 1s infinite 0.2s"></span>
        <span style="width:6px;height:6px;border-radius:50%;background:#00d4ff;animation:bounce 1s infinite 0.4s"></span>
      </span>
    </div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

// ── Laptop cards ──────────────────────────────────────────────────

function renderLaptopCards(laptops) {
  if (!laptops || !laptops.length) return;
  const messages  = document.getElementById('chat-messages');
  const sorted    = [...laptops].sort((a, b) => parseFloat(a.price) - parseFloat(b.price));
  const lowestPrice = parseFloat(sorted[0].price);

  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:flex;gap:10px;align-items:flex-start;margin-top:4px;';

  const avatar = document.createElement('div');
  avatar.style.cssText = 'width:32px;height:32px;border-radius:8px;background:rgba(0,212,255,0.12);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;';
  avatar.textContent = '🤖';

  const content = document.createElement('div');
  content.style.cssText = 'background:#1e2535;border-radius:12px;padding:16px;max-width:92%;width:100%;';

  const heading = document.createElement('div');
  heading.style.cssText = 'font-size:13px;font-weight:700;color:#00d4ff;margin-bottom:12px;';
  heading.textContent = '🛒 Matching Laptops — Sorted by Price';
  content.appendChild(heading);

  sorted.forEach(laptop => {
    const isBest = parseFloat(laptop.price) === lowestPrice;
    const card   = document.createElement('div');
    card.style.cssText = `background:${isBest ? 'rgba(0,212,255,0.08)' : 'rgba(255,255,255,0.03)'};border:1px solid ${isBest ? 'rgba(0,212,255,0.4)' : 'rgba(255,255,255,0.06)'};border-radius:10px;padding:12px;margin-bottom:10px;`;

    card.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
        <a href="${laptop.image_url}" target="_blank" style="flex-shrink:0;width:44px;height:44px;border-radius:8px;background:rgba(0,212,255,0.1);border:1px solid rgba(0,212,255,0.25);display:flex;align-items:center;justify-content:center;text-decoration:none;">
          <svg width="26" height="26" viewBox="0 0 40 40" fill="none"><rect x="6" y="8" width="28" height="18" rx="2" stroke="#00d4ff" stroke-width="1.5" fill="none"/><rect x="9" y="11" width="22" height="12" rx="1" fill="rgba(0,212,255,0.15)"/><rect x="4" y="26" width="32" height="3" rx="1.5" fill="#00d4ff" opacity="0.4"/><rect x="14" y="29" width="12" height="2" rx="1" fill="#00d4ff" opacity="0.3"/></svg>
        </a>
        <div>
          <div style="font-size:13px;font-weight:700;color:#e6edf3;">${laptop.brand} ${laptop.laptop}${isBest ? ' <span style="background:#00d4ff;color:#0d1117;font-size:10px;padding:2px 6px;border-radius:10px;font-weight:700;margin-left:4px;">BEST VALUE</span>' : ''}</div>
          <div style="font-size:11px;color:#8b949e;margin-top:2px;">${laptop.cpu} · ${laptop.ram}GB RAM · ${laptop.storage}GB · ${laptop.screen}"</div>
        </div>
      </div>
      <div style="font-size:15px;font-weight:800;color:#00d4ff;margin-bottom:10px;">💰 LKR ${Number(laptop.price).toLocaleString()}</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;">
        <a href="${laptop.daraz_url}" target="_blank" style="background:#F57C00;color:white;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:700;text-decoration:none;">🛒 Daraz</a>
        <a href="${laptop.ikman_url}" target="_blank" style="background:#e53935;color:white;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:700;text-decoration:none;">📌 ikman.lk</a>
        <a href="${laptop.kapruka_url}" target="_blank" style="background:#1565c0;color:white;padding:6px 12px;border-radius:8px;font-size:12px;font-weight:700;text-decoration:none;">🔎 Google Shop</a>
        <button onclick="compareWith('${laptop.laptop}')" style="background:rgba(124,58,237,0.2);color:#a78bfa;border:1px solid rgba(124,58,237,0.4);padding:6px 12px;border-radius:8px;font-size:12px;font-weight:700;cursor:pointer;">⚖️ Compare</button>
      </div>`;
    content.appendChild(card);
  });

  wrap.appendChild(avatar);
  wrap.appendChild(content);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

// ── Comparison cards ──────────────────────────────────────────────

function renderComparisonCards(laptopA, laptopB, narrativeText, scorePct, nearTie, useCase) {
  scorePct = scorePct || { a: 0, b: 0 };
  nearTie  = nearTie  || false;
  useCase  = useCase  || 'general use';

  const messages = document.getElementById('chat-messages');
  const wrap     = document.createElement('div');
  wrap.style.cssText = 'display:flex;gap:10px;align-items:flex-start;margin-top:8px;';

  const avatar = document.createElement('div');
  avatar.style.cssText = 'width:32px;height:32px;border-radius:8px;background:rgba(0,212,255,0.12);display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;';
  avatar.textContent = '🤖';

  const content = document.createElement('div');
  content.style.cssText = 'background:#1e2535;border-radius:12px;padding:16px;max-width:96%;width:100%;';

  // ── Header ──────────────────────────────────────────────────────
  const header = document.createElement('div');
  header.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-wrap:wrap;gap:8px;';
  header.innerHTML = `
    <div style="font-size:14px;font-weight:700;color:#00d4ff;">⚖️ Head-to-Head Comparison</div>
    <div style="font-size:11px;color:#8b949e;background:rgba(255,255,255,0.05);border-radius:20px;padding:4px 10px;">
      Ranked for: <span style="color:#a78bfa;font-weight:600;">${useCase.charAt(0).toUpperCase()+useCase.slice(1)}</span>
    </div>`;
  content.appendChild(header);

  // ── Verdict block ────────────────────────────────────────────────
  const verdictEl = document.createElement('div');
  verdictEl.classList.add('verdict-block');
  if (nearTie) {
    verdictEl.innerHTML = `
      <div class="verdict-icon">🤝</div>
      <div class="verdict-text">
        <div class="verdict-title">Near Tie</div>
        <div class="verdict-sub">Both laptops are strong choices — pick based on your priority.</div>
      </div>
      <div class="verdict-scores">
        <span class="vs-score">${scorePct.a}%</span>
        <span class="vs-sep">vs</span>
        <span class="vs-score">${scorePct.b}%</span>
      </div>`;
  } else {
    const winnerLaptop = scorePct.a >= scorePct.b ? laptopA : laptopB;
    const winnerScore  = scorePct.a >= scorePct.b ? scorePct.a : scorePct.b;
    verdictEl.innerHTML = `
      <div class="verdict-icon">🏆</div>
      <div class="verdict-text">
        <div class="verdict-title">Best Pick: ${winnerLaptop.brand} ${winnerLaptop.laptop}</div>
        <div class="verdict-sub">Top scorer for ${useCase}</div>
      </div>
      <div class="verdict-score-pill">${winnerScore}%</div>`;
  }
  content.appendChild(verdictEl);

  // ── Score bars ───────────────────────────────────────────────────
  const barsWrap = document.createElement('div');
  barsWrap.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px;';

  [laptopA, laptopB].forEach((l, i) => {
    const pct  = i === 0 ? scorePct.a : scorePct.b;
    const isWinner = !nearTie && ((i === 0 && scorePct.a >= scorePct.b) || (i === 1 && scorePct.b > scorePct.a));
    const barEl = document.createElement('div');
    barEl.style.cssText = `background:rgba(255,255,255,0.03);border:1px solid ${isWinner ? 'rgba(0,212,255,0.35)' : 'rgba(255,255,255,0.06)'};border-radius:10px;padding:10px 12px;`;
    barEl.innerHTML = `
      <div style="font-size:12px;font-weight:700;color:#e6edf3;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
        ${isWinner ? '🏆 ' : ''}${l.brand} ${l.laptop}
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <div style="flex:1;height:6px;background:#0d1117;border-radius:3px;overflow:hidden;">
          <div class="score-bar-fill" style="height:100%;width:${pct}%;background:${isWinner ? 'linear-gradient(90deg,#00d4ff,#7c3aed)' : '#2d3748'};border-radius:3px;transition:width 0.8s ease;"></div>
        </div>
        <span style="font-size:12px;font-weight:700;color:${isWinner ? '#00d4ff' : '#8b949e'};min-width:32px;text-align:right;">${pct}%</span>
      </div>`;
    barsWrap.appendChild(barEl);
  });
  content.appendChild(barsWrap);

  // ── Dimension table ──────────────────────────────────────────────
  const dims = [
    { key: 'CPU',     label: 'CPU',      icon: '🔲', valA: laptopA.cpu,                     valB: laptopB.cpu },
    { key: 'RAM',     label: 'RAM',      icon: '💾', valA: laptopA.ram + 'GB',              valB: laptopB.ram + 'GB' },
    { key: 'Storage', label: 'Storage',  icon: '💿', valA: laptopA.storage + 'GB',          valB: laptopB.storage + 'GB' },
    { key: 'GPU',     label: 'GPU',      icon: '🎮', valA: laptopA.gpu || 'Integrated',    valB: laptopB.gpu || 'Integrated' },
    { key: 'Display', label: 'Display',  icon: '🖥️', valA: laptopA.screen + '"',            valB: laptopB.screen + '"' },
    { key: 'Price',   label: 'Price',    icon: '💰', valA: 'LKR ' + Number(laptopA.price).toLocaleString(), valB: 'LKR ' + Number(laptopB.price).toLocaleString() },
  ];

  // map breakdown keys to dim keys
  const breakdownKeyMap = {
    'CPU': 'cpu', 'RAM': 'ram', 'Storage': 'storage',
    'GPU': 'gpu', 'Display': 'display', 'Price': 'price',
  };

  // Re-compute simple dimension winners from values (frontend fallback)
  function dimWinner(dim, valA, valB) {
    if (dim === 'RAM' || dim === 'Storage') {
      const a = parseFloat(valA), b = parseFloat(valB);
      if (a > b) return 'A'; if (b > a) return 'B'; return 'tie';
    }
    if (dim === 'Display') {
      const a = parseFloat(valA), b = parseFloat(valB);
      if (a > b) return 'A'; if (b > a) return 'B'; return 'tie';
    }
    if (dim === 'Price') {
      const a = parseFloat(laptopA.price), b = parseFloat(laptopB.price);
      if (a < b) return 'A'; if (b < a) return 'B'; return 'tie';
    }
    return 'tie';
  }

  const table = document.createElement('div');
  table.style.cssText = 'border:1px solid rgba(255,255,255,0.06);border-radius:10px;overflow:hidden;margin-bottom:12px;';

  // Table header
  const thead = document.createElement('div');
  thead.classList.add('cmp-thead');
  thead.innerHTML = `
    <div class="cmp-th cmp-th-dim">Dimension</div>
    <div class="cmp-th">${laptopA.brand} ${laptopA.laptop.split(' ').slice(0,2).join(' ')}</div>
    <div class="cmp-th">${laptopB.brand} ${laptopB.laptop.split(' ').slice(0,2).join(' ')}</div>`;
  table.appendChild(thead);

  dims.forEach((d, idx) => {
    const bKey   = breakdownKeyMap[d.key];
    const winner = dimWinner(d.key, d.valA, d.valB);
    const winA   = winner === 'A';
    const winB   = winner === 'B';
    const isTie  = winner === 'tie';

    const row = document.createElement('div');
    row.classList.add('cmp-row');
    if (idx % 2 === 0) row.style.background = 'rgba(255,255,255,0.01)';

    row.innerHTML = `
      <div class="cmp-td cmp-dim-cell">
        <span style="margin-right:6px;">${d.icon}</span>${d.label}
        ${isTie ? '<span class="cmp-tie-badge">TIE</span>' : ''}
      </div>
      <div class="cmp-td ${winA ? 'cmp-winner' : ''}">
        <span class="cmp-val">${d.valA}</span>
        ${winA ? '<span class="cmp-win-icon" aria-label="Winner">✓</span>' : ''}
      </div>
      <div class="cmp-td ${winB ? 'cmp-winner' : ''}">
        <span class="cmp-val">${d.valB}</span>
        ${winB ? '<span class="cmp-win-icon" aria-label="Winner">✓</span>' : ''}
      </div>`;
    table.appendChild(row);
  });
  content.appendChild(table);

  // ── Buy buttons ──────────────────────────────────────────────────
  const btnRow = document.createElement('div');
  btnRow.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px;';
  [laptopA, laptopB].forEach(l => {
    btnRow.innerHTML += `
      <div style="display:flex;gap:6px;flex-wrap:wrap;">
        <a href="${l.daraz_url}" target="_blank" aria-label="Buy ${l.laptop} on Daraz"
           style="background:#F57C00;color:white;padding:5px 10px;border-radius:7px;font-size:11px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">🛒 Daraz</a>
        <a href="${l.kapruka_url}" target="_blank" aria-label="Google Shop for ${l.laptop}"
           style="background:#1565c0;color:white;padding:5px 10px;border-radius:7px;font-size:11px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:4px;">🔎 Shop</a>
        <a href="${l.image_url}" target="_blank" aria-label="View images of ${l.laptop}"
           style="background:rgba(0,212,255,0.1);color:#00d4ff;padding:5px 10px;border-radius:7px;font-size:11px;font-weight:700;text-decoration:none;border:1px solid rgba(0,212,255,0.25);display:inline-flex;align-items:center;gap:4px;">🖼️</a>
      </div>`;
  });
  content.appendChild(btnRow);

  wrap.appendChild(avatar);
  wrap.appendChild(content);
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

// ── Compare helper ────────────────────────────────────────────────

let compareQueue = [];
function compareWith(laptopName) {
  if (compareQueue.length >= 1) {
    // Reset on 3rd+ click without completing a pair
    compareQueue = [laptopName];
    addBotMessage(`Queue reset. Comparing **${laptopName}** — click a second "Compare" button or type the second laptop name.`, true);
    return;
  }
  compareQueue.push(laptopName);
  if (compareQueue.length === 1) {
    addBotMessage(`Got it! Queued **${laptopName}** for comparison. Click another "Compare" button to pick the second laptop.`, true);
  } else if (compareQueue.length === 2) {
    const [a, b] = compareQueue;
    compareQueue = [];
    addBotMessage(`⚙️ Comparing **${a}** vs **${b}**...`, true);
    sendCompareRequest(a, b);
  }
}

async function sendCompareRequest(nameA, nameB) {
  try {
    const res = await fetch('/compare', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ laptop_a: nameA, laptop_b: nameB, use_case: currentUseCase }),
    });
    const data = await res.json();
    if (res.ok) {
      addBotMessage(data.comparison, true);
      if (data.laptop_a && data.laptop_b) {
        renderComparisonCards(
          data.laptop_a, data.laptop_b,
          data.comparison,
          data.score_pct  || { a: 0, b: 0 },
          data.near_tie   || false,
          data.use_case   || currentUseCase
        );
      }
    } else {
      addBotMessage(`⚠️ ${data.error || 'Could not compare laptops.'}`);
    }
  } catch (e) {
    addBotMessage('⚠️ Comparison failed. Server error.');
  }
}

// ── SAGE Voice Assistant ──────────────────────────────────────────

let sageRecognition = null;
let sageListening   = false;

function updateSageClock() {
  const now = new Date();
  let h = now.getHours(), m = now.getMinutes(), s = now.getSeconds();
  const ap = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  const el = document.getElementById('sage-clock');
  if (el) el.textContent = `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')} ${ap}`;
}
setInterval(updateSageClock, 1000);
updateSageClock();

function openSAGE() {
  document.getElementById('sage-overlay').style.display = 'flex';
  document.body.style.overflow = 'hidden';
  playSAGEOpenSound();
  setTimeout(() => {
    sageTerminalLog('SAGE', 'Systems online. I am SAGE — Smart Advisor for Gadget Evaluation. How can I help you find the perfect laptop today?');
    speakSAGE('Good day! I am SAGE. Systems are fully operational. How can I help you today?');
  }, 300);
}

function closeSAGE() {
  document.getElementById('sage-overlay').style.display = 'none';
  document.body.style.overflow = '';
  if (sageListening) stopSAGEListening();
  if (window.speechSynthesis) window.speechSynthesis.cancel();
}

function clearSAGETerminal() {
  document.getElementById('sage-terminal').innerHTML = '';
  sageTerminalLog('System', 'Terminal cleared.');
}

function setSAGEStatus(msg) {
  const el = document.getElementById('sage-status');
  if (el) el.textContent = msg;
}

function sageTerminalLog(speaker, message) {
  const terminal = document.getElementById('sage-terminal');
  const now = new Date();
  let h = now.getHours(), m = now.getMinutes(), s = now.getSeconds();
  const ap = h >= 12 ? 'PM' : 'AM';
  h = h % 12 || 12;
  const time  = `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')} ${ap}`;
  const color = speaker === 'SAGE' ? '#00d4ff' : speaker === 'You' ? '#a78bfa' : '#8b949e';
  const div   = document.createElement('div');
  div.style.marginBottom = '10px';
  div.innerHTML = `<span style="color:#555;">[${time}]</span> <span style="color:${color};font-weight:700;">${speaker}</span><br><span style="color:#c9d1d9;">${message.replace(/</g,'&lt;').replace(/\n/g,'<br>')}</span>`;
  terminal.appendChild(div);
  terminal.scrollTop = terminal.scrollHeight;
}

function playSAGEOpenSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [330,440,550,660].forEach((freq,i) => {
      const osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination); osc.type='sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime+i*0.1);
      gain.gain.setValueAtTime(0, ctx.currentTime+i*0.1);
      gain.gain.linearRampToValueAtTime(0.18, ctx.currentTime+i*0.1+0.04);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime+i*0.1+0.3);
      osc.start(ctx.currentTime+i*0.1); osc.stop(ctx.currentTime+i*0.1+0.3);
    });
  } catch(e) {}
}

function toggleSAGEListening() { sageListening ? stopSAGEListening() : startSAGEListening(); }

function startSAGEListening() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { sageTerminalLog('System','Voice recognition not supported. Use Chrome or Edge.'); document.getElementById('sage-input-row').style.display='block'; return; }
  navigator.mediaDevices.getUserMedia({audio:true})
    .then(() => _startRecognition(SR))
    .catch(() => { sageTerminalLog('System','Microphone access denied.'); setSAGEStatus('● MIC BLOCKED'); });
}

function _startRecognition(SR) {
  if (sageRecognition) { try { sageRecognition.abort(); } catch(e) {} }
  sageRecognition = new SR();
  sageRecognition.lang='en-US'; sageRecognition.continuous=false; sageRecognition.interimResults=true; sageRecognition.maxAlternatives=5;
  sageRecognition.onstart = () => {
    sageListening=true;
    document.getElementById('sage-mic-btn').style.cssText='width:46px;height:46px;border-radius:50%;background:rgba(255,68,68,0.2);border:2px solid #ff4444;color:#ff4444;cursor:pointer;font-size:20px;display:flex;align-items:center;justify-content:center;';
    document.getElementById('sage-mic-btn').innerHTML='⏹';
    document.getElementById('sage-ring-outer').style.animation='sage-listen-pulse 0.8s ease-in-out infinite';
    setSAGEStatus('● LISTENING — speak now...');
  };
  sageRecognition.onresult = (e) => {
    let interim='', final='';
    for (let i=e.resultIndex;i<e.results.length;i++) { const t=e.results[i][0].transcript; if(e.results[i].isFinal) final+=t; else interim+=t; }
    if (interim) setSAGEStatus('● HEARING: '+interim.substring(0,50)+'...');
    if (final) { sageTerminalLog('You',final); askSAGE(final); }
  };
  sageRecognition.onerror = (e) => {
    const msgs={'no-speech':'No speech detected.','audio-capture':'Mic not found.','not-allowed':'Mic blocked.','network':'Network error.','aborted':'Stopped.'};
    sageTerminalLog('System', msgs[e.error]||'Error: '+e.error);
    setSAGEStatus('● '+(e.error||'ERROR').toUpperCase()); stopSAGEListening();
  };
  sageRecognition.onend = () => stopSAGEListening();
  try { sageRecognition.start(); } catch(e) { sageTerminalLog('System','Could not start mic: '+e.message); stopSAGEListening(); }
}

function stopSAGEListening() {
  sageListening=false;
  if (sageRecognition) sageRecognition.stop();
  const btn=document.getElementById('sage-mic-btn');
  if (btn) { btn.style.background='rgba(0,212,255,0.15)'; btn.style.borderColor='#00d4ff'; btn.style.color='#00d4ff'; btn.innerHTML='🎤'; }
  const ring=document.getElementById('sage-ring-outer');
  if (ring) ring.style.animation='';
  setSAGEStatus('● READY');
}

async function askSAGE(query) {
  if (!query || !query.trim()) return;
  const q = query.toLowerCase().trim();
  setSAGEStatus('● PROCESSING...');

  // ── Link opening commands ──────────────────────────────────────
  const openCmds = ['open','go to','show','launch','visit','take me to'];
  if (openCmds.some(c => q.startsWith(c) || q.includes(c))) {
    const links = document.querySelectorAll('#chat-messages a[href]');
    let matched = null;
    if (q.includes('daraz'))                       matched = [...links].find(a => a.href.includes('daraz.lk'));
    else if (q.includes('kapruka'))                matched = [...links].find(a => a.href.includes('kapruka.com'));
    else if (q.includes('image') || q.includes('photo')) matched = [...links].find(a => a.href.includes('tbm=isch'));
    else if (q.includes('link') || q.includes('buy'))    matched = [...links].find(a => a.href.includes('daraz.lk'));
    if (matched) {
      window.open(matched.href, '_blank');
      sageTerminalLog('SAGE', 'Opening link now...');
      setSAGEStatus('● LINK OPENED');
      speakSAGE('Opening the link now.');
    } else {
      sageTerminalLog('SAGE', 'No link found yet. Ask me for a laptop recommendation first, then I can open the link for you.');
      setSAGEStatus('● READY');
      speakSAGE('Please ask for a laptop recommendation first, then I can open the link for you.');
    }
    return;
  }

  // ── Real AI query ──────────────────────────────────────────────
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message:  query,
        budget:   currentBudget  || '500000',
        use_case: currentUseCase || 'general use',
      }),
    });

    if (!res.ok) throw new Error('Server error ' + res.status);
    const data = await res.json();

    // Full AI reply — strip markdown symbols for clean terminal display
    const fullText = (data.reply || 'Sorry, I could not get a response.')
      .replace(/#{1,6}\s*/g, '')   // headings
      .replace(/\*\*/g, '')        // bold
      .replace(/\*/g, '')          // italic/bullets
      .replace(/`/g, '')           // code
      .replace(/\n{3,}/g, '\n\n')  // excessive newlines
      .trim();

    // Show full response in terminal (no truncation)
    sageTerminalLog('SAGE', fullText);

    // If laptops were returned, show a brief card summary in terminal
    if (data.laptops && data.laptops.length > 0) {
      const topLaptop = data.laptops[0];
      sageTerminalLog('📦 Top Pick', `${topLaptop.brand} ${topLaptop.laptop} — LKR ${Number(topLaptop.price).toLocaleString()} | ${topLaptop.cpu} | ${topLaptop.ram}GB RAM`);
    }

    setSAGEStatus('● RESPONSE READY');

    // Speak a natural summary — first 2 sentences or 400 chars, whichever is shorter
    const sentences = fullText.match(/[^.!?]+[.!?]+/g) || [fullText];
    const spokenSummary = sentences.slice(0, 3).join(' ').substring(0, 400);
    speakSAGE(spokenSummary);

  } catch (err) {
    sageTerminalLog('System', 'Could not reach the server. Make sure the backend is running on localhost:5000.');
    setSAGEStatus('● CONNECTION ERROR');
  }
}

function speakSAGE(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(text);
  u.rate=0.92; u.pitch=1.1; u.volume=1.0;
  const femaleNames=['Microsoft Zira','Microsoft Zira Desktop','Zira','Samantha','Karen','Moira','Tessa','Veena','Victoria','Fiona','Google UK English Female','Google US English Female','Microsoft Aria','Microsoft Jenny','Microsoft Michelle','Microsoft Monica','Microsoft Clara','Microsoft Emma','Microsoft Libby','Microsoft Mia','Microsoft Natasha'];
  const loadVoices=()=>{
    const voices=window.speechSynthesis.getVoices();
    let pick=voices.find(v=>femaleNames.includes(v.name));
    if (!pick) pick=voices.find(v=>{const n=v.name.toLowerCase();return n.includes('zira')||n.includes('samantha')||n.includes('female')||n.includes('aria')||n.includes('jenny')||n.includes('michelle')||n.includes('emma')||n.includes('karen')||n.includes('tessa');});
    if (!pick) pick=voices.find(v=>v.lang==='en-GB'||v.lang==='en-AU');
    if (pick) u.voice=pick;
  };
  if (window.speechSynthesis.getVoices().length) loadVoices(); else window.speechSynthesis.onvoiceschanged=loadVoices;
  u.onstart=()=>{setSAGEStatus('● SPEAKING...'); document.getElementById('sage-ring-outer').style.animation='sage-listen-pulse 1s ease-in-out infinite';};
  u.onend=()=>{setSAGEStatus('● READY'); document.getElementById('sage-ring-outer').style.animation='';};
  window.speechSynthesis.speak(u);
}

document.addEventListener('DOMContentLoaded',()=>{
  const so=document.getElementById('sage-overlay');
  if (so) so.addEventListener('click',function(e){if(e.target===this)closeSAGE();});
  const co=document.getElementById('chatbot-overlay');
  if (co) co.addEventListener('click',function(e){if(e.target===this)closeChatbot();});
});

// ── Quiz / Modal ──────────────────────────────────────────────────

let currentStep=1, selectedUseCase='', preselectedUseCase='';
const totalSteps=3;

function openModal() {
  resetQuiz();
  document.getElementById('overlay').classList.add('active');
  document.body.style.overflow='hidden';
  if (preselectedUseCase) {
    goToStep(2);
    document.querySelectorAll('.uc-opt').forEach(o=>{if(o.querySelector('.ol').textContent.toLowerCase()===preselectedUseCase.toLowerCase()) selectUseCase(o,preselectedUseCase);});
    preselectedUseCase='';
  }
}
function openModalWithUseCase(uc){preselectedUseCase=uc;openModal();}
function closeModal(){document.getElementById('overlay').classList.remove('active');document.body.style.overflow='';}
function handleOverlayClick(e){if(e.target===document.getElementById('overlay'))closeModal();}
function toggleMobile(){document.getElementById('mobileMenu').classList.toggle('open');}

function goToStep(n){
  document.getElementById('step'+currentStep).classList.remove('active');
  currentStep=n;
  document.getElementById('step'+currentStep).classList.add('active');
  updateProgress();updateNavButtons();
}
function nextStep(){
  if(currentStep===1){const b=document.getElementById('budgetInput').value.trim();if(!b||isNaN(b)||Number(b)<=0){showToast('Please enter a valid budget amount.');return;}goToStep(2);}
  else if(currentStep===2){if(!selectedUseCase){showToast('Please select a use case.');return;}goToStep(3);}
  else if(currentStep===3){submitQuiz();}
}
function prevStep(){if(currentStep>1)goToStep(currentStep-1);}
function updateProgress(){document.getElementById('progressFill').style.width=(currentStep/totalSteps*100)+'%';document.getElementById('progressLabel').textContent='Step '+currentStep+' of '+totalSteps;}
function updateNavButtons(){document.getElementById('backBtn').style.visibility=currentStep>1?'visible':'hidden';document.getElementById('nextBtn').textContent=currentStep===totalSteps?'Get My Recommendation ✨':'Next →';}
function selectUseCase(el,uc){document.querySelectorAll('.uc-opt').forEach(o=>o.classList.remove('selected'));el.classList.add('selected');selectedUseCase=uc;}
function resetQuiz(){currentStep=1;selectedUseCase='';document.querySelectorAll('.quiz-step').forEach(s=>s.classList.remove('active'));document.getElementById('step1').classList.add('active');document.getElementById('budgetInput').value='';document.getElementById('prefInput').value='';document.querySelectorAll('.uc-opt').forEach(o=>o.classList.remove('selected'));document.getElementById('loadingWrap').classList.remove('active');document.getElementById('modalNav').style.display='flex';updateProgress();updateNavButtons();}

async function submitQuiz(){
  const budget=document.getElementById('budgetInput').value.trim();
  const useCase=selectedUseCase;
  const prefs=document.getElementById('prefInput').value.trim()||'no specific preferences';

  // Store globally for chat context
  currentBudget  = budget;
  currentUseCase = useCase;

  document.querySelectorAll('.quiz-step').forEach(s=>s.classList.remove('active'));
  document.getElementById('loadingWrap').classList.add('active');
  document.getElementById('modalNav').style.display='none';

  try {
    const res=await fetch('/recommend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({budget:budget+' LKR',use_case:useCase,preferences:prefs})});
    if(!res.ok){const err=await res.json().catch(()=>({}));throw new Error(err.error||'Server returned '+res.status);}
    const data=await res.json();
    closeModal();
    showResults(data.recommendation,budget,useCase,data.laptops);
  } catch(err){
    document.getElementById('loadingWrap').classList.remove('active');
    document.getElementById('modalNav').style.display='flex';
    document.getElementById('step3').classList.add('active');
    showToast('Error: '+(err.message||'Could not reach the server.'));
  }
}

function showResults(markdown, budget, useCase, laptops){
  document.getElementById('resultMeta').textContent='Budget: LKR '+Number(budget).toLocaleString()+' • Use case: '+capitalize(useCase);
  document.getElementById('resultBody').innerHTML=renderMarkdown(markdown);
  if (laptops && laptops.length) renderResultLaptopCards(laptops);
  const r=document.getElementById('results');
  r.classList.add('active');
  r.scrollIntoView({behavior:'smooth',block:'start'});
}

function renderResultLaptopCards(laptops){
  let el=document.getElementById('result-laptop-cards');
  if(!el){el=document.createElement('div');el.id='result-laptop-cards';document.getElementById('results').querySelector('.result-card').appendChild(el);}
  el.innerHTML='';
  const sorted=[...laptops].sort((a,b)=>parseFloat(a.price)-parseFloat(b.price));
  sorted.forEach(l=>{
    const card=document.createElement('div');
    card.style.cssText='border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:12px;margin-top:12px;background:rgba(255,255,255,0.02);';
    card.innerHTML=`<div style="font-weight:700;color:#e6edf3;">${l.brand} ${l.laptop}</div><div style="font-size:12px;color:#8b949e;margin:4px 0;">${l.cpu} · ${l.ram}GB RAM · ${l.storage}GB · ${l.gpu}</div><div style="font-size:14px;font-weight:700;color:#00d4ff;margin-bottom:8px;">LKR ${Number(l.price).toLocaleString()}</div><a href="${l.daraz_url}" target="_blank" style="background:#F57C00;color:white;padding:5px 10px;border-radius:6px;font-size:11px;font-weight:700;text-decoration:none;margin-right:6px;">🛒 Daraz</a><a href="${l.ikman_url}" target="_blank" style="background:#e53935;color:white;padding:5px 10px;border-radius:6px;font-size:11px;font-weight:700;text-decoration:none;">📌 ikman.lk</a>`;
    el.appendChild(card);
  });
}

function startOver(){document.getElementById('results').classList.remove('active');window.scrollTo({top:0,behavior:'smooth'});}
function showToast(msg){const t=document.getElementById('toast');t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),4000);}
function capitalize(s){return s.charAt(0).toUpperCase()+s.slice(1);}

document.addEventListener('keydown',e=>{
  if(e.key==='Escape')closeModal();
  if(e.key==='Enter'&&document.getElementById('overlay').classList.contains('active')){if(!document.getElementById('loadingWrap').classList.contains('active'))nextStep();}
});
