<script lang="ts">
  import { api } from './lib/api.js'
  import { onMount } from 'svelte'
  import BatchOperations from './modals/BatchOperations.svelte'
  import EditModal from './modals/EditModal.svelte'
  import DeleteModal from './modals/DeleteModal.svelte'
  import InventoryDetailModal from './modals/InventoryDetailModal.svelte'
  import BatchLendModal from './modals/LendModal.svelte'
  import BatchReturnModal from './modals/ReturnModal.svelte'
  // 导入修改后的图片组件
  import InventoryImage from './image/InventoryImage.svelte'
  // 新增：导入撤销操作子组件
  import UndoButton from './modals/UndoButton.svelte'

  // ========== 导出Props类型注解 ==========
  export let productTypes: any[] = []
  export let floors: any[] = []
  export let loading: boolean = false
  export let batchLoading: boolean = false
  export let detailLoading: boolean = false
  export let showMessage: (msg: string, type: string) => void = () => {}
  export let debounce: (func: Function, wait: number) => Function = (func, wait) => func
  export let loadProductTypes: () => void = () => {}
  export let loadFloors: () => void = () => {}

  // ========== 库存筛选表单数据类型注解 ==========
  interface InventoryFilter {
    货号: string;
    类型: string;
    状态: string;
    楼层: string;
    架号: string;
    框号: string;
    包号: string;
    厂家: string;
    材质: string;
    颜色: string;
  }
  let inventoryFilter: InventoryFilter = {
    货号: '',
    类型: '',
    状态: '',
    楼层: '',
    架号: '',
    框号: '',
    包号: '',
    厂家: '',
    材质: '',
    颜色: ''
  }

  // ========== 数据存储类型注解 ==========
  let inventoryList: any[] = []
  let filteredInventoryList: any[] = []
  let paginatedInventoryList: any[] = []

  // ========== 分页相关类型注解 ==========
  let currentPage: number = 1
  let itemsPerPage: number = 10
  let totalPages: number = 1

  // ========== 模态框状态类型注解 ==========
  let showInventoryDetailModal: boolean = false
  let showEditModal: boolean = false
  let showDeleteModal: boolean = false
  let showLendModal: boolean = false
  let showReturnModal: boolean = false
  let lendLoading: boolean = false
  let returnLoading: boolean = false

  // ========== 核心数据类型注解 ==========
  let selectedInventory: any | null = null
  let inventoryOperations: any[] = []
  let editingInventory: any | null = null

  // ========== 编辑表单数据类型注解 ==========
  interface EditForm {
    货号: string;
    类型: string;
    单价: string;
    重量: string;
    厂家: string;
    厂家地址: string;
    电话: string;
    用途: string;
    规格: string;
    备注: string;
    材质: string;
    颜色: string;
    形状: string;
    风格: string;
    图片路径: string;
    地址类型: number;
    楼层: number;
    架号: string;
    框号: string;
    包号: string;
    批次: number;
  }
  let editForm: EditForm = {
    货号: '',
    类型: '',
    单价: '',
    重量: '',
    厂家: '',
    厂家地址: '',
    电话: '',
    用途: '',
    规格: '',
    备注: '',
    材质: '',
    颜色: '',
    形状: '',
    风格: '',
    图片路径: '',
    地址类型: 1,
    楼层: 1,
    架号: '',
    框号: '',
    包号: '',
    批次: 1
  }

  // ========== 批量选择相关类型注解 ==========
  let selectedIds: Set<number | string> = new Set();

  // ========== 响应式计算属性类型注解 ==========
  $: selectedItems = ((): any[] => {
    const filtered = inventoryList.filter(item => selectedIds.has(item.库存ID));
    const uniqueMap = new Map();
    filtered.forEach(item => {
      if (!uniqueMap.has(item.库存ID)) {
        uniqueMap.set(item.库存ID, item);
      }
    });
    const uniqueItems = Array.from(uniqueMap.values());
    return uniqueItems;
  })();

  $: isAllSelected =
    paginatedInventoryList.length > 0 &&
    selectedIds.size > 0 &&
    paginatedInventoryList.every(item => selectedIds.has(item.库存ID));

  $: filteredCount = filteredInventoryList.length;
  $: totalSelected = selectedIds.size;
  $: currentPageSelected = ((): number => {
    const currentPageIds = new Set(paginatedInventoryList.map(item => item.库存ID));
    return Array.from(selectedIds).filter(id => currentPageIds.has(id)).length;
  })();

  // ========== 防抖筛选类型注解 ==========
  const debouncedApplyInventoryFilter: Function = debounce(applyInventoryFilter, 300)

  // ========== 核心方法类型注解 ==========
  async function loadInventoryList(): Promise<void> {
    loading = true
    try {
      const result = await api.getAllInventory()
      if (result && result.data) {
        // 仅去重，不修改任何库存数值
        inventoryList = deduplicateInventoryList(result.data);
        applyInventoryFilter()
        showMessage('库存数据加载成功', 'success')
      } else {
        throw new Error('返回数据格式不正确')
      }
    } catch (error) {
      console.error('加载库存列表失败:', error)
      showMessage('加载库存列表失败: ' + (error as Error).message, 'error')
      inventoryList = []
      applyInventoryFilter()
    } finally {
      loading = false
    }
  }

  // 辅助函数：仅去重，不修改库存数值
  function deduplicateInventoryList(list: any[]): any[] {
    const uniqueMap = new Map();
    list.forEach(item => {
      if (!uniqueMap.has(item.库存ID)) {
        uniqueMap.set(item.库存ID, item);
      }
    });
    return Array.from(uniqueMap.values());
  }

  // 应用库存筛选（仅过滤展示，无数据修改）
  function applyInventoryFilter(): void {
    const filter = inventoryFilter
    const list = inventoryList

    const hasActiveFilter = Object.values(filter).some(value => value !== '')
    if (!hasActiveFilter) {
      filteredInventoryList = list
      filteredInventoryList = deduplicateInventoryList(filteredInventoryList);
      updatePagination()
      return
    }

    filteredInventoryList = list.filter(item => {
      // 商品信息筛选（仅匹配，无计算）
      if (filter.货号 &&
          !item.商品信息?.货号?.toLowerCase().includes(filter.货号.toLowerCase())) {
        return false
      }

      if (filter.类型 && item.商品信息?.类型 !== filter.类型) {
        return false
      }

      // 库存状态筛选（仅匹配）
      if (filter.状态 && item.状态 !== filter.状态) {
        return false
      }

      // 位置信息筛选（仅匹配）
      if (filter.楼层 && item.位置信息?.楼层 !== parseInt(filter.楼层)) {
        return false
      }

      if (filter.架号 && item.位置信息?.架号 !== filter.架号) {
        return false
      }

      if (filter.框号 && item.位置信息?.框号 !== filter.框号) {
        return false
      }

      if (filter.包号 && item.位置信息?.包号 !== filter.包号) {
        return false
      }

      // 厂家信息筛选（仅匹配）
      if (filter.厂家 &&
          !item.厂家信息?.厂家?.toLowerCase().includes(filter.厂家.toLowerCase())) {
        return false
      }

      // 特征信息筛选（仅匹配）
      if (filter.材质 &&
          !item.特征信息?.材质?.toLowerCase().includes(filter.材质.toLowerCase())) {
        return false
      }

      if (filter.颜色 &&
          !item.特征信息?.颜色?.toLowerCase().includes(filter.颜色.toLowerCase())) {
        return false
      }

      return true
    })

    filteredInventoryList = deduplicateInventoryList(filteredInventoryList);
    updatePagination()
  }

  // 更新分页（仅切割展示，无数据修改）
  function updatePagination(): void {
    totalPages = Math.ceil(filteredInventoryList.length / itemsPerPage) || 1
    currentPage = Math.min(currentPage, totalPages)
    currentPage = Math.max(1, currentPage)

    const startIndex = (currentPage - 1) * itemsPerPage
    const endIndex = startIndex + itemsPerPage
    paginatedInventoryList = filteredInventoryList.slice(startIndex, endIndex)
  }

  // 改变页码（仅切换展示）
  function goToPage(page: number): void {
    currentPage = page
    updatePagination()
  }

  // 改变每页显示数量（仅切换展示）
  function changeItemsPerPage(value: string): void {
    itemsPerPage = parseInt(value)
    currentPage = 1
    updatePagination()
  }

  // 清空库存筛选条件（仅重置筛选）
  function clearInventoryFilter(): void {
    inventoryFilter = {
      货号: '',
      类型: '',
      状态: '',
      楼层: '',
      架号: '',
      框号: '',
      包号: '',
      厂家: '',
      材质: '',
      颜色: ''
    }
    applyInventoryFilter()
  }

  // 导出库存CSV（仅调用后端接口）
  async function exportInventoryCSV(): Promise<void> {
    if (filteredInventoryList.length === 0) {
      showMessage('没有数据可导出', 'warning')
      return
    }

    loading = true
    try {
      await api.exportInventoryCSV()
      showMessage('导出成功', 'success')
    } catch (error) {
      console.error('导出CSV失败:', error)
      showMessage('导出失败: ' + (error as Error).message, 'error')
    } finally {
      loading = false
    }
  }

  // 查看库存详情（仅读取后端数据）
  async function viewInventoryDetail(item: any): Promise<void> {
    if (detailLoading) return

    detailLoading = true
    selectedInventory = item
    try {
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('加载超时')), 10000)
      )

      const result = await Promise.race([
        api.getInventoryDetail(item.库存ID),
        timeoutPromise
      ])

      if (result.status === 'success' && result.data && result.data.operations) {
        inventoryOperations = result.data.operations || []
        showInventoryDetailModal = true
      } else {
        throw new Error('数据格式错误')
      }
    } catch (error) {
      console.error('加载操作记录失败:', error)
      inventoryOperations = []
      showInventoryDetailModal = true
      if ((error as Error).message === '加载超时') {
        showMessage('详情加载超时，请重试', 'warning')
      } else {
        showMessage('加载操作记录失败', 'error')
      }
    } finally {
      detailLoading = false
    }
  }

  // 关闭库存详情模态框（仅重置状态）
  function closeInventoryDetailModal(): void {
    showInventoryDetailModal = false
    selectedInventory = null
    inventoryOperations = []
  }

  // 打开编辑模态框（仅读取数据，无修改）
  function openEditModal(item: any): void {
    editingInventory = item
    // 仅复制后端返回的原始值，无计算/修改
    editForm = {
      货号: item.商品信息?.货号 || '',
      类型: item.商品信息?.类型 || '',
      单价: item.特征信息?.单价 || '',
      重量: item.特征信息?.重量 || '',
      厂家: item.厂家信息?.厂家 || '',
      厂家地址: item.厂家信息?.厂家地址 || '',
      电话: item.厂家信息?.电话 || '',
      用途: item.商品信息?.用途 || '',
      规格: item.特征信息?.规格 || '',
      备注: item.商品信息?.备注 || '',
      材质: item.特征信息?.材质 || '',
      颜色: item.特征信息?.颜色 || '',
      形状: item.特征信息?.形状 || '',
      风格: item.特征信息?.风格 || '',
      // 直接使用后端返回的图片相对路径
      图片路径: item.特征信息?.图片路径 || '',
      地址类型: item.位置信息?.地址类型 || 1,
      楼层: item.位置信息?.楼层 || 1,
      架号: item.位置信息?.架号 || '',
      框号: item.位置信息?.框号 || '',
      包号: item.位置信息?.包号 || '',
      批次: item.批次 || 1
    }
    showEditModal = true
  }

  // 关闭编辑模态框（仅重置状态）
  function closeEditModal(): void {
    showEditModal = false
    editingInventory = null
    editForm = {
      货号: '',
      类型: '',
      单价: '',
      重量: '',
      厂家: '',
      厂家地址: '',
      电话: '',
      用途: '',
      规格: '',
      备注: '',
      材质: '',
      颜色: '',
      形状: '',
      风格: '',
      图片路径: '',
      地址类型: 1,
      楼层: 1,
      架号: '',
      框号: '',
      包号: '',
      批次: 1
    }
  }

  // 保存编辑（仅传递数据给后端，前端不修改库存）
  async function saveEdit(): Promise<void> {
    if (!editForm.货号 || !editForm.类型) {
      showMessage('请填写货号和类型', 'error')
      return
    }

    loading = true
    try {
      const result = await api.updateInventory(editingInventory.库存ID, editForm)
      showMessage(result.message || '编辑成功', 'success')
      closeEditModal()
      // 重新从后端加载最新数据
      await loadInventoryList()
    } catch (error) {
      console.error('编辑失败:', error)
      showMessage('编辑失败: ' + (error as Error).message, 'error')
    } finally {
      loading = false
    }
  }

  // 打开删除确认模态框（仅读取数据）
  function openDeleteModal(item: any): void {
    selectedInventory = item
    showDeleteModal = true
  }

  // 关闭删除确认模态框（仅重置状态）
  function closeDeleteModal(): void {
    showDeleteModal = false
    selectedInventory = null
  }

  // 确认删除（仅调用后端接口，前端不修改数据）
  async function confirmDelete(): Promise<void> {
    loading = true
    try {
      const result = await api.deleteInventory(selectedInventory.库存ID)
      showMessage(result.message || '删除成功', 'success')
      closeDeleteModal()
      // 重新从后端加载最新数据
      await loadInventoryList()
    } catch (error) {
      console.error('删除失败:', error)
      showMessage('删除失败: ' + (error as Error).message, 'error')
    } finally {
      loading = false
    }
  }

  // ========== 批量选择核心逻辑（仅记录ID，不修改库存） ==========
  function toggleSelectItem(item: any): void {
    const itemId = item.库存ID;
    if (selectedIds.has(itemId)) {
      selectedIds.delete(itemId);
    } else {
      selectedIds.add(itemId);
    }
    selectedIds = new Set(selectedIds);
  }

  function toggleSelectAll(): void {
    if (isAllSelected) {
      const currentPageIds = new Set(paginatedInventoryList.map(item => item.库存ID));
      currentPageIds.forEach(id => selectedIds.delete(id));
    } else {
      const currentPageIds = new Set(paginatedInventoryList.map(item => item.库存ID));
      currentPageIds.forEach(id => selectedIds.add(id));
    }
    selectedIds = new Set(selectedIds);
  }

  function clearAllSelected(): void {
    selectedIds.clear();
    selectedIds = new Set(selectedIds);
    showMessage('已清空所有选中项', 'success');
  }

  // ========== 批量借出/归还核心逻辑（仅传递数据给后端，前端不修改库存） ==========
  function openLendModal(): void {
    if (selectedIds.size === 0) {
      showMessage('请先选择需要借出的库存项', 'warning');
      return;
    }
    const hasOutItem = selectedItems.some(item => item.状态 === '已出库');
    if (hasOutItem) {
      showMessage('选中项包含已出库的库存，无法借出', 'error');
      return;
    }
    showLendModal = true;
  }

  function closeLendModal(): void {
    showLendModal = false;
    lendLoading = false;
  }

  async function confirmLend(requestData: any): Promise<void> {
    lendLoading = true;
    try {
      const finalParams = {
        lend_items: requestData.lend_items.map((item: any) => ({
          inventory_id: item.inventory_id,
          quantity: item.quantity
        })),
        operator: requestData.operator,
        remark: requestData.remark,
        out_time: requestData.out_time
      };

      const result = await api.batchLendInventory(finalParams);
      showMessage(result.message || '批量借出成功', 'success');
      closeLendModal();
      clearAllSelected();
      await loadInventoryList();
    } catch (error) {
      console.error('批量借出失败:', error);
      showMessage('批量借出失败: ' + (error as Error).message, 'error');
    } finally {
      lendLoading = false;
    }
  }

  function openReturnModal(): void {
    if (selectedIds.size === 0) {
      showMessage('请先选择需要归还的库存项', 'warning');
      return;
    }
    const hasNormalItem = selectedItems.some(item => item.状态 === '正常');
    if (hasNormalItem) {
      showMessage('选中项包含未出库的库存，无法归还', 'error');
      return;
    }
    showReturnModal = true;
  }

  function closeReturnModal(): void {
    showReturnModal = false;
    returnLoading = false;
  }

  async function confirmReturn(requestData: any): Promise<void> {
    returnLoading = true;
    try {
      const finalParams = {
        return_items: requestData.return_items?.map((item: any) => ({
          inventory_id: item.inventory_id,
          quantity: item.quantity || 1
        })) || [],
        operator: requestData.operator,
        remark: requestData.remark,
        return_time: requestData.return_time || requestData.out_time
      };

      const result = await api.batchReturnInventory(finalParams);
      showMessage(result.message || '批量归还成功', 'success');
      closeReturnModal();
      clearAllSelected();
      await loadInventoryList();
    } catch (error) {
      console.error('批量归还失败:', error);
      showMessage('批量归还失败: ' + (error as Error).message, 'error');
    } finally {
      returnLoading = false;
    }
  }

  // ========== 纯读取类辅助方法（无任何计算/修改） ==========
  function getAddressString(item: any): string {
    const parts: string[] = []
    if (item.位置信息?.楼层) parts.push(`${item.位置信息.楼层}楼`)
    if (item.位置信息?.架号) parts.push(`架${item.位置信息.架号}`)
    if (item.位置信息?.框号) parts.push(`框${item.位置信息.框号}`)
    if (item.位置信息?.包号) parts.push(`包${item.位置信息.包号}`)
    return parts.join(' - ') || '-'
  }

  // 仅读取后端返回的库存数量，无任何前端计算/修改
  function getCurrentStock(item: any): number {
    return item.库存数量 || 0
  }

  // 仅读取后端返回的累计入库数量，无任何前端计算/修改
  function getTotalInQuantity(item: any): number {
    return item.累计入库数量 || 0
  }

  // 仅读取后端返回的累计出库数量，无任何前端计算/修改
  function getTotalOutQuantity(item: any): number {
    return item.累计出库数量 || 0
  }

  // 获取实时库存（仅读取本地列表中的后端原始值，无计算/修改）
  function getRealTimeStock(inventoryId: number | string): number {
    const item = inventoryList.find(item => item.库存ID === inventoryId)
    return item ? (item.库存数量 || 0) : 0
  }

  // 响应式更新（仅触发筛选，无数据修改）
  $: debouncedApplyInventoryFilter()

  onMount(() => {
    // 加载数据时仅从后端获取，无缓存/前端修改
    loadInventoryList()
  })
