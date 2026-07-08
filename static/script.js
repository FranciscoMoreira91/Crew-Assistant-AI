const chatEl = document.getElementById('chat');
const chatEmptyEl = document.getElementById('chatEmpty');
const composerEl = document.getElementById('composer');
const inputEl = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const relayProgressEl = document.getElementById('relayProgress');

const NODE_ORDER = ['coordenador', 'pesquisador', 'especialista', 'redator'];

// Mapeia o "role" devolvido pelo CrewAI (Python) para a chave do node no HTML.
const AGENT_ROLE_TO_NODE = {
  'Coordenador de Atendimento': 'coordenador',
  'Pesquisador': 'pesquisador',
  'Especialista Técnico': 'especialista',
  'Redator Final': 'redator',
};

let sessionId = localStorage.getItem('crew_session_id') || null;

function getNodeEl(key) {
  return document.querySelector(`.relay__node[data-node="${key}"]`);
}

function resetRelay() {
  NODE_ORDER.forEach((key) => {
    const el = getNodeEl(key);
    el.classList.remove('active', 'done');
  });
  relayProgressEl.style.width = '0%';
}

function setNodeActive(key) {
  NODE_ORDER.forEach((k) => {
    const el = getNodeEl(k);
    if (k === key) {
      el.classList.add('active');
      el.classList.remove('done');
    }
  });
}

function markNodeDone(key) {
  const el = getNodeEl(key);
  if (!el) return;
  el.classList.remove('active');
  el.classList.add('done');

  const idx = NODE_ORDER.indexOf(key);
  const pct = ((idx + 1) / NODE_ORDER.length) * 100;
  relayProgressEl.style.width = pct + '%';

  const nextKey = NODE_ORDER[idx + 1];
  if (nextKey) setNodeActive(nextKey);
}

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

function addMessage(text, role) {
  if (chatEmptyEl) chatEmptyEl.remove();
  const div = document.createElement('div');
  div.className = `msg msg--${role}`;
  div.textContent = text;
  chatEl.appendChild(div);
  scrollToBottom();
  return div;
}

function addProgressMessage(text) {
  if (chatEmptyEl) chatEmptyEl.remove();
  const div = document.createElement('div');
  div.className = 'msg msg--progress';
  div.textContent = text;
  chatEl.appendChild(div);
  scrollToBottom();
  return div;
}

async function sendMessage(message) {
  addMessage(message, 'user');
  resetRelay();
  setNodeActive(NODE_ORDER[0]);

  sendBtn.disabled = true;
  inputEl.disabled = true;

  const progressEl = addProgressMessage('🧭 Coordenador a analisar o pedido...');

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const parts = buffer.split('\n\n');
      buffer = parts.pop(); // guarda o resto incompleto

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data:')) continue;
        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;

        let payload;
        try {
          payload = JSON.parse(jsonStr);
        } catch (e) {
          continue;
        }

        if (payload.type === 'progress') {
          const nodeKey = AGENT_ROLE_TO_NODE[payload.agent];
          if (nodeKey) markNodeDone(nodeKey);
          progressEl.textContent = payload.label;
          scrollToBottom();
        } else if (payload.type === 'final') {
          sessionId = payload.session_id;
          localStorage.setItem('crew_session_id', sessionId);
          progressEl.remove();
          addMessage(payload.reply, 'assistant');
          NODE_ORDER.forEach((k) => markNodeDone(k));
        } else if (payload.type === 'error') {
          progressEl.remove();
          addMessage('Ocorreu um erro ao contactar a equipa de agentes: ' + payload.message, 'assistant');
        }
      }
    }
  } catch (err) {
    progressEl.remove();
    addMessage('Não foi possível ligar ao servidor. Verifica se o backend Flask está a correr.', 'assistant');
  } finally {
    sendBtn.disabled = false;
    inputEl.disabled = false;
    inputEl.focus();
  }
}

composerEl.addEventListener('submit', (e) => {
  e.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;
  inputEl.value = '';
  sendMessage(message);
});
