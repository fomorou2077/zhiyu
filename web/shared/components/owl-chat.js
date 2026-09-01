/**
 * 知舆 ZhiYu - 知知AI对话抽屉组件
 * 依赖: ZhiYuAPI, theme.css
 */
const OwlChat = {
  _visible: false,
  _messages: [],
  _loading: false,

  toggle() {
    if (this._visible) {
      this.hide();
    } else {
      this.show();
    }
  },

  show() {
    if (this._visible) return;
    this._visible = true;
    this._render();
  },

  hide() {
    this._visible = false;
    const drawer = document.getElementById('owl-chat-drawer');
    if (drawer) drawer.remove();
  },

  _addMessage(role, content) {
    this._messages.push({ role, content, time: new Date().toISOString() });
    const list = document.getElementById('owl-chat-messages');
    if (!list) return;
    const msgEl = document.createElement('div');
    msgEl.className = `msg-${role}`;
    msgEl.innerHTML = `
      <div class="msg-bubble">${this._escapeHtml(content)}</div>
    `;
    list.appendChild(msgEl);
    list.scrollTop = list.scrollHeight;
  },

  _escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  },

  async _send(message) {
    if (this._loading || !message.trim()) return;
    this._loading = true;
    this._addMessage('user', message);

    const input = document.getElementById('owl-chat-input');
    if (input) input.value = '';

    // 显示加载指示器
    const list = document.getElementById('owl-chat-messages');
    const loadingEl = document.createElement('div');
    loadingEl.className = 'msg-assistant';
    loadingEl.innerHTML = '<div class="msg-bubble pulse">🦉 知知正在思考...</div>';
    list.appendChild(loadingEl);
    list.scrollTop = list.scrollHeight;

    try {
      const resp = await ZhiYuAPI.post('/chat/', {
        message,
        history: this._messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
      });
      loadingEl.remove();
      this._addMessage('assistant', resp.reply || '（知知暂时无法回复，请稍后再试~）');
    } catch (err) {
      loadingEl.remove();
      this._addMessage('assistant', '🦉 抱歉，知知暂时无法连接，请检查网络后重试~');
    }
    this._loading = false;
  },

  _render() {
    const drawer = document.createElement('div');
    drawer.id = 'owl-chat-drawer';
    drawer.style.cssText = `
      position: fixed; right: 0; top: 0; bottom: 0; width: 380px; max-width: 95vw;
      background: var(--card-bg); border-left: 1px solid var(--card-border);
      backdrop-filter: blur(20px); z-index: 1100;
      display: flex; flex-direction: column;
      animation: slideIn 0.3s ease;
    `;
    drawer.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:16px 20px;border-bottom:1px solid var(--card-border);">
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="font-size:28px;">🦉</span>
          <div>
            <div style="font-weight:600;font-size:15px;">知知 AI助手</div>
            <div style="font-size:11px;color:var(--text-muted);">审辩思维 · 舆情洞察</div>
          </div>
        </div>
        <button id="owl-chat-close" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:20px;padding:4px;">&times;</button>
      </div>

      <div id="owl-chat-messages" style="flex:1;overflow-y:auto;padding:16px;">
        ${this._messages.length === 0 ? `
        <div style="text-align:center;color:var(--text-muted);padding:40px 20px;">
          <div style="font-size:48px;margin-bottom:12px;">🦉</div>
          <p>你好！我是知知，你的AI审辩助手。</p>
          <p style="font-size:13px;margin-top:8px;">我可以帮你分析舆情风险、识别逻辑谬误、提供创作建议~</p>
        </div>` : ''}
      </div>

      <div style="padding:12px 16px;border-top:1px solid var(--card-border);">
        <div style="display:flex;gap:8px;">
          <input id="owl-chat-input" type="text" placeholder="和知知聊聊..."
            style="flex:1;padding:10px 14px;font-size:14px;"
            autocomplete="off">
          <button id="owl-chat-send" class="btn-primary" style="padding:10px 16px;">
            <i class="fa-solid fa-paper-plane"></i>
          </button>
        </div>
        <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;">
          <button class="quick-btn" data-msg="帮我分析一下最近的舆情风险">📊 风险分析</button>
          <button class="quick-btn" data-msg="给我一些创作灵感">💡 创作灵感</button>
          <button class="quick-btn" data-msg="最近有什么热点事件？">🔥 热点速览</button>
        </div>
      </div>
    `;

    document.body.appendChild(drawer);

    // 事件绑定
    document.getElementById('owl-chat-close').addEventListener('click', () => this.hide());
    document.getElementById('owl-chat-send').addEventListener('click', () => {
      const input = document.getElementById('owl-chat-input');
      this._send(input.value);
    });
    document.getElementById('owl-chat-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const input = document.getElementById('owl-chat-input');
        this._send(input.value);
      }
    });

    // 快捷按钮
    drawer.querySelectorAll('.quick-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this._send(btn.dataset.msg);
      });
    });

    // 样式注入
    if (!document.getElementById('owl-chat-styles')) {
      const style = document.createElement('style');
      style.id = 'owl-chat-styles';
      style.textContent = `
        .msg-user { display: flex; justify-content: flex-end; margin-bottom: 12px; }
        .msg-assistant { display: flex; justify-content: flex-start; margin-bottom: 12px; }
        .msg-bubble {
          max-width: 80%; padding: 10px 16px; border-radius: 16px;
          font-size: 14px; line-height: 1.6; white-space: pre-wrap;
        }
        .msg-user .msg-bubble {
          background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
          color: #fff; border-bottom-right-radius: 4px;
        }
        .msg-assistant .msg-bubble {
          background: rgba(255,255,255,0.06);
          color: var(--text-main); border-bottom-left-radius: 4px;
        }
        .quick-btn {
          padding: 4px 12px; font-size: 12px; border-radius: 14px;
          background: rgba(255,255,255,0.04); color: var(--text-dim);
          border: 1px solid rgba(255,255,255,0.08); cursor: pointer;
          transition: var(--transition); white-space: nowrap;
        }
        .quick-btn:hover { background: rgba(0,242,255,0.1); color: var(--accent-cyan); border-color: var(--accent-cyan); }
        @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
      `;
      document.head.appendChild(style);
    }

    // 自动聚焦
    setTimeout(() => {
      const input = document.getElementById('owl-chat-input');
      if (input) input.focus();
    }, 200);
  }
};

// 全局快捷函数
function toggleOwlChat() { OwlChat.toggle(); }
