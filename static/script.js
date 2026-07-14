const languageButton = document.getElementById("languageButton");
const languageMenu = document.getElementById("languageMenu");
const languageFlag = document.getElementById("languageFlag");
const languageCode = document.getElementById("languageCode");
const newChatBtn = document.getElementById("newChatBtn");
const historyEl = document.getElementById("chatHistory");
const themeToggle = document.getElementById("themeToggle");
const themeIcon = document.getElementById("themeIcon");
const chatEl = document.getElementById('chat');
const chatMessagesEl = document.getElementById('chatMessages');
const composerEl = document.getElementById('composer');
const inputEl = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const relayProgressEl = document.getElementById('relayProgress');
const attachBtn = document.getElementById('attachBtn');
const fileInput = document.getElementById('fileInput');
const attachmentsPreviewEl = document.getElementById('attachmentsPreview');
const replyPreviewEl = document.getElementById('replyPreview');
const replyPreviewTextEl = document.getElementById('replyPreviewText');
const replyPreviewCloseBtn = document.getElementById('replyPreviewClose');

const NODE_ORDER = ['coordenador', 'pesquisador', 'especialista', 'redator'];

// Mapeia o "role" devolvido pelo CrewAI (Python) para a chave do node no HTML.
const AGENT_ROLE_TO_NODE = {
  'Coordenador de Atendimento': 'coordenador',
  'Pesquisador': 'pesquisador',
  'Especialista Técnico': 'especialista',
  'Redator Final': 'redator',
};

let conversations =
  JSON.parse(localStorage.getItem("crew_conversations")) || [];

let currentConversation = [];
let sessionId = localStorage.getItem('crew_session_id') || null;
let pendingAttachments = []; // { name, dataUrl }
let replyingTo = null; // texto da mensagem do assistente a que se está a responder

let translations = {};

let currentLanguage =
  localStorage.getItem("language") || "pt";

async function loadLanguage(language) {

  const response =
    await fetch(`/static/translations/${language}.json`);

  translations =
    await response.json();

  translatePage();

}

function translatePage() {

  document.querySelectorAll("[data-i18n]")

    .forEach(element => {

      element.textContent =
        translations[
        element.dataset.i18n
        ];

    });

  document.querySelectorAll(
    "[data-i18n-placeholder]")

    .forEach(element => {

      element.placeholder =

        translations[
        element.dataset.i18nPlaceholder
        ];

    });

  languageButton.onclick = () => {

    languageMenu.classList.toggle("show");

  }

  document
    .querySelectorAll(".language-item")

    .forEach(item => {

      item.onclick = () => {

        const lang = item.dataset.lang;

        currentLanguage = lang;

        localStorage.setItem(
          "language",
          lang
        );

        languageFlag.src =
          `/static/img/flags/${lang}.svg`;

        languageCode.textContent =
          lang.toUpperCase();

        loadLanguage(lang);

        languageMenu.classList.remove("show");

      };

    });


}


function saveHistory() {

  if (currentConversation.length === 0) return;

  if (
    conversations.length &&
    JSON.stringify(conversations[0].messages) === JSON.stringify(currentConversation)
  ) {
    return;
  }

  conversations.unshift({
    title: currentConversation[0].text.substring(0, 40),
    messages: [...currentConversation]
  });

  localStorage.setItem(
    "crew_conversations",
    JSON.stringify(conversations)
  );

  renderHistory();

}

function renderHistory() {

  historyEl.innerHTML = "";

  conversations.forEach((conv, index) => {

    const item = document.createElement("div");
    item.className = "chat-item";

    const title = document.createElement("span");
    title.className = "chat-item-title";
    title.textContent = conv.title;

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "chat-delete";
    deleteBtn.innerHTML = "🗑️";
    deleteBtn.title = "Eliminar conversa";

    deleteBtn.onclick = (e) => {

      e.stopPropagation();

      if (!confirm("Pretende eliminar esta conversa?"))
        return;

      conversations.splice(index, 1);

      localStorage.setItem(
        "crew_conversations",
        JSON.stringify(conversations)
      );

      renderHistory();

    };

    item.onclick = () => loadConversation(index);

    item.appendChild(title);
    item.appendChild(deleteBtn);

    historyEl.appendChild(item);

  });

}

