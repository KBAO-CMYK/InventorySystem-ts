// api.ts - 适配特征ID图片接口版 (TypeScript 重构)
const API_BASE = 'http://192.168.110.40:5000/api' as const;

// ===================== 核心类型定义（新增图片添加相关类型） =====================
/** 通用请求选项类型（扩展fetch的RequestInit） */
interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: Record<string, any>;
  headers?: Record<string, string>;
}

/** 通用API成功响应类型 */
export interface ApiSuccessResponse<T = any> {
  status: 'success';
  message?: string;
  data?: T;
  [key: string]: any;
}

/** 图片添加（上传）请求参数类型（匹配后端 /api/image_add 接口） */
interface ImageAddParams {
  featureId: number | string; // 商品特征ID（必传，无undefined）
  productCode?: string;       // 关联商品货号（可选）
  overwrite: boolean;         // 是否覆盖现有图片
  keepOriginalName: boolean;  // 是否保留原文件名
  file: File;                 // 上传的图片文件
}

/** 图片添加（上传）响应类型（匹配后端返回格式） */
interface ImageAddResponse {
  status: 'success' | 'error';
  message: string;
  featureId: number;
  image_path: string;
  full_image_path?: string;
  csv_updated: boolean;
}

/** 根据特征ID获取图片的返回结果类型 */
interface ImageByFeatureIdResult {
  success: true;
  imageUrl: string;
  blob: Blob;
  revokeUrl: () => void;
}

/** 删除图片请求参数类型 */
interface DeleteImageParams {
  featureId?: number | string;
  imagePath?: string;
  relatedProductId?: string;
}

/** 批量删除图片请求参数类型（新增） */
interface BatchDeleteImageParams {
  featureIds?: (number | string)[];
  imagePaths?: string[];
  relatedProductIds?: string[];
  cleanCsv?: boolean;
}

/** 批量删除图片响应类型（新增，和后端批量接口返回对齐） */
interface BatchDeleteImageResponse {
  status: 'success' | 'partial_success' | 'error';
  message: string;
  total: number;
  success_count: number;
  fail_count: number;
  details: Array<{
    type: 'featureId' | 'imagePath';
    id: string;
    status: 'success' | 'fail';
    message: string;
    image_path: string;
    full_image_path?: string;
    image_deleted: boolean;
    csv_cleaned: boolean;
    remaining_references: number;
  }>;
}

/** 原始库存数据类型 */
interface InventoryRawData {
  inventory?: {
    库存ID?: number | string;
    次品数量?: number;
    库存数量?: number;
    单位?: string;
    批次?: number;
    状态?: string;
    [key: string]: any;
  };
  product?: {
    商品ID?: number | string;
    货号?: string;
    类型?: string;
    用途?: string;
    备注?: string;
    图片路径?: string;
    [key: string]: any;
  };
  feature?: {
    商品特征ID?: number | string;
    单价?: number;
    重量?: number;
    规格?: string;
    材质?: string;
    颜色?: string;
    形状?: string;
    风格?: string;
    [key: string]: any;
  };
  manufacturer?: {
    厂家ID?: number | string | null;
    厂家?: string;
    厂家地址?: string;
    电话?: string;
    [key: string]: any;
  };
  location?: {
    地址ID?: number | string;
    地址类型?: number | string;
    楼层?: number | string;
    架号?: string;
    框号?: string;
    包号?: string;
    [key: string]: any;
  };
  operation_stats?: {
    current_stock?: number;
    total_in_quantity?: number;
    total_out_quantity?: number;
    total_lend_quantity?: number;
    total_return_quantity?: number;
    last_operation_time?: string;
    [key: string]: any;
  };
  [key: string]: any;
}

/** 格式化后的库存显示数据类型 */
interface InventoryDisplayData {
  id: number | string | undefined;
  productId: number | string | undefined;
  featureId: number | string | ''; // 确保无undefined（空字符串兜底）
  productCode: string;
  productType: string;
  status: string;
  batch: number; // 数字类型，无undefined
  defectiveQuantity: number;
  stockQuantity: number;
  totalInQuantity: number;
  totalOutQuantity: number;
  totalLendQuantity: number;
  totalReturnQuantity: number;
  addressId: number | string | undefined;
  addressType: number | string; // 无undefined
  floor: string;
  shelfNo: string;
  boxNo: string;
  packageNo: string;
  unit: string;
  manufacturerId: number | string | ''; // 确保无undefined（空字符串兜底）
  manufacturerName: string;
  manufacturerAddress: string;
  manufacturerPhone: string;
  unitPrice: number;
  weight: number;
  specification: string;
  material: string;
  color: string;
  shape: string;
  style: string;
  usage: string;
  remark: string;
  imagePath: string;
  fullImageUrl: string;
  lastOperationTime: string;
  operator?: string; // 可选字段（允许undefined）
}

