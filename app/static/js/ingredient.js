// 监听搜索输入框的回车事件
document.getElementById('searchInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        // 重置页码为第一页
        currentSearch.currentPage = 1;
        searchIngredient();
    }
});

// 搜索功能
function searchIngredient() {
    const searchInput = document.getElementById('searchInput');
    const dataSourceFilter = document.getElementById('dataSourceFilter');
    const searchTerm = searchInput.value.trim();
    const dataSource = dataSourceFilter.value;
    const resultsContainer = document.getElementById('searchResults');
    
    if (!searchTerm) {
        resultsContainer.innerHTML = '<p class="no-results">请输入要搜索的成分名称</p>';
        return;
    }

    // 显示加载状态
    resultsContainer.innerHTML = '<p class="loading">正在搜索...</p>';

    // 更新当前搜索状态
    currentSearch.keyword = searchTerm;
    currentSearch.dataSource = dataSource;

    // 构造查询参数
    const params = new URLSearchParams({
        keyword: searchTerm,
        data_source: dataSource,
        page: currentSearch.currentPage,
        per_page: 12  // 每页显示12个结果
    });

// 调用搜索API
    fetch(`/ingredient/api/ingredient/search?${params.toString()}`, {
        method: 'GET'
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            resultsContainer.innerHTML = `<p class="error">${data.message}</p>`;
            return;
        }
        displayResults(data.data, data.pagination);
    })
    .catch(error => {
        console.error('搜索出错:', error);
        resultsContainer.innerHTML = '<p class="error">搜索时发生错误，请稍后重试</p>';
    });
}

// 全局变量存储当前搜索状态
let currentSearch = {
    keyword: '',
    dataSource: 'all',
    currentPage: 1,
    totalPages: 1,
    totalResults: 0
};

// 显示搜索结果
function displayResults(data, pagination) {
    const resultsContainer = document.getElementById('searchResults');
    
    if (!data || data.length === 0) {
        resultsContainer.innerHTML = '<p class="no-results">未找到相关成分</p>';
        return;
    }

    // 更新当前搜索状态
    if (pagination) {
        currentSearch.currentPage = pagination.current_page;
        currentSearch.totalPages = pagination.total_pages;
        currentSearch.totalResults = pagination.total;
    }

    let html = `
        <div class="results-header">
            <p>找到 ${currentSearch.totalResults} 个结果</p>
        </div>
        <div class="results-grid">
    `;
    
    data.forEach(item => {
        // 根据数据源设置标签颜色
        let dataSourceTag = '';
        if (item.数据源) {
            const tagClass = item.数据源 === '注册' ? 'registration-tag' : 
                            item.数据源 === '备案' ? 'filing-tag' : 'unknown-tag';
            dataSourceTag = `<span class="data-source-tag ${tagClass}">${item.数据源}</span>`;
        }
        
        html += `
            <div class="result-card">
                <h3>${item.产品名称} ${dataSourceTag}</h3>
                <p><strong>主要成分：</strong>${item.主要成分}</p>
                ${item.截图路径 ? `
                <button class="download-btn" onclick="downloadFile('${item.截图路径}')">
                    <i class="bi bi-download"></i> 下载文件
                </button>` : ''}
            </div>
        `;
    });
    
    html += '</div>';
    
    // 添加分页控件
    if (currentSearch.totalPages > 1) {
        html += `
            <div class="pagination">
                <button class="pagination-btn" ${currentSearch.currentPage <= 1 ? 'disabled' : ''} 
                        onclick="goToPage(${currentSearch.currentPage - 1})">
                    <i class="bi bi-chevron-left"></i> 上一页
                </button>
                <span class="pagination-info">
                    第 ${currentSearch.currentPage} 页，共 ${currentSearch.totalPages} 页
                </span>
                <button class="pagination-btn" ${currentSearch.currentPage >= currentSearch.totalPages ? 'disabled' : ''} 
                        onclick="goToPage(${currentSearch.currentPage + 1})">
                    下一页 <i class="bi bi-chevron-right"></i>
                </button>
            </div>
        `;
    }

    resultsContainer.innerHTML = html;
}

// 跳转到指定页码
function goToPage(page) {
    if (page < 1 || page > currentSearch.totalPages || page === currentSearch.currentPage) {
        return;
    }
    
    currentSearch.currentPage = page;
    searchIngredient();
}

// 下载文件
function downloadFile(filePath) {
    // 处理文件路径，确保正确的URL编码
    const encodedPath = encodeURIComponent(filePath);
    
    // 使用正确的路径前缀
    fetch(`/ingredient/api/ingredient/download/${encodedPath}`, {
        method: 'GET'
    })
    .then(response => {
        if (response.ok) {
            return response.blob();
        }
        throw new Error('文件下载失败');
    })
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // 从路径中提取文件名
        const fileName = filePath.split(/[\\/]/).pop();
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
    })
    .catch(error => {
        console.error('下载出错:', error);
        // showToast('文件下载失败，请稍后重试', 'error');
        alert('文件下载失败，请稍后重试');
    });
}
