/**
 * 知舆 ZhiYu - 版本切换按钮组件
 * 依赖: ZhiYuAPI, ZhiYuStore
 * 在DEMO中允许用户在个人版/企业版UI之间即时切换
 */
const VersionSwitcher = {
  /**
   * 在给定容器中渲染版本切换按钮
   * @param {string|HTMLElement} container - 容器元素或选择器
   */
  render(container) {
    const el = typeof container === 'string'
      ? document.querySelector(container)
      : container;
    if (!el) return;

    const currentView = ZhiYuStore.currentView || 'personal';

    el.innerHTML = `
      <div class="version-switcher" id="version-switcher">
        <button data-version="personal" class="${currentView === 'personal' ? 'active' : ''}">
          🧠 个人版
        </button>
        <button data-version="enterprise" class="${currentView === 'enterprise' ? 'active' : ''}">
          🏢 企业版
        </button>
      </div>
    `;

    // 绑定点击事件
    const buttons = el.querySelectorAll('#version-switcher button');
    buttons.forEach(btn => {
      btn.addEventListener('click', async () => {
        const target = btn.dataset.version;
        if (target === ZhiYuStore.currentView) return;

        try {
          if (ZhiYuStore.isLoggedIn) {
            await ZhiYuStore.switchVersion(target);
            showToast(`已切换到${target === 'enterprise' ? '企业版' : '个人版'}`, 'info');
          } else {
            // 未登录时，仅在前端切换视图
            ZhiYuStore._state.currentView = target;
            localStorage.setItem('current_view', target);
            showToast(`已切换到${target === 'enterprise' ? '企业版' : '个人版'}预览`, 'info');
          }
          // 刷新当前页面导航
          if (typeof onVersionSwitch === 'function') {
            onVersionSwitch(target);
          } else {
            // 默认行为：跳转到对应页面
            window.location.href = target === 'enterprise' ? '/enterprise' : '/personal';
          }
        } catch (err) {
          showToast('版本切换失败: ' + err.message, 'error');
        }
      });
    });

    // 监听存储变更（跨标签页同步）
    window.addEventListener('storage', (e) => {
      if (e.key === 'current_view') {
        const newView = e.newValue;
        const btns = el.querySelectorAll('#version-switcher button');
        btns.forEach(b => {
          b.classList.toggle('active', b.dataset.version === newView);
        });
      }
    });
  },

  /**
   * 获取切换按钮的HTML字符串（用于直接插入模板）
   * @returns {string}
   */
  getHTML() {
    const currentView = localStorage.getItem('current_view') || 'personal';
    return `
      <div class="version-switcher" id="version-switcher">
        <button data-version="personal" class="${currentView === 'personal' ? 'active' : ''}"
                onclick="VersionSwitcher._handleClick('personal')">
          🧠 个人版
        </button>
        <button data-version="enterprise" class="${currentView === 'enterprise' ? 'active' : ''}"
                onclick="VersionSwitcher._handleClick('enterprise')">
          🏢 企业版
        </button>
      </div>
    `;
  },

  async _handleClick(target) {
    if (target === ZhiYuStore.currentView) return;

    try {
      if (ZhiYuStore.isLoggedIn) {
        await ZhiYuStore.switchVersion(target);
        showToast(`已切换到${target === 'enterprise' ? '企业版' : '个人版'}`, 'info');
      } else {
        ZhiYuStore._state.currentView = target;
        localStorage.setItem('current_view', target);
        showToast(`已切换到${target === 'enterprise' ? '企业版' : '个人版'}预览`, 'info');
      }
      if (typeof onVersionSwitch === 'function') {
        onVersionSwitch(target);
      } else {
        window.location.href = target === 'enterprise' ? '/enterprise' : '/personal';
      }
    } catch (err) {
      showToast('版本切换失败: ' + err.message, 'error');
    }
  }
};

// ========================================
// 通用 Toast 通知
// ========================================
function showToast(message, type = 'info') {
  // 确保容器存在
  let container = document.querySelector('.toast-container');
  if (!container) {
    container = document.createElement('div');
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type} fade-in`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(30px)';
    toast.style.transition = '0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ========================================
// 全局回调（页面可覆盖）
// ========================================
function onAuthSuccess(userInfo) {
  // 登录成功后默认刷新页面
  const currentView = userInfo.user_type || 'personal';
  if (window.location.pathname === '/' || window.location.pathname === '') {
    window.location.href = currentView === 'enterprise' ? '/enterprise' : '/personal';
  } else {
    window.location.reload();
  }
}

function onVersionSwitch(targetView) {
  window.location.href = targetView === 'enterprise' ? '/enterprise' : '/personal';
}
