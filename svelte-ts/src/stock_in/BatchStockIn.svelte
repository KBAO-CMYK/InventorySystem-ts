<script lang="ts">
  import { api, formatStockInData, validateFormData, handleApiError } from '../lib/api';
  import type { ApiSuccessResponse } from '../lib/api';
  import ImageUpload from '../image/ImageUpload.svelte';

  // ========== 类型定义 ==========
  interface BatchVariation {
    product_code: string;
    [key: string]: string | number | undefined;
  }

  interface VariableField {
    id: '入库数量' | '单价' | '重量' | '规格' | '材质' | '颜色' | '形状' | '风格' | '厂家' | '厂家地址' | '电话' | '用途' | '备注' | '图片路径';
    label: string;
    type: 'number' | 'text';
    enabled: boolean;
  }

  interface BatchForm {
    start_code: string;
    end_code: string;
    类型: string;
    地址类型: number;
    楼层: number;
    入库数量: number;
    架号: string;
    框号: string;
    包号: string;
    use_auto_in_time: boolean;
    入库时间: string;
    单价: string;
    重量: string;
    厂家: string;
    厂家地址: string;
    电话: string;
    用途: string;
    规格: string;
    材质: string;
    颜色: string;
    形状: string;
    风格: string;
    备注: string;
    图片路径: string;
    批次: string;
    操作人: string;
  }

  interface AddressValidation {
    types: number[];
    field: '架号' | '框号' | '包号';
    message: string;
  }

  interface ProductStockInData {
    货号: string;
    类型: string;
    入库数量: number;
    入库时间?: string;
    地址类型: number;
    楼层: number;
    架号: string;
    框号: string;
    包号: string;
    单价?: number;
    重量?: number;
    规格?: string;
    材质?: string;
    颜色?: string;
    形状?: string;
    风格?: string;
    厂家?: string;
    厂家地址?: string;
    电话?: string;
    用途?: string;
    备注?: string;
    图片路径?: string;
    批次?: number;
    操作人?: string;
    [key: string]: string | number | undefined;
  }

  // ========== Props 接收 ==========
  export let productTypes: string[] = [];
  export let floors: number[] = [];
  export let loading: boolean = false;
  export let showMessage: (text: string, type?: 'info' | 'success' | 'error' | 'warning') => void = () => {};
  export let debounce: <T extends (...args: any[]) => any>(func: T, wait: number) => T = (func) => func as any;
  export let lastAddressInfo: { 架号: string; 框号: string; 包号: string } = { 架号: '', 框号: '', 包号: '' };
  export let hasInitialized: boolean = false;
  export let fetchLastAddressInfo: (addressType: number, formType?: 'single' | 'batch') => Promise<void>;
  export let updateLoading: (status: boolean) => void;

  // ========== 状态变量 ==========
  let batchForm: BatchForm = {
    start_code: '',
    end_code: '',
    类型: '样品',
    地址类型: 5,
    楼层: 5,
    入库数量: 1,
    架号: '',
    框号: '',
    包号: '',
    use_auto_in_time: true,
    入库时间: '',
    单价: '',
    重量: '',
    厂家: '',
    厂家地址: '',
    电话: '',
    用途: '',
    规格: '',
    材质: '',
    颜色: '',
    形状: '',
    风格: '',
    备注: '',
    图片路径: '',
    批次: '',
    操作人: ''
  };

  let batchVariations: BatchVariation[] = [];

  let variableFields: VariableField[] = [
    { id: '入库数量', label: '入库数量', type: 'number', enabled: false },
    { id: '单价', label: '单价', type: 'number', enabled: false },
    { id: '重量', label: '重量', type: 'number', enabled: false },
    { id: '规格', label: '规格', type: 'text', enabled: false },
    { id: '材质', label: '材质', type: 'text', enabled: false },
    { id: '颜色', label: '颜色', type: 'text', enabled: false },
    { id: '形状', label: '形状', type: 'text', enabled: false },
    { id: '风格', label: '风格', type: 'text', enabled: false },
    { id: '厂家', label: '厂家', type: 'text', enabled: false },
    { id: '厂家地址', label: '厂家地址', type: 'text', enabled: false },
    { id: '电话', label: '电话', type: 'text', enabled: false },
    { id: '用途', label: '用途', type: 'text', enabled: false },
    { id: '备注', label: '备注', type: 'text', enabled: false },
    { id: '图片路径', label: '图片路径', type: 'text', enabled: false }
  ];

  // 启用的差异字段（响应式）
  $: enabledVariableFields = variableFields.filter(field => field.enabled);

  // 连号范围变化时更新差异信息
  $: if (batchForm.start_code) {
    const codes = generateBatchCodes(batchForm.start_code, batchForm.end_code);
    const currentVariations = new Map<string, BatchVariation>();

    batchVariations.forEach(variation => {
      currentVariations.set(variation.product_code, { ...variation });
    });

    batchVariations = codes.map(code => {
      const existingVariation = currentVariations.get(code);
      if (existingVariation) {
        return existingVariation;
      }

      const variation: BatchVariation = { product_code: code };
      enabledVariableFields.forEach(field => {
        variation[field.id] = batchForm[field.id] || '';
      });
      return variation;
    });
  }

  // ========== 事件处理函数 ==========
  function handleBatchImageChange(path: string): void {
    batchForm.图片路径 = path;
  }

  function handleVariationImageChange(variation: BatchVariation, path: string): void {
    variation.图片路径 = path;
  }

  // 地址类型变化处理
  let previousBatch地址类型: number = batchForm.地址类型;
  $: if (batchForm.地址类型 !== previousBatch地址类型) {
    // 清空不匹配的地址字段
    if ([1, 3, 5].includes(previousBatch地址类型) && ![1, 3, 5].includes(batchForm.地址类型)) {
      batchForm.架号 = '';
    }
    if ([2, 3, 4, 5].includes(previousBatch地址类型) && ![2, 3, 4, 5].includes(batchForm.地址类型)) {
      batchForm.框号 = '';
    }
    if ([4, 5, 6].includes(previousBatch地址类型) && ![4, 5, 6].includes(batchForm.地址类型)) {
      batchForm.包号 = '';
    }

    previousBatch地址类型 = batchForm.地址类型;
    fetchLastAddressInfo(batchForm.地址类型, 'batch');
  }

  // 手动获取默认地址
  async function handleBatchGetDefaultAddress(): Promise<void> {
    if (batchForm.地址类型) {
      await fetchLastAddressInfo(batchForm.地址类型, 'batch');

      if ([1, 3, 5].includes(batchForm.地址类型) && lastAddressInfo.架号) {
        batchForm.架号 = lastAddressInfo.架号;
      }
      if ([2, 3, 4, 5].includes(batchForm.地址类型) && lastAddressInfo.框号) {
        batchForm.框号 = lastAddressInfo.框号;
      }
      if ([4, 5, 6].includes(batchForm.地址类型) && lastAddressInfo.包号) {
        batchForm.包号 = lastAddressInfo.包号;
      }

      showMessage('已获取默认地址信息', 'success');
    } else {
      showMessage('请先选择地址类型', 'error');
    }
  }

  // 生成连号编码
  function generateBatchCodes(start: string, end: string): string[] {
    const codes: string[] = [];

    if (!end || end.trim() === '') {
      return [start];
    }

    const startNumMatch = start.match(/\d+/);
    const endNumMatch = end.match(/\d+/);

    if (!startNumMatch || !endNumMatch) {
      return [start];
    }

    const startNum = parseInt(startNumMatch[0]);
    const endNum = parseInt(endNumMatch[0]);
    const prefix = start.replace(/\d+$/, '');

    if (!isNaN(startNum) && !isNaN(endNum) && startNum <= endNum) {
      const numLength = startNumMatch[0].length;
      for (let i = startNum; i <= endNum; i++) {
        codes.push(prefix + i.toString().padStart(numLength, '0'));
      }
    }
    return codes;
  }

  // 批量填充差异值
  function quickFillVariations(fieldId: string, value: string | number): void {
    batchVariations = batchVariations.map(variation => ({
      ...variation,
      [fieldId]: value
    }));
  }

  // 获取商品数量文本
  function getProductCountText(): string {
    if (!batchForm.start_code) {
      return '请填写起始编号';
    }

    const count = generateBatchCodes(batchForm.start_code, batchForm.end_code).length;
    return count === 1 ? '1 个商品（单号入库）' : `${count} 个商品（连号入库）`;
  }

  // 表单验证
  function validateBatchForm(): boolean {
    try {
      if (!batchForm.start_code) {
        throw new Error('请填写起始编号');
      }

      const codes = generateBatchCodes(batchForm.start_code, batchForm.end_code);
      if (codes.length === 0) {
        throw new Error('起始编号不能大于结束编号');
      }

      if (codes.length > 100) {
        throw new Error('单次连号入库不能超过100个商品');
      }

      // 必填字段验证
      const requiredFields = {
        类型: { label: '商品类型', required: true, type: 'string' },
        楼层: { label: '楼层', required: true, type: 'string' }
      };
      validateFormData(batchForm, requiredFields);

      // 非差异化必填字段
      const nonVariableRequiredFields = ['入库数量'];
      for (const field of nonVariableRequiredFields) {
        const fieldConfig = variableFields.find(f => f.id === field);
        if ((!fieldConfig || !fieldConfig.enabled) && !batchForm[field]) {
          throw new Error(`请填写${fieldConfig?.label || field}`);
        }
      }

      // 地址验证
      const addressValidations: AddressValidation[] = [
        { types: [1, 3, 5], field: '架号', message: '架号不能为空' },
        { types: [2, 3, 4, 5], field: '框号', message: '框号不能为空' },
        { types: [4, 5, 6], field: '包号', message: '包号不能为空' }
      ];

      for (const validation of addressValidations) {
        if (validation.types.includes(batchForm.地址类型) && !batchForm[validation.field]) {
          throw new Error(validation.message);
        }
      }

      return true;
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      showMessage(err.message, 'error');
      return false;
    }
  }

    // 准备入库数据
  function prepareProductData(formData: BatchForm, productCode: string): ProductStockInData {
    const data: ProductStockInData = {
      货号: productCode,
      类型: formData.类型,
      入库数量: parseInt(String(formData.入库数量 ?? ''), 10) || 0,
      地址类型: parseInt(formData.地址类型.toString()),
      楼层: parseInt(formData.楼层.toString()),
      架号: formData.架号,
      框号: formData.框号,
      包号: formData.包号,
      单价: formData.单价 ? parseFloat(formData.单价) : undefined,
      重量: formData.重量 ? parseFloat(formData.重量) : undefined,
      规格: formData.规格 || undefined,
      材质: formData.材质 || undefined,
      颜色: formData.颜色 || undefined,
      形状: formData.形状 || undefined,
      风格: formData.风格 || undefined,
      厂家: formData.厂家 || undefined,
      厂家地址: formData.厂家地址 || undefined,
      电话: formData.电话 || undefined,
      用途: formData.用途 || undefined,
      备注: formData.备注 || undefined,
      图片路径: formData.图片路径 || undefined,
      批次: formData.批次 ? parseInt(formData.批次) : undefined,
      操作人: formData.操作人 || undefined
    };

    // 处理入库时间
    if (!formData.use_auto_in_time && formData.入库时间) {
      data.入库时间 = formData.入库时间;
    }

    // 移除空值
    Object.keys(data).forEach(key => {
      const value = data[key as keyof ProductStockInData];
      if (value === undefined || value === '' || value === null) {
        delete data[key as keyof ProductStockInData];
      }
    });

    return data;
  }

  // 处理批量入库
  async function handleBatchStockIn(): Promise<void> {
    if (!validateBatchForm()) return;

    updateLoading(true);
    try {
      const codes = generateBatchCodes(batchForm.start_code, batchForm.end_code);
      const stockInItems = codes.map((code, index) => {
        const variation = batchVariations[index] || {};
        const productData = prepareProductData(batchForm, code);

        // 应用差异化字段
        enabledVariableFields.forEach(field => {
          if (variation[field.id] !== undefined && variation[field.id] !== '') {
            const val = variation[field.id];
            productData[field.id] = field.type === 'number'
              ? parseFloat(val.toString())
              : val;
          }
        });

        return productData;
      });

      const response = await api.batchStockIn({
        stock_in_items: stockInItems
      }) as ApiSuccessResponse<{
        success_count: number;
        error_count: number;
        success_details: string[];
        error_details: string[];
      }>;

      if (response.status === 'success') {
        const { success_count, error_count, error_details } = response.data || {
          success_count: 0,
          error_count: 0,
          error_details: []
        };

        if (success_count > 0) {
          showMessage(`批量入库成功！成功: ${success_count} 个，失败: ${error_count} 个`, 'success');
        }

        if (error_count > 0 && error_details) {
          const errorMessages = error_details.slice(0, 5).join('; ');
          showMessage(`部分商品入库失败: ${errorMessages}${error_details.length > 5 ? '...' : ''}`, 'warning');
        }

        resetBatchForm();
      } else {
        showMessage(response.message || '批量入库失败', 'error');
      }
    } catch (error) {
      console.error('批量入库错误:', error);
      const errMsg = handleApiError(error, '批量入库请求失败');
      showMessage(errMsg, 'error');
    } finally {
      updateLoading(false);
    }
  }

  // 重置批量表单
  function resetBatchForm(): void {
    batchForm = {
      start_code: '',
      end_code: '',
      类型: '样品',
      地址类型: 5,
      楼层: 5,
      入库数量: 1,
      架号: '',
      框号: '',
      包号: '',
      use_auto_in_time: true,
      入库时间: '',
      单价: '',
      重量: '',
      厂家: '',
      厂家地址: '',
      电话: '',
      用途: '',
      规格: '',
      材质: '',
      颜色: '',
      形状: '',
      风格: '',
      备注: '',
      图片路径: '',
      批次: '',
      操作人: ''
    };
    batchVariations = [];
  }

  // 获取批量按钮文本
  function getBatchButtonText(): string {
    const count = batchForm.start_code ? generateBatchCodes(batchForm.start_code, batchForm.end_code).length : 0;
    const baseText = loading ? '入库中...' : (count === 1 ? '单号入库' : `批量入库 (${count}个)`);
    return baseText;
  }
