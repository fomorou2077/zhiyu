/**
 * 知舆 ZhiYu - 登录/注册模态框组件
 * 依赖: ZhiYuAPI, ZhiYuStore, theme.css
 */
const AuthModal = {
  _visible: false,

  show(mode = 'login') {
    if (this._visible) return;
    this._visible = true;
    this._render(mode);
  },

  hide() {
    this._visible = false;
    const overlay = document.getElementById('auth-modal-overlay');
    if (overlay) overlay.remove();
  },

  _render(mode) {
    const overlay = document.createElement('div');
    overlay.id = 'auth-modal-overlay';
    overlay.className = 'modal-overlay fade-in';
    overlay.innerHTML = `
      <div class="glass-card" style="width:420px;max-width:95vw;padding:32px;">
        <div style="text-align:center;margin-bottom:24px;">
          <div style="font-size:48px;margin-bottom:8px;">🦉</div>
          <h2 style="font-size:22px;">${mode === 'login' ? '欢迎回来' : '加入知舆'}</h2>
          <p class="text-dim" style="font-size:14px;">${mode === 'login' ? '登录你的知舆账号' : '创建账号，开启审辩思维之旅'}</p>
        </div>

        <form id="auth-form">
          ${mode === 'register' ? `
          <div class="form-group">
            <label>用户名</label>
            <input type="text" id="auth-username" placeholder="给自己起个名字" required>
          </div>` : ''}

          <div class="form-group">
            <label>邮箱 / 手机号</label>
            <input type="text" id="auth-identifier" placeholder="输入邮箱或11位手机号" required>
          </div>

          <div class="form-group">
            <label>密码</label>
            <input type="password" id="auth-password" placeholder="输入密码" required>
          </div>

          <div id="auth-error" style="color:var(--risk-high);font-size:13px;margin-bottom:12px;display:none;"></div>

          <button type="submit" class="btn-primary" style="width:100%;padding:14px;font-size:16px;">
            ${mode === 'login' ? '登 录' : '注 册'}
          </button>
        </form>

        <div style="text-align:center;margin-top:20px;font-size:13px;color:var(--text-dim);">
          ${mode === 'login'
            ? '还没有账号？<a href="#" id="auth-switch-register" style="color:var(--accent-cyan);">立即注册</a>'
            : '已有账号？<a href="#" id="auth-switch-login" style="color:var(--accent-cyan);">去登录</a>'}
        </div>

        <div style="text-align:center;margin-top:16px;font-size:12px;color:var(--text-muted);">
          Demo版本 · 个人版免费使用
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // 点击遮罩关闭
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) this.hide();
    });

    // 切换登录/注册
    const switchRegister = overlay.querySelector('#auth-switch-register');
    const switchLogin = overlay.querySelector('#auth-switch-login');
    if (switchRegister) switchRegister.addEventListener('click', (e) => { e.preventDefault(); this.hide(); this.show('register'); });
    if (switchLogin) switchLogin.addEventListener('click', (e) => { e.preventDefault(); this.hide(); this.show('login'); });

    // 表单提交
    const form = overlay.querySelector('#auth-form');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errorEl = overlay.querySelector('#auth-error');
      errorEl.style.display = 'none';

      const identifier = overlay.querySelector('#auth-identifier').value.trim();
      const password = overlay.querySelector('#auth-password').value.trim();

      if (!identifier || !password) {
        errorEl.textContent = '请填写所有必填项';
        errorEl.style.display = 'block';
        return;
      }

      try {
        let result;
        if (mode === 'login') {
          result = await ZhiYuAPI.post('/auth/login', { identifier, password });
        } else {
          const username = overlay.querySelector('#auth-username').value.trim();
          if (!username) {
            errorEl.textContent = '请输入用户名';
            errorEl.style.display = 'block';
            return;
          }
          const isEmail = identifier.includes('@');
          result = await ZhiYuAPI.post('/auth/register', {
            username,
            [isEmail ? 'email' : 'phone']: identifier,
            password,
          });
        }

        // 获取用户信息
        const userResp = await fetch(`${window.location.origin}/auth/me`, {
          headers: { 'Authorization': `Bearer ${result.access_token}` }
        });
        const userInfo = await userResp.json();

        ZhiYuStore.setToken(result.access_token, userInfo);
        this.hide();

        // 触发登录成功回调
        if (typeof onAuthSuccess === 'function') onAuthSuccess(userInfo);

        showToast('登录成功', 'success');
      } catch (err) {
        errorEl.textContent = err.message || '操作失败，请重试';
        errorEl.style.display = 'block';
      }
    });

    // 自动聚焦
    setTimeout(() => {
      const firstInput = overlay.querySelector('input');
      if (firstInput) firstInput.focus();
    }, 100);
  }
};

// 全局快捷函数
function showAuthModal(mode) { AuthModal.show(mode); }
function hideAuthModal() { AuthModal.hide(); }
