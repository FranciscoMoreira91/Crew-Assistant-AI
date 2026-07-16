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
let pendingAttachments = []; // { name, dataUrl, mime }

function fileExtension(name) {
  const parts = (name || '').split('.');
  return parts.length > 1 ? parts.pop().toUpperCase().slice(0, 4) : '';
}
let replyingTo = null; // texto da mensagem do assistente a que se está a responder

let translations = {};

let currentLanguage =
  localStorage.getItem("language") || "pt";

/* ---------------- Definições ---------------- */

async function loadSettings() {

    try {

        const response = await fetch("/api/config");

        if (!response.ok) {
            throw new Error("Erro ao carregar configurações.");
        }

        const config = await response.json();

        // IA
        if (document.getElementById("llm_provider"))
            document.getElementById("llm_provider").value = config.LLM_PROVIDER || "";

        if (document.getElementById("model_name"))
            document.getElementById("model_name").value = config.MODEL_NAME || "";

        // Imagem
        if (document.getElementById("image_provider"))
            document.getElementById("image_provider").value = config.IMAGE_PROVIDER || "";

        if (document.getElementById("image_model"))
            document.getElementById("image_model").value = config.IMAGE_MODEL || "";

        // Vídeo
        if (document.getElementById("video_provider"))
            document.getElementById("video_provider").value = config.VIDEO_PROVIDER || "";

        if (document.getElementById("video_model"))
            document.getElementById("video_model").value = config.VIDEO_MODEL || "";

        // OCR
        if (document.getElementById("ocr_enabled"))
            document.getElementById("ocr_enabled").value = config.OCR_ENABLED || "true";

        if (document.getElementById("ocr_language"))
            document.getElementById("ocr_language").value = config.OCR_LANGUAGE || "por";

        // IMAP
        if (document.getElementById("email_host"))
            document.getElementById("email_host").value = config.EMAIL_HOST || "";

        if (document.getElementById("email_port"))
            document.getElementById("email_port").value = config.EMAIL_PORT || "";

        if (document.getElementById("email_user"))
            document.getElementById("email_user").value = config.EMAIL_USERNAME || "";

        if (document.getElementById("email_password"))
            document.getElementById("email_password").value = config.EMAIL_PASSWORD || "";

        // SMTP
        if (document.getElementById("smtp_host"))
            document.getElementById("smtp_host").value = config.SMTP_HOST || "";

        if (document.getElementById("smtp_port"))
            document.getElementById("smtp_port").value = config.SMTP_PORT || "";

        if (document.getElementById("smtp_user"))
            document.getElementById("smtp_user").value = config.SMTP_USERNAME || "";

        if (document.getElementById("smtp_password"))
            document.getElementById("smtp_password").value = config.SMTP_PASSWORD || "";

        // API Keys
        if (document.getElementById("openai_api_key"))
            document.getElementById("openai_api_key").value = config.OPENAI_API_KEY || "";

        if (document.getElementById("anthropic_api_key"))
            document.getElementById("anthropic_api_key").value = config.ANTHROPIC_API_KEY || "";

        if (document.getElementById("hf_token"))
            document.getElementById("hf_token").value = config.HF_TOKEN || "";

        if (document.getElementById("fal_key"))
            document.getElementById("fal_key").value = config.FAL_KEY || "";

        if (document.getElementById("replicate_api_token"))
            document.getElementById("replicate_api_token").value = config.REPLICATE_API_TOKEN || "";

    }
    catch (err) {

        console.error("Erro ao carregar definições:", err);
        alert(err.message);

    }

}


async function saveSettings() {

    // Mapeia todos os campos do painel de definições para as chaves
    // esperadas pelo backend (CONFIG_KEYS em app.py). Só inclui um campo
    // se o elemento existir de facto no HTML, para não sobrescrever
    // valores de secções que não estejam presentes na página.
    const FIELD_MAP = {
        llm_provider: "LLM_PROVIDER",
        model_name: "MODEL_NAME",

        image_provider: "IMAGE_PROVIDER",
        image_model: "IMAGE_MODEL",

        video_provider: "VIDEO_PROVIDER",
        video_model: "VIDEO_MODEL",

        ocr_enabled: "OCR_ENABLED",
        ocr_language: "OCR_LANGUAGE",

        email_host: "EMAIL_HOST",
        email_port: "EMAIL_PORT",
        email_user: "EMAIL_USERNAME",
        email_password: "EMAIL_PASSWORD",

        smtp_host: "SMTP_HOST",
        smtp_port: "SMTP_PORT",
        smtp_user: "SMTP_USERNAME",
        smtp_password: "SMTP_PASSWORD",

        openai_api_key: "OPENAI_API_KEY",
        anthropic_api_key: "ANTHROPIC_API_KEY",
        hf_token: "HF_TOKEN",
        fal_key: "FAL_KEY",
        replicate_api_token: "REPLICATE_API_TOKEN",
    };

    const settings = {};

    for (const [elementId, configKey] of Object.entries(FIELD_MAP)) {
        const el = document.getElementById(elementId);
        if (el) {
            settings[configKey] = el.value;
        }
    }

    try {

        const response = await fetch("/update-config", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(settings)

        });

        const result = await response.json();

        if (!response.ok)
            throw new Error(result.message);

        alert(result.message);

        const panel = document.getElementById("settings-panel");

        if (panel)
            panel.classList.remove("show");

    }
    catch (err) {

        console.error(err);

        alert(err.message);

    }

}

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

