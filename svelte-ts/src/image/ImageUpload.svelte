<script lang="ts">
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { api, handleApiError } from '../lib/api.ts';
  import type { ApiSuccessResponse } from '../lib/api.ts';

  // ========== 类型定义 ==========
  interface UploadImageResponseData {
    relative_path: string;
    [key: string]: any;
  }

  // 🔥 新增：删除接口相关类型
  interface BatchDeleteImageRequest {
    featureIds: string[];
    imagePaths: string[];
    relatedProductIds?: string[];
    cleanCsv: boolean;
  }

  interface BatchDeleteImageResponse {
    status: 'success' | 'error' | 'partial_success';
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
      image_deleted: boolean;
      csv_cleaned: boolean;
      remaining_references: number;
      full_image_path?: string;
    }>;
  }

  type ImageUploadEvents = {
    change: string;
  };

  // ========== 事件派发 ==========
  const dispatch = createEventDispatcher<ImageUploadEvents>();

  // ========== Props 定义 ==========
  export let value: string | CustomEvent<string> | Record<string, any> = '';
  export let productCode: string = '';
  export let disabled: boolean = false;
  // 🔥 新增：特征ID（用于删除接口，外部传入）
  export let featureId: string | number = '';

  // ========== 核心配置 ==========
  const IMAGE_API_BASE: string = 'http://127.0.0.1:5000/api/get_image';
  const IMAGE_STATIC_BASE: string = 'http://127.0.0.1:5000/image';
  // 🔥 新增：删除接口地址
  const DELETE_IMAGE_API: string = 'http://127.0.0.1:5000/api/batch_delete_image';
  const ERROR_PLACEHOLDER: string = 'https://picsum.photos/40/40?grayscale&text=无图';
  const ALLOWED_FORMATS: readonly string[] = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'];
  const MAX_FILE_SIZE: number = 16 * 1024 * 1024;

  // ========== 状态变量 ==========
  let previewUrlCache: string = '';
  let imgLoadError: boolean = false;
  let debugPreviewUrl: string = '';
  let isModalOpen: boolean = false;
  let isUploading: boolean = false; // 上传状态
  let uploadProgress: number = 0; // 上传进度
  // 🔥 新增：删除状态
  let isDeleting: boolean = false;

  // ========== 响应式处理 ==========
  $: safeValue = (() => {
    if (value && typeof value === 'object' && 'detail' in value) {
      return (value as CustomEvent<string>).detail || '';
    }
    if (value && typeof value === 'object' && !(value instanceof Event)) {
      return String(value) || '';
    }
    return String(value || '').trim();
  })();

  // ========== 工具函数 ==========
  function getFileExtension(file: File): string {
    return file.name.split('.').pop()?.toLowerCase() || '';
  }

  /**
   * 🔥 修改：处理文件选择 - 直接上传（无需确认）
   */
  async function handleFileSelect(e: Event & { target: HTMLInputElement }): Promise<void> {
    const fileInput = e.target;
    const file = fileInput.files?.[0];

    // 重置输入框值（避免重复选择同文件不触发change）
    fileInput.value = '';

    // 校验商品货号
    if (!productCode || productCode.trim() === '') {
      alert('错误：商品货号不能为空！');
      return;
    }

    // 校验文件
    if (!file) {
      return;
    }

    // 校验格式
    const ext = getFileExtension(file);
    if (!ALLOWED_FORMATS.includes(ext)) {
      alert(`错误：仅支持上传 ${ALLOWED_FORMATS.join('、')} 格式的图片！`);
      return;
    }

    // 校验大小
    if (file.size > MAX_FILE_SIZE) {
      alert('错误：图片大小不能超过16MB，请压缩后上传！');
      return;
    }

    // 直接触发上传
    await uploadImage(file);
  }

  /**
   * 🔥 修改：直接上传图片（无需确认）
   */
  async function uploadImage(file: File): Promise<void> {
    if (!file || !productCode) {
      alert('错误：没有待上传的图片或商品货号为空！');
      return;
    }

    // 重置上传状态
    isUploading = true;
    uploadProgress = 0;
    imgLoadError = false;

    try {
      // 模拟上传进度（实际API若支持可替换为真实进度）
      const progressInterval = setInterval(() => {
        if (uploadProgress < 90) {
          uploadProgress += 10;
        }
      }, 100);

      // 调用上传API
      const result = await api.uploadProductImage(
        productCode.trim(),
        file
      ) as ApiSuccessResponse<UploadImageResponseData>;

      clearInterval(progressInterval);
      uploadProgress = 100;

      if (result.status === 'success') {
        const newValue = result.data?.relative_path?.trim() || '';
        console.log('【上传成功】返回的图片路径：', newValue);

        // 派发事件并更新value
        dispatch('change', newValue);
        value = newValue;

        alert('图片上传成功！');
      }
    } catch (error) {
      const errorMsg = handleApiError(error, '图片上传失败');
      alert(`上传失败：${errorMsg}`);
      console.error('【上传错误详情】', error);
    } finally {
      isUploading = false;
      uploadProgress = 0;
    }
  }

  /**
   * 🔥 新增：清除图片（删除文件 + 清空路径）
   */
  async function clearImage(): Promise<void> {
    if (!safeValue || isDeleting || !productCode) {
      console.warn('【清除图片】前置校验失败', {
        hasPath: !!safeValue,
        isDeleting,
        productCode
      });
      return;
    }

    const confirmClear = confirm(
      `确认删除该图片吗？\n路径：${safeValue}\n删除后无法恢复！`
    );
    if (!confirmClear) return;

    try {
      isDeleting = true;

      // 构建删除请求参数（复用批量删除接口）
      const deleteParams: BatchDeleteImageRequest = {
        featureIds: [],
        imagePaths: [safeValue],
        cleanCsv: true,
        relatedProductIds: [productCode.trim()]
      };

      console.log('【清除图片】调用删除接口，参数：', deleteParams);

      // 调用删除接口
      const response = await fetch(DELETE_IMAGE_API, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify(deleteParams)
      });

      if (!response.ok) {
        throw new Error(`删除请求失败：${response.status} ${response.statusText}`);
      }

      const result: BatchDeleteImageResponse = await response.json();
      console.log('【清除图片】删除响应：', result);

      if (result.status === 'error') {
        throw new Error(result.message || '图片删除失败');
      } else if (result.status === 'partial_success') {
        const failDetail = result.details.find(d => d.status === 'fail');
        if (failDetail) {
          alert(`⚠️ 部分处理失败：${failDetail.message}\n成功：${result.success_count}个 | 失败：${result.fail_count}个`);
        } else {
          alert(`✅ 图片删除成功！\n${result.message}`);
        }
      } else {
        alert(`✅ 图片删除成功！\n${result.message}`);
      }

      // 清空路径并派发事件
      dispatch('change', '');
      value = '';
      previewUrlCache = '';
      imgLoadError = false;

    } catch (error) {
      const errorMsg = handleApiError(error, '图片删除失败');
      alert(`清除失败：${errorMsg}`);
      console.error('【清除图片错误详情】', error);
    } finally {
      isDeleting = false;
    }
  }

  /**
   * 生成图片预览URL
   */
  function getPreviewUrl(): string {
    if (!safeValue) {
      console.log('【URL生成】路径为空');
      return '';
    }

    try {
      const pathStr = safeValue;
      console.log('【URL生成】原始路径：', pathStr);

      // 已经是完整的HTTP/HTTPS URL
      if (pathStr.startsWith('http://') || pathStr.startsWith('https://')) {
        previewUrlCache = pathStr;
        debugPreviewUrl = pathStr;
        return previewUrlCache;
      }

      // 补全image/前缀
      let safePath = pathStr;
      if (!safePath.startsWith('image/')) {
        safePath = `image/${safePath}`;
      }

      // 使用专用图片接口
      const encodedPath = encodeURIComponent(safePath).replace(/%2F/g, '/');
      previewUrlCache = `${IMAGE_API_BASE}?path=${encodedPath}`;
      debugPreviewUrl = previewUrlCache;

      return previewUrlCache;
    } catch (error) {
      console.error('【URL生成错误】', error);
      imgLoadError = true;
      return ERROR_PLACEHOLDER;
    }
  }

  /**
   * 处理图片加载错误
   */
  function handleImgError(e: ErrorEvent<HTMLImageElement>): void {
    imgLoadError = true;
    console.error('【图片加载失败】', {
      targetSrc: e.target?.src,
      safeValue: safeValue,
      debugPreviewUrl: debugPreviewUrl
    });

    if (e.target?.src !== ERROR_PLACEHOLDER && !e.target?.src.startsWith('blob:')) {
      e.target.src = ERROR_PLACEHOLDER;
    }
  }

  /**
   * 打开图片预览弹窗
   */
  function openImageModal(): void {
    const imgUrl = getPreviewUrl();
    if (!imgUrl || imgUrl === ERROR_PLACEHOLDER) {
      alert('图片路径无效，无法预览！');
      return;
    }
    isModalOpen = true;
    document.body.style.overflow = 'hidden';
  }

  /**
   * 关闭图片预览弹窗
   */
  function closeImageModal(): void {
    isModalOpen = false;
    document.body.style.overflow = 'auto';
  }

  function handleModalOverlayClick(e: MouseEvent): void {
    if (e.target === e.currentTarget) {
      closeImageModal();
    }
  }

  // ========== 响应式状态 ==========
  $: hasValidPath = Boolean(safeValue && safeValue.trim() !== '');
  $: combinedDisabled = disabled || !productCode || isUploading || isDeleting;
  $: showUploadedSection = hasValidPath && !isUploading;

  // 路径变化时重新生成URL
  $: if (hasValidPath) {
    imgLoadError = false;
    getPreviewUrl();
  }

  // ========== 组件销毁清理 ==========
  onDestroy(() => {
    // 🔥 修复：Blob URL释放错误（create → revoke）
    if (previewUrlCache && previewUrlCache.startsWith('blob:')) {
      URL.revokeObjectURL(previewUrlCache);
    }
    previewUrlCache = '';
    debugPreviewUrl = '';
    document.body.style.overflow = 'auto';
  });
