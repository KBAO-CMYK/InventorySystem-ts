<script lang="ts">
  import { onMount } from 'svelte'
  //import StockIn from './StockIn.svelte'
  import StockIn from './stock_in/ProductStockIn.svelte'
  import InventoryManagement from './InventoryManagement.svelte'
  import StockOutRecords from './Records.svelte'
  // 适配 api.ts 导入（注意后缀改为 .ts，若项目配置了路径别名可保持不变）
  import { api, handleApiError } from './lib/api'
  // 导入 api.ts 中定义的核心类型
  import type { ApiSuccessResponse } from './lib/api'

  // ========== 类型定义 ==========
  /** 活跃标签类型 */
  type ActiveTab = 'stockIn' | 'inventory' | 'stockOutRecords'

  /** 消息类型 */
  type MessageType = 'info' | 'success' | 'error' | 'warning'

  /** 消息对象类型 */
  interface Message {
    text: string
    type: MessageType
  }

  /** 缓存数据项类型 */
  interface CacheItem<T = any> {
    data: T | null
    timestamp: number
  }

  /** 整体缓存对象类型 */
  interface DataCache {
    inventory: CacheItem
    stockOut: CacheItem
    productTypes: CacheItem<string[]>
    floors: CacheItem<number[]>
  }

  // ========== 共享状态（带类型注解） ==========
  let activeTab: ActiveTab = 'stockIn'
  let loading: boolean = false
  let batchLoading: boolean = false
  let detailLoading: boolean = false
  let message: Message = { text: '', type: 'info' }

  // ========== 共享数据（带类型注解） ==========
  let productTypes: string[] = []
  let floors: number[] = [1, 2, 3, 4, 5]

  // ========== 缓存机制（带类型注解） ==========
  const CACHE_DURATION: number = 5 * 60 * 1000
  let dataCache: DataCache = {
    inventory: { data: null, timestamp: 0 },
    stockOut: { data: null, timestamp: 0 },
    productTypes: { data: null, timestamp: 0 },
    floors: { data: null, timestamp: 0 }
  }

  // ========== 共享函数（带类型注解） ==========
  /** 显示提示消息 */
  function showMessage(text: string, type: MessageType = 'info'): void {
    message = { text, type }
    setTimeout(() => {
      if (message.text === text) {
        message = { text: '', type: 'info' }
      }
    }, 5000)
  }

  /** 防抖函数（泛型支持） */
  function debounce<T extends (...args: any[]) => any>(
    func: T,
    wait: number
  ): (...args: Parameters<T>) => void {
    let timeout: ReturnType<typeof setTimeout>
    return function executedFunction(...args: Parameters<T>) {
      const later = () => {
        clearTimeout(timeout)
        func(...args)
      }
      clearTimeout(timeout)
      timeout = setTimeout(later, wait)
    }
  }

  /** 加载商品类型 */
  async function loadProductTypes(): Promise<void> {
    const now = Date.now()
    if (dataCache.productTypes.data && now - dataCache.productTypes.timestamp < CACHE_DURATION) {
      productTypes = dataCache.productTypes.data
      return
    }

    try {
      const result = await api.getProductTypes() as ApiSuccessResponse<string[]>
      if (result.status === 'success') {
        productTypes = result.data || ["样品", "原材料", "HB"]
        dataCache.productTypes = { data: productTypes, timestamp: now }
      } else {
        throw new Error(result.message || '获取商品类型失败')
      }
    } catch (error) {
      console.error('加载商品类型失败:', error)
      showMessage(handleApiError(error, '加载商品类型失败'), 'error')
      productTypes = ["样品", "原材料", "HB"]
    }
  }

  /** 加载楼层选项 */
  async function loadFloors(): Promise<void> {
    const now = Date.now()
    if (dataCache.floors.data && now - dataCache.floors.timestamp < CACHE_DURATION) {
      floors = dataCache.floors.data
      return
    }

    try {
      const result = await api.getFloors() as ApiSuccessResponse<number[]>
      if (result.status === 'success') {
        floors = result.data || [1, 2, 3, 4, 5]
        dataCache.floors = { data: floors, timestamp: now }
      } else {
        throw new Error(result.message || '获取楼层选项失败')
      }
    } catch (error) {
      console.error('加载楼层选项失败:', error)
      showMessage(handleApiError(error, '加载楼层选项失败'), 'error')
      floors = [1, 2, 3, 4, 5]
    }
  }

  /** 健康检查 */
  async function healthCheck(): Promise<void> {
    try {
      const result = await api.healthCheck() as ApiSuccessResponse
      if (result.status === 'success') {
        console.log('API服务状态正常')
      }
    } catch (error) {
      console.error('API服务连接失败:', error)
      showMessage('API服务连接失败，请检查网络连接', 'error')
    }
  }

  /** 刷新所有数据 */
  async function refreshAllData(): Promise<void> {
    loading = true
    try {
      await Promise.all([
        loadProductTypes(),
        loadFloors()
      ])
      showMessage('数据刷新成功', 'success')
    } catch (error) {
      console.error('刷新数据失败:', error)
      showMessage(handleApiError(error, '刷新数据失败'), 'error')
    } finally {
      loading = false
    }
  }

  // ========== 初始化加载 ==========
  onMount(() => {
    // 先进行健康检查
    healthCheck()
    // 然后加载所有数据
    refreshAllData()
  })
