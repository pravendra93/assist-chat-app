/**
 * Support AI Chat Widget v2.0 - "The WOW Edition"
 */
(function () {
    const script = document.currentScript || (function () {
        const scripts = document.getElementsByTagName('script');
        for (let s of scripts) {
            if (s.src && s.src.includes('widget.js')) return s;
        }
        return document.querySelector('script[data-api-key]');
    })();

    if (!script) return;

    const apiKey = script.getAttribute('data-api-key');
    const apiUrl = script.getAttribute('data-api-url') || "http://localhost:8001";
    const apiBase = `${apiUrl.replace(/\/$/, '')}/v1/widget`;
    const staticBase = `${apiUrl.replace(/\/$/, '')}/static`;

    if (!apiKey) return;

    let config = null;
    let sessionId = null;
    try {
        sessionId = localStorage.getItem('asst_session_id');
    } catch (e) { }

    async function init() {
        try {
            const response = await fetch(`${apiBase}/config`, {
                headers: { 'ASST-API-KEY': apiKey }
            });
            if (!response.ok) throw new Error("Failed to load config");
            config = await response.json();

            applyBranding(config);

            if (document.body) render();
            else window.addEventListener('load', () => render());
        } catch (err) {
            console.error("Support AI Widget:", err);
            if (document.body) render(true);
            else window.addEventListener('load', () => render(true));
        }
    }

    function applyBranding(conf) {
        if (!conf || !conf.primary_color) return;

        const primary = conf.primary_color;
        const bg = conf.background_color || '#0f172a';
        const pattern = conf.pattern_type || 'none';

        let style = document.getElementById('asst-dynamic-branding');
        if (!style) {
            style = document.createElement('style');
            style.id = 'asst-dynamic-branding';
            document.head.appendChild(style);
        }

        const secondary = adjustColor(primary, -25);
        const patternCSS = generatePatternCSS(pattern, primary, bg);

        style.innerHTML = `
            #support-ai-widget-root {
                --primary: ${primary} !important;
                --primary-light: ${primary}33 !important; 
                --primary-gradient: linear-gradient(135deg, ${primary} 0%, ${secondary} 100%) !important;
                --bg-main: ${bg} !important;
            }
            #chat-pattern-bg {
                ${patternCSS}
            }
        `;
    }

    function generatePatternCSS(type, primary, bg) {
        // High-end CSS Patterns
        switch (type) {
            case 'waves':
                return `background: radial-gradient(circle at 50% 50%, ${primary}11 0%, transparent 60%), 
                            linear-gradient(180deg, transparent 0%, ${primary}05 100%);
                        background-size: 100% 100%;`;
            case 'mesh':
                return `background-color: ${bg};
                        background-image: 
                            radial-gradient(at 0% 0%, ${primary}22 0, transparent 50%), 
                            radial-gradient(at 50% 0%, ${primary}11 0, transparent 50%), 
                            radial-gradient(at 100% 0%, ${primary}22 0, transparent 50%);`;
            case 'dots':
                return `background-image: radial-gradient(${primary}33 1px, transparent 1px);
                        background-size: 20px 20px;`;
            case 'grid':
                return `background-image: linear-gradient(${primary}11 1px, transparent 1px), 
                                          linear-gradient(90deg, ${primary}11 1px, transparent 1px);
                        background-size: 30px 30px;`;
            default:
                return `background: transparent;`;
        }
    }

    function adjustColor(hex, percent) {
        try {
            var num = parseInt(hex.replace("#", ""), 16), amt = Math.round(2.55 * percent),
                R = (num >> 16) + amt, B = (num >> 8 & 0x00FF) + amt, G = (num & 0x0000FF) + amt;
            return "#" + (0x1000000 + (R < 255 ? R < 0 ? 0 : R : 255) * 0x10000 + (B < 255 ? B < 0 ? 0 : B : 255) * 0x100 + (G < 255 ? G < 0 ? 0 : G : 255)).toString(16).slice(1);
        } catch (e) { return hex; }
    }

    function render(isError = false) {
        const activeConfig = isError ? { primary_color: '#6366f1', chat_title: 'Support AI', welcome_message: 'Maintenance Mode', position: 'bottom-right' } : config;

        const container = document.createElement('div');
        container.id = 'support-ai-widget-root';
        document.body.appendChild(container);

        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `${staticBase}/widget.css?v=${Date.now()}`;
        document.head.appendChild(link);

        const wrapper = document.createElement('div');
        wrapper.id = 'widget-wrapper';
        wrapper.className = `pos-${activeConfig.position || 'bottom-right'}`;
        container.appendChild(wrapper);

        const bubble = document.createElement('div');
        bubble.id = 'chat-bubble';
        bubble.innerHTML = `<svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>`;
        wrapper.appendChild(bubble);

        const chatWindow = document.createElement('div');
        chatWindow.id = 'chat-window';
        chatWindow.style.display = 'none';
        chatWindow.classList.remove('open');
        chatWindow.innerHTML = `
            <div id="chat-pattern-bg"></div>
            <div id="chat-header">
                <div class="header-info">
                   <div class="bot-avatar">
                       <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
                   </div>
                   <div class="header-text">
                       <h3>${activeConfig.bot_name || activeConfig.chat_title || 'RAKRI AI'}</h3>
                       <p class="status"><span class="status-dot"></span>Active now</p>
                   </div>
                </div>
                <button id="close-chat">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            <div id="chat-messages">
                <div class="message bot">${activeConfig.welcome_message || 'Hello!'}</div>
            </div>
            ${isError ? '' : `
            <div id="quick-actions" style="display:flex; gap:8px; padding:0 24px 12px; overflow-x:auto; scrollbar-width:none; -ms-overflow-style:none;">
                ${(activeConfig.suggested_questions || []).map(q => `
                    <button class="quick-action" data-msg="${q.replace(/"/g, '&quot;')}" style="background:rgba(255,255,255,0.05); border:1px solid var(--border-glass); color:var(--text-main); padding:8px 16px; border-radius:12px; font-size:12px; white-space:nowrap; cursor:pointer; transition:all 0.2s;">${q}</button>
                `).join('')}
            </div>
            <div id="chat-input-container">
                <input type="text" id="chat-input" placeholder="Type a message...">
                <button id="send-chat">
                    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="3"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            </div>
            `}
            <div id="footer-branding">Powered by Raki Labs</div>
        `;
        wrapper.appendChild(chatWindow);

        // Core Element References
        const input = chatWindow.querySelector('#chat-input');
        const sendBtn = chatWindow.querySelector('#send-chat');
        const messagesContainer = chatWindow.querySelector('#chat-messages');
        const quickActions = chatWindow.querySelector('#quick-actions');
        let isProcessing = false;

        // Toggle Logic
        const toggleChat = () => {
            const isOpen = chatWindow.classList.contains('open');
            if (!isOpen) {
                chatWindow.style.display = 'flex';
                setTimeout(() => {
                    chatWindow.classList.add('open');
                    chatWindow.classList.add('entrance-anim');
                }, 10);
                setTimeout(() => {
                    chatWindow.classList.remove('entrance-anim');
                }, 2000);
            } else {
                chatWindow.classList.remove('open');
                setTimeout(() => chatWindow.style.display = 'none', 500);
            }
        };

        bubble.onclick = toggleChat;
        chatWindow.querySelector('#close-chat').onclick = toggleChat;

        // Messaging Core
        const sendMessage = async (overrideText = null) => {
            // Priority: overrideText (Quick Actions) > input.value (Manual Typing)
            const text = overrideText ? overrideText.trim() : (input ? input.value.trim() : "");
            console.log("Support AI: Attempting to send message:", text);

            if (!text || isProcessing) return;

            // Clear manual input only
            if (!overrideText && input) {
                input.value = '';
            }

            isProcessing = true;
            
            // UI: Only add manual message here (Quick Actions add immediately in their handler)
            if (!overrideText) {
                addMessage(text, 'user');
            }
            
            showLoading();

            if (quickActions) quickActions.style.display = 'none';

            let botMsgDiv = null;

            try {
                const payload = {
                    message: text,
                    session_id: (sessionId && sessionId !== 'undefined') ? sessionId : null
                };

                const response = await fetch(`${apiBase}/chat-stream`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json', 'ASST-API-KEY': apiKey },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) throw new Error("Stream failed");

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let accumulatedAnswer = "";

                hideLoading();
                botMsgDiv = addMessage("", 'bot');

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });

                    if (chunk.includes("[SESSION_ID:")) {
                        const match = chunk.match(/\[SESSION_ID:(.*?)\]/);
                        if (match) {
                            sessionId = match[1];
                            localStorage.setItem('asst_session_id', sessionId);
                            const cleanChunk = chunk.replace(/\[SESSION_ID:.*?\]/, '');
                            if (cleanChunk) {
                                accumulatedAnswer += cleanChunk;
                                botMsgDiv.textContent = accumulatedAnswer;
                            }
                            continue;
                        }
                    }

                    accumulatedAnswer += chunk;
                    botMsgDiv.textContent = accumulatedAnswer;

                    if (messagesContainer) {
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    }
                }
            } catch (err) {
                console.error("Support AI Error:", err);
                hideLoading();
                if (botMsgDiv) botMsgDiv.textContent = "Connection lost. Please try again.";
                else addMessage("Brain lag! Please try again.", 'bot');
            } finally {
                isProcessing = false;
                if (input) input.focus();
            }
        };

        // Attach Quick Actions
        if (quickActions) {
            quickActions.querySelectorAll('.quick-action').forEach(btn => {
                btn.onclick = (e) => {
                    e.preventDefault();
                    if (isProcessing) return;
                    
                    const msg = btn.getAttribute('data-msg');
                    console.log("Support AI: Quick Action Clicked ->", msg);
                    if (msg) {
                        addMessage(msg, 'user'); // Add immediately as per instructions
                        sendMessage(msg);
                    }
                };
            });
        }

        // Attach Input Events
        if (input) {
            input.onkeydown = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    sendMessage();
                }
            };
        }

        if (sendBtn) {
            sendBtn.onclick = (e) => {
                e.preventDefault();
                sendMessage();
            };
        }

        // Helper Functions
        function addMessage(text, type) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${type}`;
            msgDiv.innerHTML = formatMessage(text);

            if (messagesContainer) {
                messagesContainer.appendChild(msgDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }

            return msgDiv;
        }

        function formatMessage(text) {
            if (!text) return '';
            return text
                .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                .replace(/\n?\d+\.\s/g, '<br/><br/>• ')
                .replace(/\n/g, '<br/>')
                .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" style="color:#8b5cf6;">$1</a>');
        }

        function showLoading() {
            const loader = document.createElement('div');
            loader.id = 'asst-loader';
            loader.className = 'message bot loading';
            loader.innerHTML = '<span></span><span></span><span></span>';
            if (messagesContainer) {
                messagesContainer.appendChild(loader);
                messagesContainer.scrollTo({ top: messagesContainer.scrollHeight, behavior: 'smooth' });
            }
        }

        function hideLoading() {
            const loader = chatWindow.querySelector('#asst-loader');
            if (loader) loader.remove();
        }

        // Add Floating Particles
        for (let i = 0; i < 5; i++) {
            const p = document.createElement('div');
            p.className = 'asst-particle';
            p.style.width = Math.random() * 50 + 20 + 'px';
            p.style.height = p.style.width;
            p.style.top = Math.random() * 100 + '%';
            p.style.left = Math.random() * 100 + '%';
            p.style.animationDelay = Math.random() * 10 + 's';
            chatWindow.appendChild(p);
        }
    }

    init();
})();