function deleteConversation(index) {

  if (!confirm("Eliminar esta conversa?"))
    return;

  conversations.splice(index, 1);

  localStorage.setItem(
    "crew_conversations",
    JSON.stringify(conversations)
  );

  renderHistory();

}

function removeEmptyState() {
  const empty = document.getElementById('chatEmpty');
  if (empty) empty.remove();
}

function clearConversation() {

  chatMessagesEl.innerHTML = '';

  if (!document.getElementById('chatEmpty')) {

    const empty = document.createElement('div');

    empty.className = 'chat__empty';
    empty.id = 'chatEmpty';

    empty.innerHTML = `
        <p class="chat__empty-eyebrow">EQUIPA DE AGENTES</p>
        <h2 class="chat__empty-title">Como posso ajudar?</h2>
        <p class="chat__empty-sub">Escreve uma mensagem para começar.</p>
    `;

    chatEl.insertBefore(empty, chatMessagesEl);

  }

}

function loadConversation(index) {

  clearConversation();

  currentConversation = conversations[index].messages;

  currentConversation.forEach(msg => {

    addMessage(msg.text, msg.role);

  });

}

newChatBtn.onclick = () => {

  saveHistory();

  currentConversation = [];

  sessionId = null;

  localStorage.removeItem("crew_session_id");

  clearConversation();

  resetRelay();

};

/* ---------------- Relay (agentes) ---------------- */

function getNodeEl(key) {
  return document.querySelector(`.relay__node[data-node="${key}"]`);
}