</script>

<svelte:head>
  <title>库存管理系统</title>
</svelte:head>

<!-- 完全占满视口的外层容器 -->
<div class="app-container">
  <header class="header">
    <h1>📦 库存管理系统</h1>
    <div class="status-bar">
      {#if loading}
        <span class="loading">加载中...</span>
      {/if}
      {#if batchLoading}
        <span class="loading">批量处理中...</span>
      {/if}
      {#if detailLoading}
        <span class="loading">加载详情中...</span>
      {/if}
      {#if message.text}
        <div class={`message ${message.type}`}>
          {message.text}
        </div>
      {/if}
      <button class="btn-refresh" on:click={refreshAllData} title="刷新所有数据" disabled={loading}>
        🔄
      </button>
    </div>
  </header>

  <nav class="tabs">
    <button class:active={activeTab === 'stockIn'} on:click={() => activeTab = 'stockIn'}>
      商品入库
    </button>
    <button class:active={activeTab === 'inventory'} on:click={() => activeTab = 'inventory'}>
      库存管理
    </button>
    <button class:active={activeTab === 'stockOutRecords'} on:click={() => activeTab = 'stockOutRecords'}>
      操作记录
    </button>
  </nav>

  <main class="main-content">
    {#if activeTab === 'stockIn'}
      <StockIn
        {productTypes}
        {floors}
        {loading}
        {showMessage}
        {debounce}
      />
    {:else if activeTab === 'inventory'}
      <InventoryManagement
        {productTypes}
        {floors}
        {loading}
        {batchLoading}
        {detailLoading}
        {showMessage}
        {debounce}
        {dataCache}
        {loadProductTypes}
        {loadFloors}
      />
    {:else if activeTab === 'stockOutRecords'}
      <StockOutRecords
        {productTypes}
        {loading}
        {showMessage}
        {debounce}
        {dataCache}
      />
    {/if}
  </main>
</div>

<style>
  /* 完全重置，移除所有默认边距和滚动 */
  :global(*), :global(*::before), :global(*::after) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  :global(html), :global(body) {
    width: 100vw;
    height: 100vh;
    overflow: hidden; /* 完全禁用滚动 */
  }

  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: #f5f5f5;
    color: #333;
  }

  /* 外层容器完全占满浏览器 */
  .app-container {
    width: 100vw;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* 头部区域 */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    border-bottom: 2px solid #e0e0e0;
    flex-shrink: 0; /* 固定高度不压缩 */
    background: white;
  }

  .header h1 {
    color: #2c3e50;
    font-size: clamp(1.5rem, 3vw, 2.2rem);
  }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
  }

  .loading {
    color: #666;
    font-style: italic;
  }

  .message {
    padding: 0.5rem 1rem;
    border-radius: 5px;
    font-weight: 500;
    font-size: 0.9rem;
    max-width: 300px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .message.success {
    background-color: #d4edda;
    color: #155724;
    border: 1px solid #c3e6cb;
  }

  .message.error {
    background-color: #f8d7da;
    color: #721c24;
    border: 1px solid #f5c6cb;
  }

  .message.info {
    background-color: #d1ecf1;
    color: #0c5460;
    border: 1px solid #bee5eb;
  }

  .message.warning {
    background-color: #fff3cd;
    color: #856404;
    border: 1px solid #ffeaa7;
  }

  /* 刷新按钮 */
  .btn-refresh {
    background: #3498db;
    color: white;
    border: none;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 1.2rem;
  }

  .btn-refresh:hover:not(:disabled) {
    background: #2980b9;
    transform: rotate(90deg);
  }

  .btn-refresh:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  /* 标签栏 */
  .tabs {
    display: flex;
    gap: 0; /* 移除标签间空隙 */
    background: white;
    border-bottom: 1px solid #e0e0e0;
    flex-shrink: 0;
  }

  .tabs button {
    flex: 1;
    padding: 1rem 2rem;
    border: none;
    background: transparent;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.3s ease;
    font-size: clamp(0.9rem, 1.5vw, 1rem);
  }

  .tabs button:hover {
    background: #f8f9fa;
  }

  .tabs button.active {
    background: #3498db;
    color: white;
    box-shadow: inset 0 -3px 0 #2980b9;
  }

  /* 主内容区域 - 完全填充剩余空间 */
  .main-content {
    flex: 1; /* 占满剩余高度 */
    padding: 2rem;
    background: white;
    overflow-y: auto; /* 内容溢出时内部滚动 */
    overflow-x: hidden;
  }

  /* 响应式适配 - 小屏幕也完全占满 */
  @media (max-width: 768px) {
    .header {
      flex-direction: column;
      gap: 1rem;
      text-align: center;
      padding: 1rem;
    }

    .status-bar {
      justify-content: center;
      width: 100%;
    }

    .tabs {
      flex-direction: column;
    }

    .main-content {
      padding: 1rem;
    }

    .message {
      max-width: 100%;
      white-space: normal;
    }

    .btn-refresh {
      width: 35px;
      height: 35px;
      font-size: 1rem;
    }
  }

  @media (max-width: 480px) {
    .header h1 {
      font-size: 1.5rem;
    }

    .tabs button {
      padding: 0.8rem;
    }
  }
</style>