/**
 * Support AI Chat Widget
 */
(function () {
    const script = document.currentScript || (function() {
        const scripts = document.getElementsByTagName('script');
        for (let s of scripts) {
            if (s.src && s.src.includes('widget.js')) return s;
        }
        return document.querySelector('script[data-api-key]');
    })();

    if (!script) {
        console.error("Support AI Widget: Attribution failed.");
        return;
    }
    
    const apiKey = script.getAttribute('data-api-key');
    const apiUrl = script.getAttribute('data-api-url') || "http://localhost:8001";

    const apiBase = `${apiUrl.replace(/\/$/, '')}/v1/widget`;
    const staticBase = `${apiUrl.replace(/\/$/, '')}/static`;

    if (!apiKey) {
        console.error("Support AI Widget: Missing data-api-key attribute.");
        return;
    }

    let config = null;
    let sessionId = null;
    try {
        sessionId = localStorage.getItem('asst_session_id');
    } catch (e) {
        console.warn("Support AI Widget: LocalStorage inaccessible.", e);
    }

    async function init() {
        try {
            console.log("Support AI Widget: Initializing...");
            const response = await fetch(`${apiBase}/config`, {
                headers: { 'ASST-API-KEY': apiKey }
            });
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to load config");
            }
            config = await response.json();
            console.log("Support AI Widget: Config loaded", config);
            
            // Defend against premature rendering
            if (document.body) {
                render();
            } else {
                window.addEventListener('load', () => render());
            }
        } catch (err) {
            console.error("Support AI Widget: Initialization failed", err);
            if (document.body) {
                render(true);
            } else {
                window.addEventListener('load', () => render(true));
            }
        }
    }

    function render(isError = false) {
        // Default config for error state or initial load
        const defaultConfig = {
            primary_color: '#6366f1',
            chat_title: 'RaKri AI Assistant',
            welcome_message: 'Our systems are undergoing maintenance. Please reach out via email.',
            position: 'bottom-right'
        };
        const activeConfig = isError ? defaultConfig : config;

        // Cleanup existing
        const existing = document.getElementById('support-ai-widget-root');
        if (existing) existing.remove();

        const container = document.createElement('div');
        container.id = 'support-ai-widget-root';
        document.body.appendChild(container);

        // Inject styles
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `${staticBase}/widget.css`;
        document.head.appendChild(link);

        // Wrapper
        const wrapper = document.createElement('div');
        wrapper.id = 'widget-wrapper';
        wrapper.className = `pos-${activeConfig.position || 'bottom-right'}`;
        container.appendChild(wrapper);

        // Bubble Button
        const bubble = document.createElement('div');
        bubble.id = 'chat-bubble';
        bubble.innerHTML = `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`;
        wrapper.appendChild(bubble);

        // Chat Window
        const chatWindow = document.createElement('div');
        chatWindow.id = 'chat-window';
        chatWindow.className = 'hidden';
        
        chatWindow.innerHTML = `
            <div id="chat-header">
                <div class="header-info">
                   <div class="bot-avatar">
                       <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2zm0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8z"/><path d="M12 6v6l4 2"/></svg>
                   </div>
                   <div class="header-text">
                       <h3>RaKri AI Assistant</h3>
                       <p class="status">${isError ? 'Maintenance' : '<span class="status-dot"></span>Active now'}</p>
                   </div>
                </div>
                <button id="close-chat">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            <div id="chat-messages">
                <div class="message bot">${activeConfig.welcome_message || 'Hello! How can I assist you today?'}</div>
            </div>
            ${isError ? '' : `
            <div id="quick-actions" style="display:flex; gap:8px; padding:0 24px 12px; overflow-x:auto;">
                <button class="quick-action" style="background:var(--bg-glass); border:1px solid var(--border-glass); color:var(--text-main); padding:6px 12px; border-radius:10px; font-size:11px; white-space:nowrap; cursor:pointer;">How it works?</button>
                <button class="quick-action" style="background:var(--bg-glass); border:1px solid var(--border-glass); color:var(--text-main); padding:6px 12px; border-radius:10px; font-size:11px; white-space:nowrap; cursor:pointer;">Pricing</button>
            </div>
            <div id="chat-input-container">
                <input type="text" id="chat-input" placeholder="Type a message...">
                <button id="send-chat">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            </div>
            `}
            <div id="footer-branding">Powered by Raki Labs</div>
        `;
        wrapper.appendChild(chatWindow);

        // Events
        const toggleChat = () => {
            const isHidden = chatWindow.classList.contains('hidden');
            if (isHidden) {
                chatWindow.style.display = 'flex';
                setTimeout(() => chatWindow.classList.remove('hidden'), 10);
            } else {
                chatWindow.classList.add('hidden');
                setTimeout(() => chatWindow.style.display = 'none', 400);
            }
        };

        bubble.onclick = toggleChat;
        container.querySelector('#close-chat').onclick = toggleChat;

        const input = container.querySelector('#chat-input');
        const sendBtn = container.querySelector('#send-chat');

        // Quick action handler
        container.querySelectorAll('.quick-action').forEach(btn => {
            btn.onclick = () => {
                if (input) {
                    input.value = btn.innerText;
                    sendMessage();
                }
            };
        });

        const sendMessage = async () => {
            const text = input.value.trim();
            if (!text) return;

            input.value = '';
            addMessage(text, 'user');
            showLoading();

            try {
                const res = await fetch(`${apiBase}/chat`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'ASST-API-KEY': apiKey
                    },
                    body: JSON.stringify({
                        query: text,
                        session_id: sessionId
                    })
                });
                const data = await res.json();
                hideLoading();

                sessionId = data.session_id;
                localStorage.setItem('asst_session_id', sessionId);
                addMessage(data.answer, 'bot');
            } catch (err) {
                console.error("Support AI:", err);
                hideLoading();
                addMessage("I'm having trouble connecting to my brain. Please try again.", 'bot');
            }
        };

        if (input && sendBtn) {
            input.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
            sendBtn.onclick = sendMessage;
        }

        function showLoading() {
            const loadingDiv = document.createElement('div');
            loadingDiv.id = 'typing-indicator';
            loadingDiv.className = 'message bot loading';
            loadingDiv.innerHTML = '<span></span><span></span><span></span>';
            container.querySelector('#chat-messages').appendChild(loadingDiv);
            loadingDiv.scrollIntoView({ behavior: 'smooth' });
            if (sendBtn) sendBtn.disabled = true;
        }

        function hideLoading() {
            const loadingDiv = container.querySelector('#typing-indicator');
            if (loadingDiv) loadingDiv.remove();
            if (sendBtn) sendBtn.disabled = false;
        }

        function addMessage(text, type) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${type}`;
            msgDiv.textContent = text;
            const messagesContainer = container.querySelector('#chat-messages');
            messagesContainer.appendChild(msgDiv);
            messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
        }
    }


    init();
})();
