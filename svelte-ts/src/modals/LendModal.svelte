<script lang="ts">
  import { onMount } from 'svelte'

  // ========== 接口定义 ==========
  /** 验证状态接口 */
  interface ValidationState {
    isValid: boolean;
    message: string;
  }

  /** 借出表单数据接口 */
  interface LendForm {
    operator: string;
    remark: string;
    use_auto_out_time: boolean;
    out_time: string;
  }

  // ========== 导出Props类型注解 ==========
  export let show: boolean = false
  export let loading: boolean = false
  export let selectedItems: any[] = []
  export let showMessage: (msg: string, type: string) => void
  export let onClose: () => void
  export let onConfirm: (data: any) => void | Promise<void>
  export let getRealTimeStock: ((inventoryId: number | string) => number) | null = null

  // ========== 变量类型注解 ==========
  // 缓存计算结果
  let currentStockCache: Map<number | string, number> = new Map()

  // 替换Map为普通对象存储差异化数量（解决响应式渲染问题）
  let batchLendQuantities: Record<number | string, string | number> = {}
  let validationStates: Map<number | string, ValidationState> = new Map()

  // 表单数据
  let lendForm: LendForm = {
    operator: '',
    remark: '',
    use_auto_out_time: true,
    out_time: ''
  }

  // 快速填充输入框绑定值（替代DOM查询）
  let quickFillValue: string = ''

  // ========== 响应式变量先声明+类型注解，再赋值 ==========
  let inventoryIds: (number | string)[] = []
  let lendButtonDisabled: boolean = false
  let lendButtonTitle: string = ''

  // 响应式赋值（Svelte正确写法）
  $: inventoryIds = selectedItems.map(item => item.库存ID)
  $: lendButtonDisabled = loading || selectedItems.length === 0
  $: lendButtonTitle = selectedItems.length === 0 ? '请先选择要借出的商品' : `批量借出 ${selectedItems.length} 个商品`

  // ========== 核心函数类型注解 ==========
  // 【核心修复】导出本地库存更新函数（对齐出库逻辑）
  export function updateLocalStock(inventoryId: number | string, lendQuantity: number): void {
    if (getRealTimeStock) {
      // 清空缓存，下次重新获取实时库存
      currentStockCache.delete(inventoryId)
    } else {
      // 1. 更新缓存中的库存数量
      const currentStock = currentStockCache.get(inventoryId)
      if (currentStock !== undefined) {
        currentStockCache.set(inventoryId, currentStock - lendQuantity)
      }

      // 2. 关键：解构生成新对象，触发Svelte响应式
      const index = selectedItems.findIndex(item => item.库存ID === inventoryId)
      if (index > -1) {
        const item = selectedItems[index]
        selectedItems[index] = {
          ...item,
          当前库存数量: (item.当前库存数量 || getCurrentStock(item)) - lendQuantity,
          累计出库数量: (item.累计出库数量 || 0) + lendQuantity,
          状态: '已借出'
        }
      }
    }
  }

  // 获取当前库存数量（优化版）
  function getCurrentStock(item: any): number {
    if (getRealTimeStock) {
      const realTimeStock = getRealTimeStock(item.库存ID)
      currentStockCache.set(item.库存ID, realTimeStock)
      return realTimeStock
    }

    if (currentStockCache.has(item.库存ID)) {
      return currentStockCache.get(item.库存ID)!
    }

    let stock = item.当前库存数量 || item.库存数量 || 0
    if (!item.当前库存数量 && !item.库存数量) {
      const inQty = item.累计入库数量 || 0
      const outQty = item.累计出库数量 || 0
      stock = inQty - outQty
    }

    currentStockCache.set(item.库存ID, stock)
    return stock
  }

  // 监听show状态，初始化数据
  $: if (show) {
    // 清空缓存，确保获取最新数据
    currentStockCache.clear()
    batchLendQuantities = {} // 清空对象（替代Map.clear）
    validationStates = new Map()

    // 初始化每个商品的借出数量为1（对象赋值）
    selectedItems.forEach(item => {
      batchLendQuantities[item.库存ID] = '1' // 对象属性赋值
      validationStates.set(item.库存ID, { isValid: true, message: '' })
    })

    // 设置默认出库时间
    if (lendForm.use_auto_out_time) {
      const now = new Date()
      const year = now.getFullYear()
      const month = String(now.getMonth() + 1).padStart(2, '0')
      const day = String(now.getDate()).padStart(2, '0')
      const hour = String(now.getHours()).padStart(2, '0')
      const minute = String(now.getMinutes()).padStart(2, '0')
      lendForm.out_time = `${year}-${month}-${day} ${hour}:${minute}`
    }
  }

  // 智能格式化时间输入
  function formatTimeInput(e: Event): void {
    const target = e.target as HTMLInputElement
    let value = target.value.trim()
    value = value.replace('T', ' ').replace(/[^\d\-\:\s]/g, '')

    // 处理日期部分
    if (value.length >= 4 && !value.includes('-')) {
      value = `${value.slice(0, 4)}-${value.slice(4)}`
    }
    if (value.length >= 7 && value.slice(5, 7) !== '-') {
      value = `${value.slice(0, 7)}-${value.slice(7)}`
    }
    if (value.length >= 10 && !value.includes(' ')) {
      value = `${value.slice(0, 10)} ${value.slice(10)}`
    }
    if (value.includes(' ') && value.split(' ')[1].length >= 2 && !value.split(' ')[1].includes(':')) {
      const [datePart, timePart] = value.split(' ')
      value = `${datePart} ${timePart.slice(0, 2)}:${timePart.slice(2)}`
    }
    if (value.length > 19) {
      value = value.slice(0, 19)
    }

    // 小时/分钟范围校验
    if (value.includes(' ')) {
      const [datePart, timePart] = value.split(' ')
      if (timePart.includes(':')) {
        const [hh, mm, ss] = timePart.split(':')
        const hour = parseInt(hh)
        const minute = parseInt(mm || 0)
        const second = parseInt(ss || 0)

        if (!isNaN(hour) && hour > 23) value = `${datePart} 23:${mm}:${ss}`
        if (!isNaN(minute) && minute > 59) value = `${datePart} ${hh}:59:${ss}`
        if (!isNaN(second) && second > 59) value = `${datePart} ${hh}:${mm}:59`
      } else {
        const hour = parseInt(timePart)
        if (!isNaN(hour) && hour > 23) value = `${datePart} 23`
      }
    }

    lendForm.out_time = value
  }

  // 快速填充所有商品的借出数量（适配普通对象）
  function quickFillAllQuantities(value: string | number): void {
    const numValue = Number(value)
    if (!numValue || numValue <= 0 || !Number.isInteger(numValue)) {
      showMessage('请输入有效的正整数（如1、5、10）', 'error');
      return
    }

    console.log('选中商品数量：', selectedItems.length);
    console.log('选中商品详情：', selectedItems);

    // 复制原对象（避免直接修改，触发响应式）
    const newQuantities = { ...batchLendQuantities };
    selectedItems.forEach(item => {
      console.log('商品库存ID：', item.库存ID, '要填充的值：', numValue);
      newQuantities[item.库存ID] = numValue; // 对象赋值
      updateValidationState(item.库存ID, numValue);
    })

    console.log('填充后的数量对象：', newQuantities);
    batchLendQuantities = newQuantities; // 重新赋值触发响应式
    console.log('最终的batchLendQuantities：', batchLendQuantities);
  }

  // 【核心修改】验证数量输入 - 库存<0时允许借出数量大于库存
  function validateQuantityInput(value: string | number | null | undefined, item: any): ValidationState {
    // 输入过程中空值/未填写：暂时标记为有效，避免误提示
    if (value === '' || value == null || value === undefined) {
      return { isValid: true, message: '' }
    }

    const numValue = Number(value)
    if (isNaN(numValue)) {
      return { isValid: false, message: '借出数量必须是数字' }
    }

    if (!Number.isInteger(numValue)) {
      return { isValid: false, message: '借出数量必须是整数' }
    }

    if (numValue <= 0) {
      return { isValid: false, message: '借出数量必须大于0' }
    }

    const currentStock = getCurrentStock(item)
    // 核心修改：只有库存≥0时才限制借出数量不超过库存，库存<0时允许超出
    if (currentStock >= 0 && numValue > currentStock) {
      return {
        isValid: false,
        message: `借出数量不能超过当前库存 (${currentStock})`
      }
    }

    // 库存为负数时给出友好提示（不影响验证通过）
    if (currentStock < 0) {
      return {
        isValid: true,
        message: `当前库存为负数 (${currentStock})，允许借出数量大于库存`
      }
    }

    return { isValid: true, message: '' }
  }

  // 更新验证状态
  function updateValidationState(itemId: number | string, value: string | number | null | undefined): void {
    const item = selectedItems.find(item => item.库存ID === itemId)
    if (!item) return

    validationStates.set(itemId, validateQuantityInput(value, item))
  }

  // 处理数量输入变化（优化：去掉防抖，实时验证，解决手动输入空值提示问题）
  function handleQuantityChange(itemId: number | string, value: string | number): void {
    // 空值处理：输入框清空时赋值为空字符串，避免undefined
    const finalValue = value === '' ? '' : value
    // 实时更新数量（双向绑定已同步，这里兜底触发响应式）
    batchLendQuantities = {
      ...batchLendQuantities,
      [itemId]: finalValue
    }
    // 实时验证，不延迟
    updateValidationState(itemId, finalValue)
  }

  // 验证批量借出数据（优化：提交时强制检查空值）
  function validateBatchLend(): boolean {
    try {
      // 验证操作人员
      if (!lendForm.operator.trim()) {
        throw new Error('请填写操作人员')
      }

      // 验证时间格式
      if (!lendForm.use_auto_out_time && !lendForm.out_time.trim()) {
        throw new Error('请填写借出时间')
      }

      if (!lendForm.use_auto_out_time) {
        const timeRegex1 = /^\d{4}-\d{2}-\d{2} \d{2}$/
        const timeRegex2 = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/
        if (!timeRegex1.test(lendForm.out_time) && !timeRegex2.test(lendForm.out_time)) {
          throw new Error('时间格式错误，请使用：YYYY-MM-DD HH 或 YYYY-MM-DD HH:MM:SS')
        }
      }

      // 批量验证数量
      let hasError = false
      const errorMessages: string[] = []

      selectedItems.forEach(item => {
        const quantity = batchLendQuantities[item.库存ID]
        // 提交时强制验证空值（核心：解决手动输入空值提交问题）
        if (quantity === '' || quantity == null || quantity === undefined) {
          errorMessages.push(`商品 ${item.商品信息?.货号 || item.库存ID}: 借出数量不能为空`)
          hasError = true
          return // 跳过后续验证
        }
        // 原有数值验证
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

  // 准备批量借出请求数据（适配对象）
  function prepareBatchLendData(): any {
    const lendItems = selectedItems.map(item => ({
      inventory_id: item.库存ID,
      quantity: parseInt(batchLendQuantities[item.库存ID] as string) // 读取对象属性
    }))

    const requestData = {
      lend_items: lendItems,
      operator: lendForm.operator,
      remark: lendForm.remark
    }

    // 处理借出时间
    if (!lendForm.use_auto_out_time && lendForm.out_time) {
      requestData.out_time = lendForm.out_time
    } else {
      const now = new Date()
      const year = now.getFullYear()
      const month = String(now.getMonth() + 1).padStart(2, '0')
      const day = String(now.getDate()).padStart(2, '0')
      const hour = String(now.getHours()).padStart(2, '0')
      requestData.out_time = `${year}-${month}-${day} ${hour}`
    }

    return requestData
  }

  // 确认按钮处理
  function handleConfirm(): void {
    if (!validateBatchLend()) return

    const requestData = prepareBatchLendData()
    onConfirm(requestData)
  }

  // 关闭模态框重置表单
  function handleClose(): void {
    lendForm = {
      operator: '',
      remark: '',
      use_auto_out_time: true,
      out_time: ''
    }
    batchLendQuantities = {} // 清空对象
    validationStates.clear()
    currentStockCache.clear()
    quickFillValue = '' // 清空快速填充输入框
    onClose()
  }
</script>

<div class="modal-overlay" class:show={show}>
  <div class="modal-content large-modal" on:click|stopPropagation>
    <div class="modal-header">
      <h2>批量借出 ({selectedItems.length} 项)</h2>
      <button class="modal-close" on:click={handleClose} disabled={loading}>×</button>
    </div>

    <div class="modal-body">
      <form on:submit|preventDefault={handleConfirm}>
        <!-- 公共信息 -->
        <div class="form-section">
          <h3>公共信息</h3>
          <div class="form-row">
            <div class="form-group">
              <label for="lend_operator">操作人员 *</label>
              <input
                id="lend_operator"
                type="text"
                bind:value={lendForm.operator}
                placeholder="请输入操作人员姓名"
                required
                disabled={loading}
              />
            </div>
            <div class="form-group">
              <label for="lend_remark">备注</label>
              <input
                id="lend_remark"
                type="text"
                bind:value={lendForm.remark}
                placeholder="请输入备注信息"
                disabled={loading}
              />
            </div>
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input
                type="checkbox"
                bind:checked={lendForm.use_auto_out_time}
                disabled={loading}
              />
              自动生成借出时间
            </label>
          </div>

          {#if !lendForm.use_auto_out_time}
            <div class="form-group">
              <label for="lend_out_time">借出时间 *</label>
              <input
                id="lend_out_time"
                type="text"
                bind:value={lendForm.out_time}
                on:input={formatTimeInput}
                placeholder="例：2025-12-11 14 或 2025-12-11 14:30:00"
                maxlength="19"
                disabled={loading}
              />
              <small class="form-hint">格式：YYYY-MM-DD HH（四位年+日期+小时），支持扩展：YYYY-MM-DD HH:MM:SS</small>
            </div>
          {/if}
        </div>

        <div class="form-section">
          <!-- 模块头部：标题 + 快速填充功能区 -->
          <div class="section-header">
            <h3>差异化归还数量设置</h3>
            <!-- 快速填充子容器：标签 + 输入框 + 应用按钮 -->
            <div class="quick-fill-section">
              <label>快速填充:</label>
              <!-- 数字输入框：限定正整数，加载中禁用（双向绑定） -->
              <input
                type="number"
                min="1"
                step="1"
                placeholder="统一数量"
                class="quick-fill-input"
                disabled={loading}
                bind:value={quickFillValue}
              />
              <!-- 应用所有按钮：点击触发批量填充，加载中禁用 -->
              <button
                type="button"
                class="btn-quick-fill"
                on:click={() => {
                  quickFillAllQuantities(quickFillValue);
                  quickFillValue = ''; // 清空绑定值，自动同步到输入框
                }}
                disabled={loading || !quickFillValue}
              >
                应用所有
              </button>
            </div>
          </div>

          <!-- 商品列表：动态key强制重渲染 -->
          <div class="batch-quantities-table">
            <div class="table-header">
              <div class="row">
                <div class="cell product-info">商品信息</div>
                <div class="cell current-stock">当前库存</div>
                <div class="cell status">状态</div>
                <div class="cell lend-quantity">借出数量 *</div>
              </div>
            </div>
            <div class="table-body">
              <!-- 动态key：数量变化时强制重渲染输入框 -->
              {#each selectedItems as item (item.库存ID + '-' + JSON.stringify(batchLendQuantities[item.库存ID]))}
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
                    <!-- 强制重新渲染库存数值 -->
                    {#key getCurrentStock(item) + item.库存ID}
                      <span
                        class:stock-low={getCurrentStock(item) < 10 && getCurrentStock(item) >= 0}
                        class:stock-negative={getCurrentStock(item) < 0}
                      >
                        {getCurrentStock(item)}
                      </span>
                    {/key}
                  </div>
                  <div class="cell status">
                    <span class:status-out={item.状态 === '已出库' || item.状态 === '已借出'}>
                      {item.状态 || '正常'}
                    </span>
                  </div>
                  <div class="cell lend-quantity">
                    <!-- 核心修改：动态max限制 + 占位符提示 -->
                    <input
                      type="number"
                      min="1"
                      step="1"
                      max={getCurrentStock(item) >= 0 ? getCurrentStock(item) : ''}
                      bind:value={batchLendQuantities[item.库存ID]}
                      placeholder={
                        getCurrentStock(item) >= 0
                          ? `最大 ${getCurrentStock(item)}`
                          : `当前库存为负数 (${getCurrentStock(item)})，可输入任意正整数`
                      }
                      class:quantity-error={!validationStates.get(item.库存ID)?.isValid && batchLendQuantities[item.库存ID] !== undefined}
                      on:input={(e) => handleQuantityChange(item.库存ID, e.target.value)}
                      disabled={loading}
                    />
                    <!-- 错误/提示文本：区分错误和友好提示 -->
                    {#if validationStates.get(item.库存ID)?.message}
                      <div
                        class:error-text={!validationStates.get(item.库存ID)?.isValid}
                        class:hint-text={validationStates.get(item.库存ID)?.isValid}
                      >
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
          <button type="button" class="btn-outline" on:click={handleClose} disabled={loading}>
            取消
          </button>
          <button type="submit" class="btn-primary" disabled={lendButtonDisabled || loading}>
            {loading ? `处理中...` : `确认批量借出 (${selectedItems.length})`}
          </button>
        </div>
      </form>
    </div>
  </div>
</div>

<style>
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
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.3s ease;
  }

  .modal-overlay.show {
    opacity: 1;
    pointer-events: auto;
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
    font-size: 1.3rem;
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
    transition: color 0.3s ease;
  }

  .modal-close:hover:not(:disabled) {
    color: #e74c3c;
  }

  .modal-close:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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

  .form-hint {
    display: block;
    margin-top: 5px;
    font-size: 12px;
    color: #999;
  }

  input, select, textarea {
    width: 100%;
    padding: 8px 12px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 14px;
    transition: border-color 0.3s ease;
  }

  input:focus, select:focus, textarea:focus {
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

  .btn-quick-fill:hover:not(:disabled) {
    background: #218838;
  }

  .btn-quick-fill:disabled {
    opacity: 0.6;
    cursor: not-allowed;
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

  .product-name {
    font-size: 13px;
    color: #555;
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

  .lend-quantity {
    flex-direction: column;
    align-items: stretch;
    gap: 5px;
  }

  .lend-quantity input {
    padding: 6px;
    font-size: 13px;
  }

  .quantity-error {
    border-color: #e74c3c !important;
    background-color: #fdf2f2;
  }

  /* 区分错误文本和提示文本 */
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
    padding-top: 20px;
    border-top: 1px solid #eee;
  }

  .btn-outline, .btn-primary {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
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

  .btn-primary {
    background: #3498db;
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: #2980b9;
    transform: translateY(-1px);
  }

  .btn-outline:disabled, .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  .status-out {
    color: #e74c3c;
    font-weight: bold;
  }

  /* 响应式调整 */
  @media (max-width: 768px) {
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

    .row {
      grid-template-columns: 1fr;
    }

    .cell {
      min-height: 50px;
    }
  }
</style>