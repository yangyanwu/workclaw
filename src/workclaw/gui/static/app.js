/**
 * WorkClaw — Chat Application JavaScript
 * Handles WebSocket communication, message rendering, and conversation management.
 */

(() => {
    'use strict';

    // --- Configuration ---
    const WS_URL = `ws://${window.location.host}/ws/chat`;
    const RECONNECT_DELAY = 3000;
    const MAX_RECONNECT_ATTEMPTS = 10;

    // --- State ---
    let ws = null;
    let reconnectAttempts = 0;
    let currentConversationId = null;
    let isProcessing = false;

    // --- DOM Elements ---
    const els = {
        app: document.getElementById('app'),
        sidebar: document.getElementById('sidebar'),
        conversationList: document.getElementById('conversation-list'),
        welcomeScreen: document.getElementById('welcome-screen'),
        messagesContainer: document.getElementById('messages-container'),
        messages: document.getElementById('messages'),
        messageInput: document.getElementById('message-input'),
        btnSend: document.getElementById('btn-send'),
        btnNewChat: document.getElementById('btn-new-chat'),
        btnToggleSidebar: document.getElementById('btn-toggle-sidebar'),
        modelIndicator: document.getElementById('model-indicator'),
    };

    // --- Initialize ---
    function init() {
        connectWebSocket();
        loadConversations();
        setupEventListeners();
        autoResizeTextarea();
    }

    // --- WebSocket ---
    function connectWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) return;

        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            reconnectAttempts = 0;
            updateStatus('Connected', true);
            console.log('[WS] Connected');
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            handleServerEvent(data);
        };

        ws.onclose = () => {
            updateStatus('Disconnected', false);
            console.log('[WS] Disconnected');
            scheduleReconnect();
        };

        ws.onerror = (err) => {
            console.error('[WS] Error:', err);
        };
    }

    function scheduleReconnect() {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            updateStatus('Connection failed', false);
            return;
        }
        reconnectAttempts++;
        setTimeout(connectWebSocket, RECONNECT_DELAY);
    }

    function sendMessage(message) {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            console.error('[WS] Not connected');
            return;
        }

        ws.send(JSON.stringify({
            action: 'chat',
            message: message,
            conversation_id: currentConversationId,
        }));
    }

    function sendAction(action, data = {}) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        ws.send(JSON.stringify({ action, ...data }));
    }

    // --- Server Event Handler ---
    function handleServerEvent(data) {
        switch (data.type) {
            case 'status':
                showThinking(data.message || 'Thinking...');
                break;

            case 'tool_call':
                removeThinking();
                addToolCall(data.tool, data.arguments);
                break;

            case 'tool_result':
                updateToolResult(data.tool, data.output);
                break;

            case 'response':
                removeThinking();
                addAssistantMessage(data.content);
                if (data.conversation_id) {
                    currentConversationId = data.conversation_id;
                }
                if (data.conversation_title) {
                    updateConversationTitle(data.conversation_id, data.conversation_title);
                }
                updateStatus(`${data.model || 'Ready'} · ${data.usage?.total_tokens || 0} tokens`, true);
                setProcessing(false);
                loadConversations();
                break;

            case 'error':
                removeThinking();
                addErrorMessage(data.message);
                setProcessing(false);
                break;

            case 'conversation_created':
                currentConversationId = data.conversation_id;
                clearMessages();
                showWelcome(false);
                loadConversations();
                break;

            case 'conversation_loaded':
                currentConversationId = data.conversation_id;
                clearMessages();
                showWelcome(false);
                if (data.history) {
                    data.history.forEach(msg => {
                        if (msg.role === 'user') addUserMessage(msg.content, false);
                        else if (msg.role === 'assistant') addAssistantMessage(msg.content, false);
                    });
                }
                scrollToBottom();
                loadConversations();
                break;
        }
    }

    // --- UI Rendering ---
    function addUserMessage(content, animate = true) {
        showWelcome(false);
        const msg = createMessageElement('user', content, animate);
        els.messages.appendChild(msg);
        scrollToBottom();
    }

    function addAssistantMessage(content, animate = true) {
        const msg = createMessageElement('assistant', content, animate);
        els.messages.appendChild(msg);
        // Highlight code blocks
        msg.querySelectorAll('pre code').forEach(block => {
            hljs.highlightElement(block);
        });
        scrollToBottom();
    }

    function addErrorMessage(content) {
        const msg = document.createElement('div');
        msg.className = 'message assistant';
        msg.innerHTML = `
            <div class="message-avatar">⚠️</div>
            <div class="message-body">
                <div class="message-sender">Error</div>
                <div class="message-content" style="color: var(--accent-error);">
                    ${escapeHtml(content)}
                </div>
            </div>
        `;
        els.messages.appendChild(msg);
        scrollToBottom();
    }

    function createMessageElement(role, content, animate = true) {
        const msg = document.createElement('div');
        msg.className = `message ${role}`;
        if (!animate) msg.style.animation = 'none';

        const avatar = role === 'user' ? '👤' : '🦞';
        const sender = role === 'user' ? 'You' : 'WorkClaw';
        const renderedContent = role === 'assistant'
            ? renderMarkdown(content)
            : escapeHtml(content);

        msg.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-body">
                <div class="message-sender">${sender}</div>
                <div class="message-content">${renderedContent}</div>
            </div>
        `;

        return msg;
    }

    function addToolCall(toolName, args) {
        const card = document.createElement('div');
        card.className = 'tool-call-card';
        card.id = `tool-${toolName}-${Date.now()}`;

        const argsStr = JSON.stringify(args, null, 2);

        card.innerHTML = `
            <div class="tool-call-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="tool-call-icon">🔧</span>
                <span class="tool-call-name">${escapeHtml(toolName)}</span>
                <span class="tool-call-toggle">▼</span>
            </div>
            <div class="tool-call-body">${escapeHtml(argsStr)}</div>
            <div class="tool-result" data-tool="${toolName}"></div>
        `;

        els.messages.appendChild(card);
        scrollToBottom();
    }

    function updateToolResult(toolName, output) {
        // Find the last tool result element for this tool
        const results = document.querySelectorAll(`.tool-result[data-tool="${toolName}"]`);
        if (results.length > 0) {
            const last = results[results.length - 1];
            last.textContent = output;
            last.style.display = 'block';
        }
    }

    function showThinking(message) {
        removeThinking();
        const indicator = document.createElement('div');
        indicator.className = 'thinking-indicator';
        indicator.id = 'thinking';
        indicator.innerHTML = `
            <div class="thinking-dots">
                <span></span><span></span><span></span>
            </div>
            <span>${escapeHtml(message)}</span>
        `;
        els.messages.appendChild(indicator);
        scrollToBottom();
    }

    function removeThinking() {
        const el = document.getElementById('thinking');
        if (el) el.remove();
    }

    function showWelcome(show) {
        els.welcomeScreen.classList.toggle('hidden', !show);
        els.messagesContainer.classList.toggle('active', !show);
    }

    function clearMessages() {
        els.messages.innerHTML = '';
    }

    // --- Conversations ---
    async function loadConversations() {
        try {
            const resp = await fetch('/api/conversations');
            const data = await resp.json();
            renderConversationList(data.conversations || []);
        } catch (err) {
            console.error('Failed to load conversations:', err);
        }
    }

    function renderConversationList(conversations) {
        els.conversationList.innerHTML = '';

        if (conversations.length === 0) {
            els.conversationList.innerHTML = `
                <div style="padding: 1rem; text-align: center; color: var(--text-muted); font-size: var(--text-xs);">
                    No conversations yet
                </div>
            `;
            return;
        }

        conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = `conversation-item${conv.id === currentConversationId ? ' active' : ''}`;
            item.innerHTML = `
                <span class="conv-icon">💬</span>
                <span class="conv-title">${escapeHtml(conv.title || 'Untitled')}</span>
            `;
            item.addEventListener('click', () => {
                sendAction('load_conversation', { conversation_id: conv.id });
            });
            els.conversationList.appendChild(item);
        });
    }

    function updateConversationTitle(convId, title) {
        // Update the active conversation in the sidebar
        const items = els.conversationList.querySelectorAll('.conversation-item');
        items.forEach(item => {
            const titleEl = item.querySelector('.conv-title');
            if (item.classList.contains('active') && titleEl) {
                titleEl.textContent = title;
            }
        });
    }

    // --- Utilities ---
    function renderMarkdown(text) {
        if (!text) return '';
        try {
            return marked.parse(text, {
                breaks: true,
                gfm: true,
            });
        } catch (e) {
            return escapeHtml(text);
        }
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function scrollToBottom() {
        requestAnimationFrame(() => {
            els.messagesContainer.scrollTop = els.messagesContainer.scrollHeight;
        });
    }

    function setProcessing(processing) {
        isProcessing = processing;
        els.btnSend.disabled = processing;
        els.messageInput.disabled = processing;
        if (!processing) {
            els.messageInput.focus();
        }
    }

    function updateStatus(text, connected) {
        const dot = els.modelIndicator.querySelector('.status-dot');
        const name = els.modelIndicator.querySelector('.model-name');
        dot.style.background = connected ? 'var(--accent-success)' : 'var(--accent-error)';
        dot.style.boxShadow = connected ? '0 0 6px var(--accent-success)' : '0 0 6px var(--accent-error)';
        name.textContent = text;
    }

    function autoResizeTextarea() {
        els.messageInput.addEventListener('input', () => {
            els.messageInput.style.height = 'auto';
            els.messageInput.style.height = Math.min(els.messageInput.scrollHeight, 200) + 'px';
        });
    }

    // --- Event Listeners ---
    function setupEventListeners() {
        // Send message
        els.btnSend.addEventListener('click', handleSend);

        els.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });

        // New chat
        els.btnNewChat.addEventListener('click', () => {
            sendAction('new_conversation');
            showWelcome(true);
        });

        // Toggle sidebar
        els.btnToggleSidebar.addEventListener('click', () => {
            els.sidebar.classList.toggle('collapsed');
        });

        // Welcome card clicks
        document.querySelectorAll('.welcome-card').forEach(card => {
            card.addEventListener('click', () => {
                const prompt = card.getAttribute('data-prompt');
                if (prompt) {
                    els.messageInput.value = prompt;
                    handleSend();
                }
            });
        });
    }

    function handleSend() {
        const message = els.messageInput.value.trim();
        if (!message || isProcessing) return;

        // Show in UI
        addUserMessage(message);

        // Send via WebSocket
        sendMessage(message);

        // Reset input
        els.messageInput.value = '';
        els.messageInput.style.height = 'auto';
        setProcessing(true);
    }

    // --- Start ---
    document.addEventListener('DOMContentLoaded', init);
})();
