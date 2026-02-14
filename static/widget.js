/**
 * Support AI Chat Widget
 */
(function () {
    const script = document.currentScript;
    const apiKey = script.getAttribute('data-api-key');
    const apiUrl = script.getAttribute('data-api-url') || "http://localhost:8001";

    const apiBase = `${apiUrl.replace(/\/$/, '')}/v1/widget`;
    const staticBase = `${apiUrl.replace(/\/$/, '')}/static`;

    if (!apiKey) {
        console.error("Support AI Widget: Missing data-api-key attribute.");
        return;
    }

    let config = null;
    let sessionId = localStorage.getItem('asst_session_id');

    async function init() {
        try {
            const response = await fetch(`${apiBase}/config`, {
                headers: { 'ASST-API-Key': apiKey }
            });
            if (!response.ok) throw new Error("Failed to load config");
            config = await response.json();
            render();
        } catch (err) {
            console.error("Support AI Widget:", err);
            render(true); // Render in error state
        }
    }

    function render(isError = false) {
        // Default config for error state or initial load
        const defaultConfig = {
            primary_color: '#0ea5e9',
            chat_title: 'Support',
            welcome_message: 'Customer service is currently unavailable. Please try again later.',
            position: 'bottom-right'
        };
        const activeConfig = isError ? defaultConfig : config;

        const container = document.createElement('div');
        container.id = 'support-ai-widget-root';
        document.body.appendChild(container);

        const shadow = container.attachShadow({ mode: 'open' });

        // Add CSS
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = `${staticBase}/widget.css`;
        shadow.appendChild(link);

        // Wrapper for positioning
        const wrapper = document.createElement('div');
        wrapper.id = 'widget-wrapper';
        wrapper.className = `pos-${activeConfig.position || 'bottom-right'}`;
        shadow.appendChild(wrapper);

        // Bubble Button
        const bubble = document.createElement('div');
        bubble.id = 'chat-bubble';
        bubble.innerHTML = '<span>💬</span>';
        bubble.style.backgroundColor = activeConfig.primary_color;
        wrapper.appendChild(bubble);

        // Chat Window
        const chatWindow = document.createElement('div');
        chatWindow.id = 'chat-window';
        chatWindow.className = 'hidden';
        if (!isError && activeConfig.background_color) {
            chatWindow.style.backgroundColor = activeConfig.background_color;
        }
        chatWindow.innerHTML = `
            <div id="chat-header" style="background-color: ${activeConfig.primary_color}">
                <div class="header-info">
                   <div class="bot-avatar">🤖</div>
                   <div class="header-text">
                       <h3>${activeConfig.chat_title}</h3>
                       <p class="status">${isError ? 'Offline' : '<span class="status-dot"></span>Online'}</p>
                   </div>
                </div>
                <button id="close-chat">×</button>
            </div>
            <div id="chat-messages">
                <div class="message bot">${activeConfig.welcome_message}</div>
            </div>
            ${isError ? '' : `
            <div id="chat-input-container">
                <input type="text" id="chat-input" placeholder="Type a message...">
                <button id="send-chat" style="background-color: ${activeConfig.primary_color}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="send-icon"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
                </button>
            </div>
            `}
            <div id="footer-branding">Powered by Support AI</div>
        `;
        wrapper.appendChild(chatWindow);

        // Events
        const toggleChat = () => {
            const isHidden = chatWindow.classList.contains('hidden');
            if (isHidden) {
                chatWindow.classList.remove('hidden', 'slide-down');
                chatWindow.classList.add('slide-up');
            } else {
                chatWindow.classList.remove('slide-up');
                chatWindow.classList.add('slide-down');
                setTimeout(() => {
                    if (chatWindow.classList.contains('slide-down')) {
                        chatWindow.classList.add('hidden');
                    }
                }, 300);
            }
        };

        bubble.onclick = toggleChat;
        shadow.getElementById('close-chat').onclick = toggleChat;

        const input = shadow.getElementById('chat-input');
        const sendBtn = shadow.getElementById('send-chat');

        if (input && sendBtn) {
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
                            'ASST-API-Key': apiKey
                        },
                        body: JSON.stringify({
                            message: text,
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
                    addMessage("Sorry, something went wrong.", 'bot');
                }
            };

            input.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
            sendBtn.onclick = sendMessage;
        }

        function showLoading() {
            const loadingDiv = document.createElement('div');
            loadingDiv.id = 'typing-indicator';
            loadingDiv.className = 'message bot loading';
            loadingDiv.innerHTML = '<span></span><span></span><span></span>';
            shadow.getElementById('chat-messages').appendChild(loadingDiv);
            loadingDiv.scrollIntoView();
            sendBtn.disabled = true;
            sendBtn.style.opacity = '0.5';
        }

        function hideLoading() {
            const loadingDiv = shadow.getElementById('typing-indicator');
            if (loadingDiv) loadingDiv.remove();
            sendBtn.disabled = false;
            sendBtn.style.opacity = '1';
        }

        function addMessage(text, type) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${type}`;
            msgDiv.textContent = text;
            shadow.getElementById('chat-messages').appendChild(msgDiv);
            msgDiv.scrollIntoView();
        }
    }

    init();
})();
