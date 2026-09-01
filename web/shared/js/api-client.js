/**
 * 知舆 ZhiYu - 统一 API 客户端
 * 自动管理 token，处理认证错误
 */
const API_BASE = window.location.origin;

const ZhiYuAPI = {
  async request(path, options = {}) {
    const token = localStorage.getItem('token');
    const headers = { ...options.headers };

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // FormData 不设置 Content-Type，让浏览器自动处理
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const resp = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    // 处理认证错误
    if (resp.status === 401) {
      localStorage.removeItem('token');
      localStorage.removeItem('user_info');
      // 如果不在登录页则触发登录
      if (typeof showAuthModal === 'function') {
        showAuthModal();
      }
      throw new Error('登录已过期，请重新登录');
    }

    if (resp.status === 403) {
      throw new Error('无权限访问此功能');
    }

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: '请求失败' }));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }

    return resp;
  },

  async get(path) {
    const resp = await this.request(path);
    return resp.json();
  },

  async post(path, body) {
    const resp = await this.request(path, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
    });
    return resp.json();
  },

  async put(path, body) {
    const resp = await this.request(path, {
      method: 'PUT',
      body: JSON.stringify(body),
    });
    return resp.json();
  },

  async delete(path) {
    const resp = await this.request(path, { method: 'DELETE' });
    return resp.json();
  },

  // SSE 流式请求（报告生成用）
  async stream(path, body, onChunk, onDone, onError) {
    const token = localStorage.getItem('token');
    try {
      const resp = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            onChunk(line.slice(6));
          }
        }
      }
      onDone();
    } catch (e) {
      onError(e);
    }
  }
};