</script>

<div class="image-upload-container">
  <!-- 文件选择区域 -->
  <div class="upload-section">
    <input
      type="file"
      accept="image/png, image/jpg, image/jpeg, image/gif, image/bmp, image/webp"
      on:change={handleFileSelect}
      class="upload-input"
      disabled={combinedDisabled}
    />

    {#if !productCode && !disabled}
      <p class="warning-text">⚠️ 请先填写商品货号</p>
    {/if}
  </div>

  <!-- 上传中状态 -->
  {#if isUploading}
    <div class="uploading-section">
      <div class="progress-container">
        <div class="progress-bar" style="width: {uploadProgress}%"></div>
        <div class="progress-text">{uploadProgress}%</div>
      </div>
      <p class="uploading-text">正在上传图片...</p>
    </div>
  {/if}

  <!-- 已上传图片区域 -->
  {#if showUploadedSection}
    <div class="path-section">
      <div class="path-header">
        <label class="path-label">路径：</label>
        <!-- 🔥 新增：清除按钮 -->
        <button
          type="button"
          class="clear-btn"
          on:click={clearImage}
          disabled={isDeleting || !hasValidPath}
          title="删除图片并清空路径"
        >
          {isDeleting ? '删除中...' : '🗑️ 清除'}
        </button>
      </div>
      <input
        type="text"
        value={safeValue}
        readonly
        class="path-input"
        title="点击复制路径"
        on:click={(e) => e.target.select()}
      />
      <div class="debug-text">
        预览URL：{debugPreviewUrl || '未生成'}
      </div>
    </div>

    <div class="preview-wrapper">
      <img
        src={getPreviewUrl() || ERROR_PLACEHOLDER}
        alt="商品图片预览"
        class="preview-img"
        on:error={handleImgError}
        title="点击查看大图"
        on:click={openImageModal}
      />
      <p class="preview-text">
        <button
          type="button"
          class="preview-btn"
          on:click={openImageModal}
          title="查看大图"
          disabled={imgLoadError}
        >
          查看大图 ↗
        </button>
      </p>
    </div>
  {/if}
</div>

<!-- 图片预览弹窗 -->
{#if isModalOpen}
  <div class="image-preview-modal" on:click={handleModalOverlayClick}>
    <div class="preview-content">
      <button class="close-btn" on:click={closeImageModal}>&times;</button>
      <div class="preview-image-container">
        <img
          src={previewUrlCache || ERROR_PLACEHOLDER}
          alt="商品图片预览"
          class="modal-preview-img"
          on:error={handleImgError}
        />
      </div>
    </div>
  </div>
{/if}

<style>
  .image-upload-container {
    margin: 4px 0;
    width: 100%;
    font-size: 11px;
  }

  .upload-section {
    margin-bottom: 4px;
  }

  .upload-input {
    padding: 4px 6px;
    border: 1px solid #ddd;
    border-radius: 3px;
    cursor: pointer;
    width: 100%;
    background-color: white;
    font-size: 10px;
    height: 30px;
  }

  .upload-input:disabled {
    cursor: not-allowed;
    background-color: #f5f5f5;
    opacity: 0.6;
  }

  /* 上传中状态样式 */
  .uploading-section {
    margin: 8px 0;
    padding: 8px;
    border: 1px solid #2196f3;
    border-radius: 4px;
    background-color: #e3f2fd;
  }

  .progress-container {
    position: relative;
    height: 20px;
    background-color: #eee;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 6px;
  }

  .progress-bar {
    height: 100%;
    background-color: #4caf50;
    transition: width 0.3s ease;
  }

  .progress-text {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 9px;
    font-weight: bold;
    color: #333;
  }

  .uploading-text {
    font-size: 9px;
    color: #2196f3;
    text-align: center;
    margin: 0;
  }

  /* 路径区域样式（新增清除按钮布局） */
  .path-section {
    margin: 2px 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
    align-items: flex-start;
  }

  /* 🔥 新增：路径头部（标签+清除按钮） */
  .path-header {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
  }

  .path-label {
    font-weight: 500;
    color: #555;
    font-size: 10px;
    min-width: 40px;
  }

  /* 🔥 新增：清除按钮样式 */
  .clear-btn {
    padding: 2px 8px;
    background-color: #ff4444;
    color: white;
    border: none;
    border-radius: 3px;
    cursor: pointer;
    font-size: 9px;
    display: flex;
    align-items: center;
    gap: 2px;
    margin-left: auto;
  }

  .clear-btn:hover:not(:disabled) {
    background-color: #cc0000;
  }

  .clear-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .path-input {
    width: 100%;
    padding: 2px 4px;
    border: 1px solid #ddd;
    border-radius: 3px;
    background-color: #f9f9f9;
    font-size: 9px;
    color: #333;
    cursor: text;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    height: 24px;
  }

  .path-input:focus {
    outline: none;
    border-color: #3498db;
    background-color: #fff;
  }

  .debug-text {
    font-size: 8px;
    color: #999;
    margin-top: 2px;
    word-break: break-all;
  }

  .warning-text {
    color: #ff6b6b;
    font-size: 9px;
    margin: 2px 0 0 0;
    padding-left: 2px;
    line-height: 1.2;
  }

  .preview-wrapper {
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px dashed #dee2e6;
  }

  .preview-img {
    max-width: 100px;
    max-height: 80px;
    border: 1px solid #ced4da;
    border-radius: 3px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
    cursor: pointer;
  }

  .preview-text {
    font-size: 9px;
    color: #666;
    margin: 2px 0 0 0;
  }

  .preview-btn {
    background: transparent;
    border: none;
    color: #3498db;
    cursor: pointer;
    font-size: 9px;
    padding: 0;
    margin-left: 4px;
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  .preview-btn:disabled {
    color: #999;
    cursor: not-allowed;
    text-decoration: none;
  }

  .preview-btn:hover:not(:disabled) {
    text-decoration: underline;
  }

  /* 弹窗样式 */
  .image-preview-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.85);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 9999;
    padding: 20px;
  }

  .preview-content {
    position: relative;
    max-width: 90%;
    max-height: 90%;
  }

  .close-btn {
    position: absolute;
    top: -10px;
    right: -10px;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background-color: #ff4444;
    color: white;
    border: none;
    font-size: 24px;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10;
  }

  .close-btn:hover {
    background-color: #cc0000;
  }

  .preview-image-container {
    max-width: 100%;
    max-height: 80vh;
    overflow: hidden;
    border-radius: 8px;
  }

  .modal-preview-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }
</style>