/** 表单验证规则类型 */
interface ValidationRule {
  required?: boolean;
  label?: string;
  type?: 'number' | 'image' | 'string' | 'enum' | 'boolean'; // 新增boolean类型
  min?: number;
  enum?: string[];
}

/** 编辑库存格式化数据类型 */
interface FormattedEditInventoryData {
  货号: string;
  类型: string;
  单价: number;
  重量: number;
  厂家: string;
  厂家地址: string;
  电话: string;
  地址类型: number | string; // 无undefined
  楼层: string;
  架号: string;
  框号: string;
  包号: string;
  批次: number;
  状态: string;
  次品数量: number;
  用途: string;
  规格: string;
  备注: string;
  材质: string;
  颜色: string;
  形状: string;
  风格: string;
  图片路径: string;
  操作人: string;
}

/** 入库项类型 */
interface StockInItem {
  货号: string;
  类型: string;
  地址类型: number;
  楼层: number;
  入库数量: number;
  架号: string;
  框号: string;
  包号: string;
  单价: number;
  重量: number;
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
  批次: number;
}

/** 入库表单数据类型 */
interface StockInFormData {
  inTime?: string;
  items: Array<{
    productCode: string;
    productType: string;
    addressType: string | number;
    floor: string | number;
    quantity: string | number;
    shelfNo: string;
    boxNo: string;
    packageNo: string;
    unitPrice: string | number;
    weight: string | number;
    manufacturerName: string;
    manufacturerAddress: string;
    manufacturerPhone: string;
    usage: string;
    specification: string;
    remark: string;
    material: string;
    color: string;
    shape: string;
    style: string;
    imagePath?: string;
    fullImageUrl?: string;
    batch: string | number;
  }>;
}

/** 借出/归还/出库项类型 */
interface LendReturnOutItem {
  库存ID: number;
  [key: string]: number | string;
}

/** 借出/归还/出库表单数据类型 */
interface LendReturnOutFormData {
  operateTime?: string;
  items: Array<{
    inventoryId: string | number;
    quantity: string | number;
    remark?: string;
  }>;
  operator?: string;
}

// ===================== 通用工具函数（优化适配图片添加） =====================
/**
 * 通用请求函数（核心增强：支持图片Blob返回 + 兼容null/undefined序列化）
 * @param endpoint 接口路径
 * @param options 请求选项
 * @param isImageRequest 是否为图片请求（返回Blob）
 */
