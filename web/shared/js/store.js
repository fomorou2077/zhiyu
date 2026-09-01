/**
 * 知舆 ZhiYu - 用户状态管理
 */
const ZhiYuStore = {
  _state: {
    user: null,
    token: null,
    currentView: 'personal',  // personal | enterprise
  },

  init() {
    const token = localStorage.getItem('token');
    const userInfo = localStorage.getItem('user_info');
    if (token) {
      this._state.token = token;
      try { this._state.user = JSON.parse(userInfo); } catch(e) {}
    }
    // 读取当前展示版本
    const view = localStorage.getItem('current_view');
    if (view) this._state.currentView = view;

    // 自动从服务端拉取用户信息
    if (token) {
      this.fetchUserInfo();
    }
  },

  async fetchUserInfo() {
    try {
      const user = await ZhiYuAPI.get('/auth/me');
      this._state.user = user;
      this._state.currentView = user.user_type || 'personal';
      localStorage.setItem('user_info', JSON.stringify(user));
      localStorage.setItem('current_view', this._state.currentView);
    } catch(e) {
      console.log('获取用户信息失败:', e.message);
    }
  },

  get user() { return this._state.user; },
  get isLoggedIn() { return !!this._state.token; },
  get isEnterprise() { return this._state.currentView === 'enterprise'; },
  get currentView() { return this._state.currentView; },

  setToken(token, userInfo) {
    this._state.token = token;
    this._state.user = userInfo;
    localStorage.setItem('token', token);
    if (userInfo) {
      localStorage.setItem('user_info', JSON.stringify(userInfo));
      this._state.currentView = userInfo.user_type || 'personal';
    }
  },

  async switchVersion(targetType) {
    if (!this._state.token) return;
    try {
      const result = await ZhiYuAPI.post('/auth/switch-version', { user_type: targetType });
      this._state.currentView = result.user_type;
      localStorage.setItem('current_view', result.user_type);
      // 更新用户信息
      await this.fetchUserInfo();
      return result;
    } catch(e) {
      console.error('版本切换失败:', e);
      throw e;
    }
  },

  logout() {
    this._state.token = null;
    this._state.user = null;
    localStorage.removeItem('token');
    localStorage.removeItem('user_info');
    localStorage.removeItem('current_view');
  }
};