</script>

<div class="compact-form">
  <h2>商品入库 - 单号/连号入库</h2>
  <p class="help-text">
    支持单个商品入库或连续编号批量入库。
    填写起始编号和结束编号，可进行连续编号的批量入库；只填写起始编号则为单号入库。
  </p>

  <!-- 单号/连号入库表单 -->
  <form on:submit|preventDefault={handleBatchStockIn}>
    <!-- 第一行：起始编号、结束编号、商品类型、操作人、批次 -->
    <div class="form-section">
      <div class="form-row compact-row">
        <div class="form-group">
          <label for="start_code">起始编号 *</label>
          <input
            id="start_code"
            type="text"
            bind:value={batchForm.start_code}
            placeholder="如：PROD001"
            required
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="end_code">结束编号</label>
          <input
            id="end_code"
            type="text"
            bind:value={batchForm.end_code}
            placeholder="如：PROD010"
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="batch_类型">商品类型 *</label>
          <select id="batch_类型" bind:value={batchForm.类型} required disabled={loading}>
            <option value="">请选择商品类型</option>
            {#each productTypes as type}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label for="batch_操作人">操作人</label>
          <input
            id="batch_操作人"
            type="text"
            bind:value={batchForm.操作人}
            placeholder="请输入操作人"
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="batch_批次">批次</label>
          <input
            id="batch_批次"
            type="number"
            bind:value={batchForm.批次}
            placeholder="批次号"
            min="1"
            disabled={loading}
          />
        </div>
      </div>
      <div class="form-group">
        <span class="help-text">{getProductCountText()}</span>
      </div>
    </div>

    <!-- 第二行：地址类型、楼层、数量、架号、框号、包号 -->
    <div class="form-section">
      <div class="form-row compact-row">
        <div class="form-group">
          <label for="batch_地址类型">地址类型 *</label>
          <select id="batch_地址类型" bind:value={batchForm.地址类型} disabled={loading}>
            <option value={1}>1-楼层+架号（单位：框）</option>
            <option value={2}>2-楼层+框号（单位：包）</option>
            <option value={3}>3-楼层+架号+框号（单位：包）</option>
            <option value={4}>4-楼层+框号+包号（单位：个）</option>
            <option value={5}>5-楼层+架号+框号+包号（单位：个）</option>
            <option value={6}>6-楼层+包号（单位：个）</option>
          </select>
        </div>
        <div class="form-group">
          <label for="batch_楼层">楼层 *</label>
          <select id="batch_楼层" bind:value={batchForm.楼层} required disabled={loading}>
            <option value="" disabled>请选择楼层</option>
            {#each floors as floor}
              <option value={floor}>{floor}楼</option>
            {/each}
          </select>
        </div>
        <!-- 入库数量字段只在未被设置为差异化字段时显示 -->
        {#if !variableFields.find(f => f.id === '入库数量')?.enabled}
          <div class="form-group">
            <label for="batch_入库数量">入库数量 *</label>
            <input
              id="batch_入库数量"
              type="number"
              bind:value={batchForm.入库数量}
              placeholder="请输入入库数量"
              min="1"
              step="1"
              required
              disabled={loading}
            />
          </div>
        {/if}

        <!-- 地址字段区域 -->
        {#if [1, 3, 5].includes(batchForm.地址类型)}
          <div class="form-group">
            <label for="batch_架号">架号 *</label>
            <div class="input-with-button">
              <input
                id="batch_架号"
                type="text"
                bind:value={batchForm.架号}
                placeholder="请输入架号"
                required
                disabled={loading}
              />
              {#if lastAddressInfo.架号}
                <button type="button" class="btn-default" on:click={() => batchForm.架号 = lastAddressInfo.架号} disabled={loading}>
                  使用默认值
                </button>
              {/if}
            </div>
            {#if lastAddressInfo.架号 && !batchForm.架号}
              <div class="default-hint">默认值: {lastAddressInfo.架号}</div>
            {/if}
          </div>
        {/if}

        {#if [2, 3, 4, 5].includes(batchForm.地址类型)}
          <div class="form-group">
            <label for="batch_框号">框号 *</label>
            <div class="input-with-button">
              <input
                id="batch_框号"
                type="text"
                bind:value={batchForm.框号}
                placeholder="请输入框号"
                required
                disabled={loading}
              />
              {#if lastAddressInfo.框号}
                <button type="button" class="btn-default" on:click={() => batchForm.框号 = lastAddressInfo.框号} disabled={loading}>
                  使用默认值
                </button>
              {/if}
            </div>
            {#if lastAddressInfo.框号 && !batchForm.框号}
              <div class="default-hint">默认值: {lastAddressInfo.框号}</div>
            {/if}
          </div>
        {/if}

        {#if [4, 5, 6].includes(batchForm.地址类型)}
          <div class="form-group">
            <label for="batch_包号">包号 *</label>
            <div class="input-with-button">
              <input
                id="batch_包号"
                type="text"
                bind:value={batchForm.包号}
                placeholder="请输入包号"
                required
                disabled={loading}
              />
              {#if lastAddressInfo.包号}
                <button type="button" class="btn-default" on:click={() => batchForm.包号 = lastAddressInfo.包号} disabled={loading}>
                  使用默认值
                </button>
              {/if}
            </div>
            {#if lastAddressInfo.包号 && !batchForm.包号}
              <div class="default-hint">默认值: {lastAddressInfo.包号}</div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- 获取默认地址按钮 -->
      <div class="form-group">
        <button type="button" class="btn-default" on:click={handleBatchGetDefaultAddress} disabled={loading}>
          获取默认地址信息
        </button>
      </div>
    </div>

    <!-- 其他非差异化字段 -->
    <div class="form-section">
      <div class="form-row compact-row">
        {#each variableFields as field}
          {#if !field.enabled && field.id !== '入库数量' && field.id !== '图片路径'}
            <div class="form-group">
              <label for="batch_{field.id}">{field.label}</label>
              {#if field.type === 'number'}
                <input
                  id="batch_{field.id}"
                  type="number"
                  step="0.01"
                  bind:value={batchForm[field.id]}
                  placeholder={`请输入${field.label}`}
                  disabled={loading}
                />
              {:else}
                <input
                  id="batch_{field.id}"
                  type="text"
                  bind:value={batchForm[field.id]}
                  placeholder={`请输入${field.label}`}
                  disabled={loading}
                />
              {/if}
            </div>
          {/if}
        {/each}
        <!-- 非差异化时显示公共图片上传 -->
        {#if !variableFields.find(f => f.id === '图片路径')?.enabled}
          <div class="form-group">
            <label>公共图片（所有商品默认）</label>
            <ImageUpload
              bind:value={batchForm.图片路径}
              productCode={batchForm.start_code}
              on:change={handleBatchImageChange}
              disabled={loading}
            />
          </div>
        {/if}
      </div>
    </div>

    <!-- 差异化字段配置 -->
    <div class="form-section">
      <h3>差异化字段配置</h3>
      <p class="help-text">选择需要在每个商品中单独设置的字段（未选择的字段将使用公共信息中的值）：</p>
      <div class="variable-fields-grid">
        {#each variableFields as field}
          <label class="checkbox-label compact">
            <input
              type="checkbox"
              bind:checked={field.enabled}
              disabled={loading}
            />
            <span>{field.label}</span>
          </label>
        {/each}
      </div>
    </div>

    <!-- 差异化字段公共信息设置 -->
    {#if enabledVariableFields.length > 0}
      <div class="form-section">
        <h3>差异化字段公共信息设置</h3>
        <p class="help-text">以下字段的默认值将应用于所有商品，您可以在下一步中为每个商品单独修改：</p>
        <div class="form-row compact-row">
          {#each enabledVariableFields as field}
            <div class="form-group">
              <label for="batch_{field.id}">{field.label}</label>
              {#if field.id === '图片路径'}
                <!-- 差异化字段中的公共图片上传 -->
                <ImageUpload
                  bind:value={batchForm[field.id]}
                  productCode={batchForm.start_code}
                  on:change={handleBatchImageChange}
                  disabled={loading}
                />
              {:else if field.type === 'number'}
                <input
                  id="batch_{field.id}"
                  type="number"
                  step="0.01"
                  bind:value={batchForm[field.id]}
                  placeholder={`请输入${field.label}`}
                  disabled={loading}
                />
              {:else}
                <input
                  id="batch_{field.id}"
                  type="text"
                  bind:value={batchForm[field.id]}
                  placeholder={`请输入${field.label}`}
                  disabled={loading}
                />
              {/if}
            </div>
          {/each}
        </div>
      </div>
    {/if}

    <!-- 商品差异信息编辑 -->
    {#if batchVariations.length > 0 && enabledVariableFields.length > 0 && batchForm.end_code}
      <div class="form-section">
        <h3>商品差异信息编辑</h3>
        <p class="help-text">以下字段需要为每个商品单独设置：</p>
        <div class="batch-variations-table">
          <div class="table-header">
            <div class="row">
              <div class="cell product-code">商品编号</div>
              {#each enabledVariableFields as field}
                <div class="cell variable-field">
                  <span>{field.label}</span>
                  <button
                    type="button"
                    class="btn-quick-fill"
                    on:click={() => quickFillVariations(field.id, batchForm[field.id])}
                    title="使用公共信息填充所有"
                    disabled={loading}
                  >
                    批量填充
                  </button>
                </div>
              {/each}
            </div>
          </div>
          <div class="table-body">
            {#each batchVariations as variation, index}
              <div class="row">
                <div class="cell product-code">
                  <strong>{variation.product_code}</strong>
                </div>
                {#each enabledVariableFields as field}
                  <div class="cell variable-field">
                    {#if field.id === '图片路径'}
                      <!-- 每个商品单独的图片上传 -->
                      <ImageUpload
                        bind:value={variation[field.id]}
                        productCode={variation.product_code}
                        on:change={(path) => handleVariationImageChange(variation, path)}
                        disabled={loading}
                      />
                    {:else if field.type === 'number'}
                      <input
                        type="number"
                        step="0.01"
                        bind:value={variation[field.id]}
                        placeholder={batchForm[field.id] || `请输入${field.label}`}
                        disabled={loading}
                      />
                    {:else}
                      <input
                        type="text"
                        bind:value={variation[field.id]}
                        placeholder={batchForm[field.id] || `请输入${field.label}`}
                        disabled={loading}
                      />
                    {/if}
                  </div>
                {/each}
              </div>
            {/each}
          </div>
        </div>
      </div>
    {/if}

    <!-- 入库时间设置 -->
    <div class="form-group inline-checkbox">
      <label class="checkbox-label">
        <input
          type="checkbox"
          bind:checked={batchForm.use_auto_in_time}
          disabled={loading}
        />
        自动生成入库时间
      </label>
    </div>

    {#if !batchForm.use_auto_in_time}
      <div class="form-group">
        <label for="batch_入库时间">入库时间 *</label>
        <input
          id="batch_入库时间"
          type="datetime-local"
          bind:value={batchForm.入库时间}
          required
          disabled={loading}
        />
      </div>
    {/if}

    <button type="submit" class="btn-primary" disabled={loading}>
      {getBatchButtonText()}
    </button>
  </form>
</div>