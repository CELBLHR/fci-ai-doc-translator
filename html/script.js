const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const messageDiv = document.getElementById('message');
const selectedFileDiv = document.getElementById('selectedFile');
const loadingContainer = document.getElementById('loadingContainer');
const progressContainer = document.getElementById('progressContainer');

// 进度检查相关变量
let statusCheckInterval = null;
let isTranslating = false;

// 点击上传区域选择文件
dropZone.addEventListener('click', (e) => {
    // 防止点击已选择的文件名称或上传按钮时触发文件选择
    if (e.target === dropZone || e.target.tagName === 'P') {
        fileInput.click();
    }
});

// 处理拖拽事件
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        fileInput.files = files;
        validateFile(files[0]);
    }
});

// 文件选择处理
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    validateFile(file);
});

// 文件验证
function validateFile(file) {
    const validTypes = [
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation'
    ];

    if (!file) {
        showMessage('请选择文件', 'error');
        uploadBtn.disabled = true;
        selectedFileDiv.textContent = '';
        return;
    }

    if (!validTypes.includes(file.type)) {
        showMessage('只支持 PPT/PPTX 格式文件', 'error');
        uploadBtn.disabled = true;
        selectedFileDiv.textContent = '';
        return;
    }

    if (file.size > 50 * 1024 * 1024) {
        showMessage('文件大小不能超过 50MB', 'error');
        uploadBtn.disabled = true;
        selectedFileDiv.textContent = '';
        return;
    }

    selectedFileDiv.textContent = `已选择: ${file.name}`;
    showMessage('', ''); // 清除消息
    uploadBtn.disabled = false;
}

// 上传文件
uploadBtn.addEventListener('click', async () => {
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    uploadBtn.disabled = true;
    loadingContainer.classList.remove('hidden');
    progressContainer.classList.add('hidden');
    isTranslating = true;

    try {
        // 先上传文件启动翻译任务
        console.log('开始上传文件...');
        const uploadResponse = await fetch('http://127.0.0.1:5000/start_translation', {
            method: 'POST',
            body: formData
        });

        if (!uploadResponse.ok) {
            throw new Error('上传失败');
        }

        const uploadResult = await uploadResponse.json();
        const taskId = uploadResult.task_id;
        console.log('任务已创建，ID:', taskId);

        // 上传完成，开始检查翻译进度
        loadingContainer.classList.add('hidden');
        progressContainer.classList.remove('hidden');

        // 开始定期检查翻译状态
        startStatusCheck(taskId);

        // 等待翻译完成
        await waitForTranslationComplete(taskId, file.name);

    } catch (error) {
        console.error('翻译过程出错:', error);
        showMessage(error.message, 'error');
        stopStatusCheck();
    } finally {
        uploadBtn.disabled = false;
        loadingContainer.classList.add('hidden');
        progressContainer.classList.add('hidden');
        isTranslating = false;
    }
});

// 显示消息
function showMessage(text, type) {
    messageDiv.textContent = text;
    messageDiv.className = text ? `message ${type}` : '';
}

// 开始状态检查
function startStatusCheck(taskId) {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }

    // 存储当前任务ID
    window.currentTaskId = taskId;

    // 立即检查一次
    checkTaskStatus();

    // 每2秒检查一次状态（更频繁的更新）
    statusCheckInterval = setInterval(checkTaskStatus, 2000);
}

// 停止状态检查
function stopStatusCheck() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
    progressContainer.classList.add('hidden');
}

// 检查任务状态
async function checkTaskStatus() {
    if (!isTranslating || !window.currentTaskId) return;

    try {
        const response = await fetch(`http://127.0.0.1:5000/task_status/${window.currentTaskId}`);
        const data = await response.json();

        console.log('任务状态:', data);
        updateProgressDisplay(data);

    } catch (error) {
        console.error('检查状态失败:', error);
        // 如果状态检查失败，尝试使用通用状态接口
        try {
            const fallbackResponse = await fetch('http://127.0.0.1:5000/task_status');
            const fallbackData = await fallbackResponse.json();
            updateProgressDisplay(fallbackData);
        } catch (fallbackError) {
            console.error('备用状态检查也失败:', fallbackError);
        }
    }
}