</script>

<section class="inventory-section">
  <h2>库存管理</h2>

  <!-- 筛选表单（仅筛选，无数据修改） -->
  <div class="filter-section">
    <h3>筛选条件</h3>
    <div class="filter-form">
      <div class="form-row">
        <div class="form-group">
          <label for="filter_货号">货号</label>
          <input
            id="filter_货号"
            type="text"
            bind:value={inventoryFilter.货号}
            placeholder="货号"
          />
        </div>
        <div class="form-group">
          <label for="filter_类型">商品类型</label>
          <select id="filter_类型" bind:value={inventoryFilter.类型}>
            <option value="">全部类型</option>
            {#each productTypes as type}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label for="filter_状态">状态</label>
          <select id="filter_状态" bind:value={inventoryFilter.状态}>
            <option value="">全部状态</option>
            <option value="正常">正常</option>
            <option value="已出库">已出库</option>
            <option value="异常">异常</option>
          </select>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="filter_楼层">楼层</label>
          <select id="filter_楼层" bind:value={inventoryFilter.楼层}>
            <option value="">全部楼层</option>
            {#each floors as floor}
              <option value={floor}>{floor}楼</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label for="filter_架号">架号</label>
          <input
            id="filter_架号"
            type="text"
            bind:value={inventoryFilter.架号}
            placeholder="架号"
          />
        </div>
        <div class="form-group">
          <label for="filter_框号">框号</label>
          <input
            id="filter_框号"
            type="text"
            bind:value={inventoryFilter.框号}
            placeholder="框号"
          />
        </div>
        <div class="form-group">
          <label for="filter_包号">包号</label>
          <input
            id="filter_包号"
            type="text"
            bind:value={inventoryFilter.包号}
            placeholder="包号"
          />
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="filter_厂家">厂家</label>
          <input
            id="filter_厂家"
            type="text"
            bind:value={inventoryFilter.厂家}
            placeholder="厂家名称"
          />
        </div>
        <div class="form-group">
          <label for="filter_材质">材质</label>
          <input
            id="filter_材质"
            type="text"
            bind:value={inventoryFilter.材质}
            placeholder="材质"
          />
        </div>
        <div class="form-group">
          <label for="filter_颜色">颜色</label>
          <input
            id="filter_颜色"
            type="text"
            bind:value={inventoryFilter.颜色}
            placeholder="颜色"
          />
        </div>
      </div>

      <div class="filter-actions">
        <button type="button" class="btn-outline" on:click={clearInventoryFilter}>
          清空条件
        </button>
        <button type="button" class="btn-primary" on:click={applyInventoryFilter}>
          搜索
        </button>
      </div>
    </div>
  </div>


  <div class="section-header">
      <div class="section-info">
        共找到 {filteredInventoryList.length} 条记录
        {#if selectedIds.size > 0}
          <span class="selected-count">
            已选择 {selectedIds.size} 项
            <button
              class="clear-selected-btn"
              on:click={clearAllSelected}
              title="清空所有选中项"
            >
              ×
            </button>
          </span>
        {/if}
      </div>
      <div class="section-controls">
        <div class="pagination-controls">
          <label>每页显示:</label>
          <select bind:value={itemsPerPage} on:change={() => changeItemsPerPage(itemsPerPage)}>
            <option value={10}>10</option>
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>
        <button
          class="btn-outline clear-all-selected-btn"
          on:click={clearAllSelected}
          disabled={selectedIds.size === 0}
        >
          清空所有选中
        </button>
        <button
          class="btn-primary"
          on:click={openLendModal}
          disabled={loading || selectedIds.size === 0}
        >
          批量借出
        </button>
        <button
          class="btn-secondary"
          on:click={openReturnModal}
          disabled={loading || selectedIds.size === 0}
        >
          批量归还
        </button>
        <button class="btn-primary" on:click={loadInventoryList} disabled={loading}>
          {loading ? '刷新中...' : '刷新数据'}
        </button>

        <!-- 批量操作组件（仅传递读取类参数，无修改权限） -->
        <BatchOperations
          {selectedItems}
          {batchLoading}
          {loading}
          {showMessage}
          refreshInventory={loadInventoryList}
          clearAllSelected={clearAllSelected}
          {getRealTimeStock}
        />

        <button class="btn-secondary" on:click={exportInventoryCSV} disabled={loading || filteredInventoryList.length === 0}>
          导出CSV
        </button>

        <!-- 新增：撤销操作组件 -->
        <UndoButton
          {api}
          {showMessage}
          parentLoading={loading}
          loadInventoryList={loadInventoryList}
          buttonText="撤销操作"
          apiBaseUrl="http://localhost:5000"
        />
      </div>
    </div>

  {#if loading && inventoryList.length === 0}
    <div class="loading-state">加载中...</div>
  {:else if paginatedInventoryList.length > 0}
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th class="checkbox-header">
              <input
                type="checkbox"
                checked={isAllSelected}
                on:change={toggleSelectAll}
                disabled={paginatedInventoryList.length === 0}
              />
            </th>
            <th>库存ID</th>
            <th>货号</th>
            <!-- 图片列 -->
            <th class="image-header">图片</th>
            <th>备注</th>
            <th>商品类型</th>
            <th>累计入库</th>
            <th>累计出库</th>
            <th>当前库存</th>
            <th>状态</th>
            <th>单价</th>
            <th>重量</th>
            <th>厂家</th>
            <th>材质</th>
            <th>颜色</th>
            <th>位置信息</th>
            <th class="actions-header">操作</th>
          </tr>
        </thead>
        <tbody>
          {#each paginatedInventoryList as item (item.库存ID)}
            <tr>
              <td class="checkbox-cell">
                <input
                  type="checkbox"
                  checked={selectedIds.has(item.库存ID)}
                  on:change={() => toggleSelectItem(item)}
                  disabled={item.状态 === '已出库'}
                />
              </td>
              <td>{item.库存ID}</td>
              <td>{item.商品信息?.货号 || '-'}</td>
              <!-- 图片列：传入后端返回的图片相对路径 -->
              <td class="image-cell">
                {console.log('当前库存项:', item.商品特征ID, '完整数据:', item)}
                <InventoryImage imagePath={item.特征信息?.图片路径}
                featureId={item.特征信息?.商品特征ID}
                relatedProductId={item.商品信息?.货号 || ''}
                inventoryId={item.库存ID}
                updateInventory={api.updateInventory}
                showMessage={showMessage}
                onRefresh={loadInventoryList}
                />
              </td>
              <td class="remark-cell">{item.商品信息?.备注 || '-'}</td>
              <td>{item.商品信息?.类型 || '-'}</td>
              <td>{getTotalInQuantity(item)}</td>
              <td>{getTotalOutQuantity(item)}</td>
              <td>{getCurrentStock(item)}</td>
              <td>
                <span class:status-normal={item.状态 === '正常'}
                      class:status-out={item.状态 === '已出库'}
                      class:status-error={item.状态 === '异常'}>
                  {item.状态}
                </span>
              </td>
              <td>{item.特征信息?.单价 || '-'}</td>
              <td>{item.特征信息?.重量 || '-'}</td>
              <td>{item.厂家信息?.厂家 || '-'}</td>
              <td>{item.特征信息?.材质 || '-'}</td>
              <td>{item.特征信息?.颜色 || '-'}</td>
              <td>{getAddressString(item)}</td>
              <td class="actions">
                <button class="btn-info" on:click={() => viewInventoryDetail(item)}
                        disabled={detailLoading} title="查看详情">
                  {detailLoading && selectedInventory?.库存ID === item.库存ID ? '加载中...' : '详情'}
                </button>
                <button class="btn-edit" on:click={() => openEditModal(item)} title="编辑">
                  编辑
                </button>
                <button class="btn-delete" on:click={() => openDeleteModal(item)} title="删除">
                  删除
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- 分页控件（仅展示切换，无数据修改） -->
    {#if totalPages > 1}
      <div class="pagination">
        <button class="pagination-btn" disabled={currentPage === 1} on:click={() => goToPage(1)}>
          首页
        </button>
        <button class="pagination-btn" disabled={currentPage === 1} on:click={() => goToPage(currentPage - 1)}>
          上一页
        </button>

        {#each Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
          let page = currentPage <= 3 ? i + 1 :
                    currentPage >= totalPages - 2 ? totalPages - 4 + i :
                    currentPage - 2 + i;
          if (page > 0 && page <= totalPages) {
            return page;
          }
        }).filter(Boolean) as page}
          <button class="pagination-btn {currentPage === page ? 'active' : ''}" on:click={() => goToPage(page)}>
            {page}
          </button>
        {/each}

        <button class="pagination-btn" disabled={currentPage === totalPages} on:click={() => goToPage(currentPage + 1)}>
          下一页
        </button>
        <button class="pagination-btn" disabled={currentPage === totalPages} on:click={() => goToPage(totalPages)}>
          末页
        </button>

        <span class="pagination-info">
          第 {currentPage} 页，共 {totalPages} 页
        </span>
      </div>
    {/if}
  {:else if inventoryList.length === 0}
    <div class="no-data">
      暂无库存数据
    </div>
  {:else}
    <div class="no-data">
      没有找到匹配的库存记录，请调整筛选条件
    </div>
  {/if}
</section>

<!-- 模态框组件（仅传递读取类数据，无修改权限） -->
<EditModal
  {showEditModal}
  {editingInventory}
  {editForm}
  {loading}
  {productTypes}
  {floors}
  {showMessage}
  onClose={closeEditModal}
  onSave={saveEdit}
/>

<DeleteModal
  {showDeleteModal}
  {selectedInventory}
  {loading}
  {showMessage}
  onClose={closeDeleteModal}
  onConfirm={confirmDelete}
/>

<InventoryDetailModal
  {showInventoryDetailModal}
  {selectedInventory}
  {detailLoading}
  {inventoryOperations}
  {showMessage}
  onClose={closeInventoryDetailModal}
/>

<!-- 批量借出模态框（仅传递读取类参数） -->
<BatchLendModal
  bind:show={showLendModal}
  bind:selectedItems={selectedItems}
  loading={lendLoading}
  {showMessage}
  {getRealTimeStock}
  onClose={closeLendModal}
  onConfirm={confirmLend}
/>

<!-- 批量归还模态框（仅传递读取类参数） -->
<BatchReturnModal
  show={showReturnModal}
  loading={returnLoading}
  {selectedItems}
  {showMessage}
  onClose={closeReturnModal}
  onConfirm={confirmReturn}
/>

<style>
  /* 样式优化：更紧凑的布局 */
  .inventory-section {
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    padding: 16px;
    box-sizing: border-box;
    background: #f5f7fa;
  }

  .inventory-section h2 {
    color: #2c3e50;
    margin-bottom: 20px;
    font-size: 1.4rem;
    flex-shrink: 0;
    font-weight: 600;
  }

  /* 筛选区域样式 - 更紧凑 */
  .filter-section {
    background: white;
    padding: 16px;
    border-radius: 12px;
    margin-bottom: 15px;
    border: 1px solid #e4e7ed;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  .filter-section h3 {
    margin-bottom: 12px;
    color: #495057;
    font-size: 1rem;
    font-weight: 600;
    display: flex;
    align-items: center;
  }

  .filter-section h3::before {
    content: '';
    width: 4px;
    height: 16px;
    background: #3498db;
    margin-right: 8px;
    border-radius: 2px;
  }

  .filter-form {
    width: 100%;
  }

  .form-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
    margin-bottom: 15px;
  }

  .form-group {
    margin-bottom: 0;
  }

  label {
    display: block;
    margin-bottom: 6px;
    font-weight: 500;
    color: #555;
    font-size: 13px;
  }

  input, select {
    width: 100%;
    padding: 8px 10px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 13px;
    transition: all 0.3s ease;
    background: white;
    color: #333;
  }

  input:focus, select:focus {
    outline: none;
    border-color: #3498db;
    box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
  }

  input::placeholder {
    color: #999;
  }

  .filter-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 15px;
    padding-top: 15px;
    border-top: 1px solid #eaeaea;
  }

  /* 按钮样式 - 更紧凑 */
  .btn-primary, .btn-danger, .btn-secondary, .btn-outline, .btn-info, .btn-edit, .btn-delete {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .btn-primary {
    background: linear-gradient(135deg, #3498db, #2980b9);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #2980b9, #1f639b);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(52, 152, 219, 0.2);
  }

  .btn-danger {
    background: linear-gradient(135deg, #e74c3c, #c0392b);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background: linear-gradient(135deg, #c0392b, #a93226);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(231, 76, 60, 0.2);
  }

  .btn-secondary {
    background: linear-gradient(135deg, #95a5a6, #7f8c8d);
    color: white;
  }

  .btn-secondary:hover:not(:disabled) {
    background: linear-gradient(135deg, #7f8c8d, #6c7b7d);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(149, 165, 166, 0.2);
  }

  .btn-outline {
    background: transparent;
    border: 2px solid #bdc3c7;
    color: #7f8c8d;
  }

  .btn-outline:hover:not(:disabled) {
    background: #f8f9fa;
    border-color: #3498db;
    color: #3498db;
    transform: translateY(-2px);
  }

  .btn-info {
    background: linear-gradient(135deg, #3498db, #2980b9);
    color: white;
  }

  .btn-info:hover:not(:disabled) {
    background: linear-gradient(135deg, #2980b9, #1f639b);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(52, 152, 219, 0.2);
  }

  .btn-edit {
    background: linear-gradient(135deg, #f39c12, #e67e22);
    color: white;
  }

  .btn-edit:hover:not(:disabled) {
    background: linear-gradient(135deg, #e67e22, #d35400);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(243, 156, 18, 0.2);
  }

  .btn-delete {
    background: linear-gradient(135deg, #e74c3c, #c0392b);
    color: white;
  }

  .btn-delete:hover:not(:disabled) {
    background: linear-gradient(135deg, #c0392b, #a93226);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(231, 76, 60, 0.2);
  }

  .btn-primary:disabled, .btn-danger:disabled, .btn-secondary:disabled, .btn-outline:disabled, .btn-info:disabled, .btn-edit:disabled, .btn-delete:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  /* 操作按钮和分页控制样式 - 更紧凑 */
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    padding: 12px 16px;
    background: white;
    border-radius: 12px;
    border: 1px solid #e4e7ed;
    flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  .section-info {
    font-weight: 600;
    color: #495057;
    font-size: 14px;
  }

  .selected-count {
    margin-left: 12px;
    padding: 4px 10px;
    background: #e7f3ff;
    color: #0066cc;
    border-radius: 6px;
    font-size: 13px;
    font-weight: normal;
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  /* 清空选中按钮样式 */
  .clear-selected-btn {
    padding: 2px 6px;
    border: none;
    background: #ff4444;
    color: white;
    border-radius: 50%;
    cursor: pointer;
    font-size: 12px;
    line-height: 1;
    width: 18px;
    height: 18px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  .clear-selected-btn:hover {
    background: #cc0000;
  }

  /* 清空所有选中按钮（独立） */
  .clear-all-selected-btn {
    padding: 6px 12px !important;
    font-size: 12px !important;
  }

  .section-controls {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .pagination-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #f8f9fa;
    padding: 6px 10px;
    border-radius: 8px;
  }

  .pagination-controls label {
    margin: 0;
    font-weight: 500;
    color: #495057;
    font-size: 13px;
  }

  .pagination-controls select {
    width: auto;
    padding: 4px 8px;
    border-radius: 6px;
    background: white;
    border: 1px solid #ced4da;
    font-size: 12px;
  }

  /* 表格样式 - 更紧凑 */
  .table-container {
    overflow-x: auto;
    border-radius: 12px;
    border: 1px solid #e4e7ed;
    flex: 1;
    min-height: 0;
    background: white;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  .data-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 12px;
    min-width: 1400px;
  }

  .data-table th {
    background: #f8f9fa;
    padding: 10px 6px;
    text-align: left;
    font-weight: 600;
    color: #2c3e50;
    border-bottom: 2px solid #e4e7ed;
    position: sticky;
    top: 0;
    z-index: 10;
    white-space: nowrap;
    font-size: 12px;
  }

  .data-table td {
    padding: 8px 6px;
    border-bottom: 1px solid #e4e7ed;
    color: #495057;
    font-size: 12px;
  }

  .data-table tr:hover {
    background: #f8f9fa;
  }

  /* 图片列样式 */
  .image-header {
    width: 60px;
    text-align: center;
    padding: 10px 4px;
  }

  .image-cell {
    width: 60px;
    text-align: center;
    vertical-align: middle;
    padding: 8px 4px;
  }

  /* 备注列样式 - 自动换行 */
  .remark-cell {
    max-width: 100px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    cursor: help;
  }

  .status-normal {
    color: #27ae60;
    font-weight: 500;
    padding: 2px 6px;
    background: rgba(39, 174, 96, 0.1);
    border-radius: 4px;
    font-size: 11px;
  }

  .status-out {
    color: #e74c3c;
    font-weight: 500;
    padding: 2px 6px;
    background: rgba(231, 76, 60, 0.1);
    border-radius: 4px;
    font-size: 11px;
  }

  .status-error {
    color: #f39c12;
    font-weight: 500;
    padding: 2px 6px;
    background: rgba(243, 156, 18, 0.1);
    border-radius: 4px;
    font-size: 11px;
  }

  /* 操作列样式 - 更紧凑 */
  .actions-header {
    width: 160px;
    text-align: center;
  }

  .actions {
    display: flex;
    gap: 6px;
    justify-content: center;
    flex-wrap: wrap;
  }

  .actions button {
    padding: 4px 8px;
    font-size: 12px;
    margin: 0;
    min-width: 50px;
  }

  /* 复选框列样式 - 更紧凑 */
  .checkbox-header, .checkbox-cell {
    width: 40px;
    text-align: center;
    vertical-align: middle;
  }

  .checkbox-header input, .checkbox-cell input {
    width: 16px;
    height: 16px;
    cursor: pointer;
    border-radius: 4px;
    border: 2px solid #bdc3c7;
    transition: all 0.3s ease;
  }

  .checkbox-header input:checked, .checkbox-cell input:checked {
    background-color: #3498db;
    border-color: #3498db;
  }

  /* 分页样式 - 更紧凑 */
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 6px;
    margin-top: 15px;
    padding: 12px;
    flex-shrink: 0;
    background: white;
    border-radius: 12px;
    border: 1px solid #e4e7ed;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  .pagination-btn {
    padding: 6px 10px;
    border: 1px solid #dee2e6;
    background: white;
    color: #495057;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.3s ease;
    font-size: 12px;
    min-width: 36px;
  }

  .pagination-btn:hover:not(:disabled) {
    background: #f8f9fa;
    border-color: #3498db;
    color: #3498db;
    transform: translateY(-2px);
  }

  .pagination-btn.active {
    background: #3498db;
    color: white;
    border-color: #3498db;
    font-weight: 600;
  }

  .pagination-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background: #f8f9fa;
  }

  .pagination-info {
    margin-left: 15px;
    color: #6c757d;
    font-size: 12px;
    font-weight: 500;
  }

  .no-data {
    text-align: center;
    padding: 60px 20px;
    color: #7f8c8d;
    font-style: italic;
    font-size: 14px;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: white;
    border-radius: 12px;
    border: 1px solid #e4e7ed;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  .loading-state {
    text-align: center;
    padding: 60px 20px;
    color: #3498db;
    font-size: 14px;
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    background: white;
    border-radius: 12px;
    border: 1px solid #e4e7ed;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  }

  /* 批量操作按钮组样式 */
  .batch-operations-group {
    display: flex;
    gap: 8px;
  }

  /* 响应式设计 - 适配小屏幕 */
  @media (max-width: 1200px) {
    .section-header {
      flex-direction: column;
      gap: 15px;
      align-items: stretch;
    }

    .section-controls {
      flex-wrap: wrap;
      justify-content: center;
    }

    .form-row {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 768px) {
    .inventory-section {
      padding: 10px;
      height: auto;
      min-height: 100vh;
    }

    .actions {
      flex-direction: column;
      align-items: stretch;
    }

    .actions button {
      width: 100%;
      margin-bottom: 4px;
    }

    .pagination {
      flex-wrap: wrap;
      gap: 4px;
      padding: 10px;
    }

    .pagination-info {
      margin-left: 0;
      margin-top: 8px;
      text-align: center;
      width: 100%;
    }

    .data-table {
      font-size: 11px;
    }

    .data-table th,
    .data-table td {
      padding: 6px 4px;
    }
  }

  @media (max-width: 480px) {
    .inventory-section h2 {
      font-size: 1.2rem;
    }

    .filter-section {
      padding: 12px;
    }

    .btn-primary, .btn-danger, .btn-secondary, .btn-outline, .btn-info, .btn-edit, .btn-delete {
      padding: 6px 12px;
      font-size: 12px;
    }
  }
</style>