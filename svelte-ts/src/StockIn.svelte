<script lang="ts">
  import { onMount } from 'svelte';
  // 适配 api.ts 导入（若路径有别名可调整）
  import { api, formatStockInData, validateFormData, handleApiError } from './lib/api.ts';
  import type { ApiSuccessResponse } from './lib/api.ts';
  // 导入图片上传子组件
  import ImageUpload from './image/ImageUpload.svelte';

  // ========== 核心类型定义 ==========
  /** 活跃标签类型 */
  type ActiveTab = 'batch' | 'single';

  /** 特征组合类型 */
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

  /** 批量差异信息类型 */
  interface BatchVariation {
    product_code: string;
    [key: string]: string | number | undefined;
  }

  /** 特征字段配置类型 */
  interface FeatureField {
    id: '单价' | '重量' | '规格' | '材质' | '颜色' | '形状' | '风格' | '入库数量' | '图片路径';
    label: string;
    type: 'number' | 'text' | 'image';
    required: boolean;
  }

  /** 差异化字段配置类型 */
  interface VariableField {
    id: '入库数量' | '单价' | '重量' | '规格' | '材质' | '颜色' | '形状' | '风格' | '厂家' | '厂家地址' | '电话' | '用途' | '备注' | '图片路径';
    label: string;
    type: 'number' | 'text';
    enabled: boolean;
  }

  /** 单特征入库表单类型 */
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

  /** 批量入库表单类型 */
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

  /** 最后地址信息类型 */
  interface LastAddressInfo {
    架号: string;
    框号: string;
    包号: string;
  }

  /** 地址验证规则类型 */
  interface AddressValidation {
    types: number[];
    field: '架号' | '框号' | '包号';
    message: string;
  }

  /** 商品入库数据类型 */
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

  // ========== Props 定义（带类型注解） ==========
  export let productTypes: string[] = [];
  export let floors: number[] = [];
  export let loading: boolean = false;
  export let showMessage: (text: string, type?: 'info' | 'success' | 'error' | 'warning') => void = () => {};
  export let debounce: <T extends (...args: any[]) => any>(func: T, wait: number) => T = (func) => func as any;

  // ========== 状态变量（带类型注解） ==========
  let activeTab: ActiveTab = 'batch';

  // 多特征入库的表单数据
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

  // 单号/连号入库表单数据
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

  // 多特征入库的特征组合
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

  // 单号/连号入库的商品差异信息
  let batchVariations: BatchVariation[] = [];

  // 多特征入库的特征字段定义
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

  // 单号/连号入库的可差异化字段配置
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

  // 最后地址信息
  let lastAddressInfo: LastAddressInfo = {
    架号: '',
    框号: '',
    包号: ''
  };

  // 初始化标记
  let hasInitialized: boolean = false;

  // 计算总数量（响应式）
  $: totalQuantity = calculateTotalQuantity();

  // ========== 图片上传处理函数（带类型注解） ==========
  function handleSingleImageChange(path: string): void {
    singleForm.图片路径 = path;
  }

  function handleBatchImageChange(path: string): void {
    batchForm.图片路径 = path;
  }

  function handleVariationImageChange(variation: FeatureVariation, path: string): void {
    variation.图片路径 = path;
  }

  // ========== 地址信息相关函数（带类型注解） ==========
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

        // 初始化填充
        if (!hasInitialized) {
          const form = formType === 'single' ? singleForm : batchForm;

          if ([1, 3, 5].includes(addressType) && !form.架号 && lastAddressInfo.架号) {
            form.架号 = lastAddressInfo.架号;
          }
          if ([2, 3, 4, 5].includes(addressType) && !form.框号 && lastAddressInfo.框号) {
            form.框号 = lastAddressInfo.框号;
          }
          if ([4, 5, 6].includes(addressType) && !form.包号 && lastAddressInfo.包号) {
            form.包号 = lastAddressInfo.包号;
          }
          hasInitialized = true;
        }
      }
    } catch (error) {
      console.error('获取最后地址信息失败:', error);
    } finally {
      loading = false;
    }
  }

  // 页面加载初始化
  onMount(() => {
    if (singleForm.地址类型) {
      fetchLastAddressInfo(singleForm.地址类型, 'single');
    }
  });

  // 地址类型变化处理（多特征入库）
  function handleSingleAddressTypeChange(newAddressType: number, oldAddressType: number): void {
    if ([1, 3, 5].includes(oldAddressType) && ![1, 3, 5].includes(newAddressType)) {
      singleForm.架号 = '';
    }

    if ([2, 3, 4, 5].includes(oldAddressType) && ![2, 3, 4, 5].includes(newAddressType)) {
      singleForm.框号 = '';
    }

    if ([4, 5, 6].includes(oldAddressType) && ![4, 5, 6].includes(newAddressType)) {
      singleForm.包号 = '';
    }

    lastAddressInfo = {
      架号: '',
      框号: '',
      包号: ''
    };
  }

  // 地址类型变化处理（单号/连号入库）
  function handleBatchAddressTypeChange(newAddressType: number, oldAddressType: number): void {
    if ([1, 3, 5].includes(oldAddressType) && ![1, 3, 5].includes(newAddressType)) {
      batchForm.架号 = '';
    }

    if ([2, 3, 4, 5].includes(oldAddressType) && ![2, 3, 4, 5].includes(newAddressType)) {
      batchForm.框号 = '';
    }

    if ([4, 5, 6].includes(oldAddressType) && ![4, 5, 6].includes(newAddressType)) {
      batchForm.包号 = '';
    }

    lastAddressInfo = {
      架号: '',
      框号: '',
      包号: ''
    };
  }

  // 监听地址类型变化（多特征入库）
  let previousSingle地址类型: number = singleForm.地址类型;
  $: if (singleForm.地址类型 !== previousSingle地址类型) {
    handleSingleAddressTypeChange(singleForm.地址类型, previousSingle地址类型);
    previousSingle地址类型 = singleForm.地址类型;

    if (singleForm.地址类型) {
      fetchLastAddressInfo(singleForm.地址类型, 'single');
    }
  }

  // 监听地址类型变化（单号/连号入库）
  let previousBatch地址类型: number = batchForm.地址类型;
  $: if (batchForm.地址类型 !== previousBatch地址类型) {
    handleBatchAddressTypeChange(batchForm.地址类型, previousBatch地址类型);
    previousBatch地址类型 = batchForm.地址类型;

    if (batchForm.地址类型) {
      fetchLastAddressInfo(batchForm.地址类型, 'batch');
    }
  }

  // 手动获取默认地址（多特征）
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

  // 手动获取默认地址（批量）
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

  // 启用的差异字段（响应式）
  $: enabledVariableFields = variableFields.filter(field => field.enabled);

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

  // ========== 多特征入库相关函数 ==========
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

    // 触发响应式更新
    featureVariations = [...featureVariations];
  }

  function quickAddVariations(count: number = 5): void {
    for (let i = 0; i < count; i++) {
      addFeatureVariation();
    }
  }

  function removeFeatureVariation(index: number): void {
    featureVariations.splice(index, 1);
    featureVariations = [...featureVariations];
  }

  function quickFillAllFeatures(fieldId: string, value: string | number): void {
    requestAnimationFrame(() => {
      featureVariations = featureVariations.map(variation => ({
        ...variation,
        [fieldId]: value
      }));
    });
  }

  function calculateTotalQuantity(): number {
    let total = 0;
    for (const variation of featureVariations) {
      const qty = parseInt(variation.入库数量.toString()) || 0;
      total += qty;
    }
    return total;
  }

  function validateSingleForm(): boolean {
    try {
      if (!singleForm.product_code) {
        throw new Error('请填写商品编号');
      }

      // 必填字段验证
      const requiredFields = {
        类型: { label: '商品类型', required: true },
        楼层: { label: '楼层', required: true }
      };

      // 调用 validateFormData（适配 TS 类型）
      validateFormData(singleForm, Object.fromEntries(
        Object.entries(requiredFields).map(([key, val]) => [key, { ...val, type: 'string' }])
      ));

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

  function prepareProductData(formData: SingleForm | BatchForm, productCode: string): ProductStockInData {
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

  async function handleSingleStockIn(): Promise<void> {
    if (!validateSingleForm()) return;

    loading = true;
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
      loading = false;
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
    hasInitialized = false;
  }

  // ========== 单号/连号入库相关函数 ==========
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
        类型: { label: '商品类型', required: true },
        楼层: { label: '楼层', required: true }
      };
      validateFormData(batchForm, Object.fromEntries(
        Object.entries(requiredFields).map(([key, val]) => [key, { ...val, type: 'string' }])
      ));

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
    hasInitialized = false;
  }

  async function handleBatchStockIn(): Promise<void> {
    if (!validateBatchForm()) return;

    loading = true;
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
      loading = false;
    }
  }

  function quickFillVariations(fieldId: string, value: string | number): void {
    batchVariations = batchVariations.map(variation => ({
      ...variation,
      [fieldId]: value
    }));
  }

  function getProductCountText(): string {
    if (!batchForm.start_code) {
      return '请填写起始编号';
    }

    const count = generateBatchCodes(batchForm.start_code, batchForm.end_code).length;
    return count === 1 ? '1 个商品（单号入库）' : `${count} 个商品（连号入库）`;
  }

  function getSingleButtonText(): string {
    const baseText = loading ? '入库中...' : '多特征入库';
    return `${baseText} (${featureVariations.length}个组合, ${totalQuantity}个商品)`;
  }

  function getBatchButtonText(): string {
    const count = batchForm.start_code ? generateBatchCodes(batchForm.start_code, batchForm.end_code).length : 0;
    const baseText = loading ? '入库中...' : (count === 1 ? '单号入库' : `批量入库 (${count}个)`);
    return baseText;
  }
