<script lang="ts">
  import { api, formatStockOutData, validateFormData, handleApiError } from '../lib/api.ts'

  // ========== 导出Props类型注解 ==========
  export let selectedItems: any[] = []
  export let batchLoading: boolean = false
  export let loading: boolean = false
  export let showMessage: (msg: string, type: string) => void = () => {}
  export let refreshInventory: () => Promise<void> | void = () => {}
  export let getRealTimeStock: ((inventoryId: number | string) => number) | null = null // 接收实时库存函数

  // ========== 接口定义 ==========
  /** 批量出库表单数据接口 */
  interface BatchStockOutForm {
    operator: string;
    remark: string;
    use_auto_out_time: boolean;
    out_time: string;
  }

  /** 验证状态接口 */
  interface ValidationState {
    isValid: boolean;
    message: string;
  }

  /** 性能监控接口 */
  interface PerformanceMetrics {
    batchProcessingTime: number;
    requestCount: number;
    successCount: number;
    errorCount: number;
    startTime: number;
  }

  /** 出库记录接口 */
  interface StockOutRecord {
    商品编号: string;
    商品名称: string;
    出库数量: number;
    楼层: string | number;
    架号: string;
    框号: string;
    包号: string;
    颜色: string;
    规格: string;
    类型: string;
    操作时间: string;
  }

  /** 出库请求项接口 */
  interface StockOutItem {
    inventory_id: number | string;
    out_quantity: number;
  }

  /** 批量出库请求数据接口 */
  interface StockOutRequestData {
    stock_out_items: StockOutItem[];
    operator: string;
    remark: string;
    out_time?: string;
  }

  // ========== 状态变量类型注解 ==========
  // 批量出库模态框状态
  let showBatchStockOutModal: boolean = false
  // 导出确认模态框状态
  let showExportConfirmModal: boolean = false

  // 批量出库表单数据
  let batchStockOutForm: BatchStockOutForm = {
    operator: '',
    remark: '',
    use_auto_out_time: true,
    out_time: ''
  }

  // 使用Map存储差异化数量，提高查找性能
  let batchStockOutQuantities: Map<number | string, number | string> = new Map()
  let validationStates: Map<number | string, ValidationState> = new Map()

  // 存储出库成功的记录（用于导出）
  let successfulStockOutRecords: StockOutRecord[] = []

  // 性能监控
  let performanceMetrics: PerformanceMetrics = {
    batchProcessingTime: 0,
    requestCount: 0,
    successCount: 0,
    errorCount: 0,
    startTime: 0
  }

  // 缓存仅存储后端返回的库存值，前端不修改
  let currentStockCache: Map<number | string, number> = new Map()

  // 防抖定时器
  let debounceTimer: NodeJS.Timeout | undefined

  // ========== 响应式变量类型注解 ==========
  $: batchButtonDisabled = batchLoading || loading || selectedItems.length === 0
  $: batchButtonTitle = selectedItems.length === 0 ? '请先选择要出库的商品' : `批量出库 ${selectedItems.length} 个商品`

  // ========== 核心函数类型注解 ==========
  // 【核心修改】仅读取库存值，无任何前端计算/修改
  function getCurrentStock(item: any): number {
    // 1. 优先使用实时库存函数获取后端计算后的最新库存
    if (getRealTimeStock) {
      const realTimeStock = getRealTimeStock(item.库存ID)
      currentStockCache.set(item.库存ID, realTimeStock)
      return realTimeStock
    }

    // 2. 有缓存直接返回（仅缓存后端/原始值）
    if (currentStockCache.has(item.库存ID)) {
      return currentStockCache.get(item.库存ID)!
    }

    // 3. 仅直接读取原始字段值，不做任何计算
    let stock = item.库存数量 || 0
    currentStockCache.set(item.库存ID, stock)
    return stock
  }

  // 【核心修改】仅清空缓存，触发重新获取后端最新库存，不做任何前端修改
  function updateStockCacheAfterStockOut(inventoryId: number | string): void {
    // 清空缓存，下次自动从后端获取最新值
    currentStockCache.delete(inventoryId)
    // 不再修改选中项的库存数值，由refreshInventory从后端重新拉取
  }

  // 获取库存状态
  function getInventoryStatus(item: any): string {
    return item.状态 || '未知'
  }

  // 打开批量出库模态框
  function openBatchStockOutModal(): void {
    if (selectedItems.length === 0) {
      showMessage('请先选择要出库的商品', 'warning')
      return
    }

    // 清空缓存，确保获取后端最新的库存值
    currentStockCache.clear()
    batchStockOutQuantities = new Map()
    validationStates = new Map()

    // 检查并过滤已出库的商品
    const invalidItemsSet = new Set(
      selectedItems
        .filter(item => getInventoryStatus(item) === '已出库')
        .map(item => item.库存ID)
    )

    if (invalidItemsSet.size > 0) {
      showMessage(`选中的 ${invalidItemsSet.size} 个商品已出库，无法再次出库`, 'error')
      selectedItems = selectedItems.filter(item => !invalidItemsSet.has(item.库存ID))
      return
    }

    // 批量初始化
    selectedItems.forEach(item => {
      batchStockOutQuantities.set(item.库存ID, '')
      validationStates.set(item.库存ID, { isValid: true, message: '' })
    })

    batchStockOutForm = {
      operator: '',
      remark: '',
      use_auto_out_time: true,
      out_time: ''
    }
    showBatchStockOutModal = true
  }

  // 关闭批量出库模态框
  function closeBatchStockOutModal(): void {
    showBatchStockOutModal = false
    batchStockOutForm = {
      operator: '',
      remark: '',
      use_auto_out_time: true,
      out_time: ''
    }
    batchStockOutQuantities.clear()
    validationStates.clear()
    currentStockCache.clear()
  }

  // 快速填充所有商品的出库数量（仅赋值，无计算）
  function quickFillAllQuantities(value: string | number): void {
    const numValue = Number(value)
    if (!numValue || numValue <= 0 || !Number.isInteger(numValue)) {
      return
    }

    const newQuantities = new Map(batchStockOutQuantities)
    selectedItems.forEach(item => {
      newQuantities.set(item.库存ID, numValue)
      updateValidationState(item.库存ID, numValue)
    })

    batchStockOutQuantities = newQuantities
  }

  // 【核心修改】验证数量输入 - 库存<0时允许出库数量大于库存
  function validateQuantityInput(value: string | number | null | undefined, item: any): ValidationState {
    if (value === '' || value == null) {
      return { isValid: false, message: '出库数量不能为空' }
    }

    const numValue = Number(value)
    if (isNaN(numValue)) {
      return { isValid: false, message: '出库数量必须是数字' }
    }

    if (!Number.isInteger(numValue)) {
      return { isValid: false, message: '出库数量必须是整数' }
    }

    if (numValue <= 0) {
      return { isValid: false, message: '出库数量必须大于0' }
    }

    // 仅使用后端返回的库存值做比较
    const currentStock = getCurrentStock(item)
    // 核心修改：只有库存≥0时才限制出库数量不超过库存，库存<0时允许超出
    if (currentStock >= 0 && numValue > currentStock) {
      return {
        isValid: false,
        message: `出库数量不能超过当前库存 (${currentStock})`
      }
    }

    // 库存为负数时给出友好提示（不影响验证通过）
    if (currentStock < 0) {
      return {
        isValid: true,
        message: `当前库存为负数 (${currentStock})，允许出库数量大于库存`
      }
    }

    return { isValid: true, message: '' }
  }

  // 更新验证状态（仅校验，无计算）
  function updateValidationState(itemId: number | string, value: string | number | null | undefined): void {
    const item = selectedItems.find(item => item.库存ID === itemId)
    if (!item) return

    validationStates.set(itemId, validateQuantityInput(value, item))
  }

  // 处理数量输入变化（防抖优化，无计算）
  function handleQuantityChange(itemId: number | string, value: string | number): void {
    batchStockOutQuantities.set(itemId, value)

    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      updateValidationState(itemId, value)
    }, 300)
  }

  // 验证批量出库数据
  function validateBatchStockOut(): boolean {
    try {
      // 验证操作人员
      validateFormData(batchStockOutForm, ['operator'])

      let hasError = false
      const errorMessages: string[] = []

      selectedItems.forEach(item => {
        const quantity = batchStockOutQuantities.get(item.库存ID)
        const validation = validateQuantityInput(quantity, item)

        if (!validation.isValid) {
          errorMessages.push(`商品 ${item.商品信息?.货号 || item.库存ID}: ${validation.message}`)
          hasError = true
        }
      })

      if (hasError) {
        throw new Error(errorMessages.slice(0, 3).join('；') + (errorMessages.length > 3 ? '...' : ''))
      }

      return true
    } catch (error) {
      showMessage((error as Error).message, 'error')
      return false
    }
  }

  // 准备批量出库请求数据 - 仅组装参数，无库存计算
  function prepareBatchStockOutData(): StockOutRequestData {
    const stockOutItems = selectedItems.map(item => ({
      inventory_id: item.库存ID,
      out_quantity: parseInt(batchStockOutQuantities.get(item.库存ID) as string)
    }))

    const requestData: StockOutRequestData = {
      stock_out_items: stockOutItems,
      operator: batchStockOutForm.operator,
      remark: batchStockOutForm.remark
    }

    // 处理出库时间
    if (!batchStockOutForm.use_auto_out_time && batchStockOutForm.out_time) {
      const date = new Date(batchStockOutForm.out_time)
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      requestData.out_time = `${year}-${month}-${day} ${hours}:${minutes}`
    }

    return requestData
  }

  // 创建出库记录（仅组装展示数据，无库存计算）
  function createStockOutRecord(item: any, quantity: number): StockOutRecord {
    const productInfo = item.商品信息 || {}
    const locationInfo = item.位置信息 || {}
    const featureInfo = item.特征信息 || {}

    return {
      商品编号: productInfo.货号 || productInfo.商品编号 || '',
      商品名称: productInfo.商品名称 || '',
      出库数量: quantity,
      楼层: locationInfo.楼层 || '',
      架号: locationInfo.架号 || '',
      框号: locationInfo.框号 || '',
      包号: locationInfo.包号 || '',
      颜色: featureInfo.颜色 || '',
      规格: featureInfo.规格 || '',
      类型: productInfo.类型 || '',
      操作时间: new Date().toLocaleString('zh-CN')
    }
  }

  // 显示批次处理结果
  function showBatchResult(successCount: number, errorCount: number, resultData: any): void {
    const total = successCount + errorCount
    let message = `批量出库完成，成功 ${successCount}/${total} 个商品`

    if (errorCount > 0) {
      message += `，失败 ${errorCount} 个`
    }

    if (performanceMetrics.batchProcessingTime > 0) {
      message += `，耗时 ${performanceMetrics.batchProcessingTime.toFixed(0)}ms`
    }

    showMessage(message, errorCount > 0 ? 'warning' : 'success')

    if (resultData?.error_details) {
      console.warn('批量出库错误详情:', resultData.error_details)
    }
  }

  // 使用新的批量出库接口（仅透传数据，无前端库存修改）
  async function handleBatchStockOut(): Promise<void> {
    if (!validateBatchStockOut()) return

    performanceMetrics.startTime = performance.now()
    batchLoading = true
    successfulStockOutRecords = []
    performanceMetrics = {
      ...performanceMetrics,
      requestCount: 1,
      successCount: 0,
      errorCount: 0
    }

    try {
      // 准备请求数据
      const requestData = prepareBatchStockOutData()
      console.log('批量出库请求数据:', requestData)

      // 调用批量出库接口
      const result = await api.batchStockOut(requestData)

      if (result.status === 'success' || result.status === 'partial_success') {
        const successCount = result.data.success_count
        const errorCount = result.data.error_count

        // 仅清空缓存，不修改前端库存值
        if (result.data.success_details) {
          result.data.success_details.forEach((detail: any) => {
            updateStockCacheAfterStockOut(detail.inventory_id)

            // 构建成功记录（仅展示用，无库存计算）
            const item = selectedItems.find(item => item.库存ID === detail.inventory_id)
            if (item) {
              successfulStockOutRecords.push(
                createStockOutRecord(item, detail.out_quantity)
              )
            }
          })
        } else {
          // 如果没有成功详情，仅清空缓存
          selectedItems.forEach(item => {
            const quantity = batchStockOutQuantities.get(item.库存ID)
            if (quantity && Number(quantity) > 0) {
              successfulStockOutRecords.push(createStockOutRecord(item, Number(quantity)))
              updateStockCacheAfterStockOut(item.库存ID)
            }
          })
        }

        performanceMetrics.successCount = successCount
        performanceMetrics.errorCount = errorCount

        // 显示性能统计
        performanceMetrics.batchProcessingTime = performance.now() - performanceMetrics.startTime
        showBatchResult(successCount, errorCount, result.data)

        // 如果有成功的记录，显示导出确认
        if (successfulStockOutRecords.length > 0) {
          showExportConfirmModal = true
        }

        closeBatchStockOutModal()
        // 触发从后端重新拉取库存数据
        await refreshInventory()
      } else {
        showMessage(result.message || '批量出库失败', 'error')
      }
    } catch (error) {
      console.error('批量出库错误:', error)
      showMessage(handleApiError(error, '批量出库请求失败'), 'error')
    } finally {
      batchLoading = false
    }
  }

  // 转换出库记录为CSV格式（仅展示，无库存计算）
  function convertStockOutToCSV(records: StockOutRecord[]): string {
    if (!records || records.length === 0) return ''

    const headers = [
      '商品编号', '商品名称', '类型', '出库数量', '规格', '颜色',
      '楼层', '架号', '框号', '包号', '操作时间'
    ]

    const csvContent = [
      headers.join(','),
      ...records.map(record => {
        const escapeValue = (value: any) => {
          if (value === undefined || value === null) return ''
          const strValue = String(value)
          if (strValue.includes(',') || strValue.includes('"') ||
              strValue.includes('\n') || strValue.includes('\r')) {
            return `"${strValue.replace(/"/g, '""')}"`
          }
          return strValue
        }

        return [
          escapeValue(record.商品编号 || ''),
          escapeValue(record.商品名称 || ''),
          escapeValue(record.类型 || ''),
          escapeValue(record.出库数量 || 0),
          escapeValue(record.规格 || ''),
          escapeValue(record.颜色 || ''),
          escapeValue(record.楼层 || ''),
          escapeValue(record.架号 || ''),
          escapeValue(record.框号 || ''),
          escapeValue(record.包号 || ''),
          escapeValue(record.操作时间 || '')
        ].join(',')
      })
    ].join('\n')

    return csvContent
  }

  // 下载出库记录CSV（仅导出数据，无库存计算）
  function downloadStockOutCSV(): void {
    if (successfulStockOutRecords.length === 0) {
      showMessage('没有可导出的出库记录', 'warning')
      showExportConfirmModal = false
      return
    }

    loading = true
    try {
      const csvContent = convertStockOutToCSV(successfulStockOutRecords)

      const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
      const timeStr = new Date().toTimeString().slice(0, 8).replace(/:/g, '')
      const filename = `出库记录_${timestamp}_${timeStr}_${successfulStockOutRecords.length}条.csv`

      downloadCSVFile(csvContent, filename)

      showMessage(`成功导出 ${successfulStockOutRecords.length} 条出库记录`, 'success')
    } catch (error) {
      console.error('导出出库记录失败:', error)
      showMessage(handleApiError(error, '导出出库记录失败'), 'error')
    } finally {
      loading = false
      showExportConfirmModal = false
      successfulStockOutRecords = []
    }
  }

  // 通用CSV下载函数
  function downloadCSVFile(csvContent: string, filename: string): void {
    const bom = new Uint8Array([0xEF, 0xBB, 0xBF])
    const blob = new Blob([bom, csvContent], { type: 'text/csv;charset=utf-8;' })

    if (navigator.msSaveBlob) {
      navigator.msSaveBlob(blob, filename)
    } else {
      const link = document.createElement('a')
      const url = URL.createObjectURL(blob)

      link.href = url
      link.download = filename
      link.style.display = 'none'

      document.body.appendChild(link)
      link.click()

      setTimeout(() => {
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
      }, 100)
    }
  }

  // 将选中数据转换为CSV格式（仅读取展示，无库存计算）
  function convertSelectedToCSV(data: any[]): string {
    if (!data || data.length === 0) return ''

    const headers = [
      '库存ID', '商品编号', '商品名称', '类型', '库存数量', '状态', '批次', '单位',
      '楼层', '架号', '框号', '包号', '地址类型',
      '单价', '重量', '规格', '材质', '颜色', '形状', '风格',
      '厂家', '厂家地址', '电话'
    ]

    const escapeCSVValue = (value: any) => {
      if (value === undefined || value === null) return ''

      let strValue = String(value)
      strValue = strValue.replace(/"/g, '""')

      if (strValue.includes(',') || strValue.includes('"') ||
          strValue.includes('\n') || strValue.includes('\r') || strValue.includes('\t')) {
        return `"${strValue}"`
      }

      return strValue
    }

    const csvRows = [headers.join(',')]

    data.forEach(item => {
      const productInfo = item.商品信息 || {}
      const locationInfo = item.位置信息 || {}
      const featureInfo = item.特征信息 || {}
      const manufacturerInfo = item.厂家信息 || {}

      const row = [
        escapeCSVValue(item.库存ID),
        escapeCSVValue(productInfo.货号 || ''),
        escapeCSVValue(productInfo.商品名称 || ''),
        escapeCSVValue(productInfo.类型 || ''),
        escapeCSVValue(getCurrentStock(item)), // 仅读取后端返回的库存值
        escapeCSVValue(item.状态 || ''),
        escapeCSVValue(item.批次 || ''),
        escapeCSVValue(item.单位 || ''),
        escapeCSVValue(locationInfo.楼层 || ''),
        escapeCSVValue(locationInfo.架号 || ''),
        escapeCSVValue(locationInfo.框号 || ''),
        escapeCSVValue(locationInfo.包号 || ''),
        escapeCSVValue(locationInfo.地址类型 || ''),
        escapeCSVValue(featureInfo.单价 || ''),
        escapeCSVValue(featureInfo.重量 || ''),
        escapeCSVValue(featureInfo.规格 || ''),
        escapeCSVValue(featureInfo.材质 || ''),
        escapeCSVValue(featureInfo.颜色 || ''),
        escapeCSVValue(featureInfo.形状 || ''),
        escapeCSVValue(featureInfo.风格 || ''),
        escapeCSVValue(manufacturerInfo.厂家 || ''),
        escapeCSVValue(manufacturerInfo.厂家地址 || ''),
        escapeCSVValue(manufacturerInfo.电话 || ''),
        escapeCSVValue(item.累计入库数量 || 0), // 仅展示，不计算
        escapeCSVValue(item.累计出库数量 || 0)  // 仅展示，不计算
      ]
      csvRows.push(row.join(','))
    })

    return csvRows.join('\n')
  }

  // 导出选中项目的CSV（仅导出展示数据，无库存修改）
  async function exportSelectedCSV(): Promise<void> {
    if (selectedItems.length === 0) {
      showMessage('请先选择要导出的商品', 'warning')
      return
    }

    loading = true
    try {
      console.log('开始导出选中项，选中数量：', selectedItems.length)

      const exportData = selectedItems.map(item => ({
        ...item,
        商品信息: item.商品信息 || {},
        位置信息: item.位置信息 || {},
        特征信息: item.特征信息 || {},
        厂家信息: item.厂家信息 || {}
      }))

      const csvContent = convertSelectedToCSV(exportData)

      if (!csvContent) {
        throw new Error('CSV内容生成失败，内容为空')
      }

      const timestamp = new Date().toISOString().slice(0, 10).replace(/-/g, '')
      const timeStr = new Date().toTimeString().slice(0, 8).replace(/:/g, '')
      const filename = `选中库存数据_${timestamp}_${timeStr}_${selectedItems.length}条.csv`

      downloadCSVFile(csvContent, filename)

      showMessage(`成功导出 ${selectedItems.length} 条记录`, 'success')
    } catch (error) {
      console.error('导出CSV失败:', error)
      showMessage(handleApiError(error, '导出失败'), 'error')
    } finally {
      loading = false
    }
  }
</script>
<div class="batch-operations">
  <!-- 批量操作按钮组 -->
  <div class="batch-buttons">
    {#if selectedItems.length > 0}
      <button
        class="btn-warning"
        on:click={openBatchStockOutModal}
        disabled={batchButtonDisabled}
        title={batchButtonTitle}
      >
        {batchLoading ? `处理中... (${performanceMetrics.successCount}/${selectedItems.length})` : `批量出库 (${selectedItems.length})`}
      </button>
      <button
        class="btn-secondary"
        on:click={exportSelectedCSV}
        disabled={loading}
        title="导出选中的商品"
      >
        {loading ? '导出中...' : `导出选中 (${selectedItems.length})`}
      </button>
      <span class="selected-count">已选择 {selectedItems.length} 项</span>

      <!-- 性能指标显示 -->
      {#if batchLoading && performanceMetrics.batchProcessingTime > 0}
        <span class="performance-indicator">
          已处理: {performanceMetrics.successCount}/{selectedItems.length} |
          耗时: {performanceMetrics.batchProcessingTime.toFixed(0)}ms
        </span>
      {/if}
    {:else}
      <button class="btn-warning disabled" disabled title={batchButtonTitle}>
        批量出库
      </button>
      <button class="btn-secondary disabled" disabled title="请先选择要导出的商品">
        导出选中
      </button>
    {/if}
  </div>

  <!-- 批量出库模态框 -->
  {#if showBatchStockOutModal}
  <div class="modal-overlay" on:click={closeBatchStockOutModal}>
    <div class="modal-content large-modal" on:click|stopPropagation>
      <div class="modal-header">
        <h2>批量出库 ({selectedItems.length} 项)</h2>
        <button class="modal-close" on:click={closeBatchStockOutModal}>×</button>
      </div>
      <div class="modal-body">
        <form on:submit|preventDefault={handleBatchStockOut}>
          <!-- 公共信息 -->
          <div class="form-section">
            <h3>公共信息</h3>
            <div class="form-row">
              <div class="form-group">
                <label for="batch_operator">操作人员 *</label>
                <input
                  id="batch_operator"
                  type="text"
                  bind:value={batchStockOutForm.operator}
                  placeholder="请输入操作人员姓名"
                  required
                />
              </div>
              <div class="form-group">
                <label for="batch_remark">备注</label>
                <input
                  id="batch_remark"
                  type="text"
                  bind:value={batchStockOutForm.remark}
                  placeholder="请输入备注信息"
                />
              </div>
            </div>

            <div class="form-group">
              <label class="checkbox-label">
                <input
                  type="checkbox"
                  bind:checked={batchStockOutForm.use_auto_out_time}
                />
                自动生成出库时间
              </label>
            </div>

            {#if !batchStockOutForm.use_auto_out_time}
              <div class="form-group">
                <label for="batch_out_time">出库时间 *</label>
                <input
                  id="batch_out_time"
                  type="datetime-local"
                  bind:value={batchStockOutForm.out_time}
                  required
                />
              </div>
            {/if}
          </div>

          <!-- 差异化出库数量设置 -->
          <div class="form-section">
            <div class="section-header">
              <h3>差异化出库数量设置</h3>
              <div class="quick-fill-section">
                <label>快速填充:</label>
                <input
                  type="number"
                  min="1"
                  step="1"
                  placeholder="统一数量"
                  class="quick-fill-input"
                  on:change={(e) => {
                    const value = e.target.value
                    if (value && Number(value) > 0 && Number.isInteger(Number(value))) {
                      quickFillAllQuantities(value)
                    }
                  }}
                />
                <button
                  type="button"
                  class="btn-quick-fill"
                  on:click={() => {
                    const input = document.querySelector('.quick-fill-input')
                    const value = input.value
                    if (value && Number(value) > 0 && Number.isInteger(Number(value))) {
                      quickFillAllQuantities(value)
                    } else {
                      showMessage('请输入有效的正整数', 'error')
                    }
                  }}
                >
                  应用所有
                </button>
              </div>
            </div>

            <!-- 商品列表 -->
            <div class="batch-quantities-table">
              <div class="table-header">
                <div class="row">
                  <div class="cell product-info">商品信息</div>
                  <div class="cell current-stock">当前库存</div>
                  <div class="cell status">状态</div>
                  <div class="cell out-quantity">出库数量 *</div>
                </div>
              </div>
              <div class="table-body">
                {#each selectedItems as item (item.库存ID)}
                  <div class="row">
                    <div class="cell product-info">
                      <div class="product-code">
                        {item.商品信息?.货号 || item.库存ID}
                      </div>
                      <div class="product-name">
                        {item.商品信息?.商品名称 || ''}
                      </div>
                      <div class="product-type">
                        {item.商品信息?.类型 || '未分类'}
                      </div>
                    </div>
                    <div class="cell current-stock">
                      {#key getCurrentStock(item) + item.库存ID}
                        <!-- 【核心修改】区分库存低和库存负数的样式 -->
                        <span
                          class:stock-low={getCurrentStock(item) < 10 && getCurrentStock(item) >= 0}
                          class:stock-negative={getCurrentStock(item) < 0}
                        >
                          {getCurrentStock(item)}
                        </span>
                      {/key}
                    </div>
                    <div class="cell status">
                      <span class:status-out={item.状态 === '已出库'}>
                        {item.状态 || '正常'}
                      </span>
                    </div>
                    <div class="cell out-quantity">
                      <input
                        type="number"
                        min="1"
                        step="1"

                        max={getCurrentStock(item) >= 0 ? getCurrentStock(item) : ''}
                        value={batchStockOutQuantities.get(item.库存ID) || ''}

                        placeholder={
                          getCurrentStock(item) >= 0
                            ? `最大 ${getCurrentStock(item)}`
                            : `当前库存为负数 (${getCurrentStock(item)})，可输入任意正整数`
                        }
                        class:quantity-error={!validationStates.get(item.库存ID)?.isValid && batchStockOutQuantities.get(item.库存ID)}
                        on:input={(e) => handleQuantityChange(item.库存ID, e.target.value)}
                      />
                      {#if validationStates.get(item.库存ID)?.message}
                        <div class:error-text={!validationStates.get(item.库存ID)?.isValid}
                             class:hint-text={validationStates.get(item.库存ID)?.isValid}>
                          {validationStates.get(item.库存ID).message}
                        </div>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            </div>
          </div>

          <div class="modal-actions">
            <button type="button" class="btn-outline" on:click={closeBatchStockOutModal}>取消</button>
            <button type="submit" class="btn-warning" disabled={batchLoading}>
              {batchLoading ? `处理中... (${performanceMetrics.successCount}/${selectedItems.length})` : '确认批量出库'}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
  {/if}

  <!-- 导出确认模态框 -->
  {#if showExportConfirmModal}
  <div class="modal-overlay" on:click={() => showExportConfirmModal = false}>
    <div class="modal-content" on:click|stopPropagation>
      <div class="modal-header">
        <h2>导出出库记录</h2>
        <button class="modal-close" on:click={() => showExportConfirmModal = false}>×</button>
      </div>
      <div class="modal-body">
        <div class="export-confirm-content">
          <p>批量出库已完成，共成功处理 <strong>{successfulStockOutRecords.length} 条</strong> 出库记录</p>
          <p>是否需要导出本次出库记录的CSV文件？</p>
          <div class="export-info">
            <h4>CSV文件将包含以下信息：</h4>
            <ul>
              <li>商品编号</li>
              <li>商品名称</li>
              <li>类型</li>
              <li>出库数量</li>
              <li>规格</li>
              <li>颜色</li>
              <li>楼层</li>
              <li>架号</li>
              <li>框号</li>
              <li>包号</li>
              <li>操作时间</li>
            </ul>
          </div>
        </div>
      </div>
      <div class="modal-actions" style="border-top: 1px solid #eee; padding: 15px 25px; margin: 0;">
        <button type="button" class="btn-outline" on:click={() => showExportConfirmModal = false} disabled={loading}>
          取消
        </button>
        <button type="button" class="btn-warning" on:click={downloadStockOutCSV} disabled={loading}>
          {loading ? '导出中...' : `导出 ${successfulStockOutRecords.length} 条记录`}
        </button>
      </div>
    </div>
  </div>
  {/if}
</div>

<style>
  .batch-operations {
    margin: 0;
  }

  .batch-buttons {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .selected-count {
    padding: 6px 12px;
    background: #e7f3ff;
    color: #0066cc;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 500;
  }

  .performance-indicator {
    padding: 4px 8px;
    background: #e8f5e8;
    color: #2d5016;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid #c8e6c9;
  }

  .btn-warning, .btn-secondary, .btn-outline {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
  }

  .btn-warning {
    background: #f39c12;
    color: white;
  }

  .btn-warning:hover:not(:disabled) {
    background: #e67e22;
    transform: translateY(-1px);
  }

  .btn-secondary {
    background: #95a5a6;
    color: white;
  }

  .btn-secondary:hover:not(:disabled) {
    background: #7f8c8d;
    transform: translateY(-1px);
  }

  .btn-outline {
    background: transparent;
    border: 2px solid #bdc3c7;
    color: #7f8c8d;
  }

  .btn-outline:hover:not(:disabled) {
    background: #f8f9fa;
    border-color: #95a5a6;
  }

  .btn-warning:disabled, .btn-secondary:disabled, .btn-outline:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  .btn-warning.disabled, .btn-secondary.disabled {
    background: #bdc3c7;
    color: #7f8c8d;
    cursor: not-allowed;
    opacity: 0.6;
  }

  .btn-warning.disabled:hover, .btn-secondary.disabled:hover {
    background: #bdc3c7;
    transform: none;
  }

  /* 模态框样式 */
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }

  .modal-content {
    background: white;
    border-radius: 10px;
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
  }

  .modal-content.large-modal {
    max-width: 800px;
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 25px;
    border-bottom: 1px solid #e0e0e0;
  }

  .modal-header h2 {
    margin: 0;
    color: #2c3e50;
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 24px;
    cursor: pointer;
    color: #7f8c8d;
    padding: 0;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .modal-close:hover {
    color: #e74c3c;
  }

  .modal-body {
    padding: 25px;
  }

  .form-section {
    margin-bottom: 30px;
  }

  .form-section h3 {
    margin: 0 0 15px 0;
    color: #34495e;
    font-size: 1.2rem;
    border-bottom: 1px solid #eee;
    padding-bottom: 8px;
  }

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 15px;
    margin-bottom: 15px;
  }

  .form-group {
    margin-bottom: 20px;
  }

  label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
    color: #555;
  }

  input, select {
    width: 100%;
    padding: 8px 12px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 14px;
    transition: border-color 0.3s ease;
  }

  input:focus, select:focus {
    outline: none;
    border-color: #3498db;
  }

  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
  }

  .checkbox-label input {
    width: auto;
  }

  /* 差异化数量表格样式 */
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
  }

  .quick-fill-section {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .quick-fill-input {
    width: 100px !important;
  }

  .btn-quick-fill {
    background: #28a745;
    color: white;
    border: none;
    padding: 6px 12px;
    border-radius: 4px;
    font-size: 12px;
    cursor: pointer;
    transition: background 0.3s ease;
  }

  .btn-quick-fill:hover {
    background: #218838;
  }

  .batch-quantities-table {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    overflow: hidden;
    max-height: 60vh;
    overflow-y: auto;
  }

  .table-header {
    background: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
  }

  .row {
    display: grid;
    grid-template-columns: 2fr 1fr 1fr 1.5fr;
    gap: 1px;
    background: #f8f9fa;
  }

  .row:not(:last-child) {
    border-bottom: 1px solid #e0e0e0;
  }

  .cell {
    padding: 12px;
    background: white;
    display: flex;
    align-items: center;
    min-height: 60px;
  }

  .table-body .row:nth-child(even) .cell {
    background: #fafbfc;
  }

  .product-info {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .product-code {
    font-weight: 500;
    color: #2c3e50;
  }

  .product-type {
    font-size: 12px;
    color: #7f8c8d;
  }

  .current-stock {
    justify-content: center;
    font-weight: 500;
  }

  /* 库存样式优化 */
  .stock-low {
    color: #fd7e14;
    font-weight: bold;
  }

  .stock-negative {
    color: #dc3545;
    font-weight: bold;
  }

  .out-quantity {
    flex-direction: column;
    align-items: stretch;
    gap: 5px;
  }

  .out-quantity input {
    padding: 6px;
    font-size: 13px;
  }

  .quantity-error {
    border-color: #e74c3c !important;
    background-color: #fdf2f2;
  }

  /* 错误和提示文本样式区分 */
  .error-text {
    color: #e74c3c;
    font-size: 11px;
  }

  .hint-text {
    color: #6c757d;
    font-size: 11px;
    font-style: italic;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 25px;
  }

  /* 导出确认模态框样式 */
  .export-confirm-content {
    line-height: 1.6;
    color: #333;
  }

  .export-confirm-content p {
    margin: 0 0 15px 0;
    font-size: 14px;
  }

  .export-confirm-content strong {
    color: #e67e22;
  }

  .export-info {
    background: #f8f9fa;
    border-radius: 8px;
    padding: 15px;
    margin-top: 20px;
  }

  .export-info h4 {
    margin: 0 0 10px 0;
    color: #2c3e50;
    font-size: 14px;
  }

  .export-info ul {
    margin: 0;
    padding-left: 20px;
    font-size: 13px;
    color: #555;
  }

  .export-info li {
    margin-bottom: 5px;
  }

  .export-info li:last-child {
    margin-bottom: 0;
  }

  .status-out {
    color: #e74c3c;
    font-weight: bold;
  }

  /* 响应式调整 */
  @media (max-width: 768px) {
    .batch-buttons {
      flex-direction: column;
      align-items: stretch;
    }

    .modal-content {
      width: 95%;
      margin: 20px;
    }

    .form-row {
      grid-template-columns: 1fr;
    }

    .section-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 10px;
    }

    .batch-quantities-table .row {
      grid-template-columns: 1fr;
    }

    .cell {
      min-height: 50px;
    }
  }
</style>