function addCopyButton(messageEl, text) {

    const btn = document.createElement("button");
    btn.className = "msg-copy";
    btn.innerHTML = "📋";
    btn.title = "Copiar resposta";

    btn.onclick = async (e) => {

        e.stopPropagation();

        try {

            await navigator.clipboard.writeText(text);

            btn.innerHTML = "✅";

            setTimeout(() => {
                btn.innerHTML = "📋";
            }, 1500);

        } catch {

            btn.innerHTML = "❌";

            setTimeout(() => {
                btn.innerHTML = "📋";
            }, 1500);

        }

    };

    messageEl.appendChild(btn);

}

function addMessage(text, role) {
  removeEmptyState();
  const div = document.createElement('div');
  div.className = `msg msg--${role}`;
  div.textContent = text;
  if (role === 'assistant') {
    addReplyButton(div, text);
    addCopyButton(div, text);
  }
  chatMessagesEl.appendChild(wrapWithAvatar(div, role));
  scrollToBottom();
  return div;
}

function addUserMessageWithAttachments(text, attachments, quotedText) {
  removeEmptyState();
  const div = document.createElement('div');
  div.className = 'msg msg--user';

  if (quotedText) addQuoteToMessage(div, quotedText);

  if (attachments && attachments.length) {
    const grid = document.createElement('div');
    grid.className = 'msg__attachments';
    attachments.forEach((att) => {
      const isImage = (att.mime || '').startsWith('image/');
      if (isImage) {
        const img = document.createElement('img');
        img.src = att.dataUrl;
        grid.appendChild(img);
      } else {
        const chip = document.createElement('span');
        chip.className = 'msg__file-chip';
        chip.textContent = `📎 ${att.name}`;
        grid.appendChild(chip);
      }
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

function addVideoMessage(videoUrl) {
  removeEmptyState();
  const wrapper = document.createElement('div');
  wrapper.className = 'msg msg--assistant msg--video';

  const video = document.createElement('video');
  video.src = videoUrl;
  video.controls = true;
  video.autoplay = false;
  video.loop = true;
  video.className = 'msg__video';

  wrapper.appendChild(video);
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
    const isImage = (att.mime || '').startsWith('image/');
    thumb.className = isImage ? 'attachment-thumb' : 'attachment-thumb attachment-thumb--file';
    thumb.title = att.name;

    if (isImage) {
      const img = document.createElement('img');
      img.src = att.dataUrl;
      img.alt = att.name;
      thumb.appendChild(img);
    } else {
      const icon = document.createElement('span');
      icon.className = 'attachment-thumb__ext';
      icon.textContent = fileExtension(att.name) || '📄';

      const name = document.createElement('span');
      name.className = 'attachment-thumb__name';
      name.textContent = att.name;

      thumb.appendChild(icon);
      thumb.appendChild(name);
    }

    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'attachment-thumb__remove';
    removeBtn.textContent = '×';
    removeBtn.title = 'Remover';
    removeBtn.addEventListener('click', () => {
      pendingAttachments.splice(idx, 1);
      renderAttachmentsPreview();
    });

    thumb.appendChild(removeBtn);
    attachmentsPreviewEl.appendChild(thumb);
  });
}

attachBtn.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async (e) => {
  const files = Array.from(e.target.files || []);
  for (const file of files) {
    try {
      const dataUrl = await readFileAsDataURL(file);
      pendingAttachments.push({ name: file.name, dataUrl, mime: file.type || '' });
    } catch (err) {
      console.error('Erro a ler ficheiro', err);
    }
  }
  fileInput.value = '';
  renderAttachmentsPreview();
});

/* ---------------- Envio de mensagens ---------------- */

async function sendMessage(message, attachments, replyTo) {
  addUserMessageWithAttachments(message, attachments, replyTo);
  currentConversation.push({
    role: "user",
    text: message || "[Anexo]"
  });
  resetRelay();
  // O primeiro nó só acende quando soubermos (pela 1ª mensagem do servidor)
  // se este pedido vai pelo pipeline de texto, imagem ou anexos.

  sendBtn.disabled = true;
  inputEl.disabled = true;

  const progressEl = addProgressMessage(
    attachments.length ? '📎 A preparar os anexos...' : '🧭 Coordenador a analisar o pedido...'
  );

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, language: currentLanguage, attachments, session_id: sessionId, reply_to: replyTo || null }),
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
        } else if (payload.type === 'image_progress' || payload.type === 'video_progress' || payload.type === 'attachment_progress') {
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
        } else if (payload.type === 'video') {
          sessionId = payload.session_id;
          localStorage.setItem('crew_session_id', sessionId);

          progressEl.remove();

          addVideoMessage(payload.video_url);

          currentConversation.push({
            role: "assistant",
            text: "[Vídeo gerado]"
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
  const attachments = pendingAttachments.map((a) => ({ name: a.name, dataUrl: a.dataUrl, mime: a.mime }));

  if (!message && attachments.length === 0) return;

  const replyTo = replyingTo;

  inputEl.value = '';
  pendingAttachments = [];
  renderAttachmentsPreview();
  clearReplyTarget();

  sendMessage(message, attachments, replyTo);
  renderHistory();
});

document.addEventListener("DOMContentLoaded", () => {

    const buttons = document.querySelectorAll(".settings-tab-btn");
    const tabs = document.querySelectorAll(".settings-tab");

    buttons.forEach(button => {

        button.addEventListener("click", () => {

            // Remove ativo dos botões
            buttons.forEach(b => b.classList.remove("active"));

            // Esconde todas as tabs
            tabs.forEach(tab => tab.classList.remove("active"));

            // Ativa botão clicado
            button.classList.add("active");

            // Mostra a tab correspondente
            const target = document.getElementById(
                "tab-" + button.dataset.tab
            );

            if (target) {
                target.classList.add("active");
            }

        });

    });

});

loadLanguage(currentLanguage);
loadSettings();

languageFlag.src=
`/static/img/flags/${currentLanguage}.svg`;

languageCode.textContent=
currentLanguage.toUpperCase();