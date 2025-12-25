<script lang="ts">
  import { onMount } from 'svelte';
  // 导入子组件
  import SingleStockIn from './SingleStockIn.svelte';
  import BatchStockIn from './BatchStockIn.svelte';
  // 导入共享CSS（根据项目配置调整导入方式）
  import './stock-in-shared.css';
  // 导入API类型（若需要）
  import type { ApiSuccessResponse } from '../lib/api.ts';
  import { api } from '../lib/api.ts';

  // ========== 公共类型定义 ==========
  type ActiveTab = 'batch' | 'single';
  interface LastAddressInfo {
    架号: string;
    框号: string;
    包号: string;
  }

  // ========== Props 定义（带类型注解） ==========
  export let productTypes: string[] = [];
  export let floors: number[] = [];
  export let loading: boolean = false;
  export let showMessage: (text: string, type?: 'info' | 'success' | 'error' | 'warning') => void = () => {};
  export let debounce: <T extends (...args: any[]) => any>(func: T, wait: number) => T = (func) => func as any;

  // ========== 公共状态 ==========
  let activeTab: ActiveTab = 'batch';
  let lastAddressInfo: LastAddressInfo = {
    架号: '',
    框号: '',
    包号: ''
  };
  let hasInitialized: boolean = false;

  // ========== 公共函数 ==========
  async function fetchLastAddressInfo(addressType: number, formType: 'single' | 'batch' = 'single'): Promise<void> {
    if (!addressType) return;

    try {
      loading = true;
      const response = await api.getLastAddressInfo({
        地址类型: parseInt(addressType.toString())
      }) as ApiSuccessResponse<LastAddressInfo>;

      if (response.status === 'success') {
        lastAddressInfo = {
          架号: response.data?.架号 || '',
          框号: response.data?.框号 || '',
          包号: response.data?.包号 || ''
        };
        hasInitialized = true;
      }
    } catch (error) {
      console.error('获取最后地址信息失败:', error);
      showMessage('获取默认地址失败', 'error');
    } finally {
      loading = false;
    }
  }

  // 页面加载初始化
  onMount(() => {
    // 初始加载默认地址（可选）
    fetchLastAddressInfo(5);
  });

  // 更新loading状态的回调
  function updateLoading(status: boolean) {
    loading = status;
  }
</script>

<!-- 核心修改：添加根容器 stock-in-container，包裹所有模板内容 -->
<div class="stock-in-container">
  <section class="form-section">
    <!-- 选项卡导航 -->
    <div class="tab-nav">
      <button
        class:active={activeTab === 'single'}
        on:click={() => activeTab = 'single'}
        disabled={loading}
      >
        多特征入库
      </button>
      <button
        class:active={activeTab === 'batch'}
        on:click={() => activeTab = 'batch'}
        disabled={loading}
      >
        单号/连号入库
      </button>
    </div>

    <!-- 子组件渲染 -->
    {#if activeTab === 'single'}
      <SingleStockIn
        {productTypes}
        {floors}
        {loading}
        {showMessage}
        {debounce}
        {lastAddressInfo}
        {hasInitialized}
        fetchLastAddressInfo={fetchLastAddressInfo}
        updateLoading={updateLoading}
      />
    {:else}
      <BatchStockIn
        {productTypes}
        {floors}
        {loading}
        {showMessage}
        {debounce}
        {lastAddressInfo}
        {hasInitialized}
        fetchLastAddressInfo={fetchLastAddressInfo}
        updateLoading={updateLoading}
      />
    {/if}
  </section>
</div>