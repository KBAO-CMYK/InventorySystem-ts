// src/lib/constants.ts - 网络相关常量统一管理
export const NETWORK_CONSTANTS = {
  // 后端图片服务基础地址
  IMAGE_API_BASE: 'http://192.168.110.40:5000/api/get_image',
  IMAGE_STATIC_BASE: 'http://192.168.110.40:5000/image',

  // 图片删除接口
  DELETE_IMAGE_API: 'http://192.168.110.40:5000/api/batch_delete_image',

  // 图片临时上传接口
  TEMP_UPLOAD_API: 'http://192.168.110.40:5000/api/temp_upload_image',

  // 图片编辑页面地址（前端B）
  EDIT_IMAGE_URL: 'http://192.168.110.40:5174/',

  // 图片加载失败占位图
  ERROR_PLACEHOLDER: 'https://picsum.photos/40/40?grayscale&text=无图',

  // 扩展：可添加其他网络常量（如超时时间、请求头）
  REQUEST_TIMEOUT: 10000, // 请求超时时间10秒
  CONTENT_TYPE_JSON: 'application/json'
};

// 图片上传相关常量（独立导出，按需使用）
export const UPLOAD_CONSTANTS = {
  // 允许的图片格式
  ALLOWED_FORMATS: ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'] as const,
  // 最大文件大小（16MB）
  MAX_FILE_SIZE: 16 * 1024 * 1024,
  // 编辑窗口就绪超时时间（5秒）
  EDITOR_READY_TIMEOUT: 5000
};