</script>

<section class="form-section">
  <!-- 选项卡导航 -->
  <div class="tab-nav">
    <button
      class:active={activeTab === 'single'}
      on:click={() => activeTab = 'single'}
    >
      多特征入库
    </button>
    <button
      class:active={activeTab === 'batch'}
      on:click={() => activeTab = 'batch'}
    >
      单号/连号入库
    </button>
  </div>

  <!-- 多特征入库表单 -->
  {#if activeTab === 'single'}
  <div class="multi-feature-form">
    <h2>商品入库 - 多特征入库</h2>
    <p class="help-text">
      为一个商品编号创建多个特征组合，每个特征组合会生成独立的库存记录。
      适用于同一商品有不同规格、颜色、形状、风格的场景。
    </p>

    <form on:submit|preventDefault={handleSingleStockIn}>
      <!-- 第一行：商品编号、商品类型、操作人、批次 -->
      <div class="form-section">
        <div class="form-row compact-row">
          <div class="form-group">
            <label for="product_code">商品编号 *</label>
            <input
              id="product_code"
              type="text"
              bind:value={singleForm.product_code}
              placeholder="如：PROD001"
              required
            />
          </div>
          <div class="form-group">
            <label for="single_类型">商品类型 *</label>
            <select id="single_类型" bind:value={singleForm.类型} required>
              <option value="">请选择商品类型</option>
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
            />
          </div>
        </div>
      </div>

      <!-- 第二行：地址类型、楼层、架号、框号、包号 -->
      <div class="form-section">
        <div class="form-row compact-row">
          <div class="form-group">
            <label for="single_地址类型">地址类型 *</label>
            <select id="single_地址类型" bind:value={singleForm.地址类型}>
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
            <select id="single_楼层" bind:value={singleForm.楼层} required>
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
                />
                {#if lastAddressInfo.架号}
                  <button type="button" class="btn-default" on:click={() => singleForm.架号 = lastAddressInfo.架号}>
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
                />
                {#if lastAddressInfo.框号}
                  <button type="button" class="btn-default" on:click={() => singleForm.框号 = lastAddressInfo.框号}>
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
                />
                {#if lastAddressInfo.包号}
                  <button type="button" class="btn-default" on:click={() => singleForm.包号 = lastAddressInfo.包号}>
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
          <button type="button" class="btn-default" on:click={handleSingleGetDefaultAddress}>
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
                  />
                {:else}
                  <input
                    id="single_feature_{field.id}"
                    type="text"
                    bind:value={singleForm[field.id]}
                    placeholder={`${field.label}（公共值）`}
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
            />
          </div>
          <div class="form-group">
            <label for="single_厂家地址">厂家地址</label>
            <input
              id="single_厂家地址"
              type="text"
              bind:value={singleForm.厂家地址}
              placeholder="请输入厂家地址"
            />
          </div>
          <div class="form-group">
            <label for="single_电话">电话</label>
            <input
              id="single_电话"
              type="text"
              bind:value={singleForm.电话}
              placeholder="请输入电话"
            />
          </div>
          <div class="form-group">
            <label for="single_用途">用途</label>
            <input
              id="single_用途"
              type="text"
              bind:value={singleForm.用途}
              placeholder="请输入用途"
            />
          </div>
          <div class="form-group">
            <label for="single_备注">备注</label>
            <input
              id="single_备注"
              type="text"
              bind:value={singleForm.备注}
              placeholder="请输入备注"
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
            <button type="button" class="btn-default" on:click={addFeatureVariation}>
              + 添加单个组合
            </button>
            <button type="button" class="btn-default" on:click={() => quickAddVariations(5)}>
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
          />
        </div>
      {/if}

      <button type="submit" class="btn-primary" disabled={loading}>
        {getSingleButtonText()}
      </button>
    </form>
  </div>
  {/if}

  <!-- 单号/连号入库表单 -->
  {#if activeTab === 'batch'}
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
            />
          </div>
          <div class="form-group">
            <label for="end_code">结束编号</label>
            <input
              id="end_code"
              type="text"
              bind:value={batchForm.end_code}
              placeholder="如：PROD010"
            />
          </div>
          <div class="form-group">
            <label for="batch_类型">商品类型 *</label>
            <select id="batch_类型" bind:value={batchForm.类型} required>
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
            />
          </div>
        </div>
      </div>

      <!-- 第二行：地址类型、楼层、数量、架号、框号、包号 -->
      <div class="form-section">
        <div class="form-row compact-row">
          <div class="form-group">
            <label for="batch_地址类型">地址类型 *</label>
            <select id="batch_地址类型" bind:value={batchForm.地址类型}>
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
            <select id="batch_楼层" bind:value={batchForm.楼层} required>
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
                />
                {#if lastAddressInfo.架号}
                  <button type="button" class="btn-default" on:click={() => batchForm.架号 = lastAddressInfo.架号}>
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
                />
                {#if lastAddressInfo.框号}
                  <button type="button" class="btn-default" on:click={() => batchForm.框号 = lastAddressInfo.框号}>
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
                />
                {#if lastAddressInfo.包号}
                  <button type="button" class="btn-default" on:click={() => batchForm.包号 = lastAddressInfo.包号}>
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
          <button type="button" class="btn-default" on:click={handleBatchGetDefaultAddress}>
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
                  />
                {:else}
                  <input
                    id="batch_{field.id}"
                    type="text"
                    bind:value={batchForm[field.id]}
                    placeholder={`请输入${field.label}`}
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
                  />
                {:else}
                  <input
                    id="batch_{field.id}"
                    type="text"
                    bind:value={batchForm[field.id]}
                    placeholder={`请输入${field.label}`}
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
                        />
                      {:else}
                        <input
                          type="text"
                          bind:value={variation[field.id]}
                          placeholder={batchForm[field.id] || `请输入${field.label}`}
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
          />
        </div>
      {/if}

      <button type="submit" class="btn-primary" disabled={loading}>
        {getBatchButtonText()}
      </button>
    </form>
  </div>
  {/if}
</section>

<style>
  /* 全局基础样式 */
  * {
    box-sizing: border-box;
  }

  .tab-nav {
    display: flex;
    gap: 6px;
    margin-bottom: 12px;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 6px;
  }

  .tab-nav button {
    padding: 8px 16px;
    background: #f8f9fa;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    color: #6c757d;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .tab-nav button:hover {
    background: #e9ecef;
    color: #495057;
  }

  .tab-nav button.active {
    background: #3498db;
    color: white;
  }

  .form-section {
    max-width: 1400px;
    margin: 0 auto;
    padding: 0 6px;
  }

  .form-section h2 {
    color: #2c3e50;
    margin-bottom: 8px;
    font-size: 1.2rem;
  }

  .form-section h3 {
    color: #34495e;
    margin: 8px 0 6px 0;
    font-size: 1rem;
    border-bottom: 1px solid #eee;
    padding-bottom: 4px;
  }

  .help-text {
    color: #6c757d;
    font-size: 11px;
    margin-bottom: 8px;
    line-height: 1.3;
  }

  /* 表单组样式 */
  .form-group {
    margin-bottom: 8px;
  }

  label {
    display: block;
    margin-bottom: 4px;
    font-weight: 500;
    color: #555;
    font-size: 11px;
  }

  /* 核心紧凑布局 */
  .form-row {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 6px;
    margin-bottom: 8px;
    align-items: start;
  }

  /* 紧凑行 - 用于需要多列紧凑排列的行 */
  .compact-row {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 6px;
    margin-bottom: 8px;
  }

  /* 输入框和选择框 */
  input, select {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 11px;
    transition: border-color 0.2s ease;
    box-sizing: border-box;
    min-height: 30px;
    background: white;
  }

  input:focus, select:focus {
    outline: none;
    border-color: #3498db;
    box-shadow: 0 0 0 2px rgba(52, 152, 219, 0.2);
  }

  /* 按钮样式 */
  .btn-primary {
    background: #3498db;
    color: white;
    padding: 8px 16px;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
    margin-top: 12px;
    display: block;
    width: 100%;
  }

  .btn-primary:hover:not(:disabled) {
    background: #2980b9;
  }

  .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .btn-default {
    background: #6c757d;
    color: white;
    padding: 4px 8px;
    border: none;
    border-radius: 3px;
    font-size: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
  }

  .btn-default:hover {
    background: #5a6268;
  }

  .btn-danger {
    background: #dc3545;
    color: white;
    padding: 4px 8px;
    border: none;
    border-radius: 3px;
    font-size: 10px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .btn-danger:hover {
    background: #c82333;
  }

  /* 复选框样式 */
  .checkbox-label {
    display: flex;
    align-items: center;
    gap: 4px;
    font-weight: normal;
    cursor: pointer;
    margin-bottom: 6px;
    font-size: 11px;
  }

  .checkbox-label.compact {
    padding: 3px 5px;
    border: 1px solid #e0e0e0;
    border-radius: 3px;
    transition: all 0.2s ease;
    margin-bottom: 4px;
    font-size: 10px;
  }

  .checkbox-label.compact:hover {
    background: #f8f9fa;
    border-color: #3498db;
  }

  .checkbox-label.compact input {
    width: auto;
    margin: 0;
    padding: 0;
    min-height: auto;
  }

  .inline-checkbox {
    display: inline-block;
    margin-right: 12px;
  }

  /* 差异化字段网格 */
  .variable-fields-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
    gap: 4px;
    margin-bottom: 8px;
  }

  /* 多特征入库专用样式 */
  .multi-feature-form .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 6px;
  }

  .header-actions {
    display: flex;
    gap: 4px;
    align-items: center;
  }

  .combination-count {
    color: #3498db;
    font-weight: 500;
    font-size: 11px;
  }

  /* 特征组合表格 - 适配图片列宽度 */
  .feature-variations-table {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
    width: 100%;
  }

  .feature-variations-table .table-header {
    background: #f8f9fa;
    border-bottom: 1px solid #e0e0e0;
  }

  /* 表格列宽优化，新增图片列 */
  .feature-variations-table .row {
    display: grid;
    grid-template-columns: 60px 60px 80px 80px 80px 80px 80px 50px 100px 40px;
    gap: 1px;
    background: #f8f9fa;
    width: 100%;
  }

  .feature-variations-table .row:not(:last-child) {
    border-bottom: 1px solid #e0e0e0;
  }

      .feature-variations-table .cell {
      padding: 4px;
      background: white;
      display: flex;
      align-items: center;
      min-height: 32px;
      box-sizing: border-box;
      font-size: 11px;
    }

    .feature-variations-table .cell.quantity {
      width: 50px;
    }

    .feature-variations-table .cell.actions {
      width: 40px;
      justify-content: center;
    }

    .feature-variations-table .table-body .row {
      background: white;
    }

    .feature-variations-table .table-body .row:hover {
      background: #f8f9fa;
    }

    .feature-variations-table .table-body input {
      width: 100%;
      padding: 3px 5px;
      font-size: 10px;
      min-height: 24px;
    }

    .feature-variations-table .table-footer {
      padding: 6px;
      background: #f8f9fa;
      border-top: 1px solid #e0e0e0;
    }

    .total-summary {
      display: flex;
      gap: 16px;
      font-size: 11px;
      color: #34495e;
    }

    .summary-item {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    /* 单号/连号入库表格样式 */
    .batch-variations-table {
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      overflow: hidden;
      margin-bottom: 8px;
      width: 100%;
    }

    .batch-variations-table .table-header {
      background: #f8f9fa;
      border-bottom: 1px solid #e0e0e0;
    }

    .batch-variations-table .row {
      display: grid;
      grid-template-columns: 100px repeat(auto-fill, minmax(120px, 1fr));
      gap: 1px;
      background: #f8f9fa;
      width: 100%;
    }

    .batch-variations-table .cell {
      padding: 4px;
      background: white;
      display: flex;
      align-items: center;
      min-height: 32px;
      box-sizing: border-box;
      font-size: 11px;
    }

    .batch-variations-table .cell.product-code {
      font-weight: 500;
      color: #2c3e50;
      padding-left: 8px;
    }

    .batch-variations-table .cell.variable-field {
      width: 100%;
    }

    .batch-variations-table .table-body .row {
      background: white;
    }

    .batch-variations-table .table-body .row:hover {
      background: #f8f9fa;
    }

    .batch-variations-table .table-body input {
      width: 100%;
      padding: 3px 5px;
      font-size: 10px;
      min-height: 24px;
    }

    /* 输入框+按钮组合样式 */
    .input-with-button {
      display: flex;
      gap: 4px;
      align-items: center;
      width: 100%;
    }

    .input-with-button input {
      flex: 1;
      min-width: 0;
    }

    .input-with-button .btn-default {
      white-space: nowrap;
      padding: 4px 6px;
      font-size: 9px;
      height: 30px;
    }

    /* 默认值提示样式 */
    .default-hint {
      font-size: 9px;
      color: #6c757d;
      margin-top: 2px;
      font-style: italic;
    }

    /* 批量填充按钮样式 */
    .btn-quick-fill {
      background: #28a745;
      color: white;
      border: none;
      border-radius: 2px;
      padding: 2px 4px;
      font-size: 9px;
      cursor: pointer;
      margin-left: 4px;
      white-space: nowrap;
    }

    .btn-quick-fill:hover {
      background: #218838;
    }

    /* 图片上传组件适配样式 */
    .ImageUpload {
      width: 100%;
    }

    .ImageUpload input {
      font-size: 9px;
      padding: 2px 4px;
    }

    /* 响应式适配 */
    @media (max-width: 1200px) {
      .compact-row {
        grid-template-columns: repeat(4, 1fr);
      }

      .feature-variations-table .row {
        grid-template-columns: 50px 50px 70px 70px 70px 70px 70px 40px 90px 35px;
      }
    }

    @media (max-width: 992px) {
      .compact-row {
        grid-template-columns: repeat(3, 1fr);
      }

      .feature-variations-table .row {
        grid-template-columns: 45px 45px 60px 60px 60px 60px 60px 35px 80px 30px;
      }

      .batch-variations-table .row {
        grid-template-columns: 80px repeat(auto-fill, minmax(100px, 1fr));
      }
    }

    @media (max-width: 768px) {
      .compact-row {
        grid-template-columns: repeat(2, 1fr);
      }

      .feature-variations-table .row {
        grid-template-columns: 40px 40px 50px 50px 50px 50px 50px 30px 70px 25px;
      }

      .total-summary {
        flex-direction: column;
        gap: 4px;
      }
    }

    @media (max-width: 576px) {
      .compact-row {
        grid-template-columns: 1fr;
      }

      .tab-nav {
        flex-direction: column;
        gap: 4px;
      }

      .feature-variations-table .row {
        display: flex;
        flex-wrap: wrap;
        gap: 2px;
      }

      .feature-variations-table .cell {
        flex: 1 1 calc(50% - 2px);
        min-width: 80px;
      }

      .batch-variations-table .row {
        display: flex;
        flex-wrap: wrap;
      }

      .batch-variations-table .cell {
        flex: 1 1 100%;
        min-width: 0;
      }
    }
</style>