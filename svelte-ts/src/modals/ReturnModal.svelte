<script lang="ts">
  import { onMount, onDestroy } from 'svelte'

  // ========== 接口定义 ==========
  /** 数量验证状态接口 */
  interface ValidationState {
    isValid: boolean;
    message: string;
  }

  /** 归还商品项接口 */
  interface ReturnItem {
    inventory_id: number | string;
    quantity: number;
  }

  /** 提交请求数据接口 */
  interface ReturnRequestData {
    return_items: ReturnItem[];
    operator: string;
    remark: string;
    lendTime: string;
    inventoryIds: (number | string)[];
  }

  // ========== 导出Props类型注解 ==========
  export let show: boolean = false          // 控制模态框显隐
  export let loading: boolean = false       // 加载状态（禁用操作）
  export let selectedItems: any[] = []      // 选中的待归还商品列表
  export let showMessage: (message: string, type: string) => void // 全局提示函数
  export let onClose: () => void            // 关闭回调
  export let onConfirm: (data: ReturnRequestData) => void | Promise<void> // 确认归还回调

  // ========== 变量类型注解 ==========
  // 差异化数量存储（核心：每个商品独立设置归还数量）
  let batchLendQuantities: Map<number | string, string> = new Map() // key: 库存ID, value: 归还数量
  let validationStates: Map<number | string, ValidationState> = new Map()    // 验证状态Map

  // 表单公共数据
  let operator: string = ''                // 操作人员
  let remark: string = ''                  // 归还备注
  let lendTime: string = ''                // 归还时间

  // 响应式变量先声明再赋值（Svelte TS兼容写法）
  let inventoryIds: (number | string)[] = []
  let confirmDisabled: boolean = false

  // 防抖计时器
  let timeFormatTimer: NodeJS.Timeout | null = null
  let quantityDebounceTimer: NodeJS.Timeout | null = null
  const DEBOUNCE_DELAY: number = 300

  // ========== 响应式逻辑 ==========
  // 实时提取选中商品的库存ID
  $: inventoryIds = selectedItems.map(item => item.库存ID)
  // 响应式判断确认按钮禁用状态
  $: confirmDisabled = loading || !operator.trim() || !lendTime.trim() || !validateAllQuantities() || selectedItems.length === 0

  // 初始化：模态框显示时重置数据
  $: if (show) {
    initModalData()
  }

  // ========== 核心函数类型注解 ==========
  // 计算商品可归还数量（核心：库存总数 - 累计归还数量）
  function getAvailableLendQty(item: any): number {
    const totalStock = item.累计借出数量 || 0
    const borrowedQty = item.累计归还数量 || 0
    return Math.max(0, totalStock - borrowedQty) // 确保非负
  }

  // 初始化模态框数据
  function initModalData(): void {
    // 重置数量和验证状态
    batchLendQuantities = new Map()
    validationStates = new Map()

    // 为每个选中商品初始化默认归还数量为1（不超过可归还数量）
    selectedItems.forEach(item => {
      const availableQty = getAvailableLendQty(item)
      const defaultQty = availableQty >= 1 ? '1' : '0' // 可归还为0时默认0
      batchLendQuantities.set(item.库存ID, defaultQty)
      validationStates.set(item.库存ID, validateQuantityInput(defaultQty, item))
    })

    // 初始化默认归还时间（仅为空时）
    if (!lendTime.trim()) {
      const now = new Date()
      const year = now.getFullYear()
      const month = String(now.getMonth() + 1).padStart(2, '0')
      const day = String(now.getDate()).padStart(2, '0')
      const hour = String(now.getHours()).padStart(2, '0')
      lendTime = `${year}-${month}-${day} ${hour}`
    }
  }

  // 时间格式校验（复用原有逻辑，仅适配变量名）
  function validateTimeFormat(time: string): boolean {
    if (!time.trim()) return false
    const timeRegex1 = /^\d{4}-\d{2}-\d{2} \d{2}$/          // YYYY-MM-DD HH
    const timeRegex2 = /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/ // YYYY-MM-DD HH:MM:SS
    return timeRegex1.test(time) || timeRegex2.test(time)
  }

  // 校验单个商品的归还数量（核心：≤可归还数量校验）
  function validateQuantityInput(value: string | null | undefined, item: any): ValidationState {
    // 1. 空值校验
    if (value === '' || value == null) {
      return { isValid: false, message: '归还数量不能为空' }
    }

    const numValue = Number(value)
    const availableQty = getAvailableLendQty(item) // 核心修改：可归还数量

    // 2. 非数字校验
    if (isNaN(numValue)) {
      return { isValid: false, message: '归还数量必须是数字' }
    }

    // 3. 非整数校验
    if (!Number.isInteger(numValue)) {
      return { isValid: false, message: '归还数量必须是整数' }
    }

    // 4. 非正数校验
    if (numValue <= 0) {
      return { isValid: false, message: '归还数量必须大于0' }
    }

    // 5. 核心规则：归还数量 ≤ 可归还数量（库存总数 - 累计归还数量）
    if (numValue > availableQty) {
      return {
        isValid: false,
        message: `归还数量不能超过可归还数量 (${availableQty})`
      }
    }

    return { isValid: true, message: '' }
  }

  // 更新单个商品的数量验证状态
  function updateValidationState(itemId: number | string, value: string | null | undefined): void {
    const item = selectedItems.find(item => item.库存ID === itemId)
    if (!item) return
    validationStates.set(itemId, validateQuantityInput(value, item))
  }

  // 处理数量输入变化（防抖+自动修正超过最大值的数值）
  function handleQuantityChange(itemId: number | string, value: string): void {
    const item = selectedItems.find(item => item.库存ID === itemId)
    if (!item) return

    const availableQty = getAvailableLendQty(item) // 核心修改：可归还数量
    let numValue = Number(value)

    // 自动修正：超过可归还数量时，重置为可归还数量
    if (!isNaN(numValue) && numValue > availableQty && availableQty > 0) {
      numValue = availableQty
      value = numValue.toString()
    }

    batchLendQuantities.set(itemId, value)

    clearTimeout(quantityDebounceTimer)
    quantityDebounceTimer = setTimeout(() => {
      updateValidationState(itemId, value)
    }, DEBOUNCE_DELAY)
  }

  // 校验所有商品的数量是否合法
  function validateAllQuantities(): boolean {
    let allValid = true
    selectedItems.forEach(item => {
      const quantity = batchLendQuantities.get(item.库存ID)
      const validation = validateQuantityInput(quantity, item)
      if (!validation.isValid) {
        allValid = false
        validationStates.set(item.库存ID, validation)
      }
    })
    return allValid
  }

  // 快速填充所有商品的归还数量（适配≤可归还数量规则）
  function quickFillAllQuantities(value: string | number): void {
    const numValue = Number(value)
    // 基础校验：有效正整数
    if (!numValue || numValue <= 0 || !Number.isInteger(numValue)) {
      showMessage('请输入有效的正整数', 'error')
      return
    }

    const newQuantities = new Map(batchLendQuantities)
    let hasInvalid = false
    let errorMsg = ''

    selectedItems.forEach(item => {
      const availableQty = getAvailableLendQty(item) // 核心修改：可归还数量
      // 填充值超过该商品可归还数量时，使用可归还数量
      const fillValue = Math.min(numValue, availableQty)

      // 记录第一个不符合的商品提示
      if (numValue > availableQty && !hasInvalid) {
        errorMsg = `商品 ${item.商品信息?.货号 || item.库存ID} 已自动调整为最大可归还数量 (${availableQty})`
        hasInvalid = true
      }

      newQuantities.set(item.库存ID, fillValue.toString())
      updateValidationState(item.库存ID, fillValue.toString())
    })

    batchLendQuantities = newQuantities

    // 提示用户有数值被自动调整
    if (hasInvalid) {
      showMessage(errorMsg, 'warning')
    }
  }

  // 确认归还逻辑
  function handleConfirm(): void {
    // 【新增防御性校验】确保 onConfirm 是函数，避免报错
    if (typeof onConfirm !== 'function') {
      showMessage('未配置确认归还的处理逻辑，请联系开发人员', 'error');
      console.error('onConfirm 必须是一个函数');
      return;
    }

    // 1. 操作人员校验
    if (!operator.trim()) {
      showMessage('请填写操作人员姓名', 'error')
      return
    }

    // 2. 归还时间校验
    if (!validateTimeFormat(lendTime)) {
      showMessage('时间格式错误，请使用：YYYY-MM-DD HH（例：2025-12-11 14）或 YYYY-MM-DD HH:MM:SS（例：2025-12-11 14:30:00）', 'error')
      return
    }

    // 3. 数量校验
    if (!validateAllQuantities()) {
      const errorMessages: string[] = []
      selectedItems.forEach(item => {
        const validation = validationStates.get(item.库存ID)
        if (validation && !validation.isValid) {
          errorMessages.push(`商品 ${item.商品信息?.货号 || item.库存ID}: ${validation.message}`)
        }
      })
      showMessage(errorMessages.slice(0, 3).join('；') + (errorMessages.length > 3 ? '...' : ''), 'error')
      return
    }

    // 4. 组装提交数据
    const lendItems: ReturnItem[] = selectedItems.map(item => ({
      inventory_id: item.库存ID,
      quantity: parseInt(batchLendQuantities.get(item.库存ID) || '0')
    }))

    const requestData: ReturnRequestData = {
      return_items: lendItems,       // 替换return_itemss
      operator: operator.trim(),
      remark: remark.trim(),
      lendTime: lendTime.trim(),   // 替换returnTime
      inventoryIds: inventoryIds
    }

    // 执行父组件确认逻辑
    onConfirm(requestData)
  }

  // 关闭模态框（重置所有数据）
  function handleClose(): void {
    // 重置表单
    operator = ''
    remark = ''
    lendTime = ''                 // 替换returnTime
    batchLendQuantities.clear()   // 替换batchReturnQuantities
    validationStates.clear()
    // 执行父组件关闭逻辑
    onClose()
  }

  // 组件销毁时清除防抖计时器
  onDestroy(() => {
    clearTimeout(timeFormatTimer)
    clearTimeout(quantityDebounceTimer)
  })

  // 【修复正则错误】formatTimeInput 函数
  function formatTimeInput(e: Event): void {
    const target = e.target as HTMLInputElement
    clearTimeout(timeFormatTimer)
    timeFormatTimer = setTimeout(() => {
      let value = target.value.trim()
      // 核心修复：将 - 移到字符类末尾，避免非法范围
      value = value.replace(/[^\d: -]/g, '')
      if (value.length === 4) value += '-'
      if (value.length === 7) value += '-'
      if (value.length === 10) value += ' '
      if (value.length === 13) value += ':'
      if (value.length === 16) value += ':'
      if (value.length > 19) value = value.slice(0, 19)
      lendTime = value
    }, DEBOUNCE_DELAY)
  }
