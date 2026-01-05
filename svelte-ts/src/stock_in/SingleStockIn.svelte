<script lang="ts">
  import { api, formatStockInData, validateFormData, handleApiError } from '../lib/api';
  import type { ApiSuccessResponse } from '../lib/api';
  import ImageUpload from '../image/ImageUpload.svelte';
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
    单位: string;
    图片路径: string; // 仅特征组合保留图片字段
  }

  interface FeatureField {
    id: '单价' | '重量' | '规格' | '材质' | '颜色' | '形状' | '风格' | '入库数量' | '单位' | '图片路径';
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
    厂家: string;
    厂家地址: string;
    电话: string;
    用途: string;
    备注: string;
    批次: string;
    操作人: string;
    // 彻底移除：公共图片相关字段
  }

  interface ProductStockInData {
    货号: string;
    类型: string;
    入库数量: number;
    单位?: string;
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
    图片路径?: string; // 仅从特征组合获取
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
    厂家: '',
    厂家地址: '',
    电话: '',
    用途: '',
    备注: '',
    批次: '',
    操作人: ''
    // 彻底移除：公共图片初始化
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
      单位: '',
      图片路径: ''
    }
  ];

  // 特征组合字段配置（仅在表格中显示）
  let featureFields: FeatureField[] = [
    { id: '单价', label: '单价', type: 'number', required: false },
    { id: '重量', label: '重量', type: 'number', required: false },
    { id: '规格', label: '规格', type: 'text', required: false },
    { id: '材质', label: '材质', type: 'text', required: false },
    { id: '颜色', label: '颜色', type: 'text', required: false },
    { id: '形状', label: '形状', type: 'text', required: false },
    { id: '风格', label: '风格', type: 'text', required: false },
    { id: '入库数量', label: '数量', type: 'number', required: true },
    { id: '单位', label: '单位', type: 'text', required: false },
    { id: '图片路径', label: '图片', type: 'image', required: false }
  ];

  // 新增：填充功能相关状态（移除了填充范围选项）
  let fillValues: Partial<FeatureVariation> = {
    单价: '',
    重量: '',
    规格: '',
    材质: '',
    颜色: '',
    形状: '',
    风格: '',
    入库数量: '',
    单位: '',
    图片路径: ''
  };

  $: totalQuantity = calculateTotalQuantity();

  // ========== 临时货号逻辑 ==========
  function handleTempCodeGenerated(code: string) {
    singleForm.product_code = code;
    showMessage(`已生成临时货号：${code}`, 'info');
  }

  // ========== 事件处理 ==========
  // 移除：公共图片变更处理函数（已无公共图片字段）
  function handleVariationImageChange(variation: FeatureVariation, path: string): void {
    variation.图片路径 = path;
  }

  // 新增：填充功能实现（仅填充所有行）
  function handleFillValues(): void {
    // 过滤掉空值的填充字段
    const validFillValues = Object.entries(fillValues).reduce((acc, [key, value]) => {
      if (value !== '' && value !== undefined && value !== null) {
        acc[key as keyof FeatureVariation] = value;
      }
      return acc;
    }, {} as Partial<FeatureVariation>);

    if (Object.keys(validFillValues).length === 0) {
      showMessage('请先填写需要填充的字段值', 'warning');
      return;
    }

    // 填充所有行
    featureVariations.forEach(variation => {
      Object.entries(validFillValues).forEach(([key, value]) => {
        const fieldKey = key as keyof FeatureVariation;
        switch (fieldKey) {
          case '入库数量':
            variation[fieldKey] = value ? Number(value) : 1;
            break;
          case '单价':
          case '重量':
            variation[fieldKey] = value ? value.toString() : '';
            break;
          default:
            variation[fieldKey] = value as never;
        }
      });
    });

    // 触发响应式更新
    featureVariations = [...featureVariations];
    showMessage(`已成功填充${featureVariations.length}行数据`, 'success');
  }

  let previousSingle地址类型: number = singleForm.地址类型;
  $: if (singleForm.地址类型 !== previousSingle地址类型) {
    if ([1, 3, 5].includes(previousSingle地址类型) && ![1, 3, 5].includes(singleForm.地址类型)) singleForm.架号 = '';
    if ([2, 3, 4, 5].includes(previousSingle地址类型) && ![2, 3, 4, 5].includes(singleForm.地址类型)) singleForm.框号 = '';
    if ([4, 5, 6].includes(previousSingle地址类型) && ![4, 5, 6].includes(singleForm.地址类型)) singleForm.包号 = '';
    previousSingle地址类型 = singleForm.地址类型;
    fetchLastAddressInfo(singleForm.地址类型, 'single');
  }

  async function handleSingleGetDefaultAddress(): Promise<void> {
    if (singleForm.地址类型) {
      await fetchLastAddressInfo(singleForm.地址类型, 'single');
      if ([1, 3, 5].includes(singleForm.地址类型) && lastAddressInfo.架号) singleForm.架号 = lastAddressInfo.架号;
      if ([2, 3, 4, 5].includes(singleForm.地址类型) && lastAddressInfo.框号) singleForm.框号 = lastAddressInfo.框号;
      if ([4, 5, 6].includes(singleForm.地址类型) && lastAddressInfo.包号) singleForm.包号 = lastAddressInfo.包号;
      showMessage('已获取默认地址信息', 'success');
    } else {
      showMessage('请先选择地址类型', 'error');
    }
  }

  function addFeatureVariation(): void {
    featureVariations.push({
      单价: '',
      重量: '',
      规格: '',
      材质: '',
      颜色: '',
      形状: '',
      风格: '',
      入库数量: 1,
      单位: '',
      图片路径: ''
    });
    featureVariations = [...featureVariations];
  }

  function quickAddVariations(count: number = 5): void {
    for (let i = 0; i < count; i++) addFeatureVariation();
  }

  function removeFeatureVariation(index: number): void {
    featureVariations.splice(index, 1);
    featureVariations = [...featureVariations];
  }

  function calculateTotalQuantity(): number {
    return featureVariations.reduce((total, v) => total + (parseInt(v.入库数量.toString()) || 0), 0);
  }

  // ========== 表单验证 ==========
  function validateSingleForm(): boolean {
    try {
      if (!singleForm.product_code) throw new Error('请填写商品编号');

      const requiredFields = {
        类型: { label: '类型', required: true, type: 'string' },
        楼层: { label: '楼层', required: true, type: 'string' }
      };
      validateFormData(singleForm, requiredFields);

      if (featureVariations.length === 0) throw new Error('请至少添加一个特征组合');

      for (let i = 0; i < featureVariations.length; i++) {
        const variation = featureVariations[i];
        const qty = parseInt(variation.入库数量.toString()) || 0;
        if (qty <= 0) throw new Error(`第${i + 1}行：请填写有效的数量`);

        const hasFeatureValue = featureFields.some(field =>
          field.id !== '入库数量' && field.id !== '图片路径' &&
          variation[field.id] && variation[field.id].toString().trim() !== ''
        );
        if (!hasFeatureValue) throw new Error(`第${i + 1}行：请至少填写一个特征值（单价/重量/规格/材质/颜色/形状/风格/单位）`);
      }

      const addressValidations = [
        { types: [1, 3, 5], field: '架号', message: '架号不能为空' },
        { types: [2, 3, 4, 5], field: '框号', message: '框号不能为空' },
        { types: [4, 5, 6], field: '包号', message: '包号不能为空' }
      ];
      for (const v of addressValidations) {
        if (v.types.includes(singleForm.地址类型) && !singleForm[v.field]) throw new Error(v.message);
      }

      return true;
    } catch (error) {
      showMessage((error as Error).message, 'error');
      return false;
    }
  }

  // ========== 入库数据准备 ==========
  function prepareProductData(formData: SingleForm, productCode: string): ProductStockInData {
    const data: ProductStockInData = {
      货号: productCode,
      类型: formData.类型,
      入库数量: 0,
      地址类型: parseInt(formData.地址类型.toString()),
      楼层: parseInt(formData.楼层.toString()),
      架号: formData.架号,
      框号: formData.框号,
      包号: formData.包号,
      厂家: formData.厂家 || undefined,
      厂家地址: formData.厂家地址 || undefined,
      电话: formData.电话 || undefined,
      用途: formData.用途 || undefined,
      备注: formData.备注 || undefined,
      批次: formData.批次 ? parseInt(formData.批次) : undefined,
      操作人: formData.操作人 || undefined
      // 彻底移除：公共图片路径相关
    };
    if (!formData.use_auto_in_time && formData.入库时间) data.入库时间 = formData.入库时间;
    Object.keys(data).forEach(key => {
      if (data[key as keyof ProductStockInData] == null || data[key as keyof ProductStockInData] === '') delete data[key as keyof ProductStockInData];
    });
    return data;
  }

  function prepareSingleStockInData(): ProductStockInData[] {
    return featureVariations.map(variation => {
      const productData = prepareProductData(singleForm, singleForm.product_code);
      // 仅从特征组合中获取特征字段值
      featureFields.forEach(field => {
        if (field.id !== '入库数量' && variation[field.id]) {
          const val = variation[field.id];
          if (val.toString().trim() !== '') {
            productData[field.id] = field.type === 'number' ? parseFloat(val.toString()) : val;
          }
        }
      });
      productData.入库数量 = parseInt(variation.入库数量.toString()) || 0;
      // 仅使用特征组合自身的图片（无公共图片兜底）
      if (variation.图片路径) productData.图片路径 = variation.图片路径;
      return productData;
    });
  }

  // ========== 入库操作 ==========
  async function handleSingleStockIn(): Promise<void> {
    if (!validateSingleForm()) return;
    updateLoading(true);
    try {
      const stockInItems = prepareSingleStockInData();
      const response = await api.batchStockIn({ stock_in_items: stockInItems }) as ApiSuccessResponse<{
        success_count: number;
        error_count: number;
        success_details: string[];
        error_details: string[];
      }>;
      if (response.status === 'success') {
        const { success_count, error_count, error_details } = response.data || { success_count: 0, error_count: 0, error_details: [] };
        if (success_count > 0) showMessage(`多特征入库成功！成功: ${success_count} 个，失败: ${error_count} 个`, 'success');
        if (error_count > 0 && error_details) {
          const msg = error_details.slice(0, 3).join('; ') + (error_details.length > 3 ? '...' : '');
          showMessage(`部分入库失败: ${msg}`, 'warning');
        }
        resetSingleForm();
      } else {
        showMessage(response.message || '入库失败', 'error');
      }
    } catch (error) {
      console.error('入库错误:', error);
      showMessage(handleApiError(error, '入库请求失败'), 'error');
    } finally {
      updateLoading(false);
    }
  }

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
      厂家: '',
      厂家地址: '',
      电话: '',
      用途: '',
      备注: '',
      批次: '',
      操作人: ''
      // 彻底移除：公共图片路径重置
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
      单位: '',
      图片路径: ''
    }];
    // 重置填充值
    fillValues = {
      单价: '',
      重量: '',
      规格: '',
      材质: '',
      颜色: '',
      形状: '',
      风格: '',
      入库数量: '',
      单位: '',
      图片路径: ''
    };
  }

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
    <!-- 商品编号、类型、操作人、批次 -->
    <div class="form-section">
      <div class="form-row compact-row">
        <div class="form-group">
          <label for="product_code">商品编号 *</label>
          <div class="input-with-button">
            <input
              id="product_code"
              type="text"
              bind:value={singleForm.product_code}
              placeholder="如：PROD001"
              required
              disabled={loading}
            />
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

    <!-- 地址类型、楼层、架号、框号、包号 -->
    <div class="form-section">
      <div class="form-row compact-row">
        <div class="form-group">
          <label for="single_地址类型">地址类型 *</label>
          <select id="single_地址类型" bind:value={singleForm.地址类型} disabled={loading}>
            <option value={1}>楼层+架号</option>
            <option value={2}>楼层+框号</option>
            <option value={3}>楼层+架号+框号</option>
            <option value={4}>楼层+框号+包号</option>
            <option value={5}>楼层+架号+框号+包号</option>
            <option value={6}>楼层+包号</option>
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

      <div class="form-group">
        <button type="button" class="btn-default" on:click={handleSingleGetDefaultAddress} disabled={loading}>
          获取默认地址信息
        </button>
      </div>
    </div>

    <!-- 公共字段区域：仅保留厂家、厂家地址、电话、用途、备注 -->
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
        <!-- 彻底移除：公共图片输入框 -->
      </div>
    </div>

    <!-- 特征组合列表（包含所有特征字段，图片仅在组合中显示） -->
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

      <div class="feature-variations-table" style="width: 100%;">
        <div class="table-header" style="display: flex; border-bottom: 1px solid #eee;">
          <div class="row" style="display: flex; width: 100%;">
            {#each featureFields as field}
              <div class="cell" style={`padding: 8px; text-align: center; ${field.id === '单位' ? 'width: 60px;' : 'flex: 1; min-width: 70px;'}`}>
                <span>{field.label}{field.required ? ' *' : ''}</span>
              </div>
            {/each}
            <div class="cell actions" style="padding: 8px; min-width: 80px; text-align: center;">操作</div>
          </div>
        </div>

        <!-- 新增：填充功能行（移除了下拉框，按钮改为绿色） -->
        <div class="table-fill-row" style="display: flex; width: 100%; align-items: center; background: #f9f9f9; border-bottom: 2px solid #eee; padding: 4px 0;">
          {#each featureFields as field}
            <div class="cell" style={`padding: 4px 8px; ${field.id === '单位' ? 'width: 60px;' : 'flex: 1; min-width: 70px;'}`}>
              {#if field.type === 'number'}
                <input
                  type="text"
                  bind:value={fillValues[field.id]}
                  placeholder={`填充${field.label}`}
                  disabled={loading}
                  style="width: 100%; padding: 4px; background: #fefefe;"
                />
              {:else if field.type === 'image'}
                <div style="color: #999; font-size: 12px; padding: 4px; text-align: center;"></div>
              {:else}
                <input
                  type="text"
                  bind:value={fillValues[field.id]}
                  placeholder={`填充${field.label}`}
                  disabled={loading}
                  style="width: 100%; padding: 4px; background: #fefefe;"
                />
              {/if}
            </div>
          {/each}
          <div class="cell actions" style="padding: 4px 8px; min-width: 80px; text-align: center;">
            <button
              type="button"
              class="btn-fill"
              on:click={handleFillValues}
              disabled={loading}
              style="padding: 4px 8px; font-size: 12px; width: 100%;"
            >
              填充
            </button>
          </div>
        </div>

        <div class="table-body">
          {#each featureVariations as variation, index}
            <div class="row" style="display: flex; width: 100%; align-items: center; border-bottom: 1px solid #f5f5f5; padding: 4px 0;">
              {#each featureFields as field}
                <div class="cell" style={`padding: 4px 8px; ${field.id === '单位' ? 'width: 60px;' : 'flex: 1; min-width: 70px;'}`}>
                  {#if field.type === 'number'}
                    <input
                      type="text"
                      bind:value={variation[field.id]}
                      placeholder={field.label}
                      required={field.required}
                      disabled={loading}
                      style="width: 100%; padding: 4px;"
                    />
                  {:else if field.type === 'image'}
                    <ImageUpload
                      bind:value={variation[field.id]}
                      productCode={`${singleForm.product_code}_var_${index}`}
                      on:change={(path) => handleVariationImageChange(variation, path)}
                      disabled={loading}
                      style="width: 100%;"
                    />
                  {:else}
                    <input
                      type="text"
                      bind:value={variation[field.id]}
                      placeholder={field.label}
                      disabled={loading}
                      style="width: 100%; padding: 4px;"
                    />
                  {/if}
                </div>
              {/each}
              <div class="cell actions" style="padding: 4px 8px; min-width: 80px; text-align: center;">
                {#if featureVariations.length > 1}
                  <button
                    type="button"
                    class="btn-danger"
                    on:click={() => removeFeatureVariation(index)}
                    disabled={loading}
                    style="padding: 4px 8px; font-size: 12px;"
                  >
                    删除
                  </button>
                {/if}
              </div>
            </div>
          {/each}
        </div>

        <div class="table-footer" style="padding: 8px; border-top: 1px solid #eee;">
          <div class="total-summary" style="display: flex; gap: 20px;">
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
    <div class="form-group inline-checkbox" style="margin: 16px 0;">
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

    <button type="submit" class="btn-primary" disabled={loading} style="padding: 8px 24px; margin-top: 16px;">
      {getSingleButtonText()}
    </button>
  </form>
</div>

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
  .form-section {
    margin-bottom: 16px;
    padding: 12px;
    border: 1px solid #f0f0f0;
    border-radius: 4px;
  }
  .form-row.compact-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
  }
  .form-group {
    flex: 1;
    min-width: 120px;
  }
  .form-group label {
    display: block;
    margin-bottom: 4px;
    font-size: 14px;
  }
  .form-group input, .form-group select {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
  }
  .btn-default {
    padding: 6px 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    background: #f8f8f8;
    cursor: pointer;
  }
  .btn-primary {
    background: #1890ff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-danger {
    background: #ff4d4f;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  /* 新增：绿色填充按钮样式 */
  .btn-fill {
    background: #52c41a;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-fill:disabled {
    background: #a3d987;
    cursor: not-allowed;
  }
  .table-fill-row input {
    border: 1px solid #e0e0e0;
    border-radius: 3px;
  }
</style>