// ====================== 公用提示 ======================
/**
 * 显示提示消息
 * @param {string} message
 * @param {'success'|'error'|'warning'|'info'} type
 */
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    if (!container) return; // 容器不存在则跳过，避免报错
  
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
  
    const icon = document.createElement('i');
    icon.className =
      type === 'success'
        ? 'bi bi-check-circle-fill'
        : type === 'warning'
        ? 'bi bi-exclamation-triangle-fill'
        : type === 'error'
        ? 'bi bi-x-circle-fill'
        : 'bi bi-info-circle-fill';
  
    toast.appendChild(icon);
    toast.appendChild(document.createTextNode(message));
    container.appendChild(toast);
  
    // 3秒后自动移除
    setTimeout(() => {
      toast.remove();
    }, 3000);
  }
  
  // ====================== 完成弹窗状态 ======================
  // 运行期“本页是否已弹过”标志（防快速重复触发）
  let completionPopupShown = false;
  // 持久化“本次任务是否已弹过”标志（跨刷新）
  let completionPopupAlreadyShown =
    localStorage.getItem('completionPopupAlreadyShown') === 'true';
  
  /**
   * 在“开始新的翻译任务”时调用，重置完成弹窗标志
   * 例如：用户点击“开始翻译”按钮后，或你确认进入了一个全新的任务队列
   */
  function resetCompletionPopupState() {
    completionPopupShown = false;
    completionPopupAlreadyShown = false;
    localStorage.removeItem('completionPopupAlreadyShown');
  }
  
  // ====================== 完成弹窗 ======================
  /**
   * 显示“翻译完成”的提示弹窗
   * @param {string} message - 显示的消息
   */
  function showCompletionPopup(message) {
    // 若当前页已弹过或持久化标志为已弹过，则不再弹
    if (completionPopupShown || completionPopupAlreadyShown) return;
  
    try {
      // 设置标志，防止重复创建
      completionPopupShown = true;
      completionPopupAlreadyShown = true;
      localStorage.setItem('completionPopupAlreadyShown', 'true');
  
      // 移除已存在的模态框，防止重复创建
      const existingModal = document.getElementById('completionModal');
      if (existingModal && existingModal.parentNode) {
        existingModal.parentNode.removeChild(existingModal);
      }
  
      // 创建模态框背景
      const modal = document.createElement('div');
      modal.id = 'completionModal';
  
      // 创建模态框内容
      const modalContent = document.createElement('div');
  
      // 添加消息文本
      const messageElement = document.createElement('p');
      messageElement.textContent = message;
  
      // 添加确认按钮
      const confirmButton = document.createElement('button');
      try {
        const lang =
          (typeof currentLanguage !== 'undefined' && currentLanguage) ||
          document.documentElement.lang ||
          'zh';
        confirmButton.textContent = lang === 'en' ? 'Noted' : '确定';
      } catch (e) {
        confirmButton.textContent = '确定';
      }
  
      // 点击确认按钮
      confirmButton.onclick = function () {
        try {
          if (modal && modal.parentNode) {
            modal.parentNode.removeChild(modal);
          }
        } catch (e) {
          console.error('Error removing modal:', e);
        } finally {
          // 注意：此处不清除 localStorage 标志！
          // 让刷新后仍然记得“已经显示过”，从而不再弹出
          completionPopupShown = false;
          // 刷新页面以显示翻译结果
          window.location.reload();
        }
      };
  
      // 组装并挂载
      modalContent.appendChild(messageElement);
      modalContent.appendChild(confirmButton);
      modal.appendChild(modalContent);
      document.body.appendChild(modal);
  
      // 最简样式
      modal.style.cssText =
        'position:fixed;left:0;top:0;width:100%;height:100%;background-color:rgba(0,0,0,0.5);display:flex;justify-content:center;align-items:center;z-index:2000';
      modalContent.style.cssText =
        'background-color:white;padding:30px;border-radius:8px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.15);max-width:400px;width:90%';
      messageElement.style.cssText =
        'margin-bottom:20px;font-size:16px;color:#6e6f72';
      confirmButton.style.cssText =
        'background-color:#0094d9;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:500';
    } catch (e) {
      console.error('Error creating completion popup:', e);
      // 兜底：恢复状态，避免把页面卡在“已显示过”的状态
      completionPopupShown = false;
      completionPopupAlreadyShown = false;
      localStorage.removeItem('completionPopupAlreadyShown');
  
      // 如果创建弹窗失败，不刷新页面，而是隐藏进度容器和队列状态
      const progressContainer = document.getElementById('progressContainer');
      const queueStatus = document.getElementById('queue-status');
      if (progressContainer) {
        progressContainer.style.display = 'none';
      }
      if (queueStatus) {
        queueStatus.style.display = 'none';
      }
      // 重新加载历史记录
      if (typeof loadHistory === 'function') {
        loadHistory();
      }
    }
  }
  
  // ====================== 其它已有功能 ======================
  /**
   * 用户信息卡片切换
   */
  function toggleUserInfo() {
    const body = document.querySelector('.user-info-body');
    const toggle = document.querySelector('.user-info-toggle i');
  
    if (!body || !toggle) return;
  
    if (body.classList.contains('expanded')) {
      body.classList.remove('expanded');
      toggle.className = 'bi bi-chevron-up';
    } else {
      body.classList.add('expanded');
      toggle.className = 'bi bi-chevron-down';
    }
  }
  
  /**
   * 处理Flash消息（占位）
   */
  function processFlashMessages() {
    // 这个函数需要在页面加载完成后调用
    // 由于这是在外部JS文件中，我们需要通过其他方式传递消息
    // 这里留空，实际处理在页面内完成
  }
  
  // 页面加载完成后执行（如需）
  document.addEventListener('DOMContentLoaded', function () {
    // 如果需要在页面加载时执行某些操作，可以在这里添加
    // 例如：根据条件显示toast、绑定按钮事件等
    // document.getElementById('startTranslate')?.addEventListener('click', resetCompletionPopupState);
  });
  
  // ====================== 使用说明（关键） ======================
  // 1) 任务真正完成时调用：showCompletionPopup('翻译完成');
  // 2) 用户点击“确定”后刷新页面，但因为 localStorage 保留标志，所以不会再次弹出。
  // 3) 当开始“新的翻译任务”时（业务入口处），务必调用：resetCompletionPopupState();
  