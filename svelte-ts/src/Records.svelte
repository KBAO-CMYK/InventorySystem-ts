<script lang="ts">
  import type { ApiInstance, ApiErrorHandler } from './lib/api.ts'; // 假设api有类型声明，无则声明为any
  import { api, handleApiError } from './lib/api.ts'
  import { onMount } from 'svelte'

  // ========== 核心接口定义 ==========
  /** 操作筛选条件接口 */
  interface OperationFilter {
    operation_type: string;
    inventory_id: string;
    product_code: string;
    product_type: string;
    operator: string;
    start_date_date: string; // 开始日期（YYYY-MM-DD）
    start_date_hour: string; // 开始小时（0-23）
    end_date_date: string;   // 结束日期（YYYY-MM-DD）
    end_date_hour: string;   // 结束小时（0-23）
  }

  /** 操作记录接口（覆盖所有字段） */
  interface OperationRecord {
    操作ID: string | number;
    关联库存ID: string | number;
    操作类型: string;
    操作数量: number | string;
    操作时间: string;
    操作人: string;
    备注: string;
    商品ID: string | number;
    商品编号: string;
    商品名称: string;
    类型: string;
    库存数量: number | string;
    次品数量: number | string;
    批次: string;
    状态: string;
    单位: string;
    特征ID: string | number;
    单价: number | string;
    重量: number | string;
    规格: string;
    材质: string;
    颜色: string;
    形状: string;
    风格: string;
    位置ID: string | number;
    地址类型: string;
    楼层: string;
    架号: string;
    框号: string;
    包号: string;
    厂家ID: string | number;
    厂家: string;
    厂家地址: string;
    电话: string;
  }

  /** 缓存项接口 */
  interface DataCacheItem {
    data: OperationRecord[];
    timestamp: number;
  }

  /** 防抖函数返回类型（包含cancel方法） */
  interface DebouncedFunction<T extends (...args: any[]) => any> {
    (...args: Parameters<T>): void;
    cancel?: () => void;
  }

  // ========== 导出Props类型注解 ==========
  export let productTypes: any[] = [];
  export let loading: boolean = false;
  export let showMessage: (message: string, type: 'success' | 'error' | 'warning' | 'info') => void = () => {};

  /** 防抖函数（带类型注解） */
  export let debounce: <T extends (...args: any[]) => any>(func: T, wait: number) => DebouncedFunction<T> = (func, wait) => {
    let timeout: NodeJS.Timeout;
    const debouncedFunc = function executedFunction(...args: Parameters<T>) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
    // 增加cancel方法
    debouncedFunc.cancel = () => clearTimeout(timeout);
    return debouncedFunc;
  };

  export let dataCache: Record<string, DataCacheItem> = {};

  // ========== 常量定义 ==========
  const CACHE_DURATION: number = 5 * 60 * 1000; // 5分钟
  const operationTypes: string[] = ['入库', '出库', '借', '还', '次品退回'];

  // ========== 变量类型注解 ==========
  /** 筛选条件（新增日期+小时字段） */
  let operationFilter: OperationFilter = {
    operation_type: '',
    inventory_id: '',
    product_code: '',
    product_type: '',
    operator: '',
    start_date_date: '',
    start_date_hour: '',
    end_date_date: '',
    end_date_hour: ''
  };

  // ========== 替换为库存管理同款分页变量 ==========
  let currentPage: number = 1;
  let itemsPerPage: number = 10;
  let totalPages: number = 1;
  let paginatedRecords: OperationRecord[] = [];
  let sortField: string = '操作时间';
  let sortDirection: 'asc' | 'desc' = 'desc';
  let operationRecords: OperationRecord[] = [];
  let filteredOperationRecords: OperationRecord[] = [];
  let selectedRecords: OperationRecord[] = [];
  let isAllSelected: boolean = false;

  // ========== 防抖函数实例 ==========
  const debouncedApplyOperationFilter: DebouncedFunction<() => void> = debounce(() => {
    applyOperationFilter();
  }, 300);

  const debouncedLoadOperationRecords: DebouncedFunction<() => void> = debounce(() => {
    loadOperationRecords();
  }, 500);

  // ========== 核心函数类型注解 ==========
  /** 解析YYYY-MM-DD HH格式为Date对象（兼容ISO格式） */
  function parseDateTimeWithHour(dateStr: string): Date | null {
    if (!dateStr) return null;
    try {
      // 先兼容ISO格式（如2025-12-13T14:00:00）
      let date = new Date(dateStr);
      if (!isNaN(date.getTime())) return date;

      // 解析YYYY-MM-DD HH格式
      const [datePart, hourPart] = dateStr.split(' ');
      if (!datePart || !hourPart) return null;
      const isoStr = `${datePart}T${String(hourPart).padStart(2, '0')}:00:00`;
      date = new Date(isoStr);
      return isNaN(date.getTime()) ? null : date;
    } catch (e) {
      console.warn('日期解析失败:', e, dateStr);
      return null;
    }
  }

  /**
   * 拼接日期+小时为YYYY-MM-DD HH格式
   * @param date 日期字符串（YYYY-MM-DD）
   * @param hour 小时字符串（0-23）
   * @param type 时间类型：'start'（开始时间）| 'end'（结束时间）
   * @returns 标准时间字符串，无日期时返回空字符串（兼容原有逻辑）
   */
  function getCombinedDateTime(date: string, hour: string, type: 'start' | 'end'): string {
    if (!date) return '';
    // 处理小时：有值则补零，无值则按类型默认（开始→00，结束→23）
    const hourStr = hour
      ? String(Number(hour)).padStart(2, '0')
      : type === 'start' ? '00' : '23';
    return `${date} ${hourStr}`;
  }

  function generateCacheKey(filter: OperationFilter): string {
    const filterStr = Object.entries(filter)
      .sort(([k1], [k2]) => k1.localeCompare(k2))
      .map(([k, v]) => `${k}=${v || 'empty'}`)
      .join('|');
    return `operation_${btoa(filterStr)}`;
  }

  async function loadOperationRecords(forceRefresh: boolean = false): Promise<void> {
    const now = Date.now();
    const cacheKey = generateCacheKey(operationFilter);

    if (!forceRefresh && dataCache[cacheKey] && dataCache[cacheKey].data &&
        now - dataCache[cacheKey].timestamp < CACHE_DURATION) {
      operationRecords = dataCache[cacheKey].data;
      applyOperationFilter();
      return;
    }

    loading = true;
    try {
      const params: Record<string, string> = {};
      if (operationFilter.operation_type) params.operation_type = operationFilter.operation_type;
      if (operationFilter.inventory_id) params.inventory_id = operationFilter.inventory_id;

      // 【修复】传入type参数区分开始/结束时间
      if (operationFilter.start_date_date) {
        params.start_date = getCombinedDateTime(operationFilter.start_date_date, operationFilter.start_date_hour, 'start');
      }
      if (operationFilter.end_date_date) {
        params.end_date = getCombinedDateTime(operationFilter.end_date_date, operationFilter.end_date_hour, 'end');
      }

      // 类型断言：适配API返回值
      const result = await api.getOperationRecords(params) as {
        status: 'success' | 'error';
        data?: any[];
        message?: string;
      };

      if (result.status === 'success') {
        if (result.data && Array.isArray(result.data)) {
          const firstItem = result.data[0];
          if (firstItem && firstItem.operation) {
            // 修复：拆分类型断言，避免紧凑写法导致解析错误
            operationRecords = result.data.map(item => {
              const operation = item.operation || {};
              const productInfo = item.product_info || {};
              const inventoryInfo = item.inventory_info || {};
              const featureInfo = item.feature_info || {};
              const locationInfo = item.location_info || {};
              const manufacturerInfo = item.manufacturer_info || {};

              // 先创建对象，再赋值给变量，最后断言（兼容Svelte解析）
              const record: OperationRecord = {
                操作ID: operation.操作ID || '',
                关联库存ID: operation.关联库存ID || '',
                操作类型: operation.操作类型 || '',
                操作数量: operation.操作数量 || 0,
                操作时间: operation.操作时间 || '',
                操作人: operation.操作人 || '',
                备注: operation.备注 || '',
                商品ID: productInfo.商品ID || '',
                商品编号: productInfo.货号 || productInfo.商品编号 || '',
                商品名称: productInfo.商品名称 || '',
                类型: productInfo.类型 || productInfo.类型 || '',
                库存数量: inventoryInfo.库存数量 || 0,
                次品数量: inventoryInfo.次品数量 || 0,
                批次: inventoryInfo.批次 || '',
                状态: inventoryInfo.状态 || '',
                单位: inventoryInfo.单位 || '',
                特征ID: featureInfo.商品特征ID || featureInfo.特征ID || '',
                单价: featureInfo.单价 || 0,
                重量: featureInfo.重量 || 0,
                规格: featureInfo.规格 || '',
                材质: featureInfo.材质 || '',
                颜色: featureInfo.颜色 || '',
                形状: featureInfo.形状 || '',
                风格: featureInfo.风格 || '',
                位置ID: locationInfo.地址ID || locationInfo.位置ID || '',
                地址类型: locationInfo.地址类型 || '',
                楼层: locationInfo.楼层 || '',
                架号: locationInfo.架号 || '',
                框号: locationInfo.框号 || '',
                包号: locationInfo.包号 || '',
                厂家ID: manufacturerInfo.厂家ID || '',
                厂家: manufacturerInfo.厂家 || '',
                厂家地址: manufacturerInfo.厂家地址 || '',
                电话: manufacturerInfo.电话 || ''
              };
              return record;
            });
          } else {
            // 修复核心错误：改用类型注解（而非紧凑as断言），避免Svelte解析失败
            operationRecords = result.data.map(record => {
              // 显式类型注解，替代紧凑的as断言
              const opRecord: OperationRecord = {
                操作ID: record.操作ID || '',
                关联库存ID: record.关联库存ID || '',
                操作类型: record.操作类型 || '',
                操作数量: record.操作数量 || 0,
                操作时间: record.操作时间 || '',
                操作人: record.操作人 || '',
                备注: record.备注 || '',
                商品ID: record.商品ID || '',
                商品编号: record.商品编号 || '',
                商品名称: record.商品名称 || '',
                类型: record.类型 || '',
                库存数量: record.库存数量 || 0,
                次品数量: record.次品数量 || 0,
                批次: record.批次 || '',
                状态: record.状态 || '',
                单位: record.单位 || '',
                特征ID: record.特征ID || '',
                单价: record.单价 || 0,
                重量: record.重量 || 0,
                规格: record.规格 || '',
                材质: record.材质 || '',
                颜色: record.颜色 || '',
                形状: record.形状 || '',
                风格: record.风格 || '',
                位置ID: record.位置ID || '',
                地址类型: record.地址类型 || '',
                楼层: record.楼层 || '',
                架号: record.架号 || '',
                框号: record.框号 || '',
                包号: record.包号 || '',
                厂家ID: record.厂家ID || '',
                厂家: record.厂家 || '',
                厂家地址: record.厂家地址 || '',
                电话: record.电话 || ''
              };
              return opRecord;
            });
          }
        } else {
          operationRecords = [];
        }

        dataCache[cacheKey] = { data: [...operationRecords], timestamp: now };
        applyOperationFilter();
        selectedRecords = [];
        isAllSelected = false;
      } else {
        throw new Error(result.message || '获取操作记录失败');
      }
    } catch (error) {
      console.error('加载操作记录失败:', error);
      showMessage(handleApiError(error as Error, '加载操作记录失败'), 'error');
      operationRecords = [];
      applyOperationFilter();
    } finally {
      loading = false;
    }
  }

  function sortRecords(records: OperationRecord[]): OperationRecord[] {
    if (!records.length) return records;

    const field = sortField;
    const direction = sortDirection;

    return [...records].sort((a, b) => {
      let valueA = a[field];
      let valueB = b[field];

      if (valueA === null || valueA === undefined) valueA = '';
      if (valueB === null || valueB === undefined) valueB = '';

      if (field === '操作时间') {
        try {
          const dateA = parseDateTimeWithHour(String(valueA))?.getTime() || 0;
          const dateB = parseDateTimeWithHour(String(valueB))?.getTime() || 0;
          return direction === 'asc' ? dateA - dateB : dateB - dateA;
        } catch (e) {
          console.warn('日期排序失败:', e);
        }
      } else if (field === '操作数量' || field === '操作ID' || field === '关联库存ID') {
        const numA = Number(valueA) || 0;
        const numB = Number(valueB) || 0;
        return direction === 'asc' ? numA - numB : numB - numA;
      } else {
        const strA = String(valueA).toLowerCase();
        const strB = String(valueB).toLowerCase();
        return direction === 'asc'
          ? strA.localeCompare(strB)
          : strB.localeCompare(strA);
      }

      return 0;
    });
  }

  function toggleSort(field: string): void {
    if (sortField === field) {
      sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      sortField = field;
      sortDirection = 'desc';
    }
    applyOperationFilter();
  }

  function getSortIndicator(field: string): string {
    if (sortField !== field) return '';
    return sortDirection === 'asc' ? ' ↑' : ' ↓';
  }

  function applyOperationFilter(): void {
    const filter = { ...operationFilter };
    const records = [...operationRecords];

    const hasActiveFilter = Object.entries(filter).some(([key, value]) => {
      if (!value || value === '') return false;
      return true;
    });

    if (!hasActiveFilter) {
      filteredOperationRecords = [...records];
    } else {
      filteredOperationRecords = records.filter(record => {
        if (filter.operation_type && record.操作类型 !== filter.operation_type) {
          return false;
        }

        if (filter.inventory_id &&
            String(record.关联库存ID).trim() !== String(filter.inventory_id).trim()) {
          return false;
        }

        if (filter.product_code) {
          const recordCode = record?.商品编号 || '';
          const inputCode = filter.product_code.toLowerCase().trim();
          const normalizedRecordCode = recordCode.toLowerCase().trim();
          if (!normalizedRecordCode.includes(inputCode)) {
            return false;
          }
        }

        if (filter.product_type && record.类型 !== filter.product_type) {
          return false;
        }

        if (filter.operator) {
          const operator = record.操作人?.toLowerCase() || '';
          if (!operator.includes(filter.operator.toLowerCase().trim())) {
            return false;
          }
        }

        // 【修复】传入type参数区分开始/结束时间，确保默认小时正确
        const startDateTime = getCombinedDateTime(filter.start_date_date, filter.start_date_hour, 'start');
        const endDateTime = getCombinedDateTime(filter.end_date_date, filter.end_date_hour, 'end');

        // 开始时间筛选（精确到小时）
        if (startDateTime && record.操作时间) {
          const recordDate = parseDateTimeWithHour(record.操作时间);
          const startDate = parseDateTimeWithHour(startDateTime);
          if (recordDate && startDate && recordDate < startDate) {
            return false;
          }
        }

        // 结束时间筛选（精确到小时）
        if (endDateTime && record.操作时间) {
          const recordDate = parseDateTimeWithHour(record.操作时间);
          const endDate = parseDateTimeWithHour(endDateTime);
          if (recordDate && endDate && recordDate > endDate) {
            return false;
          }
        }

        return true;
      });
    }

    filteredOperationRecords = sortRecords(filteredOperationRecords);
    updatePagination(); // 替换后：调用新的分页更新方法
    updateSelectAllState();
  }

  // ========== 替换为库存管理同款分页方法 ==========
  function updatePagination(): void {
    totalPages = Math.ceil(filteredOperationRecords.length / itemsPerPage) || 1;
    currentPage = Math.min(currentPage, totalPages);
    currentPage = Math.max(1, currentPage);

    const startIndex = (currentPage - 1) * itemsPerPage;
    const endIndex = startIndex + itemsPerPage;
    paginatedRecords = filteredOperationRecords.slice(startIndex, endIndex);
  }

  function goToPage(page: number): void {
    currentPage = page;
    updatePagination();
  }

  function changeItemsPerPage(value: string): void {
    itemsPerPage = parseInt(value);
    currentPage = 1;
    updatePagination();
  }

  /** 清空筛选条件时重置日期+小时字段 */
  function clearOperationFilter(): void {
    operationFilter = {
      operation_type: '',
      inventory_id: '',
      product_code: '',
      product_type: '',
      operator: '',
      start_date_date: '',
      start_date_hour: '',
      end_date_date: '',
      end_date_hour: ''
    };
    currentPage = 1;
    loadOperationRecords();
  }

  async function exportOperationCSV(): Promise<void> {
    if (filteredOperationRecords.length === 0) {
      showMessage('没有数据可导出', 'warning');
      return;
    }

    loading = true;
    try {
      const exportParams: Record<string, string> = {};
      if (operationFilter.operation_type) {
        exportParams.operation_type = operationFilter.operation_type;
      }
      if (operationFilter.inventory_id) exportParams.inventory_id = operationFilter.inventory_id;
      // 【修复】传入type参数区分开始/结束时间
      if (operationFilter.start_date_date) {
        exportParams.start_date = getCombinedDateTime(operationFilter.start_date_date, operationFilter.start_date_hour, 'start');
      }
      if (operationFilter.end_date_date) {
        exportParams.end_date = getCombinedDateTime(operationFilter.end_date_date, operationFilter.end_date_hour, 'end');
      }

      const result = await api.exportOperationRecordsCSV(exportParams) as {
        success: boolean;
        filename?: string;
      };
      if (result && result.success) {
        showMessage(`导出成功: ${result.filename}`, 'success');
      } else {
        showMessage('导出失败，未获取到数据', 'error');
      }
    } catch (error) {
      console.error('导出CSV失败:', error);
      showMessage(handleApiError(error as Error, '导出失败'), 'error');
    } finally {
      loading = false;
    }
  }

  async function exportSelectedOperationCSV(): Promise<void> {
    if (selectedRecords.length === 0) {
      showMessage('请先选择要导出的记录', 'warning');
      return;
    }

    loading = true;
    try {
      await exportSelectedRecordsAsCSV(selectedRecords);
      showMessage(`成功导出 ${selectedRecords.length} 条记录`, 'success');
    } catch (error) {
      console.error('导出选中记录失败:', error);
      showMessage(handleApiError(error as Error, '导出选中记录失败'), 'error');
    } finally {
      loading = false;
    }
  }

  function exportSelectedRecordsAsCSV(records: OperationRecord[]): Promise<void> {
    return new Promise((resolve) => {
      const headers: string[] = [
        '操作ID', '操作类型', '关联库存ID', '操作数量', '操作时间', '操作人', '操作备注',
        '商品编号', '商品名称', '类型',
        '库存数量', '状态', '单位',
        '单价', '规格', '颜色',
        '楼层', '架号', '框号', '包号',
        '厂家'
      ];

      const csvRows = records.map(record => {
        const row = [
          record.操作ID || '',
          record.操作类型 || '',
          record.关联库存ID || '',
          record.操作数量 || '',
          record.操作时间 || '',
          record.操作人 || '',
          record.备注 || '',
          record.商品编号 || '',
          record.商品名称 || '',
          record.类型 || '',
          record.库存数量 || '',
          record.状态 || '',
          record.单位 || '',
          record.单价 || '',
          record.规格 || '',
          record.颜色 || '',
          record.楼层 || '',
          record.架号 || '',
          record.框号 || '',
          record.包号 || '',
          record.厂家 || ''
        ];

        return row.map(field => {
          if (field === null || field === undefined) return '';
          const stringField = String(field);
          if (stringField.includes(',') || stringField.includes('\n') || stringField.includes('"')) {
            return `"${stringField.replace(/"/g, '""')}"`;
          }
          return stringField;
        }).join(',');
      });

      const csvContent = [headers.join(','), ...csvRows].join('\n');
      const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);

      link.setAttribute('href', url);
      let filename = '选中操作记录';
      if (operationFilter.operation_type) {
        filename += `_${operationFilter.operation_type}`;
      }
      filename += `_${new Date().toISOString().split('T')[0]}.csv`;

      link.setAttribute('download', filename);
      link.style.visibility = 'hidden';

      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      resolve();
    });
  }

  function downloadCSVFile(csvContent: string, filename: string): void {
    const bom = new Uint8Array([0xEF, 0xBB, 0xBF]);
    const blob = new Blob([bom, csvContent], { type: 'text/csv;charset=utf-8;' });

    if (navigator.msSaveBlob) {
      navigator.msSaveBlob(blob, filename);
    } else {
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);

      link.href = url;
      link.download = filename;
      link.style.display = 'none';

      document.body.appendChild(link);
      link.click();

      setTimeout(() => {
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }, 100);
    }
  }

  function toggleRecordSelection(record: OperationRecord): void {
    const index = selectedRecords.findIndex(r => r.操作ID === record.操作ID);
    if (index > -1) {
      selectedRecords.splice(index, 1);
    } else {
      selectedRecords = [...selectedRecords, record];
    }
    updateSelectAllState();
  }

  function toggleSelectAll(): void {
    if (isAllSelected) {
      selectedRecords = selectedRecords.filter(selected =>
        !paginatedRecords.some(pageRecord => pageRecord.操作ID === selected.操作ID)
      );
    } else {
      const newSelected = paginatedRecords.filter(pageRecord =>
        !selectedRecords.some(selected => selected.操作ID === pageRecord.操作ID)
      );
      selectedRecords = [...selectedRecords, ...newSelected];
    }
    isAllSelected = !isAllSelected;
  }

  function updateSelectAllState(): void {
    if (paginatedRecords.length === 0) {
      isAllSelected = false;
      return;
    }

    const allInPageSelected = paginatedRecords.every(pageRecord =>
      selectedRecords.some(selected => selected.操作ID === pageRecord.操作ID)
    );

    isAllSelected = allInPageSelected;
  }

  function clearSelection(): void {
    selectedRecords = [];
    isAllSelected = false;
  }

  // ========== 响应式逻辑 ==========
  $: {
    debouncedApplyOperationFilter();
    const apiRelatedFilters = [
      operationFilter.operation_type,
      operationFilter.inventory_id,
      operationFilter.start_date_date,
      operationFilter.end_date_date
    ];
    if (apiRelatedFilters.some(v => v)) {
      debouncedLoadOperationRecords();
    }
  }

  // ========== 生命周期 ==========
  onMount(() => {
    loadOperationRecords();
    return () => {
      debouncedApplyOperationFilter.cancel && debouncedApplyOperationFilter.cancel();
      debouncedLoadOperationRecords.cancel && debouncedLoadOperationRecords.cancel();
    };
  });
