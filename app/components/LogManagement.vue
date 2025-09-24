<template>
  <div class="log-management">
    <h2 class="text-2xl font-bold mb-4">日志管理</h2>
    
    <!-- 日志查询表单 -->
    <div class="bg-white p-4 rounded-lg shadow mb-4">
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <!-- 日志记录器选择 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            日志记录器
          </label>
          <select
            v-model="queryParams.logger_name"
            class="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
            <option v-for="logger in loggers" :key="logger" :value="logger">
              {{ logger }}
            </option>
          </select>
        </div>
        
        <!-- 日志级别选择 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            日志级别
          </label>
          <select
            v-model="queryParams.level"
            class="w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
          >
            <option value="">全部</option>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>
        
        <!-- 时间范围选择 -->
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">
            时间范围
          </label>
          <div class="flex space-x-2">
            <input
              type="datetime-local"
              v-model="queryParams.start_time"
              class="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            />
            <input
              type="datetime-local"
              v-model="queryParams.end_time"
              class="flex-1 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
            />
          </div>
        </div>
      </div>
      
      <!-- 查询按钮 -->
      <div class="mt-4 flex justify-end space-x-2">
        <button
          @click="resetQuery"
          class="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
        >
          重置
        </button>
        <button
          @click="queryLogs"
          class="px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md hover:bg-indigo-700"
        >
          查询
        </button>
      </div>
    </div>
    
    <!-- 日志级别管理 -->
    <div v-if="queryParams.logger_name" class="bg-white p-4 rounded-lg shadow mb-4">
      <h3 class="text-lg font-medium mb-2">日志级别设置</h3>
      <div class="flex items-center space-x-4">
        <select
          v-model="levelUpdate.level"
          class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
        >
          <option value="DEBUG">DEBUG</option>
          <option value="INFO">INFO</option>
          <option value="WARNING">WARNING</option>
          <option value="ERROR">ERROR</option>
          <option value="CRITICAL">CRITICAL</option>
        </select>
        <select
          v-model="levelUpdate.handler_type"
          class="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
        >
          <option value="both">全部</option>
          <option value="console">控制台</option>
          <option value="file">文件</option>
        </select>
        <button
          @click="updateLogLevel"
          class="px-4 py-2 text-sm font-medium text-white bg-green-600 border border-transparent rounded-md hover:bg-green-700"
        >
          更新级别
        </button>
      </div>
    </div>
    
    <!-- 日志列表 -->
    <div class="bg-white rounded-lg shadow overflow-hidden">
      <div class="overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200">
          <thead class="bg-gray-50">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                时间
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                级别
              </th>
              <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                内容
              </th>
            </tr>
          </thead>
          <tbody class="bg-white divide-y divide-gray-200">
            <tr v-for="(log, index) in logs" :key="index">
              <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                {{ formatDateTime(log.timestamp) }}
              </td>
              <td class="px-6 py-4 whitespace-nowrap">
                <span
                  :class="{
                    'px-2 py-1 text-xs font-medium rounded-full': true,
                    'bg-gray-100 text-gray-800': log.content.includes('DEBUG'),
                    'bg-blue-100 text-blue-800': log.content.includes('INFO'),
                    'bg-yellow-100 text-yellow-800': log.content.includes('WARNING'),
                    'bg-red-100 text-red-800': log.content.includes('ERROR'),
                    'bg-purple-100 text-purple-800': log.content.includes('CRITICAL')
                  }"
                >
                  {{ getLogLevel(log.content) }}
                </span>
              </td>
              <td class="px-6 py-4 text-sm text-gray-500">
                {{ getLogMessage(log.content) }}
              </td>
            </tr>
            <tr v-if="logs.length === 0">
              <td colspan="3" class="px-6 py-4 text-center text-gray-500">
                暂无日志记录
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

export default {
  name: 'LogManagement',
  
  setup() {
    const loggers = ref([])
    const logs = ref([])
    const queryParams = ref({
      logger_name: '',
      level: '',
      start_time: '',
      end_time: '',
      limit: 100
    })
    const levelUpdate = ref({
      logger_name: '',
      level: 'INFO',
      handler_type: 'both'
    })
    
    // 获取日志记录器列表
    const fetchLoggers = async () => {
      try {
        const response = await axios.get('/api/logs/list')
        loggers.value = response.data
        if (loggers.value.length > 0) {
          queryParams.value.logger_name = loggers.value[0]
          levelUpdate.value.logger_name = loggers.value[0]
        }
      } catch (error) {
        ElMessage.error('获取日志记录器列表失败')
        console.error(error)
      }
    }
    
    // 查询日志
    const queryLogs = async () => {
      try {
        const response = await axios.post('/api/logs/query', queryParams.value)
        logs.value = response.data.logs
      } catch (error) {
        ElMessage.error('查询日志失败')
        console.error(error)
      }
    }
    
    // 更新日志级别
    const updateLogLevel = async () => {
      try {
        levelUpdate.value.logger_name = queryParams.value.logger_name
        await axios.post('/api/logs/level', levelUpdate.value)
        ElMessage.success('日志级别更新成功')
      } catch (error) {
        ElMessage.error('更新日志级别失败')
        console.error(error)
      }
    }
    
    // 重置查询条件
    const resetQuery = () => {
      queryParams.value.level = ''
      queryParams.value.start_time = ''
      queryParams.value.end_time = ''
      queryLogs()
    }
    
    // 格式化日期时间
    const formatDateTime = (timestamp) => {
      if (!timestamp) return ''
      const date = new Date(timestamp)
      // 添加8小时偏移来修正时区问题
      date.setHours(date.getHours() + 8)
      return date.toLocaleString()
    }
    
    // 获取日志级别
    const getLogLevel = (content) => {
      const match = content.match(/- (\w+) -/)
      return match ? match[1] : ''
    }
    
    // 获取日志消息
    const getLogMessage = (content) => {
      const match = content.match(/- \w+ - (.+)$/)
      return match ? match[1] : content
    }
    
    onMounted(() => {
      fetchLoggers()
    })
    
    return {
      loggers,
      logs,
      queryParams,
      levelUpdate,
      queryLogs,
      updateLogLevel,
      resetQuery,
      formatDateTime,
      getLogLevel,
      getLogMessage
    }
  }
}
</script>

<style scoped>
.log-management {
  @apply p-4;
}
</style> 