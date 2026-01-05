<script lang="ts">
  import { onMount } from 'svelte'
  import StockIn from './stock_in/ProductStockIn.svelte'
  import InventoryManagement from './InventoryManagement.svelte'
  import StockOutRecords from './Records.svelte'
  import { api, handleApiError } from './lib/api'
  import type { ApiSuccessResponse } from './lib/api'

  // ========== 类型定义 ==========
  type ActiveTab = 'stockIn' | 'inventory' | 'stockOutRecords'
  type MessageType = 'info' | 'success' | 'error' | 'warning'

  interface Message {
    text: string
    type: MessageType
  }

  interface CacheItem<T = any> {
    data: T | null
    timestamp: number
  }

  interface DataCache {
    inventory: CacheItem
    stockOut: CacheItem
    productTypes: CacheItem<string[]>
    floors: CacheItem<number[]>
  }

  // ========== 共享状态 ==========
  let activeTab: ActiveTab = 'stockIn'
  let loading: boolean = false
  let batchLoading: boolean = false
  let detailLoading: boolean = false
  let message: Message = { text: '', type: 'info' }

  // ========== 共享数据 ==========
  let productTypes: string[] = []
  let floors: number[] = [1, 2, 3, 4, 5]

  // ========== 缓存机制 ==========
  const CACHE_DURATION: number = 5 * 60 * 1000
  let dataCache: DataCache = {
    inventory: { data: null, timestamp: 0 },
    stockOut: { data: null, timestamp: 0 },
    productTypes: { data: null, timestamp: 0 },
    floors: { data: null, timestamp: 0 }
  }

  // ========== 共享函数 ==========
  function showMessage(text: string, type: MessageType = 'info'): void {
    message = { text, type }
    setTimeout(() => {
      if (message.text === text) {
        message = { text: '', type: 'info' }
      }
    }, 5000)
  }

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
        throw new Error(result.message || '获取类型失败')
      }
    } catch (error) {
      console.error('加载类型失败:', error)
      showMessage(handleApiError(error, '加载类型失败'), 'error')
      productTypes = ["样品", "原材料", "HB"]
    }
  }

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
    healthCheck()
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
  /* 完全重置，确保无任何默认边距和内边距 */
  :global(*), :global(*::before), :global(*::after) {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
  }

  /* 确保根元素100%占满视口，无滚动条 */
  :global(html) {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
  }

  :global(body) {
    width: 100vw;
    height: 100vh;
    overflow: hidden;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: #f5f5f5;
    color: #333;
  }

  /* 主容器：绝对定位，完全贴紧浏览器 */
  .app-container {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    min-width: 100%;
    min-height: 100%;
    overflow: hidden;
  }

  /* 头部区域 */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem 2rem;
    border-bottom: 2px solid #e0e0e0;
    flex-shrink: 0;
    background: white;
    min-height: 80px;
  }

  .header h1 {
    color: #2c3e50;
    font-size: clamp(1.5rem, 3vw, 2.2rem);
    white-space: nowrap;
  }

  .status-bar {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    justify-content: flex-end;
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
    flex-shrink: 0;
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
    gap: 0;
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
    white-space: nowrap;
    min-height: 60px;
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
    flex: 1;
    padding: 2rem;
    background: white;
    overflow-y: auto;
    overflow-x: hidden;
    position: relative;
    min-height: 0; /* 重要：让flex项可以收缩 */
  }

  /* 美化主内容区域的滚动条 */
  .main-content::-webkit-scrollbar {
    width: 8px;
  }

  .main-content::-webkit-scrollbar-track {
    background: #f1f1f1;
  }

  .main-content::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 4px;
  }

  .main-content::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
  }

  /* Firefox 滚动条样式 */
  .main-content {
    scrollbar-width: thin;
    scrollbar-color: #c1c1c1 #f1f1f1;
  }

  /* 响应式适配 */
  @media (max-width: 768px) {
    .header {
      flex-direction: column;
      gap: 1rem;
      text-align: center;
      padding: 1rem;
      min-height: auto;
    }

    .status-bar {
      justify-content: center;
      width: 100%;
      flex-wrap: wrap;
    }

    .tabs {
      flex-direction: column;
    }

    .tabs button {
      min-height: 50px;
      padding: 0.8rem;
    }

    .main-content {
      padding: 1rem;
      -webkit-overflow-scrolling: touch;
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
      white-space: normal;
    }

    .tabs button {
      padding: 0.6rem;
      min-height: 45px;
      font-size: 0.9rem;
    }

    .main-content {
      padding: 0.5rem;
    }
  }

  /* 确保所有内容都能正确缩放 */
  @media (max-height: 600px) {
    .header {
      padding: 0.5rem 1rem;
      min-height: 60px;
    }

    .tabs button {
      min-height: 40px;
      padding: 0.5rem;
    }

    .main-content {
      padding: 1rem;
    }
  }
</style>