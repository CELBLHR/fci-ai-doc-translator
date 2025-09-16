// 显示提示消息的函数
function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = document.createElement('i');
    icon.className = type === 'success' ? 'bi bi-check-circle-fill' : 'bi bi-exclamation-circle-fill';

    toast.appendChild(icon);
    toast.appendChild(document.createTextNode(message));
    container.appendChild(toast);

    // 3秒后自动移除
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// 添加一个标志来防止重复调用
let completionPopupShown = false;
// 添加一个标志来记录是否已经显示过完成弹窗
// 使用localStorage来持久化存储这个标志
let completionPopupAlreadyShown = localStorage.getItem('completionPopupAlreadyShown') === 'true';

/*
 * 显示完成提示弹窗的函数
 * @param {string} message - 要显示的消息
 */
function showCompletionPopup(message) {
    // 如果弹窗已经显示过，直接返回
    if (completionPopupShown) {
        return;
    }

    try {
        // 设置标志，防止重复调用
        completionPopupShown = true;
        // 设置标志，记录已经显示过完成弹窗
        completionPopupAlreadyShown = true;
        // 使用localStorage来持久化存储这个标志
        localStorage.setItem('completionPopupAlreadyShown', 'true');

        // 先移除已存在的模态框，防止重复创建
        var existingModal = document.getElementById('completionModal');
        if (existingModal && existingModal.parentNode) {
            existingModal.parentNode.removeChild(existingModal);
        }

        // 创建模态框背景
        var modal = document.createElement('div');
        modal.id = 'completionModal';

        // 创建模态框内容
        var modalContent = document.createElement('div');

        // 添加消息文本
        var messageElement = document.createElement('p');
        messageElement.textContent = message;

        // 添加确认按钮
        var confirmButton = document.createElement('button');
        // 根据语言显示按钮文本（默认中文）
        try {
            var lang = (typeof currentLanguage !== 'undefined' && currentLanguage) ? currentLanguage : (document.documentElement.lang || 'zh');
            confirmButton.textContent = (lang === 'en') ? 'Noted' : '确定';
        } catch (e) {
            confirmButton.textContent = '确定';
        }

        // 点击确认按钮的处理函数
        confirmButton.onclick = function() {
            try {
                // 移除模态框
                if (modal && modal.parentNode) {
                    modal.parentNode.removeChild(modal);
                }
            } catch (e) {
                console.error('Error removing modal:', e);
            } finally {
                // 重置标志
                completionPopupShown = false;
                // 清除localStorage中的标志
                localStorage.removeItem('completionPopupAlreadyShown');
                // 停止轮询
                if (window.statusCheckInterval) {
                    clearInterval(window.statusCheckInterval);
                    window.statusCheckInterval = null;
                }
                // 重置翻译活动状态
                window.isTranslationActive = false;
                // 重新加载历史记录
                if (typeof loadHistory === 'function') {
                    loadHistory();
                }
                // 隐藏进度容器和队列状态
                const progressContainer = document.getElementById('progressContainer');
                const queueStatus = document.getElementById('queue-status');
                if (progressContainer) {
                    progressContainer.style.display = 'none';
                }
                if (queueStatus) {
                    queueStatus.style.display = 'none';
                }
            }
        };

        // 组装模态框
        modalContent.appendChild(messageElement);
        modalContent.appendChild(confirmButton);
        modal.appendChild(modalContent);
        document.body.appendChild(modal);

        // 设置样式 - 使用最简单的内联样式
        modal.style.cssText = 'position:fixed;left:0;top:0;width:100%;height:100%;background-color:rgba(0,0,0,0.5);display:flex;justify-content:center;align-items:center;z-index:2000';
        modalContent.style.cssText = 'background-color:white;padding:30px;border-radius:8px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,0.15);max-width:400px;width:90%';
        messageElement.style.cssText = 'margin-bottom:20px;font-size:16px;color:#6e6f72';
        confirmButton.style.cssText = 'background-color:#0094d9;color:white;border:none;padding:10px 20px;border-radius:6px;cursor:pointer;font-size:14px;font-weight:500';
    } catch (e) {
        console.error('Error creating completion popup:', e);
        // 重置标志
        completionPopupShown = false;
        completionPopupAlreadyShown = false;
        // 清除localStorage中的标志
        localStorage.removeItem('completionPopupAlreadyShown');
        // 停止轮询
        if (window.statusCheckInterval) {
            clearInterval(window.statusCheckInterval);
            window.statusCheckInterval = null;
        }
        // 重置翻译活动状态
        window.isTranslationActive = false;
        // 隐藏进度容器和队列状态
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

// 用户信息卡片切换
function toggleUserInfo() {
    const body = document.querySelector('.user-info-body');
    const toggle = document.querySelector('.user-info-toggle i');

    if (body.classList.contains('expanded')) {
        body.classList.remove('expanded');
        toggle.className = 'bi bi-chevron-up';
    } else {
        body.classList.add('expanded');
        toggle.className = 'bi bi-chevron-down';
    }
}

// 处理Flash消息
function processFlashMessages() {
    // 这个函数需要在页面加载完成后调用
    // 由于这是在外部JS文件中，我们需要通过其他方式传递消息
    // 这里留空，实际处理在页面内完成
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 如果需要在页面加载时执行某些操作，可以在这里添加
});