async function request<T = ApiSuccessResponse>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  try {
    const fetchOptions: RequestInit = {
      headers: { ...options.headers },
      ...options,
    } as RequestInit;

    // 区分请求格式：multipart/form-data（图片上传）不处理JSON序列化
    if (
      (fetchOptions.headers as Record<string, string>)['Content-Type'] !== 'multipart/form-data' &&
      options.body
    ) {
      fetchOptions.body = JSON.stringify(options.body, (key, value) => {
        if (value === null || value === undefined) return '';
        return value;
      });
      if (!(fetchOptions.headers as Record<string, string>)['Content-Type']) {
        (fetchOptions.headers as Record<string, string>)['Content-Type'] = 'application/json';
      }
    }

    const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    // 检查响应状态
    if (!response.ok) {
      let errorMessage = '请求失败';
      try {
        const errorData = await response.json();
        errorMessage = errorData.message || errorMessage;
      } catch (e) {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    if (response.status === 204) {
      return { status: 'success', message: '操作成功' } as T;
    }

    const data = await response.json();
    return normalizeData(data) as T;

    // 标准化空值（前端展示友好）
    function normalizeData(obj: any): any {
      if (typeof obj !== 'object' || obj === null) return obj;
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          if (obj[key] === null || obj[key] === undefined) {
            obj[key] = '';
          } else if (typeof obj[key] === 'object') {
            normalizeData(obj[key]);
          }
        }
      }
      return obj;
    }
  } catch (error) {
    console.error('API请求错误:', error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * 图片请求专用函数
 */
async function imageRequest(endpoint: string, options: RequestOptions = {}): Promise<Blob> {
  try {
    const fetchOptions: RequestInit = {
      headers: { ...options.headers },
      ...options,
    } as RequestInit;

    // 区分请求格式：multipart/form-data（图片上传）不处理JSON序列化
    if (
      (fetchOptions.headers as Record<string, string>)['Content-Type'] !== 'multipart/form-data' &&
      options.body
    ) {
      fetchOptions.body = JSON.stringify(options.body, (key, value) => {
        if (value === null || value === undefined) return '';
        return value;
      });
      if (!(fetchOptions.headers as Record<string, string>)['Content-Type']) {
        (fetchOptions.headers as Record<string, string>)['Content-Type'] = 'application/json';
      }
    }

    const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);

    // 检查响应状态
    if (!response.ok) {
      let errorMessage = '请求失败';
      try {
        const errorData = await response.json();
        errorMessage = errorData.message || errorMessage;
      } catch (e) {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    return response.blob();
  } catch (error) {
    console.error('API请求错误:', error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

/**
 * 构建URL查询参数（增强：过滤空值）
 * @param params 查询参数对象
 */
function buildQueryParams(params: Record<string, any>): string {
  const queryParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      queryParams.append(key, String(value));
    }
  });
  return queryParams.toString();
}

/**
 * 图片上传专用函数（处理form-data）
 * @param endpoint 接口路径
 * @param formData 表单数据
 */
async function uploadFileRequest<T = ApiSuccessResponse>(
  endpoint: string,
  formData: FormData
): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorMessage = '图片上传失败';
      try {
        const errorData = await response.json();
        errorMessage = errorData.message || errorMessage;
      } catch (e) {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    const data = await response.json();
    const normalizeData = (obj: any): any => {
      if (typeof obj !== 'object' || obj === null) return obj;
      for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
          if (obj[key] === null || obj[key] === undefined) {
            obj[key] = '';
          } else if (typeof obj[key] === 'object') {
            normalizeData(obj[key]);
          }
        }
      }
      return obj;
    };
    return normalizeData(data) as T;
  } catch (error) {
    console.error('图片上传错误:', error);
    throw error instanceof Error ? error : new Error(String(error));
  }
}