// 更新进度显示
function updateProgressDisplay(data) {
    const currentSlideSpan = document.getElementById('currentSlide');
    const totalSlidesSpan = document.getElementById('totalSlides');
    const progressTextSpan = document.getElementById('progressText');
    const progressBarFill = document.getElementById('progressBarFill');
    const queueMessageSpan = document.getElementById('queueMessage');

    if (data.status === 'no_task') {
        // 没有任务，可能翻译已完成
        stopStatusCheck();
        return;
    }

    if (data.status === 'waiting') {
        // 排队中
        queueMessageSpan.textContent = `排队中，当前位置：第${data.position || 0}位`;
        currentSlideSpan.textContent = '0';
        totalSlidesSpan.textContent = '0';
        progressTextSpan.textContent = '0%';
        progressBarFill.style.width = '0%';
    } else if (data.status === 'processing') {
        // 翻译中
        const currentSlide = data.current_slide || 0;
        const totalSlides = data.total_slides || 0;
        const progress = data.progress || 0;

        queueMessageSpan.textContent = '正在翻译中...';
        // 修正：前端显示时+1，因为后端传递的是从0开始的索引
        currentSlideSpan.textContent = currentSlide + 1;
        totalSlidesSpan.textContent = totalSlides;
        progressTextSpan.textContent = `${progress}%`;
        progressBarFill.style.width = `${progress}%`;
    } else if (data.status === 'completed') {
        // 翻译完成
        queueMessageSpan.textContent = '翻译已完成！';
        currentSlideSpan.textContent = data.total_slides || 0;
        totalSlidesSpan.textContent = data.total_slides || 0;
        progressTextSpan.textContent = '100%';
        progressBarFill.style.width = '100%';

        // 延迟停止状态检查
        setTimeout(() => {
            stopStatusCheck();
            showMessage('翻译完成！', 'success');
        }, 2000);
    } else if (data.status === 'failed') {
        // 翻译失败
        queueMessageSpan.textContent = '翻译失败';
        stopStatusCheck();
        showMessage(data.error || '翻译失败，请重试', 'error');
    }
}

// 等待翻译完成
async function waitForTranslationComplete(taskId, fileName) {
    return new Promise((resolve, reject) => {
        const checkCompletion = async () => {
            try {
                const response = await fetch(`http://127.0.0.1:5000/task_status/${taskId}`);
                const data = await response.json();

                if (data.status === 'completed') {
                    // 翻译完成，下载文件
                    console.log('翻译完成，开始下载文件');

                    try {
                        const downloadResponse = await fetch(`http://127.0.0.1:5000/download/${taskId}`);
                        if (downloadResponse.ok) {
                            const blob = await downloadResponse.blob();
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `translated_${fileName}`;
                            a.style.display = 'none';
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            window.URL.revokeObjectURL(url);

                            showMessage('翻译完成！', 'success');
                            // 清除已选择的文件
                            fileInput.value = '';
                            selectedFileDiv.textContent = '';

                            stopStatusCheck();
                            resolve();
                        } else {
                            throw new Error('下载失败');
                        }
                    } catch (downloadError) {
                        console.error('下载文件失败:', downloadError);
                        showMessage('翻译完成但下载失败', 'error');
                        stopStatusCheck();
                        reject(downloadError);
                    }
                } else if (data.status === 'failed') {
                    // 翻译失败
                    const error = data.error || '翻译失败';
                    showMessage(error, 'error');
                    stopStatusCheck();
                    reject(new Error(error));
                }
                // 如果还在处理中，继续等待（由定时器处理）
            } catch (error) {
                console.error('检查完成状态失败:', error);
                // 不立即失败，继续等待
            }
        };

        // 立即检查一次
        checkCompletion();

        // 设置超时（10分钟）
        setTimeout(() => {
            stopStatusCheck();
            reject(new Error('翻译超时'));
        }, 10 * 60 * 1000);
    });
}

// 页面加载时检查是否有正在进行的任务
document.addEventListener('DOMContentLoaded', () => {
    // 不自动检查任务状态，避免干扰
    console.log('页面已加载');
});