function resetRelay() {

  relayProgressEl.style.width = "0%";

  NODE_ORDER.forEach((key) => {

    const el = getNodeEl(key);

    el.classList.remove("active");
    el.classList.remove("done");

  });

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

/* ---------------- Chat helpers ---------------- */

function scrollToBottom() {
  chatEl.scrollTop = chatEl.scrollHeight;
}

const AVATAR_ICONS = {
  user: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <circle cx="12" cy="8" r="4" fill="currentColor"/>
    <path d="M4 20c0-4.418 3.582-8 8-8s8 3.582 8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  </svg>`,
  assistant: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <rect x="4" y="8" width="16" height="12" rx="4" fill="currentColor"/>
    <rect x="10" y="2" width="4" height="4" rx="1.5" fill="currentColor"/>
    <line x1="12" y1="6" x2="12" y2="8" stroke="currentColor" stroke-width="2"/>
    <circle cx="9" cy="14.5" r="1.6" fill="var(--bg)"/>
    <circle cx="15" cy="14.5" r="1.6" fill="var(--bg)"/>
  </svg>`,
};

function createAvatar(role) {
  const avatar = document.createElement('div');
  avatar.className = `avatar avatar--${role}`;
  avatar.innerHTML = AVATAR_ICONS[role] || AVATAR_ICONS.assistant;
  return avatar;
}

/**
 * Envolve o elemento da mensagem (bolha) numa "row" com o avatar ao lado.
 * `role` é 'user' ou 'assistant'. `extraClass` (opcional) permite limitar
 * a largura da row em casos especiais (ex: mensagens de imagem).
 */
function wrapWithAvatar(msgEl, role, extraClass) {
  const row = document.createElement('div');
  row.className = `msg-row msg-row--${role}${extraClass ? ' ' + extraClass : ''}`;
  row.appendChild(createAvatar(role));
  row.appendChild(msgEl);
  return row;
}

const REPLY_ICON = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none">
  <path d="M9 14L4 9L9 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M4 9H14C18 9 20 12 20 16V19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

function setReplyTarget(text) {
  replyingTo = text;
  replyPreviewTextEl.textContent = text;
  replyPreviewEl.hidden = false;
  inputEl.focus();
}

function clearReplyTarget() {
  replyingTo = null;
  replyPreviewTextEl.textContent = '';
  replyPreviewEl.hidden = true;
}

replyPreviewCloseBtn.addEventListener('click', clearReplyTarget);

/**
 * Adiciona, dentro da bolha de uma mensagem do assistente, um botãozinho
 * que permite responder diretamente a essa mensagem (visível ao passar o
 * rato, via CSS em .msg-row:hover .msg__reply-btn).
 */
function addReplyButton(msgEl, textoParaCitar) {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'msg__reply-btn';
  btn.title = 'Responder a esta mensagem';
  btn.innerHTML = REPLY_ICON;
  btn.addEventListener('click', () => setReplyTarget(textoParaCitar));
  msgEl.appendChild(btn);
}

/**
 * Se a mensagem do humano foi enviada como resposta a uma mensagem
 * anterior do assistente, mostra essa citação no topo da própria bolha.
 */
function addQuoteToMessage(msgEl, quotedText) {
  if (!quotedText) return;
  const quote = document.createElement('p');
  quote.className = 'msg__quote';
  quote.textContent = quotedText;
  msgEl.insertBefore(quote, msgEl.firstChild);
}

function addMessage(text, role) {
  removeEmptyState();
  const div = document.createElement('div');
  div.className = `msg msg--${role}`;
  div.textContent = text;
  if (role === 'assistant') addReplyButton(div, text);
  chatMessagesEl.appendChild(wrapWithAvatar(div, role));
  scrollToBottom();
  return div;
}

function addUserMessageWithAttachments(text, images, quotedText) {
  removeEmptyState();
  const div = document.createElement('div');
  div.className = 'msg msg--user';

  if (quotedText) addQuoteToMessage(div, quotedText);

  if (images && images.length) {
    const grid = document.createElement('div');
    grid.className = 'msg__attachments';
    images.forEach((src) => {
      const img = document.createElement('img');
      img.src = src;
      grid.appendChild(img);
    });
    div.appendChild(grid);
  }

  if (text) {
    const p = document.createElement('p');
    p.className = 'msg__text';
    p.textContent = text;
    div.appendChild(p);
  }

  chatMessagesEl.appendChild(wrapWithAvatar(div, 'user'));
  scrollToBottom();
  return div;
}
function addImageMessage(imageBase64, promptUsed) {
  removeEmptyState();
  const wrapper = document.createElement('div');
  wrapper.className = 'msg msg--assistant msg--image';

  const img = document.createElement('img');
  img.src = `data:image/png;base64,${imageBase64}`;
  img.alt = promptUsed || 'Imagem gerada';
  img.className = 'msg__image';

  const caption = document.createElement('p');
  caption.className = 'msg__caption';
  caption.textContent = promptUsed;

  wrapper.appendChild(img);
  wrapper.appendChild(caption);
  chatMessagesEl.appendChild(wrapWithAvatar(wrapper, 'assistant', 'msg-row--image'));
  scrollToBottom();
  return wrapper;
}

function addPdfMessage(pdfFilename, downloadUrl, pages) {
  removeEmptyState();
  const div = document.createElement('div');
  div.className = 'msg msg--assistant msg--pdf';

  const p = document.createElement('p');
  p.className = 'msg__text';
  p.textContent = `📎 PDF criado com ${pages} página(s).`;

  const link = document.createElement('a');
  link.href = downloadUrl;
  link.target = '_blank';
  link.rel = 'noopener';
  link.className = 'msg__pdf-link';
  link.textContent = `⬇️ Descarregar ${pdfFilename}`;

  div.appendChild(p);
  div.appendChild(link);
  chatMessagesEl.appendChild(wrapWithAvatar(div, 'assistant'));
  scrollToBottom();
  return div;
}

function addProgressMessage(text) {
  removeEmptyState();
  const div = document.createElement('div');
  div.className = 'msg msg--progress';
  div.textContent = text;
  chatMessagesEl.appendChild(div);
  scrollToBottom();
  return div;
}

/* ---------------- Tema ---------------- */

function applyTheme(theme) {

  if (theme === "light") {
    document.body.classList.add("light-mode");
    themeIcon.textContent = "☀️";
  } else {
    document.body.classList.remove("light-mode");
    themeIcon.textContent = "🌙";
  }

  localStorage.setItem("theme", theme);
}

applyTheme(localStorage.getItem("theme") || "dark");

themeToggle.addEventListener("click", () => {

  const current =
    document.body.classList.contains("light-mode")
      ? "light"
      : "dark";

  applyTheme(current === "dark" ? "light" : "dark");

});

/* ---------------- Anexos ---------------- */

function readFileAsDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function renderAttachmentsPreview() {
  attachmentsPreviewEl.innerHTML = '';

  if (pendingAttachments.length === 0) {
    attachmentsPreviewEl.classList.remove('attachments--visible');
    return;
  }

  attachmentsPreviewEl.classList.add('attachments--visible');

  pendingAttachments.forEach((att, idx) => {
    const thumb = document.createElement('div');
    thumb.className = 'attachment-thumb';

    const img = document.createElement('img');
    img.src = att.dataUrl;
    img.alt = att.name;

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'attachment-thumb__remove';
    removeBtn.textContent = '×';
    removeBtn.title = 'Remover';
    removeBtn.addEventListener('click', () => {
      pendingAttachments.splice(idx, 1);
      renderAttachmentsPreview();
    });

    thumb.appendChild(img);
    thumb.appendChild(removeBtn);
    attachmentsPreviewEl.appendChild(thumb);
  });
}

attachBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async (e) => {
  const files = Array.from(e.target.files || []);
  for (const file of files) {
    if (!file.type.startsWith('image/')) continue;
    try {
      const dataUrl = await readFileAsDataURL(file);
      pendingAttachments.push({ name: file.name, dataUrl });
    } catch (err) {
      console.error('Erro a ler ficheiro', err);
    }
  }
  fileInput.value = '';
  renderAttachmentsPreview();
});

/* ---------------- Envio de mensagens ---------------- */

async function sendMessage(message, images, replyTo) {
  addUserMessageWithAttachments(message, images, replyTo);
  currentConversation.push({
    role: "user",
    text: message || "[Imagem]"
  });
  resetRelay();
  // O primeiro nó só acende quando soubermos (pela 1ª mensagem do servidor)
  // se este pedido vai pelo pipeline de texto, imagem ou anexos.

  sendBtn.disabled = true;
  inputEl.disabled = true;

  const progressEl = addProgressMessage(
    images.length ? '📎 A preparar os anexos...' : '🧭 Coordenador a analisar o pedido...'
  );

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, language: currentLanguage, images, session_id: sessionId, reply_to: replyTo || null }),
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
        } else if (payload.type === 'image_progress' || payload.type === 'attachment_progress') {
          progressEl.textContent = payload.label;
          scrollToBottom();
        } else if (payload.type === 'attachment_done') {
          addPdfMessage(payload.pdf_filename, payload.download_url, payload.pages);
        } else if (payload.type === 'final') {
          sessionId = payload.session_id;
          localStorage.setItem('crew_session_id', sessionId);

          progressEl.remove();

          addMessage(payload.reply, "assistant");

          currentConversation.push({
            role: "assistant",
            text: payload.reply
          });

          NODE_ORDER.forEach((k) => markNodeDone(k));
        } else if (payload.type === 'image') {
          sessionId = payload.session_id;
          localStorage.setItem('crew_session_id', sessionId);

          progressEl.remove();

          addImageMessage(payload.image_base64, payload.prompt_used);

          currentConversation.push({
            role: "assistant",
            text: "[Imagem Gerada]"
          });
        } else if (payload.type === 'error') {
          progressEl.remove();
          addMessage('Ocorreu um erro: ' + payload.message, 'assistant');
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
  const images = pendingAttachments.map((a) => a.dataUrl);

  if (!message && images.length === 0) return;

  const replyTo = replyingTo;

  inputEl.value = '';
  pendingAttachments = [];
  renderAttachmentsPreview();
  clearReplyTarget();

  sendMessage(message, images, replyTo);
  renderHistory();
});

loadLanguage(currentLanguage);

languageFlag.src=
`/static/img/flags/${currentLanguage}.svg`;

languageCode.textContent=
currentLanguage.toUpperCase();