// ===================== API核心方法（新增图片添加方法） =====================
export const api = {
  // 健康检查
  healthCheck: (): Promise<ApiSuccessResponse> => request('/health'),

  // 获取商品类型
  getProductTypes: (): Promise<ApiSuccessResponse> => request('/product-types'),

  // 获取楼层选项
  getFloors: (): Promise<ApiSuccessResponse> => request('/floors'),

  // 根据特征ID获取图片
  getImageByFeatureId: (featureId: number | string): Promise<ImageByFeatureIdResult> => {
    return new Promise(async (resolve, reject) => {
      try {
        // 严格校验：排除undefined和非数字
        const featureIdNum = Number(featureId);
        if (isNaN(featureIdNum)) {
          throw new Error('无效的商品特征ID（必须为数字）');
        }
        // 请求图片二进制流
        const blob = await imageRequest(`/get_image_by_feature_id/${featureIdNum}`, {
          method: 'GET',
        });

        // 生成临时URL并返回（包含释放方法）
        const imageUrl = URL.createObjectURL(blob);
        resolve({
          success: true,
          imageUrl,
          blob,
          revokeUrl: () => URL.revokeObjectURL(imageUrl),
        });
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  },

  // ===================== 新增：图片添加（上传）核心方法 =====================
  /**
   * 商品图片添加/上传（对接后端 /api/image_add 接口）
   * @param params 上传参数（featureId/file为必传）
   */
  addProductImage: (params: ImageAddParams): Promise<ImageAddResponse> => {
    return new Promise(async (resolve, reject) => {
      try {
        // 1. 严格参数校验：排除undefined和非数字
        const featureIdNum = Number(params.featureId);
        if (isNaN(featureIdNum)) {
          throw new Error('无效的商品特征ID（必须为数字）');
        }
        if (!params.file) {
          throw new Error('请选择要上传的图片文件');
        }

        // 2. 构建FormData（匹配后端表单格式）
        const formData = new FormData();
        formData.append('featureId', String(featureIdNum)); // 确保是字符串格式的数字
        if (params.productCode) {
          formData.append('productCode', params.productCode.trim()); // 商品货号
        }
        formData.append('overwrite', String(params.overwrite)); // 是否覆盖（布尔转字符串）
        formData.append('keepOriginalName', String(params.keepOriginalName)); // 是否保留原文件名
        formData.append('file', params.file); // 图片文件

        // 3. 调用上传接口
        const result = await uploadFileRequest<ImageAddResponse>('/image_add', formData);

        // 4. 响应格式校验
        if (result.status === 'error') {
          throw new Error(result.message || '图片上传失败');
        }

        resolve(result as ImageAddResponse);
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  },

  // 原有商品图片上传（保留，兼容旧接口）
  uploadProductImage: (productCode: string, file: File): Promise<ApiSuccessResponse> => {
    return new Promise(async (resolve, reject) => {
      try {
        if (!productCode || !file) {
          throw new Error('商品货号和图片文件不能为空');
        }
        const formData = new FormData();
        formData.append('product_code', productCode);
        formData.append('file', file);
        const result = await uploadFileRequest('/upload-image', formData);
        resolve(result);
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  },

  // 删除图片（支持特征ID/图片路径双维度）
  deleteImage: (params: DeleteImageParams): Promise<ApiSuccessResponse> => {
    return new Promise(async (resolve, reject) => {
      try {
        // 参数校验：至少传特征ID或图片路径其中一个
        if (!params.featureId && !params.imagePath) {
          throw new Error('特征ID和图片路径不能同时为空');
        }

        // 格式化参数：确保featureId是数字或空字符串（无undefined）
        const submitParams = {
          featureId: params.featureId ? Number(params.featureId) : '',
          imagePath: params.imagePath || '',
          relatedProductId: params.relatedProductId || '',
        };

        const result = await request('/delete_image', {
          method: 'POST',
          body: submitParams,
        });
        resolve(result as ApiSuccessResponse);
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  },

  // 批量删除图片（新增核心方法）
  batchDeleteImage: (params: BatchDeleteImageParams): Promise<BatchDeleteImageResponse> => {
    return new Promise(async (resolve, reject) => {
      try {
        // 参数校验：至少传特征ID列表或图片路径列表其中一个
        if (!params.featureIds?.length && !params.imagePaths?.length) {
          throw new Error('特征ID列表和图片路径列表不能同时为空');
        }

        // 格式化参数：过滤undefined，确保类型正确
        const submitParams = {
          featureIds: (params.featureIds || []).filter(id => id !== undefined).map(id => Number(id)),
          imagePaths: params.imagePaths || [],
          relatedProductIds: params.relatedProductIds || [],
          cleanCsv: params.cleanCsv ?? true, // 默认清理CSV关联
        };

        // 调用批量删除接口
        const result = await request<BatchDeleteImageResponse>('/batch_delete_image', {
          method: 'POST',
          body: submitParams,
        });
        resolve(result as BatchDeleteImageResponse);
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  },

  // 批量入库
  batchStockIn: (data: any): Promise<ApiSuccessResponse> => request('/batch-stock-in', {
    method: 'POST',
    body: data,
  }),

  // 库存借出（批量）
  batchLendInventory: (data: any): Promise<ApiSuccessResponse> => request('/inventory/lend', {
    method: 'POST',
    body: data,
  }),

  // 库存归还（批量）
  batchReturnInventory: (data: any): Promise<ApiSuccessResponse> => request('/inventory/return', {
    method: 'POST',
    body: data,
  }),

  // 批量出库
  batchStockOut: (data: any): Promise<ApiSuccessResponse> => request('/batch-stock-out', {
    method: 'POST',
    body: data,
  }),

  // 批量更新状态
  batchUpdateStatus: (data: any): Promise<ApiSuccessResponse> => request('/batch-update-status', {
    method: 'POST',
    body: data,
  }),

  // 获取所有库存列表
  getAllInventory: (params: Record<string, any> = {}): Promise<ApiSuccessResponse> => {
    const queryString = buildQueryParams(params);
    return request(`/inventory${queryString ? `?${queryString}` : ''}`);
  },

  // 库存详情
  getInventoryDetail: (
    inventoryId: number | string,
    params: { page?: number; page_size?: number } = { page: 1, page_size: 50 }
  ): Promise<ApiSuccessResponse> => {
    // 确保inventoryId是数字（排除undefined）
    const inventoryIdNum = Number(inventoryId);
    if (isNaN(inventoryIdNum)) {
      return Promise.reject(new Error('无效的库存ID'));
    }
    const queryString = buildQueryParams(params);
    return request(`/inventory/${inventoryIdNum}${queryString ? `?${queryString}` : ''}`);
  },

  // 兼容旧函数名
  updateInventory: (inventoryId: number | string, data: any): Promise<ApiSuccessResponse> =>
    api.editInventory(inventoryId, data),

  // 库存编辑
  editInventory: (inventoryId: number | string, data: any): Promise<ApiSuccessResponse> => {
    // 确保inventoryId是数字（排除undefined）
    const inventoryIdNum = Number(inventoryId);
    if (isNaN(inventoryIdNum)) {
      return Promise.reject(new Error('无效的库存ID'));
    }
    return request(`/inventory/${inventoryIdNum}/edit`, {
      method: 'POST',
      body: data,
    });
  },

  // 删除库存记录
  deleteInventory: (inventoryId: number | string): Promise<ApiSuccessResponse> => {
    // 确保inventoryId是数字（排除undefined）
    const inventoryIdNum = Number(inventoryId);
    if (isNaN(inventoryIdNum)) {
      return Promise.reject(new Error('无效的库存ID'));
    }
    return request(`/inventory/${inventoryIdNum}`, {
      method: 'DELETE',
    });
  },

  // 操作记录查询
  getOperationRecords: (params: {
    operationType?: string;
    inventoryId?: number | string;
    startDate?: string;
    endDate?: string;
  } = {}): Promise<ApiSuccessResponse> => {
    // 格式化参数：排除undefined
    const queryString = buildQueryParams({
      operation_type: params.operationType,
      inventory_id: params.inventoryId ? Number(params.inventoryId) : undefined,
      start_date: params.startDate,
      end_date: params.endDate,
    });
    return request(`/get_operation_records${queryString ? `?${queryString}` : ''}`);
  },

  // 操作记录导出
  exportOperationRecordsCSV: (params: {
    operationType?: string;
    inventoryId?: number | string;
    startDate?: string;
    endDate?: string;
  } = {}): Promise<{ success: true; filename: string }> => {
    return new Promise(async (resolve, reject) => {
      try {
        // 格式化参数：排除undefined
        const queryString = buildQueryParams({
          operation_type: params.operationType || '出库',
          inventory_id: params.inventoryId ? Number(params.inventoryId) : undefined,
          start_date: params.startDate,
          end_date: params.endDate,
        });

        const url = `${API_BASE}/export_operation_records${queryString ? `?${queryString}` : ''}`;
        const response = await fetch(url);

        if (!response.ok) {
          let errorMessage = '导出失败';
          try {
            const errorData = await response.json();
            errorMessage = errorData.message || errorMessage;
          } catch (e) {
            errorMessage = `HTTP ${response.status}: ${response.statusText}`;
          }
          throw new Error(errorMessage);
        }

        const blob = await response.blob();
        const urlObj = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = urlObj;

        const disposition = response.headers.get('Content-Disposition');
        let filename = `操作记录_${new Date().toISOString().slice(0, 10)}.csv`;
        if (disposition) {
          const filenameMatch = disposition.match(/filename\*=UTF-8''(.*)/);
          if (filenameMatch && filenameMatch[1]) {
            filename = decodeURIComponent(filenameMatch[1]);
          }
        }
        a.download = filename;

        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(urlObj);
        document.body.removeChild(a);
        resolve({ success: true, filename });
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  },

  // 库存数据导出（前端本地处理）
  exportInventoryCSV: (): Promise<{ success: true; filename: string }> => {
    return new Promise(async (resolve, reject) => {
      try {
        const inventoryData = await api.getAllInventory();

        if (!inventoryData.data || inventoryData.data.length === 0) {
          throw new Error('没有数据可导出');
        }

        const headers = [
          '库存ID', '商品ID', '商品特征ID', '货号', '商品类型', '单价', '重量',
          '厂家ID', '厂家名称', '厂家地址', '厂家电话',
          '地址ID', '地址类型', '楼层', '架号', '框号', '包号', '单位',
          '库存数量', '次品数量', '批次', '状态', '用途', '规格', '备注',
          '材质', '颜色', '形状', '风格', '图片路径',
        ];

        const csvRows = inventoryData.data.map((item: InventoryRawData) => {
          const inventory = item.inventory || {};
          const product = item.product || {};
          const feature = item.feature || {};
          const manufacturer = item.manufacturer || {};
          const location = item.location || {};

          // 确保厂家ID无undefined（空字符串兜底）
          const manufacturerId = manufacturer.厂家ID === null || manufacturer.厂家ID === undefined ? '' : manufacturer.厂家ID;

          return [
            inventory.库存ID || '',
            product.商品ID || '',
            feature.商品特征ID || '',
            `"${product.货号 || ''}"`,
            `"${product.类型 || ''}"`,
            feature.单价 || '',
            feature.重量 || '',
            manufacturerId,
            `"${manufacturer.厂家 || ''}"`,
            `"${manufacturer.厂家地址 || ''}"`,
            `"${manufacturer.电话 || ''}"`,
            location.地址ID || '',
            location.地址类型 || '',
            location.楼层 || '',
            `"${location.架号 || ''}"`,
            `"${location.框号 || ''}"`,
            `"${location.包号 || ''}"`,
            `"${inventory.单位 || ''}"`,
            inventory.库存数量 || '',
            inventory.次品数量 || '',
            inventory.批次 || '',
            `"${inventory.状态 || ''}"`,
            `"${product.用途 || ''}"`,
            `"${feature.规格 || ''}"`,
            `"${product.备注 || ''}"`,
            `"${feature.材质 || ''}"`,
            `"${feature.颜色 || ''}"`,
            `"${feature.形状 || ''}"`,
            `"${feature.风格 || ''}"`,
            `"${product.图片路径 || ''}"`,
          ].join(',');
        });

        const csvContent = [headers.join(','), ...csvRows].join('\n');
        const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = `库存数据_${new Date().toISOString().slice(0, 10)}.csv`;

        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        resolve({ success: true, filename: a.download });
      } catch (error) {
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  },

  // 获取最后地址信息
  getLastAddressInfo: (params: Record<string, any>): Promise<ApiSuccessResponse> =>
    request('/inventory/last-address-info', {
      method: 'POST',
      body: params,
    }),

  // 添加这些方法来替代动态添加的属性
  getStockOutRecords: (params: {
    operationType?: string;
    inventoryId?: number | string;
    startDate?: string;
    endDate?: string;
  } = {}): Promise<ApiSuccessResponse> => {
    return api.getOperationRecords(params);
  },

  exportStockOutCSV: (params: {
    operationType?: string;
    inventoryId?: number | string;
    startDate?: string;
    endDate?: string;
  } = {}): Promise<{ success: true; filename: string }> => {
    return api.exportOperationRecordsCSV(params);
  },
};

// ===================== 工具函数（优化适配图片添加） =====================
/**
 * 错误处理工具函数（增强：区分图片上传/加载错误 + 新增图片添加错误场景）
 * @param error 错误对象
 * @param defaultMessage 默认错误信息
 */
export const handleApiError = (
  error: unknown,
  defaultMessage = '操作失败'
): string => {
  console.error('API错误详情:', error);
  const err = error instanceof Error ? error : new Error(String(error));

  if (err.message.includes('Failed to fetch')) {
    return '网络异常，请检查服务器连接';
  }
  if (err.message.includes('Request Entity Too Large')) {
    return '图片大小超过限制（最大16MB），请压缩后重新上传';
  }
  if (err.message.includes('特征ID')) {
    return `图片操作失败：${err.message}`;
  }
  if (err.message.includes('覆盖现有图片')) {
    return `图片上传失败：${err.message}`;
  }
  if (err.message.includes('HTTP')) {
    return err.message.replace('HTTP ', '请求错误：');
  }

  return err.message || defaultMessage;
};

/**
 * 数据验证工具函数（增强：支持图片格式验证 + boolean类型验证）
 * @param data 表单数据
 * @param rules 验证规则
 */
export const validateFormData = (
  data: Record<string, any>,
  rules: Record<string, ValidationRule> = {}
): true => {
  const errors: string[] = [];

  Object.entries(rules).forEach(([field, rule]) => {
    const value = data[field];
    const valStr = String(value).trim();

    if (rule.required && valStr === '') {
      errors.push(`${rule.label || field}为必填项`);
      return;
    }

    if (rule.type === 'number' && valStr !== '' && isNaN(Number(valStr))) {
      errors.push(`${rule.label || field}必须为数字`);
      return;
    }

    if (rule.type === 'boolean' && valStr !== '' && !['true', 'false'].includes(valStr)) {
      errors.push(`${rule.label || field}必须为布尔值（true/false）`);
      return;
    }

    if (rule.min !== undefined && !isNaN(Number(valStr)) && Number(valStr) < rule.min) {
      errors.push(`${rule.label || field}不能小于${rule.min}`);
    }

    if (rule.enum && valStr !== '' && !rule.enum.includes(valStr)) {
      errors.push(`${rule.label || field}必须是：${rule.enum.join('、')}`);
    }

    if (rule.type === 'image' && value) {
      const allowedTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/webp'];
      const file = value as File;
      if (!file.type || !allowedTypes.includes(file.type)) {
        errors.push(`${rule.label || field}格式不支持，仅允许：png/jpg/jpeg/gif/bmp/webp`);
      }
      const maxSize = 16 * 1024 * 1024;
      if (file.size > maxSize) {
        errors.push(`${rule.label || field}大小超过16MB，请压缩后上传`);
      }
    }
  });

  if (errors.length > 0) {
    throw new Error(errors.join('；'));
  }

  return true;
};

/**
 * 格式化库存数据用于前端显示
 * @param inventoryData 原始库存数据
 */
export const formatInventoryForDisplay = (
  inventoryData: InventoryRawData | null | undefined
): InventoryDisplayData | null => {
  if (!inventoryData) return null;

  const inventory = inventoryData.inventory || {};
  const product = inventoryData.product || {};
  const feature = inventoryData.feature || {};
  const manufacturer = inventoryData.manufacturer || {};
  const location = inventoryData.location || {};
  const operationStats = inventoryData.operation_stats || {};

  // 优先使用特征ID图片接口（确保featureId无undefined）
  const featureId = feature.商品特征ID === undefined ? '' : feature.商品特征ID;
  const imagePath = product.图片路径 || '';
  const fullImageUrl = featureId && !isNaN(Number(featureId))
    ? `${API_BASE}/get_image_by_feature_id/${featureId}`
    : (imagePath ? `${API_BASE.replace('/api', '')}/${imagePath}` : '');

  // 核心修复：所有字段兜底，确保无undefined
  return {
    id: inventory.库存ID,
    productId: product.商品ID,
    featureId: featureId,
    productCode: product.货号 || '',
    productType: product.类型 || '',
    status: inventory.状态 || '正常',
    batch: Number(inventory.批次) || 1, // 兜底为1，确保是数字
    defectiveQuantity: Number(inventory.次品数量) || 0,
    stockQuantity: Number(operationStats.current_stock || inventory.库存数量) || 0,
    totalInQuantity: Number(operationStats.total_in_quantity) || 0,
    totalOutQuantity: Number(operationStats.total_out_quantity) || 0,
    totalLendQuantity: Number(operationStats.total_lend_quantity) || 0,
    totalReturnQuantity: Number(operationStats.total_return_quantity) || 0,
    addressId: location.地址ID,
    addressType: location.地址类型 !== undefined ? location.地址类型 : 1, // 兜底为1，无undefined
    floor: String(location.楼层 || ''), // 转换为字符串，兜底为空
    shelfNo: location.架号 || '',
    boxNo: location.框号 || '',
    packageNo: location.包号 || '',
    unit: inventory.单位 || '',
    manufacturerId: manufacturer.厂家ID === null || manufacturer.厂家ID === undefined ? '' : manufacturer.厂家ID,
    manufacturerName: manufacturer.厂家 || '',
    manufacturerAddress: manufacturer.厂家地址 || '',
    manufacturerPhone: manufacturer.电话 || '',
    unitPrice: Number(feature.单价) || 0,
    weight: Number(feature.重量) || 0,
    specification: feature.规格 || '',
    material: feature.材质 || '',
    color: feature.颜色 || '',
    shape: feature.形状 || '',
    style: feature.风格 || '',
    usage: product.用途 || '',
    remark: product.备注 || '',
    imagePath: imagePath,
    fullImageUrl: fullImageUrl,
    lastOperationTime: operationStats.last_operation_time || '',
    operator: '', // 兜底为空字符串
  };
};

/**
 * 格式化编辑表单数据
 * @param formData 表单数据
 */
export const formatEditInventoryData = (
  formData: Partial<InventoryDisplayData>
): FormattedEditInventoryData => {
  // 核心修复：所有字段兜底，确保无undefined
  return {
    货号: formData.productCode || '',
    类型: formData.productType || '',
    单价: Number(formData.unitPrice) || 0,
    重量: Number(formData.weight) || 0,
    厂家: formData.manufacturerName || '',
    厂家地址: formData.manufacturerAddress || '',
    电话: formData.manufacturerPhone || '',
    地址类型: formData.addressType !== undefined ? formData.addressType : 1, // 兜底为1
    楼层: String(formData.floor || ''),
    架号: formData.shelfNo || '',
    框号: formData.boxNo || '',
    包号: formData.packageNo || '',
    批次: Number(formData.batch) || 1,
    状态: formData.status || '正常',
    次品数量: Number(formData.defectiveQuantity) || 0,
    用途: formData.usage || '',
    规格: formData.specification || '',
    备注: formData.remark || '',
    材质: formData.material || '',
    颜色: formData.color || '',
    形状: formData.shape || '',
    风格: formData.style || '',
    图片路径: formData.imagePath || formData.fullImageUrl?.replace(`${API_BASE.replace('/api', '')}/`, '') || '',
    操作人: formData.operator || '系统',
  };
};

/**
 * 格式化入库表单数据
 * @param formData 入库表单数据
 */
export const formatStockInData = (formData: StockInFormData): {
  入库时间: string;
  stock_in_items: StockInItem[];
} => {
  return {
    入库时间: formData.inTime || '',
    stock_in_items: formData.items.map(item => ({
      货号: item.productCode.trim(),
      类型: item.productType,
      地址类型: Number(item.addressType) || 1, // 兜底为1
      楼层: Number(item.floor) || 0, // 兜底为0
      入库数量: Number(item.quantity) || 0,
      架号: item.shelfNo.trim() || '',
      框号: item.boxNo.trim() || '',
      包号: item.packageNo.trim() || '',
      单价: Number(item.unitPrice) || 0,
      重量: Number(item.weight) || 0,
      厂家: item.manufacturerName.trim() || '',
      厂家地址: item.manufacturerAddress.trim() || '',
      电话: item.manufacturerPhone.trim() || '',
      用途: item.usage.trim() || '',
      规格: item.specification.trim() || '',
      备注: item.remark.trim() || '',
      材质: item.material.trim() || '',
      颜色: item.color.trim() || '',
      形状: item.shape.trim() || '',
      风格: item.style.trim() || '',
      图片路径: item.imagePath || item.fullImageUrl?.replace(`${API_BASE.replace('/api', '')}/`, '') || '',
      批次: Number(item.batch) || 1,
    })),
  };
};

/**
 * 格式化借出表单数据
 * @param formData 借出表单数据
 */
export const formatLendData = (formData: LendReturnOutFormData): {
  操作时间: string;
  lend_items: LendReturnOutItem[];
} => {
  return {
    操作时间: formData.operateTime || '',
    lend_items: formData.items.map(item => ({
      库存ID: Number(item.inventoryId), // 确保是数字（调用前已校验）
      借出数量: Number(item.quantity) || 0,
      操作人: formData.operator || '系统',
      备注: item.remark || '',
    })),
  };
};

/**
 * 格式化归还表单数据
 * @param formData 归还表单数据
 */
export const formatReturnData = (formData: LendReturnOutFormData): {
  操作时间: string;
  return_items: LendReturnOutItem[];
} => {
  return {
    操作时间: formData.operateTime || '',
    return_items: formData.items.map(item => ({
      库存ID: Number(item.inventoryId), // 确保是数字（调用前已校验）
      归还数量: Number(item.quantity) || 0,
      操作人: formData.operator || '系统',
      备注: item.remark || '',
    })),
  };
};

/**
 * 格式化出库表单数据
 * @param formData 出库表单数据
 */
export const formatStockOutData = (formData: LendReturnOutFormData): {
  操作时间: string;
  stock_out_items: LendReturnOutItem[];
} => {
  return {
    操作时间: formData.operateTime || '',
    stock_out_items: formData.items.map(item => ({
      库存ID: Number(item.inventoryId), // 确保是数字（调用前已校验）
      出库数量: Number(item.quantity) || 0,
      操作人: formData.operator || '系统',
      备注: item.remark || '',
    })),
  };
};

/**
 * 图片路径处理工具函数（适配特征ID接口 + 新上传接口）
 * @param imageUrl 图片URL/路径
 * @param featureId 商品特征ID
 */
export const processImagePath = (
  imageUrl: string | undefined,
  featureId: number | string | undefined
): string => {
  // 核心修复：严格校验featureId，排除undefined
  if (featureId !== undefined && featureId !== null && !isNaN(Number(featureId))) {
    return `${API_BASE}/get_image_by_feature_id/${featureId}`;
  }

  // 完整URL转相对路径（用于存储到后端）
  if (imageUrl && imageUrl.startsWith(API_BASE.replace('/api', ''))) {
    return imageUrl.replace(`${API_BASE.replace('/api', '')}/`, '');
  }

  // 相对路径转完整URL（无特征ID时回退）
  if (imageUrl && !imageUrl.startsWith('http')) {
    return `${API_BASE.replace('/api', '')}/${imageUrl}`;
  }

  return imageUrl || '';
};