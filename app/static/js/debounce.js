/**
 * 防抖动工具函数
 * 用于防止用户短时间内多次点击按钮导致重复提交请求
 */

/**
 * 防抖函数 - 确保函数在一定时间间隔内只执行一次
 * @param {Function} func - 要执行的函数
 * @param {number} wait - 等待时间(毫秒)
 * @returns {Function} - 返回防抖后的函数
 */
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const context = this;
        clearTimeout(timeout);
        timeout = setTimeout(() => {
            func.apply(context, args);
        }, wait);
    };
}

/**
 * 初始化带有防抖功能的按钮
 * 查找所有带有 data-debounce 属性的按钮并应用防抖
 */
function initDebouncedButtons() {
    const buttons = document.querySelectorAll('[data-debounce]');
    
    buttons.forEach(button => {
        const debounceTime = parseInt(button.getAttribute('data-debounce')) || 500;
        const originalClick = button.onclick;
        
        if (originalClick) {
            button.onclick = null;
            
            // 保存按钮的原始文本内容和加载中文本
            const originalText = button.innerHTML;
            const loadingText = button.getAttribute('data-loading-text') || '处理中...';
            
            button.addEventListener('click', debounce(function(e) {
                // 防止多次点击
                if (button.classList.contains('disabled')) {
                    return;
                }
                
                // 设置按钮为禁用状态
                button.classList.add('disabled');
                button.innerHTML = loadingText;
                
                // 执行原始点击事件
                try {
                    originalClick.call(this, e);
                } catch (error) {
                    console.error('按钮点击事件执行出错:', error);
                }
                
                // 延迟恢复按钮状态
                setTimeout(() => {
                    button.classList.remove('disabled');
                    button.innerHTML = originalText;
                }, Math.max(debounceTime, 1000)); // 至少禁用1秒
            }, debounceTime));
        }
    });
    
    // 处理 jQuery 和普通按钮点击事件
    $(document).on('click', '[data-debounce]', function(e) {
        const $btn = $(this);
        
        // 如果按钮已经被禁用，阻止点击
        if ($btn.hasClass('disabled') || $btn.prop('disabled')) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }
        
        // 获取防抖时间和加载文本
        const debounceTime = parseInt($btn.data('debounce')) || 500;
        const originalText = $btn.html();
        const loadingText = $btn.data('loading-text') || '处理中...';
        
        // 禁用按钮并更改文本
        $btn.addClass('disabled').prop('disabled', true).html(loadingText);
        
        // 设置定时器恢复按钮状态
        setTimeout(() => {
            $btn.removeClass('disabled').prop('disabled', false).html(originalText);
        }, Math.max(debounceTime, 1000));
    });
}

/**
 * 辅助函数：获取元素上的事件监听器
 * 注意：这是一个简化版本，无法获取使用addEventListener添加的匿名函数
 * 在实际使用中，我们可以使用jQuery的data存储或其他方法
 */
function getEventListeners(element, eventType) {
    // 在真实环境中，这个函数实现可能更复杂
    // 这里只是一个简化版本
    if (!element || !eventType) return [];
    
    // 这个函数在实际浏览器环境中无法正确工作
    // 仅作为示例
    return [];
}

/**
 * 为按钮添加防抖动功能
 * @param {HTMLElement} button - 按钮元素
 * @param {Function} clickHandler - 点击处理函数
 * @param {number} debounceTime - 防抖时间（毫秒）
 * @param {string} loadingText - 加载状态文本
 */
function addButtonDebounce(button, clickHandler, debounceTime = 1000, loadingText = null) {
    if (!button || !clickHandler) return;
    
    // 保存原始HTML
    const originalHTML = button.innerHTML;
    
    // 创建防抖动的点击处理函数
    const debouncedClickHandler = debounce(function(event) {
        // 禁用按钮
        button.disabled = true;
        button.classList.add('btn-disabled');
        
        // 如果有加载文本，显示加载状态
        if (loadingText) {
            button.classList.add('btn-loading');
            button.innerHTML = loadingText;
        }
        
        // 调用原始点击处理函数
        clickHandler.call(button, event);
        
        // 延迟后恢复按钮状态
        setTimeout(() => {
            button.disabled = false;
            button.classList.remove('btn-disabled');
            
            // 恢复原始文本
            if (loadingText) {
                button.classList.remove('btn-loading');
                button.innerHTML = originalHTML;
            }
        }, debounceTime);
    }, debounceTime);
    
    // 为按钮添加点击事件
    button.addEventListener('click', debouncedClickHandler);
}

// 在文档加载完成后初始化
$(document).ready(function() {
    initDebouncedButtons();
}); 