</script>

<div class="modal-overlay" class:show={show}>
  <div class="modal-content large-modal">
    <div class="modal-header">
      <h2>批量归还 ({selectedItems.length} 项)</h2>
      <button
        class="modal-close"
        on:click={handleClose}
        disabled={loading}
        aria-label="关闭批量归还弹窗"
      >
        ×
      </button>
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
                bind:value={operator}
                placeholder="请输入操作人员姓名"
                required
                disabled={loading}
                maxlength="20"
              />
            </div>
            <div class="form-group">
              <label for="lend_remark">备注</label>
              <input
                id="lend_remark"
                type="text"
                bind:value={remark}
                placeholder="请输入备注信息"
                disabled={loading}
                maxlength="200"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="lend_out_time">归还时间 *</label>
            <input
              id="lend_out_time"
              type="text"
              bind:value={lendTime}
              on:input={formatTimeInput}
              placeholder="例：2025-12-11 14 或 2025-12-11 14:30:00"
              maxlength="19"
              disabled={loading}
            />
            <small class="form-hint">格式：YYYY-MM-DD HH（四位年+日期+小时），支持扩展：YYYY-MM-DD HH:MM:SS</small>
          </div>
        </div>

        <!-- 差异化归还数量设置 -->
        <div class="form-section">
          <div class="section-header">
            <h3>差异化归还数量设置</h3>
            <div class="quick-fill-section">
              <label>快速填充:</label>
              <input
                type="number"
                min="1"
                step="1"
                placeholder="统一数量"
                class="quick-fill-input"
                disabled={loading}
              />
              <button
                type="button"
                class="btn-quick-fill"
                on:click={(e) => {
                  const input = e.target.parentElement.querySelector('.quick-fill-input')
                  const value = input.value
                  quickFillAllQuantities(value)
                  input.value = '' // 清空输入框
                }}
                disabled={loading}
              >
                应用所有
              </button>
            </div>
          </div>

          <!-- 商品数量表格 -->
          <div class="batch-quantities-table">
            <div class="table-header">
              <div class="row">
                <div class="cell product-info">商品信息</div>
                <div class="cell status">状态</div>
                <div class="cell borrowed-quantity">可归还数量</div>
                <div class="cell return-quantity">归还数量 *</div>
              </div>
            </div>
            <div class="table-body">
              {#each selectedItems as item (item.库存ID)}
                <!-- 可归还数量为0时，行标红提示 -->
                <div class="row" class:borrowed-zero={getAvailableLendQty(item) === 0}>
                  <div class="cell product-info">
                    <div class="product-code">{item.商品信息?.货号 || item.库存ID}</div>
                    <div class="product-name">{item.商品信息?.商品名称 || ''}</div>
                    <div class="product-type">{item.商品信息?.类型 || '未分类'}</div>
                  </div>
                  <div class="cell status">
                    <span class:status-borrowed={item.状态 === '已归还'}>
                      {item.状态 || '正常'}
                    </span>
                  </div>
                  <div class="cell borrowed-quantity">
                    <span class:borrowed-zero-text={getAvailableLendQty(item) === 0}>
                      {getAvailableLendQty(item) || 0}
                    </span>
                  </div>
                  <div class="cell return-quantity">
                    <!-- 可归还数量为0时禁用输入 -->
                    <input
                      type="number"
                      min="1"
                      step="1"
                      max={getAvailableLendQty(item) || 0}
                      value={batchLendQuantities.get(item.库存ID) || ''}
                      placeholder={`最大 ${getAvailableLendQty(item) || 0}`}
                      class:quantity-error={!validationStates.get(item.库存ID)?.isValid && batchLendQuantities.get(item.库存ID)}
                      class:quantity-disabled={getAvailableLendQty(item) === 0}
                      on:input={(e) => handleQuantityChange(item.库存ID, e.target.value)}
                      disabled={loading || getAvailableLendQty(item) === 0}
                    />
                    {#if getAvailableLendQty(item) === 0}
                      <div class="error-text">无可归还数量，无法归还</div>
                    {:else if !validationStates.get(item.库存ID)?.isValid && batchLendQuantities.get(item.库存ID)}
                      <div class="error-text">{validationStates.get(item.库存ID).message}</div>
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
          <button type="submit" class="btn-primary" disabled={confirmDisabled || loading}>
            {loading ? '处理中...' : `确认批量归还 (${selectedItems.length})`}
          </button>
        </div>
      </form>
    </div>
  </div>
</div>

<style>
  /* 基础模态框样式 */
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

  /* 可归还数量为0的行样式 */
  .row.borrowed-zero {
    background: #fef2f2;
  }

  .cell {
    padding: 12px;
    background: white;
    display: flex;
    align-items: center;
    min-height: 60px;
  }

  .row.borrowed-zero .cell {
    background: #fef2f2;
  }

  .table-body .row:nth-child(even) .cell {
    background: #fafbfc;
  }

  .table-body .row.borrowed-zero:nth-child(even) .cell {
    background: #fee2e2;
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

  .borrowed-quantity {
    justify-content: center;
    font-weight: 500;
  }

  /* 可归还数量为0的文字样式 */
  .borrowed-zero-text {
    color: #e74c3c;
    font-weight: bold;
  }

  .return-quantity {
    flex-direction: column;
    align-items: stretch;
    gap: 5px;
  }

  .return-quantity input {
    padding: 6px;
    font-size: 13px;
  }

  /* 可归还为0时的输入框样式 */
  .return-quantity input.quantity-disabled {
    background: #f5f5f5;
    cursor: not-allowed;
    border-color: #ddd;
  }

  .quantity-error {
    border-color: #e74c3c !important;
    background-color: #fdf2f2;
  }

  .error-text {
    color: #e74c3c;
    font-size: 11px;
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

  .status-borrowed {
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