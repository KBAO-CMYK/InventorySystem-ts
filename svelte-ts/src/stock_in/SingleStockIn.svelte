<script lang="ts">
  import { api, formatStockInData, validateFormData, handleApiError } from '../lib/api';
  import type { ApiSuccessResponse } from '../lib/api';
  import ImageUpload from '../image/ImageUpload.svelte';
  // 新增：导入生成临时货号组件（和批量入库保持一致）
  import GenerateTempCodeButton from './GenerateTempCodeButton.svelte';

  // ========== 类型定义 ==========
  interface FeatureVariation {
    单价: string;
    重量: string;
    规格: string;
    材质: string;
    颜色: string;
    形状: string;
    风格: string;
    入库数量: number;
    图片路径: string;
  }

  interface FeatureField {
    id: '单价' | '重量' | '规格' | '材质' | '颜色' | '形状' | '风格' | '入库数量' | '图片路径';
    label: string;
    type: 'number' | 'text' | 'image';
    required: boolean;
  }

  interface SingleForm {
    product_code: string;
    类型: string;
    地址类型: number;
    楼层: number;
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
  let singleForm: SingleForm = {
    product_code: '',
    类型: '样品',
    地址类型: 5,
    楼层: 5,
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

  let featureVariations: FeatureVariation[] = [
    {
      单价: '',
      重量: '',
      规格: '',
      材质: '',
      颜色: '',
      形状: '',
      风格: '',
      入库数量: 1,
      图片路径: ''
    }
  ];

  let featureFields: FeatureField[] = [
    { id: '单价', label: '单价', type: 'number', required: false },
    { id: '重量', label: '重量', type: 'number', required: false },
    { id: '规格', label: '规格', type: 'text', required: false },
    { id: '材质', label: '材质', type: 'text', required: false },
    { id: '颜色', label: '颜色', type: 'text', required: false },
    { id: '形状', label: '形状', type: 'text', required: false },
    { id: '风格', label: '风格', type: 'text', required: false },
    { id: '入库数量', label: '数量', type: 'number', required: true },
    { id: '图片路径', label: '图片', type: 'image', required: false }
  ];

  // 计算总数量（响应式）
  $: totalQuantity = calculateTotalQuantity();

  // ========== 新增：处理临时货号生成逻辑（和批量入库保持一致） ==========
  function handleTempCodeGenerated(code: string) {
    singleForm.product_code = code;
    // 提示用户货号已生成
    showMessage(`已生成临时货号：${code}`, 'info');
  }

  // ========== 事件处理函数 ==========
  function handleSingleImageChange(path: string): void {
    singleForm.图片路径 = path;
  }

  function handleVariationImageChange(variation: FeatureVariation, path: string): void {
    variation.图片路径 = path;
  }

  // 地址类型变化处理
  let previousSingle地址类型: number = singleForm.地址类型;
  $: if (singleForm.地址类型 !== previousSingle地址类型) {
    // 清空不匹配的地址字段
    if ([1, 3, 5].includes(previousSingle地址类型) && ![1, 3, 5].includes(singleForm.地址类型)) {
      singleForm.架号 = '';
    }
    if ([2, 3, 4, 5].includes(previousSingle地址类型) && ![2, 3, 4, 5].includes(singleForm.地址类型)) {
      singleForm.框号 = '';
    }
    if ([4, 5, 6].includes(previousSingle地址类型) && ![4, 5, 6].includes(singleForm.地址类型)) {
      singleForm.包号 = '';
    }

    previousSingle地址类型 = singleForm.地址类型;
    fetchLastAddressInfo(singleForm.地址类型, 'single');
  }

  // 手动获取默认地址
  async function handleSingleGetDefaultAddress(): Promise<void> {
    if (singleForm.地址类型) {
      await fetchLastAddressInfo(singleForm.地址类型, 'single');

      if ([1, 3, 5].includes(singleForm.地址类型) && lastAddressInfo.架号) {
        singleForm.架号 = lastAddressInfo.架号;
      }
      if ([2, 3, 4, 5].includes(singleForm.地址类型) && lastAddressInfo.框号) {
        singleForm.框号 = lastAddressInfo.框号;
      }
      if ([4, 5, 6].includes(singleForm.地址类型) && lastAddressInfo.包号) {
        singleForm.包号 = lastAddressInfo.包号;
      }

      showMessage('已获取默认地址信息', 'success');
    } else {
      showMessage('请先选择地址类型', 'error');
    }
  }

  // 添加特征组合
  function addFeatureVariation(): void {
    featureVariations.push({
      单价: singleForm.单价 || '',
      重量: singleForm.重量 || '',
      规格: singleForm.规格 || '',
      材质: singleForm.材质 || '',
      颜色: singleForm.颜色 || '',
      形状: singleForm.形状 || '',
      风格: singleForm.风格 || '',
      入库数量: 1,
      图片路径: ''
    });
    featureVariations = [...featureVariations];
  }

  // 快速添加多个组合
  function quickAddVariations(count: number = 5): void {
    for (let i = 0; i < count; i++) {
      addFeatureVariation();
    }
  }

  // 删除特征组合
  function removeFeatureVariation(index: number): void {
    featureVariations.splice(index, 1);
    featureVariations = [...featureVariations];
  }

  // 批量填充特征值
  function quickFillAllFeatures(fieldId: string, value: string | number): void {
    requestAnimationFrame(() => {
      featureVariations = featureVariations.map(variation => ({
        ...variation,
        [fieldId]: value
      }));
    });
  }

  // 计算总数量
  function calculateTotalQuantity(): number {
    let total = 0;
    for (const variation of featureVariations) {
      const qty = parseInt(variation.入库数量.toString()) || 0;
      total += qty;
    }
    return total;
  }

  // 表单验证
  function validateSingleForm(): boolean {
    try {
      if (!singleForm.product_code) {
        throw new Error('请填写商品编号');
      }

      // 必填字段验证
      const requiredFields = {
        类型: { label: '类型', required: true, type: 'string' },
        楼层: { label: '楼层', required: true, type: 'string' }
      };
      validateFormData(singleForm, requiredFields);

      if (featureVariations.length === 0) {
        throw new Error('请至少添加一个特征组合');
      }

      // 验证每个特征组合
      for (let i = 0; i < featureVariations.length; i++) {
        const variation = featureVariations[i];
        const qty = parseInt(variation.入库数量.toString()) || 0;

        if (qty <= 0) {
          throw new Error(`第${i + 1}行：请填写有效的数量`);
        }

        // 检查特征值
        const hasFeatureValue = featureFields.some(field =>
          field.id !== '入库数量' && field.id !== '图片路径' &&
          variation[field.id] && variation[field.id].toString().trim() !== ''
        );

        if (!hasFeatureValue) {
          throw new Error(`第${i + 1}行：请至少填写一个特征值（单价、重量、规格、材质、颜色、形状、风格）`);
        }
      }

      // 地址验证规则
      const addressValidations: AddressValidation[] = [
        { types: [1, 3, 5], field: '架号', message: '架号不能为空' },
        { types: [2, 3, 4, 5], field: '框号', message: '框号不能为空' },
        { types: [4, 5, 6], field: '包号', message: '包号不能为空' }
      ];

      for (const validation of addressValidations) {
        if (validation.types.includes(singleForm.地址类型) && !singleForm[validation.field]) {
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
  function prepareProductData(formData: SingleForm, productCode: string): ProductStockInData {
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

  // 准备多特征入库数据
  function prepareSingleStockInData(): ProductStockInData[] {
    return featureVariations.map(variation => {
      const productData = prepareProductData(singleForm, singleForm.product_code);

      // 应用特征字段值
      featureFields.forEach(field => {
        if (field.id !== '入库数量' && variation[field.id]) {
          const val = variation[field.id];
          if (val.toString().trim() !== '') {
            productData[field.id] = field.type === 'number'
              ? parseFloat(val.toString())
              : val;
          }
        }
      });

      // 设置数量
      productData.入库数量 = parseInt(variation.入库数量.toString()) || 0;

      // 图片路径优先级
      if (variation.图片路径) {
        productData.图片路径 = variation.图片路径;
      } else if (singleForm.图片路径) {
        productData.图片路径 = singleForm.图片路径;
      }

      return productData;
    });
  }

  // 处理多特征入库
  async function handleSingleStockIn(): Promise<void> {
    if (!validateSingleForm()) return;

    updateLoading(true);
    try {
      const stockInItems = prepareSingleStockInData();
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
          showMessage(`多特征入库成功！成功: ${success_count} 个特征组合，失败: ${error_count} 个`, 'success');
        }

        if (error_count > 0 && error_details) {
          const errorMessages = error_details.slice(0, 3).join('; ');
          showMessage(`部分特征组合入库失败: ${errorMessages}${error_details.length > 3 ? '...' : ''}`, 'warning');
        }

        resetSingleForm();
      } else {
        showMessage(response.message || '多特征入库失败', 'error');
      }
    } catch (error) {
      console.error('入库错误:', error);
      const errMsg = handleApiError(error, '入库请求失败');
      showMessage(errMsg, 'error');
    } finally {
      updateLoading(false);
    }
  }

  // 重置表单
  function resetSingleForm(): void {
    singleForm = {
      product_code: '',
      类型: '样品',
      地址类型: 5,
      楼层: 5,
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
    featureVariations = [{
      单价: '',
      重量: '',
      规格: '',
      材质: '',
      颜色: '',
      形状: '',
      风格: '',
      入库数量: 1,
      图片路径: ''
    }];
  }

  // 获取按钮文本
  function getSingleButtonText(): string {
    const baseText = loading ? '入库中...' : '多特征入库';
    return `${baseText} (${featureVariations.length}个组合, ${totalQuantity}个商品)`;
  }
</script>

<div class="multi-feature-form">
  <h2>商品入库 - 多特征入库</h2>
  <p class="help-text">
    为一个商品编号创建多个特征组合，每个特征组合会生成独立的库存记录。
    适用于同一商品有不同规格、颜色、形状、风格的场景。
  </p>

  <form on:submit|preventDefault={handleSingleStockIn}>
    <!-- 第一行：商品编号、类型、操作人、批次 -->
    <div class="form-section">
      <div class="form-row compact-row">
        <div class="form-group">
          <label for="product_code">商品编号 *</label>
          <!-- 新增：修改为输入框+按钮容器（和批量入库保持一致） -->
          <div class="input-with-button">
            <input
              id="product_code"
              type="text"
              bind:value={singleForm.product_code}
              placeholder="如：PROD001"
              required
              disabled={loading}
            />
            <!-- 新增：生成临时货号按钮，事件绑定和批量入库一致 -->
            <GenerateTempCodeButton
              disabled={loading}
              prefix="TEMP-"
              on:generate={e => handleTempCodeGenerated(e.detail)}
            />
          </div>
        </div>
        <div class="form-group">
          <label for="single_类型">类型 *</label>
          <select id="single_类型" bind:value={singleForm.类型} required disabled={loading}>
            <option value="">请选择类型</option>
            {#each productTypes as type}
              <option value={type}>{type}</option>
            {/each}
          </select>
        </div>
        <div class="form-group">
          <label for="single_操作人">操作人</label>
          <input
            id="single_操作人"
            type="text"
            bind:value={singleForm.操作人}
            placeholder="请输入操作人"
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="single_批次">批次</label>
          <input
            id="single_批次"
            type="number"
            bind:value={singleForm.批次}
            placeholder="批次号"
            min="1"
            disabled={loading}
          />
        </div>
      </div>
    </div>

    <!-- 第二行：地址类型、楼层、架号、框号、包号 -->
    <div class="form-section">
      <div class="form-row compact-row">
        <div class="form-group">
          <label for="single_地址类型">地址类型 *</label>
          <select id="single_地址类型" bind:value={singleForm.地址类型} disabled={loading}>
            <option value={1}>1-楼层+架号（单位：框）</option>
            <option value={2}>2-楼层+框号（单位：包）</option>
            <option value={3}>3-楼层+架号+框号（单位：包）</option>
            <option value={4}>4-楼层+框号+包号（单位：个）</option>
            <option value={5}>5-楼层+架号+框号+包号（单位：个）</option>
            <option value={6}>6-楼层+包号（单位：个）</option>
          </select>
        </div>
        <div class="form-group">
          <label for="single_楼层">楼层 *</label>
          <select id="single_楼层" bind:value={singleForm.楼层} required disabled={loading}>
            <option value="" disabled>请选择楼层</option>
            {#each floors as floor}
              <option value={floor}>{floor}楼</option>
            {/each}
          </select>
        </div>

        <!-- 地址字段区域 -->
        {#if [1, 3, 5].includes(singleForm.地址类型)}
          <div class="form-group">
            <label for="single_架号">架号 *</label>
            <div class="input-with-button">
              <input
                id="single_架号"
                type="text"
                bind:value={singleForm.架号}
                placeholder="请输入架号"
                required
                disabled={loading}
              />
              {#if lastAddressInfo.架号}
                <button type="button" class="btn-default" on:click={() => singleForm.架号 = lastAddressInfo.架号} disabled={loading}>
                  使用默认值
                </button>
              {/if}
            </div>
            {#if lastAddressInfo.架号 && !singleForm.架号}
              <div class="default-hint">默认值: {lastAddressInfo.架号}</div>
            {/if}
          </div>
        {/if}

        {#if [2, 3, 4, 5].includes(singleForm.地址类型)}
          <div class="form-group">
            <label for="single_框号">框号 *</label>
            <div class="input-with-button">
              <input
                id="single_框号"
                type="text"
                bind:value={singleForm.框号}
                placeholder="请输入框号"
                required
                disabled={loading}
              />
              {#if lastAddressInfo.框号}
                <button type="button" class="btn-default" on:click={() => singleForm.框号 = lastAddressInfo.框号} disabled={loading}>
                  使用默认值
                </button>
              {/if}
            </div>
            {#if lastAddressInfo.框号 && !singleForm.框号}
              <div class="default-hint">默认值: {lastAddressInfo.框号}</div>
            {/if}
          </div>
        {/if}

        {#if [4, 5, 6].includes(singleForm.地址类型)}
          <div class="form-group">
            <label for="single_包号">包号 *</label>
            <div class="input-with-button">
              <input
                id="single_包号"
                type="text"
                bind:value={singleForm.包号}
                placeholder="请输入包号"
                required
                disabled={loading}
              />
              {#if lastAddressInfo.包号}
                <button type="button" class="btn-default" on:click={() => singleForm.包号 = lastAddressInfo.包号} disabled={loading}>
                  使用默认值
                </button>
              {/if}
            </div>
            {#if lastAddressInfo.包号 && !singleForm.包号}
              <div class="default-hint">默认值: {lastAddressInfo.包号}</div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- 获取默认地址按钮 -->
      <div class="form-group">
        <button type="button" class="btn-default" on:click={handleSingleGetDefaultAddress} disabled={loading}>
          获取默认地址信息
        </button>
      </div>
    </div>

    <!-- 第三行：特征字段公共值 -->
    <div class="form-section">
      <div class="form-row compact-row">
        {#each featureFields as field}
          {#if field.id !== '入库数量' && field.id !== '图片路径'}
            <div class="form-group">
              <label for="single_feature_{field.id}">{field.label}</label>
              {#if field.type === 'number'}
                <input
                  id="single_feature_{field.id}"
                  type="number"
                  step="0.01"
                  bind:value={singleForm[field.id]}
                  placeholder={`${field.label}（公共值）`}
                  disabled={loading}
                />
              {:else}
                <input
                  id="single_feature_{field.id}"
                  type="text"
                  bind:value={singleForm[field.id]}
                  placeholder={`${field.label}（公共值）`}
                  disabled={loading}
                />
              {/if}
            </div>
          {/if}
        {/each}
      </div>
    </div>

    <!-- 第四行：其他字段（厂家、厂家地址等） -->
    <div class="form-section">
      <div class="form-row compact-row">
        <div class="form-group">
          <label for="single_厂家">厂家</label>
          <input
            id="single_厂家"
            type="text"
            bind:value={singleForm.厂家}
            placeholder="请输入厂家"
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="single_厂家地址">厂家地址</label>
          <input
            id="single_厂家地址"
            type="text"
            bind:value={singleForm.厂家地址}
            placeholder="请输入厂家地址"
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="single_电话">电话</label>
          <input
            id="single_电话"
            type="text"
            bind:value={singleForm.电话}
            placeholder="请输入电话"
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="single_用途">用途</label>
          <input
            id="single_用途"
            type="text"
            bind:value={singleForm.用途}
            placeholder="请输入用途"
            disabled={loading}
          />
        </div>
        <div class="form-group">
          <label for="single_备注">备注</label>
          <input
            id="single_备注"
            type="text"
            bind:value={singleForm.备注}
            placeholder="请输入备注"
            disabled={loading}
          />
        </div>
        <!-- 主表单图片上传（可选，特征组合可覆盖） -->
        <div class="form-group">
          <label>公共图片（所有组合默认）</label>
          <ImageUpload
            bind:value={singleForm.图片路径}
            productCode={singleForm.product_code}
            on:change={handleSingleImageChange}
            disabled={loading}
          />
        </div>
      </div>
    </div>

    <!-- 特征组合表格 -->
    <div class="form-section">
      <div class="section-header">
        <h3>特征组合列表</h3>
        <div class="header-actions">
          <span class="combination-count">共 {featureVariations.length} 个组合</span>
          <button type="button" class="btn-default" on:click={addFeatureVariation} disabled={loading}>
            + 添加单个组合
          </button>
          <button type="button" class="btn-default" on:click={() => quickAddVariations(5)} disabled={loading}>
            + 添加5个组合
          </button>
        </div>
      </div>

      <div class="feature-variations-table">
        <div class="table-header">
          <div class="row">
            {#each featureFields as field}
              <div class="cell {field.id === '入库数量' ? 'quantity' : ''}">
                <span>{field.label}{field.required ? ' *' : ''}</span>
                {#if singleForm[field.id] && field.id !== '图片路径'}
                  <button
                    type="button"
                    class="btn-quick-fill"
                    on:click={() => quickFillAllFeatures(field.id, singleForm[field.id])}
                    title="使用公共值填充所有"
                    disabled={loading}
                  >
                    批量填充
                  </button>
                {/if}
              </div>
            {/each}
            <div class="cell actions">操作</div>
          </div>
        </div>

        <div class="table-body">
          {#each featureVariations as variation, index}
            <div class="row">
              {#each featureFields as field}
                <div class="cell {field.id === '入库数量' ? 'quantity' : ''}">
                  {#if field.type === 'number'}
                    <input
                      type="text"
                      bind:value={variation[field.id]}
                      placeholder={singleForm[field.id] || field.label}
                      required={field.required}
                      disabled={loading}
                    />
                  {:else if field.type === 'image'}
                    <!-- 特征组合独立图片上传 -->
                    <ImageUpload
                      bind:value={variation[field.id]}
                      productCode={`${singleForm.product_code}_var_${index}`}
                      on:change={(path) => handleVariationImageChange(variation, path)}
                      disabled={loading}
                    />
                  {:else}
                    <input
                      type="text"
                      bind:value={variation[field.id]}
                      placeholder={singleForm[field.id] || field.label}
                      disabled={loading}
                    />
                  {/if}
                </div>
              {/each}
              <div class="cell actions">
                {#if featureVariations.length > 1}
                  <button
                    type="button"
                    class="btn-danger"
                    on:click={() => removeFeatureVariation(index)}
                    disabled={loading}
                  >
                    删除
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>

        <div class="table-footer">
          <div class="total-summary">
            <div class="summary-item">
              <span>特征组合数量：</span>
              <strong>{featureVariations.length} 个</strong>
            </div>
            <div class="summary-item">
              <span>商品总数量：</span>
              <strong>{totalQuantity} 个</strong>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 入库时间设置 -->
    <div class="form-group inline-checkbox">
      <label class="checkbox-label">
        <input
          type="checkbox"
          bind:checked={singleForm.use_auto_in_time}
          disabled={loading}
        />
        自动生成入库时间
      </label>
    </div>

    {#if !singleForm.use_auto_in_time}
      <div class="form-group">
        <label for="single_入库时间">入库时间 *</label>
        <input
          id="single_入库时间"
          type="datetime-local"
          bind:value={singleForm.入库时间}
          required
          disabled={loading}
        />
      </div>
    {/if}

    <button type="submit" class="btn-primary" disabled={loading}>
      {getSingleButtonText()}
    </button>
  </form>
</div>

<!-- 新增：补充输入框+按钮的样式（和批量入库保持一致） -->
<style>
  .input-with-button {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }

  .input-with-button input {
    flex: 1;
  }
</style>