</script>

<section class="records-section">
  <h2>操作记录管理</h2>

  <div class="filter-section">
    <h3>筛选条件</h3>
    <div class="filter-form">
      <div class="form-row">
        <div class="form-group">
          <label for="operation_filter_type">操作类型</label>
          <select id="operation_filter_type" bind:value={operationFilter.operation_type}>
            <option value="">全部类型</option>
            {#each operationTypes as type}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label for="operation_filter_inventory_id">库存ID</label>
          <input
            id="operation_filter_inventory_id"
            type="text"
            bind:value={operationFilter.inventory_id}
            placeholder="库存ID"
          />
        </div>
        <div class="form-group">
          <label for="operation_filter_product_code">商品编号</label>
          <input
            id="operation_filter_product_code"
            type="text"
            bind:value={operationFilter.product_code}
            placeholder="货号/商品编号（支持模糊查询）"
          />
        </div>
        <div class="form-group">
          <label for="operation_filter_product_type">类型</label>
          <select id="operation_filter_product_type" bind:value={operationFilter.product_type}>
            <option value="">全部类型</option>
            {#each productTypes as type}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
      </div>

      <div class="form-row">
        <div class="form-group">
          <label for="operation_filter_operator">操作人</label>
          <input
            id="operation_filter_operator"
            type="text"
            bind:value={operationFilter.operator}
            placeholder="操作人"
          />
        </div>
        <!-- 日期+小时输入框 -->
        <div class="form-group">
          <label>开始时间（YYYY-MM-DD HH）</label>
          <input
            type="date"
            bind:value={operationFilter.start_date_date}
            placeholder="选择日期"
            style="width: 100%; margin-bottom: 8px;"
          />
          <input
            type="number"
            bind:value={operationFilter.start_date_hour}
            min="0"
            max="23"
            placeholder="小时(0-23)"
            style="width: 100%;"
          />
        </div>
        <div class="form-group">
          <label>结束时间（YYYY-MM-DD HH）</label>
          <input
            type="date"
            bind:value={operationFilter.end_date_date}
            placeholder="选择日期"
            style="width: 100%; margin-bottom: 8px;"
          />
          <input
            type="number"
            bind:value={operationFilter.end_date_hour}
            min="0"
            max="23"
            placeholder="小时(0-23)"
            style="width: 100%;"
          />
        </div>
      </div>

      <div class="filter-actions">
        <button type="button" class="btn-outline" on:click={clearOperationFilter}>
          清空条件
        </button>
        <button type="button" class="btn-primary" on:click={() => loadOperationRecords(true)} disabled={loading}>
          {loading ? '搜索中...' : '搜索'}
        </button>
      </div>
    </div>
  </div>

  <!-- 替换为库存管理同款操作栏 + 分页控件 -->
  <div class="section-header">
    <div class="section-info">
      共找到 {filteredOperationRecords.length} 条记录
      {#if selectedRecords.length > 0}
        <span class="selected-count">
          已选择 {selectedRecords.length} 项
          <button
            class="clear-selected-btn"
            on:click={clearSelection}
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
        on:click={clearSelection}
        disabled={selectedRecords.length === 0}
      >
        清空所有选中
      </button>
      <button class="btn-primary" on:click={() => loadOperationRecords(true)} disabled={loading}>
        {loading ? '刷新中...' : '刷新数据'}
      </button>
      <button class="btn-secondary" on:click={exportOperationCSV} disabled={loading || filteredOperationRecords.length === 0}>
        导出CSV
      </button>
      <button class="btn-warning" on:click={exportSelectedOperationCSV} disabled={loading || selectedRecords.length === 0}>
        导出选中CSV ({selectedRecords.length})
      </button>
    </div>
  </div>

  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>加载中，请稍候...</p>
    </div>
  {:else if filteredOperationRecords.length > 0}
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th class="checkbox-header">
              <input
                type="checkbox"
                checked={isAllSelected}
                on:change={toggleSelectAll}
                disabled={paginatedRecords.length === 0}
              />
            </th>
            <th class="sortable" on:click={() => toggleSort('操作ID')}>
              操作ID{getSortIndicator('操作ID')}
            </th>
            <th class="sortable" on:click={() => toggleSort('操作类型')}>
              操作类型{getSortIndicator('操作类型')}
            </th>
            <th class="sortable" on:click={() => toggleSort('关联库存ID')}>
              库存ID{getSortIndicator('关联库存ID')}
            </th>
            <th>商品编号</th>
            <th class="sortable" on:click={() => toggleSort('操作数量')}>
              操作数量{getSortIndicator('操作数量')}
            </th>
            <th class="sortable" on:click={() => toggleSort('操作时间')}>
              操作时间{getSortIndicator('操作时间')}
            </th>
            <th class="sortable" on:click={() => toggleSort('操作人')}>
              操作人{getSortIndicator('操作人')}
            </th>
            <th>备注</th>
          </tr>
        </thead>
        <tbody>
          {#each paginatedRecords as record}
            <tr class:selected={selectedRecords.some(r => r.操作ID === record.操作ID)}>
              <td class="checkbox-cell">
                <input
                  type="checkbox"
                  checked={selectedRecords.some(r => r.操作ID === record.操作ID)}
                  on:change={() => toggleRecordSelection(record)}
                />
              </td>
              <td>{record.操作ID}</td>
              <td>
                <span class:operation-type-out={record.操作类型 === '出库'}
                      class:operation-type-in={record.操作类型 === '入库'}
                      class:operation-type-borrow={record.操作类型 === '借'}
                      class:operation-type-return={record.操作类型 === '还'}
                      class:operation-type-defective={record.操作类型 === '次品退回'}>
                  {record.操作类型}
                </span>
              </td>
              <td>{record.关联库存ID}</td>
              <td>{record.商品编号 || '-'}</td>
              <td class:quantity-negative={record.操作数量 < 0}>
                {record.操作数量}
              </td>
              <td>{record.操作时间}</td>
              <td>{record.操作人}</td>
              <td title={record.备注 || ''}>{record.备注 ? (record.备注.length > 20 ? record.备注.substring(0, 20) + '...' : record.备注) : '-'}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <!-- 替换为库存管理同款分页控件 -->
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
  {:else if operationRecords.length === 0}
    <div class="no-data">
      暂无操作记录
    </div>
  {:else}
    <div class="no-data">
      没有找到匹配的操作记录，请调整筛选条件
    </div>
  {/if}
</section>

<style>
  /* 完全恢复原代码的表格数据样式，仅保留分页控件的布局替换 */
  .records-section h2 {
    color: #2c3e50;
    margin-bottom: 25px;
    font-size: 1.5rem;
  }

  .filter-section {
    background: #f8f9fa;
    padding: 20px;
    border-radius: 10px;
    margin-bottom: 20px;
    border: 1px solid #e9ecef;
  }

  .filter-section h3 {
    margin-bottom: 15px;
    color: #495057;
    font-size: 1.1rem;
    font-weight: 600;
  }

  .filter-form {
    width: 100%;
  }

  .form-row {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 20px;
  }

  .form-group {
    margin-bottom: 0;
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

  .filter-actions {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin-top: 15px;
    padding-top: 15px;
    border-top: 1px solid #dee2e6;
  }

  /* 恢复原代码的按钮样式 */
  .btn-primary, .btn-secondary, .btn-outline, .btn-warning {
    padding: 8px 16px;
    border: none;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
  }

  .btn-primary {
    background: #3498db;
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: #2980b9;
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

  .btn-warning {
    background: #f39c12;
    color: white;
  }

  .btn-warning:hover:not(:disabled) {
    background: #e67e22;
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

  .btn-primary:disabled, .btn-secondary:disabled, .btn-warning:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
  }

  /* 分页控件布局样式（仅替换逻辑，样式适配原代码） */
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
    padding: 0;
    background: transparent;
    border: none;
  }

  .section-info {
    font-weight: 500;
    color: #495057;
    font-size: 14px;
  }

  .selected-count {
    margin-left: 12px;
    padding: 4px 8px;
    background: #fff3cd;
    color: #856404;
    border-radius: 4px;
    font-size: 12px;
    font-weight: normal;
  }

  .clear-selected-btn {
    margin-left: 6px;
    padding: 0 4px;
    border: none;
    background: #dc3545;
    color: white;
    border-radius: 2px;
    cursor: pointer;
    font-size: 10px;
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
  }

  .pagination-controls label {
    margin: 0;
    font-size: 14px;
    color: #555;
  }

  .pagination-controls select {
    width: auto;
    min-width: 80px;
    padding: 6px 10px;
    font-size: 13px;
  }

  /* 完全恢复原代码的表格样式 */
  .table-container {
    overflow-x: auto;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
  }

  .data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    min-width: 800px;
  }

  .data-table th {
    background: #f8f9fa;
    padding: 15px 12px;
    text-align: left;
    font-weight: 600;
    color: #2c3e50;
    border-bottom: 2px solid #e0e0e0;
    position: relative;
  }

  .data-table th.sortable {
    cursor: pointer;
    transition: background-color 0.2s ease;
  }

  .data-table th.sortable:hover {
    background-color: #e9ecef;
  }

  .data-table th.sortable::after {
    content: '';
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 6px solid #adb5bd;
    opacity: 0.6;
  }

  .data-table th.sortable:hover::after {
    opacity: 1;
  }

  .data-table td {
    padding: 12px;
    border-bottom: 1px solid #e0e0e0;
    color: #495057;
    font-size: 14px;
  }

  .data-table tr:hover {
    background: #f8f9fa;
  }

  .data-table tr.selected {
    background: #e3f2fd;
  }

  .checkbox-header, .checkbox-cell {
    width: 40px;
    text-align: center;
    vertical-align: middle;
  }

  .checkbox-header input, .checkbox-cell input {
    width: 16px;
    height: 16px;
    cursor: pointer;
  }

  /* 恢复原代码的操作类型标签样式 */
  .operation-type-out {
    color: #e74c3c;
    font-weight: bold;
    padding: 2px 8px;
    background: #fdeaea;
    border-radius: 4px;
  }

  .operation-type-in {
    color: #27ae60;
    font-weight: bold;
    padding: 2px 8px;
    background: #eafaf1;
    border-radius: 4px;
  }

  .operation-type-borrow {
    color: #f39c12;
    font-weight: bold;
    padding: 2px 8px;
    background: #fef5e7;
    border-radius: 4px;
  }

  .operation-type-return {
    color: #3498db;
    font-weight: bold;
    padding: 2px 8px;
    background: #ebf5fb;
    border-radius: 4px;
  }

  .operation-type-defective {
    color: #9b59b6;
    font-weight: bold;
    padding: 2px 8px;
    background: #f4ecf7;
    border-radius: 4px;
  }

  .quantity-negative {
    color: #e74c3c;
    font-weight: bold;
  }

  /* 分页控件基础样式（适配原代码视觉风格） */
  .pagination {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 5px;
    margin-top: 20px;
  }

  .pagination-btn {
    padding: 6px 12px;
    border: 1px solid #dee2e6;
    background: white;
    color: #495057;
    border-radius: 4px;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s ease;
    min-width: 36px;
    text-align: center;
  }

  .pagination-btn:hover:not(:disabled) {
    background: #f8f9fa;
    border-color: #adb5bd;
  }

  .pagination-btn.active {
    background: #3498db;
    color: white;
    border-color: #3498db;
  }

  .pagination-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .pagination-info {
    margin-left: 15px;
    color: #6c757d;
    font-size: 14px;
    font-weight: 500;
  }

  .no-data {
    text-align: center;
    padding: 60px 20px;
    color: #7f8c8d;
    font-style: italic;
  }

  .loading-state {
    text-align: center;
    padding: 60px 20px;
    color: #7f8c8d;
  }

  .spinner {
    border: 4px solid rgba(0, 0, 0, 0.1);
    border-left-color: #3498db;
    border-radius: 50%;
    width: 40px;
    height: 40px;
    animation: spin 1s linear infinite;
    margin: 0 auto 15px;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  /* 恢复原代码的响应式样式 */
  @media (max-width: 768px) {
    .form-row {
      grid-template-columns: 1fr;
    }

    .data-table {
      font-size: 12px;
      min-width: 700px;
    }

    .data-table th,
    .data-table td {
      padding: 8px 6px;
    }

    .section-actions {
      flex-direction: column;
      align-items: stretch;
    }

    .pagination {
      flex-wrap: wrap;
      gap: 4px;
    }

    .pagination-info {
      margin-left: 0;
      margin-top: 8px;
      text-align: center;
      width: 100%;
    }
  }
</style>