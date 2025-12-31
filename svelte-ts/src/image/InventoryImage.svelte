<script lang="ts">
  // ===================== 核心类型定义（适配后端上传接口） =====================
  interface CacheItem {
    value: string;
    timestamp: number;
  }

  type ImageErrorEvent = ErrorEvent<HTMLImageElement>;
  type ModalClickEvent = MouseEvent & {
    target: HTMLElement;
    currentTarget: HTMLElement;
  };

  // 上传响应类型（匹配后端实际返回格式）
  interface ImageAddResponse {
    status: 'success' | 'error';
    message: string;
    data?: {
      relative_path: string;
      access_url: string;
    };
  }

  interface BatchDeleteImageRequest {
    featureIds: string[];
    imagePaths: string[];
    relatedProductIds?: string[];
    cleanCsv: boolean;
  }

  interface BatchDeleteDetail {
    type: 'featureId' | 'imagePath';
    id: string;
    status: 'success' | 'fail';
    message: string;
    image_path: string;
    image_deleted: boolean;
    csv_cleaned: boolean;
    remaining_references: number;
    full_image_path?: string;
  }

  interface BatchDeleteImageResponse {
    status: 'success' | 'error' | 'partial_success';
    message: string;
    total: number;
    success_count: number;
    fail_count: number;
    details: BatchDeleteDetail[];
  }

  // ===================== 核心配置（修复：适配局域网IP，替换127.0.0.1为实际后端IP） =====================
  // 关键修改1：根据访问地址动态适配后端IP，或直接改为局域网IP（192.168.110.40）
  const BACKEND_IP = '192.168.110.40'; // 替换为实际后端服务的IP
  const BACKEND_PORT = '5000';
  const IMAGE_API_BASE: string = `http://${BACKEND_IP}:${BACKEND_PORT}/api/get_image`;
  const IMAGE_STATIC_BASE: string = `http://${BACKEND_IP}:${BACKEND_PORT}/image`;
  const DELETE_IMAGE_API: string = `http://${BACKEND_IP}:${BACKEND_PORT}/api/batch_delete_image`;
  const ADD_IMAGE_API: string = `http://${BACKEND_IP}:${BACKEND_PORT}/api/upload-image`;

  // 关键修改2：修复BACKUP_PLACEHOLDER的Base64 SVG格式（原格式可能有编码问题）
  const ERROR_PLACEHOLDER: string = 'https://picsum.photos/40/40?grayscale&text=无图';
  const BACKUP_PLACEHOLDER: string = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48Y2lyY2xlIGN4PSIyMCIgY3k9IjIwIiByPSIxOCIgZmlsbD0iI2Y1ZjdmYSIvPjxwYXRoIGQ9Ik0yMCAxNUEyIDIgMCAwIDEgMjIgMTdWMjNBMiAyIDAgMCAxIDIwIDI1QTIgMiAwIDAgMSAxOCAyM1YxN0EyIDIgMCAwIDEgMjAgMTUiIHN0cm9rZT0iIzc2NzY3NiIgc3Ryb2tlLXdpZHRoPSIxIi8+PHRleHQgeD0iMjAiIHk9IjI4IiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTIiIGZpbGw9IiM3Njc2NzYiIHg9IjIwIiB5PSIyOCIgdGV4dC1hbmNob3I9Im1pZGRsZSI+5peg5ZuPCjx0ZXh0Lz48L3N2Zz4=';

  // ===================== 核心状态变量（必须声明导出！） =====================
  export let imagePath: string = '';
  export let featureId: string | number = '';
  export let relatedProductId: string = '';
  export let unitPrice: string = '';
  export let inventoryId: string | number = '';
  export let updateInventory: (
      inventoryId: string | number,
      formData: Record<string, any>
  ) => Promise<{ status?: string; message?: string; data?: any }> = async () => ({
      status: 'error',
      message: '更新接口未配置'
  });
  export let showMessage: (msg: string, type: string) => void = () => {};
  // ✅ 新增：刷新回调函数（供父组件传入，操作成功后触发）
  export let onRefresh: () => void = () => {};

  // ===================== 缓存配置 =====================
  const CACHE_PREFIX: string = 'product_image_';
  const CACHE_EXPIRE_SECONDS: number = 3600;
  const MAX_CACHE_ITEMS: number = 100;
  const memoryCache: Map<string, CacheItem> = new Map();

  // 🚨 关键修改1：新增localStorage可用性检测（初始化时执行，避免后续频繁报错）
  let isLocalStorageAvailable: boolean = false;
  try {
    // 测试localStorage是否可用（写入空值再删除）
    const testKey = '__inventory_image_test__';
    localStorage.setItem(testKey, '');
    localStorage.removeItem(testKey);
    isLocalStorageAvailable = true;
  } catch (e) {
    console.warn('当前环境不支持localStorage，将仅使用内存缓存', e);
    isLocalStorageAvailable = false;
  }

  // ===================== 核心状态计算（区分上传/替换场景） =====================
  // 修复：确保isEmptyPath计算稳定，避免误判
  $: isEmptyPath = (() => {
    if (!imagePath) return true;
    const pathStr = String(imagePath).trim();
    return pathStr === '' || pathStr === 'undefined' || pathStr === 'null' ||
           (typeof imagePath === 'object' && Object.keys(imagePath).length === 0);
  })();

  $: isInvalidFeatureId = (() => {
    if (featureId === null || featureId === undefined || featureId === '') return true;
    const featureIdNum = Number(featureId);
    return isNaN(featureIdNum);
  })();

  $: isInvalidProductCode = (() => {
    if (!relatedProductId || relatedProductId.trim() === '') return true;
    return false;
  })();

  // 响应式变量依赖正确，避免计算时机异常
  $: isReplaceMode = !isEmptyPath && !isInvalidFeatureId;
  $: uploadBtnText = isReplaceMode ? '替换图片' : '上传图片';
  $: uploadBtnTitle = isInvalidProductCode
    ? '请先填写货号'
    : (isReplaceMode ? '点击替换当前图片' : '点击上传图片');

  // 修复：缓存Key添加空值标识，避免键冲突
  $: cacheKeyPreview = `${String(featureId)}_preview_${imagePath || 'empty'}`;
  $: cacheKeyDownload = `${String(featureId)}_download_${imagePath || 'empty'}`;
  $: cacheKeyImageBlob = `${String(featureId)}_blob_${imagePath || 'empty'}`;

  // 🚨 关键修改2：修复hasSwitchedToBackup的响应式声明（原写法每次触发都会重置为false）
  let hasSwitchedToBackup = false;
  // 改为手动控制，不再用$:声明

  // ===================== 调试日志 + 自动清理过期缓存 =====================
  $: {
    console.log('=== 图片组件调试 ===');
    console.log('特征ID:', featureId);
    console.log('关联商品货号:', relatedProductId);
    console.log('图片路径:', imagePath);
    console.log('预览URL:', previewImageUrl);
    console.log('下载URL:', downloadImageUrl);
    console.log('模式:', isReplaceMode ? '替换图片' : '首次上传');
    console.log('localStorage可用:', isLocalStorageAvailable);

    if (isEmptyPath) {
      console.warn(`[特征ID:${featureId}] 无有效图片路径`);
    }
    // 🚨 关键修改3：延迟执行清理过期缓存，避免首次加载就操作localStorage
    setTimeout(clearExpiredCache, 100);
  }

  // ===================== 缓存操作函数（核心优化：适配localStorage不可用场景） =====================
  function getCache(key: string): string | null {
    // 优先从内存缓存读取
    const memoryItem = memoryCache.get(key);
    if (memoryItem) {
      const now = Date.now();
      if (now - memoryItem.timestamp < CACHE_EXPIRE_SECONDS * 1000) {
        return memoryItem.value;
      }
      memoryCache.delete(key);
    }

    // localStorage不可用时，直接返回null
    if (!isLocalStorageAvailable) return null;

    try {
      const storageStr = localStorage.getItem(CACHE_PREFIX + key);
      if (!storageStr) return null;

      const storageItem = JSON.parse(storageStr) as CacheItem;
      if (!storageItem || typeof storageItem.value !== 'string' || typeof storageItem.timestamp !== 'number') {
        localStorage.removeItem(CACHE_PREFIX + key);
        return null;
      }

      const now = Date.now();
      if (now - storageItem.timestamp < CACHE_EXPIRE_SECONDS * 1000) {
        memoryCache.set(key, storageItem);
        return storageItem.value;
      }
      localStorage.removeItem(CACHE_PREFIX + key);
    } catch (e) {
      console.warn('读取缓存失败', e);
    }
    return null;
  }

  function setCache(key: string, value: string): void {
    if (!key || !value) return;

    // 先写入内存缓存
    const cacheItem: CacheItem = { value, timestamp: Date.now() };
    memoryCache.set(key, cacheItem);
    if (memoryCache.size > MAX_CACHE_ITEMS) {
      const oldestEntry = Array.from(memoryCache.entries())
        .sort((a, b) => a[1].timestamp - b[1].timestamp)[0];
      if (oldestEntry) memoryCache.delete(oldestEntry[0]);
    }

    // localStorage不可用时，跳过写入
    if (!isLocalStorageAvailable) return;

    try {
      localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(cacheItem));

      const cacheKeys: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const fullKey = localStorage.key(i);
        if (fullKey?.startsWith(CACHE_PREFIX)) cacheKeys.push(fullKey);
      }

      if (cacheKeys.length > MAX_CACHE_ITEMS) {
        const cacheItems = cacheKeys.map(k => ({
          key: k,
          item: JSON.parse(localStorage.getItem(k) || '{}') as CacheItem
        })).filter(item => item.item.timestamp)
          .sort((a, b) => a.item.timestamp - b.item.timestamp);

        if (cacheItems.length > 0) {
          localStorage.removeItem(cacheItems[0].key);
        }
      }
    } catch (e) {
      console.warn('写入本地缓存失败', e);
    }
  }

  function clearFeatureCache(featureId: string | number | null | undefined): void {
    if (featureId === null || featureId === undefined || featureId === '') return;
    const featureIdStr = String(featureId);

    // 先清理内存缓存
    for (const [key] of memoryCache.entries()) {
      if (key.startsWith(`${featureIdStr}_`)) {
        const cacheItem = memoryCache.get(key);
        if (cacheItem?.value.startsWith('blob:')) {
          URL.revokeObjectURL(cacheItem.value);
        }
        memoryCache.delete(key);
      }
    }

    // localStorage不可用时，跳过清理
    if (!isLocalStorageAvailable) return;

    try {
      for (let i = 0; i < localStorage.length; i++) {
        const fullKey = localStorage.key(i);
        if (fullKey?.startsWith(CACHE_PREFIX + featureIdStr + '_')) {
          localStorage.removeItem(fullKey);
          i--;
        }
      }
    } catch (e) {
      console.warn('清理特征ID缓存失败', e);
    }
  }

  function refreshImageUrlCache(): void {
    // 仅清理内存缓存，避免频繁操作localStorage
    memoryCache.delete(cacheKeyPreview);
    memoryCache.delete(cacheKeyDownload);
    memoryCache.delete(cacheKeyImageBlob);

    // localStorage可用时才清理
    if (isLocalStorageAvailable) {
      localStorage.removeItem(CACHE_PREFIX + cacheKeyPreview);
      localStorage.removeItem(CACHE_PREFIX + cacheKeyDownload);
      localStorage.removeItem(CACHE_PREFIX + cacheKeyImageBlob);
    }

    // 强制重新计算URL（响应式触发）
    previewImageUrl = previewImageUrl;
    downloadImageUrl = downloadImageUrl;
  }

  function clearExpiredCache(): void {
    const now = Date.now();
    // 先清理内存缓存
    for (const [key, item] of memoryCache.entries()) {
      if (now - item.timestamp > CACHE_EXPIRE_SECONDS * 1000) {
        if (item.value.startsWith('blob:')) {
          URL.revokeObjectURL(item.value);
        }
        memoryCache.delete(key);
      }
    }

    // localStorage不可用时，跳过清理
    if (!isLocalStorageAvailable) return;

    try {
      for (let i = 0; i < localStorage.length; i++) {
        const fullKey = localStorage.key(i);
        if (fullKey?.startsWith(CACHE_PREFIX)) {
          const storageStr = localStorage.getItem(fullKey);
          if (!storageStr) continue;

          const storageItem = JSON.parse(storageStr) as CacheItem;
          if (now - storageItem.timestamp > CACHE_EXPIRE_SECONDS * 1000) {
            localStorage.removeItem(fullKey);
            i--;
          }
        }
      }
    } catch (e) {
      console.warn('清理过期缓存失败', e);
    }
  }

  // ===================== URL拼接逻辑 =====================
  $: previewImageUrl = ((): string => {
    if (isEmptyPath) return '';

    const cachedUrl = getCache(cacheKeyPreview);
    if (cachedUrl) {
      console.log(`[特征ID:${featureId}] 预览URL命中缓存`);
      return cachedUrl;
    }

    let url = '';
    const pathStr = String(imagePath);
    const timestamp = Date.now();
    if (pathStr.startsWith('http://') || pathStr.startsWith('https://')) {
      url = `${pathStr}?t=${timestamp}`;
    } else {
      let safePath = pathStr;
      if (!safePath.startsWith('image/')) safePath = `image/${safePath}`;
      const encodedPath = encodeURIComponent(safePath).replace(/%2F/g, '/');
      url = `${IMAGE_API_BASE}?path=${encodedPath}&t=${timestamp}`;
    }

    setCache(cacheKeyPreview, url);
    return url;
  })();

  $: downloadImageUrl = ((): string => {
    if (isEmptyPath) return '';

    const cachedUrl = getCache(cacheKeyDownload);
    if (cachedUrl) {
      console.log(`[特征ID:${featureId}] 下载URL命中缓存`);
      return cachedUrl;
    }

    let url = '';
    const pathStr = String(imagePath);
    const timestamp = Date.now();
    if (pathStr.startsWith('http://') || pathStr.startsWith('https://')) {
      url = `${pathStr}?t=${timestamp}`;
    } else {
      let safePath = pathStr;
      if (safePath.startsWith('image/')) safePath = safePath.replace('image/', '');
      url = `${IMAGE_STATIC_BASE}/${safePath}?t=${timestamp}`;
    }

    setCache(cacheKeyDownload, url);
    return url;
  })();

  $: downloadFileName = ((): string => {
    if (isEmptyPath) return '商品图片.jpg';
    const pathStr = String(imagePath);
    const filename = pathStr.split('/').pop() || '商品图片.jpg';
    const displayFeatureId = isInvalidFeatureId ? '未知ID' : String(featureId);
    return `特征ID${displayFeatureId}_${filename}`;
  })();

  // ===================== 事件处理逻辑 =====================
  // 关键修改3：重构handleImageError，防止兜底占位符重复触发错误，添加状态锁和防重复监听
  function handleImageError(e: ImageErrorEvent): void {
    const img = e.target as HTMLImageElement;
    // 跳过已经是最终兜底的情况，避免无限循环
    if (img.src === BACKUP_PLACEHOLDER) {
      console.warn(`[特征ID:${featureId}] 最终备份占位符加载失败，SVG格式异常`, img.src);
      return;
    }

    console.error(`[特征ID:${featureId}] 图片加载失败:`, {
      特征ID有效性: !isInvalidFeatureId,
      目标URL: img.src,
      原始路径: imagePath,
      错误类型: e.type
    });

    // 重置备份状态
    hasSwitchedToBackup = false;

    // 第一步：切换到ERROR_PLACEHOLDER（远程占位符）
    if (img.src !== ERROR_PLACEHOLDER) {
      img.src = ERROR_PLACEHOLDER;

      // 为ERROR_PLACEHOLDER添加一次性错误监听，仅触发一次
      const errorHandler = () => {
        if (!hasSwitchedToBackup) {
          hasSwitchedToBackup = true;
          img.src = BACKUP_PLACEHOLDER;
          // 移除监听，防止重复触发
          img.removeEventListener('error', errorHandler);
        }
      };

      // 先移除可能存在的旧监听，再添加新的
      img.removeEventListener('error', errorHandler);
      img.addEventListener('error', errorHandler, { once: true });
    }
  }

  // 修复：打开预览时强制重新计算URL，确保缓存失效后能重新生成
  function openPreviewModal(): void {
    if (isEmptyPath || previewImageUrl === ERROR_PLACEHOLDER || previewImageUrl === BACKUP_PLACEHOLDER) {
      console.warn(`[特征ID:${featureId}] 无有效图片，拒绝打开预览弹窗`);
      return;
    }
    // 强制触发响应式重新计算
    previewImageUrl = previewImageUrl;
    isModalOpen = true;
    document.body.style.overflow = 'hidden';
  }

  // 核心修复：移除手动清空previewImageUrl的操作，仅释放Blob缓存
  function closePreviewModal(): void {
    isModalOpen = false;
    document.body.style.overflow = 'auto';
    isDownloading = false;
    isDeleting = false;
    // 仅释放Blob URL避免内存泄漏，不影响预览URL
    const blobUrl = getCache(cacheKeyImageBlob);
    if (blobUrl) {
      URL.revokeObjectURL(blobUrl);
      memoryCache.delete(cacheKeyImageBlob);
    }
  }

  async function downloadOriginalImage(): Promise<void> {
    if (isEmptyPath || !downloadImageUrl || isDownloading) return;

    try {
      isDownloading = true;
      console.log(`[特征ID:${featureId}] 开始下载原图:`, downloadImageUrl);

      const cachedBlobUrl = getCache(cacheKeyImageBlob);
      if (cachedBlobUrl) {
        console.log(`[特征ID:${featureId}] Blob URL命中缓存，直接下载`);
        const link = document.createElement('a');
        link.href = cachedBlobUrl;
        link.download = downloadFileName;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        isDownloading = false;
        return;
      }

      const response = await fetch(downloadImageUrl, {
        method: 'GET',
        headers: { 'Accept': 'image/*', 'Cache-Control': 'no-cache' },
        credentials: 'include'
      });

      if (!response.ok) {
        throw new Error(`HTTP错误：${response.status} ${response.statusText}`);
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      memoryCache.set(cacheKeyImageBlob, { value: blobUrl, timestamp: Date.now() });

      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = downloadFileName;
      link.style.display = 'none';
      document.body.appendChild(link);
      link.click();

      setTimeout(() => {
        document.body.removeChild(link);
        isDownloading = false;
      }, 100);

      console.log(`[特征ID:${featureId}] 下载成功：${downloadFileName}`);
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      console.error(`[特征ID:${featureId}] 下载失败:`, err);
      alert(`下载失败：${err.message}\n特征ID：${featureId}`);
      isDownloading = false;
    }
  }

  // ===================== 抽离：删除原有图片的核心逻辑（复用给替换功能） =====================
  async function deleteOriginalImage(featureId: string | number, imagePath: string, relatedProductId?: string): Promise<{
    success: boolean;
    message: string;
    imageDeleted: boolean;
    remainingReferences: number;
  }> {
    try {
      const deleteParams: BatchDeleteImageRequest = {
        featureIds: [String(featureId).trim()],
        imagePaths: [String(imagePath).trim()],
        cleanCsv: true,
        ...(relatedProductId ? { relatedProductIds: [relatedProductId.trim()] } : {})
      };

      console.log(`[特征ID:${featureId}] 替换前删除原有图片，参数：`, deleteParams);

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
        throw new Error(`接口请求失败：${response.status} ${response.statusText}`);
      }

      const result: BatchDeleteImageResponse = await response.json() as BatchDeleteImageResponse;
      console.log(`[特征ID:${featureId}] 替换前删除原有图片响应：`, result);

      const currentDetail = result.details?.[0];
      let message = '';
      let imageDeleted = false;
      let remainingReferences = 0;

      if (result.status === 'error') {
        throw new Error(result.message || '删除原有图片失败');
      } else if (result.status === 'partial_success') {
        const failDetail = result.details.find(d => d.status === 'fail');
        if (failDetail) {
          console.warn(`[特征ID:${featureId}] 替换前删除原有图片部分失败`, failDetail);
          message = `⚠️ 原有图片部分处理失败：${failDetail.message}`;
        } else {
          imageDeleted = currentDetail?.image_deleted || false;
          remainingReferences = currentDetail?.remaining_references || 0;
          message = imageDeleted
            ? `✅ 原有图片已删除（无剩余引用）`
            : `✅ 仅清空原有图片路径（仍有${remainingReferences}个引用）`;
        }
      } else {
        imageDeleted = currentDetail?.image_deleted || false;
        remainingReferences = currentDetail?.remaining_references || 0;
        message = imageDeleted
          ? `✅ 原有图片已删除（无剩余引用）`
          : `✅ 仅清空原有图片路径（仍有${remainingReferences}个引用）`;
      }

      return {
        success: true,
        message,
        imageDeleted,
        remainingReferences
      };
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      console.error(`[特征ID:${featureId}] 替换前删除原有图片失败`, err);
      return {
        success: false,
        message: `删除原有图片失败：${err.message}`,
        imageDeleted: false,
        remainingReferences: -1
      };
    }
  }

  async function deleteImage(): Promise<void> {
    if (isEmptyPath || isInvalidFeatureId || isDeleting) {
      console.warn(`[特征ID:${featureId}] 删除前置校验失败`, { isEmptyPath, isInvalidFeatureId, isDeleting });
      return;
    }

    const confirmDelete = confirm(
      `确认删除特征ID【${featureId}】的图片吗？\n路径：${imagePath}\n注：仅清空该特征ID的图片路径，若该图片被其他ID引用，文件不会删除！`
    );
    if (!confirmDelete) return;

    const oldCacheKeyPreview = cacheKeyPreview;
    const oldCacheKeyDownload = cacheKeyDownload;
    const oldCacheKeyImageBlob = cacheKeyImageBlob;

    try {
      isDeleting = true;

      // 复用抽离的删除逻辑
      const deleteResult = await deleteOriginalImage(featureId, imagePath, relatedProductId);
      if (!deleteResult.success) {
        throw new Error(deleteResult.message);
      }

      alert(deleteResult.message);

      const oldBlobUrl = getCache(oldCacheKeyImageBlob);
      if (oldBlobUrl) URL.revokeObjectURL(oldBlobUrl);

      memoryCache.delete(oldCacheKeyPreview);
      memoryCache.delete(oldCacheKeyDownload);
      memoryCache.delete(oldCacheKeyImageBlob);

      // localStorage可用时才删除
      if (isLocalStorageAvailable) {
        localStorage.removeItem(CACHE_PREFIX + oldCacheKeyPreview);
        localStorage.removeItem(CACHE_PREFIX + oldCacheKeyDownload);
        localStorage.removeItem(CACHE_PREFIX + oldCacheKeyImageBlob);
      }

      clearFeatureCache(featureId);

      // 仅清空imagePath（响应式会自动更新previewImageUrl）
      imagePath = '';
      closePreviewModal();

      // ✅ 新增：删除成功后触发父组件的刷新逻辑
      onRefresh();

    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      console.error(`[特征ID:${featureId}] 批量删除失败`, err);
      alert(`❌ 删除失败：${err.message}\n特征ID：${featureId}`);
    } finally {
      isDeleting = false;
    }
  }

  function handleModalOverlayClick(e: ModalClickEvent): void {
    if (e.target === e.currentTarget) closePreviewModal();
  }

  // ===================== 上传图片核心逻辑（新增：替换时先删除原有图片） =====================
  function openUploadModal(): void {
    const currentFeatureId = featureId;
    const currentProductCode = relatedProductId;

    if (isInvalidFeatureId) {
      alert(`特征ID无效（当前值：${currentFeatureId}），无法${uploadBtnText}！`);
      return;
    }
    if (isInvalidProductCode) {
      alert(`商品货号不能为空（当前值：${currentProductCode || '空'}），请先填写货号！`);
      return;
    }

    showUploadModal = true;
    document.body.style.overflow = 'hidden';
    uploadFile = null;
    isUploading = false;
  }

  function closeUploadModal(): void {
    showUploadModal = false;
    document.body.style.overflow = 'auto';
    isUploading = false;
    uploadFile = null;
  }

  function handleFileChange(e: Event): void {
    const target = e.target as HTMLInputElement;
    if (!target.files || target.files.length === 0) {
      uploadFile = null;
      return;
    }

    const file = target.files[0];
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp'];
    const allowedExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];
    const fileExt = file.name.toLowerCase().split('.').pop() || '';

    if (!allowedTypes.includes(file.type) && !allowedExts.includes(fileExt)) {
      alert(`仅支持上传 jpg/png/gif/webp/bmp 格式！当前文件：${file.name}（类型：${file.type}）`);
      uploadFile = null;
      target.value = '';
      return;
    }

    const maxSize = 16 * 1024 * 1024;
    if (file.size > maxSize) {
      alert(`图片大小不能超过16MB！当前大小：${(file.size / 1024 / 1024).toFixed(2)}MB`);
      uploadFile = null;
      target.value = '';
      return;
    }

    uploadFile = file;
    console.log(`[特征ID:${featureId}] 选中${isReplaceMode ? '替换' : '上传'}文件：`, file);
  }

  // 修复：上传中断时回滚状态，保留原始图片路径；新增：替换时先删除原有图片
  async function uploadImage(): Promise<void> {
    if (isInvalidFeatureId || isInvalidProductCode || !uploadFile || isUploading) {
      console.warn('上传前置校验失败', {
        featureIdValid: !isInvalidFeatureId,
        productCodeValid: !isInvalidProductCode,
        hasFile: !!uploadFile,
        isUploading
      });
      return;
    }

    // 保存原始状态，用于失败时回滚
    const originalImagePath = imagePath;
    const originalPreviewUrl = previewImageUrl;

    try {
      isUploading = true;

      // ========== 核心新增：替换模式下先处理原有图片 ==========
      let deleteOldImageMsg = '';
      if (isReplaceMode && !isEmptyPath) {
        console.log(`[特征ID:${featureId}] 替换图片，先处理原有图片`);
        const deleteResult = await deleteOriginalImage(featureId, imagePath, relatedProductId);
        if (!deleteResult.success) {
          // 原有图片删除失败，是否继续？
          const continueUpload = confirm(`${deleteResult.message}\n是否继续上传新图片？`);
          if (!continueUpload) {
            isUploading = false;
            return;
          }
          deleteOldImageMsg = `（原有图片处理提示：${deleteResult.message}）`;
        } else {
          deleteOldImageMsg = deleteResult.message;
        }
      }

      const formData = new FormData();
      formData.append('product_code', relatedProductId.trim());
      formData.append('file', uploadFile);

      console.log(`[特征ID:${featureId}] ${isReplaceMode ? '替换' : '上传'}参数：`, {
        product_code: relatedProductId.trim(),
        fileName: uploadFile.name,
        fileSize: uploadFile.size,
        originalImagePath: imagePath,
        deleteOldImageMsg
      });

      const response = await fetch(ADD_IMAGE_API, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`上传请求失败：${response.status} ${response.statusText}`);
      }

      const result: ImageAddResponse = await response.json();
      console.log(`[特征ID:${featureId}] ${isReplaceMode ? '替换' : '上传'}响应：`, result);

      if (result.status === 'error') {
        throw new Error(result.message || `${isReplaceMode ? '替换' : '上传'}图片失败`);
      }

      if (!result.data?.relative_path) {
        throw new Error('后端未返回图片路径');
      }

      console.log(`[库存ID:${inventoryId}] 开始${isReplaceMode ? '覆盖' : '同步'}图片路径到库存数据`, {
        originalPath: imagePath,
        newPath: result.data.relative_path
      });

      try {
        const updateResult = await updateInventory(inventoryId, {
          图片路径: result.data.relative_path
        });

        if (updateResult.status === 'success' || !updateResult.status) {
          const successMsg = `${isReplaceMode ? '图片替换' : '图片上传'}并同步库存成功！${deleteOldImageMsg}`;
          showMessage(successMsg, 'success');
          console.log(`[库存ID:${inventoryId}] 图片路径${isReplaceMode ? '覆盖' : '同步'}成功`, updateResult);
        } else {
          throw new Error(updateResult.message || `库存图片路径${isReplaceMode ? '覆盖' : '同步'}失败`);
        }
      } catch (updateError) {
        const err = updateError instanceof Error ? updateError : new Error(String(updateError));
        console.error(`[库存ID:${inventoryId}] 图片路径${isReplaceMode ? '覆盖' : '同步'}失败`, err);
        const warningMsg = `${isReplaceMode ? '图片替换' : '图片上传'}成功，但库存图片路径同步失败：${err.message}${deleteOldImageMsg}`;
        showMessage(warningMsg, 'warning');
      }

      // 更新图片路径并刷新缓存
      imagePath = result.data.relative_path;
      clearFeatureCache(featureId);
      refreshImageUrlCache();

      closeUploadModal();
      // 如果预览弹窗还开着，强制刷新预览
      if (isModalOpen) {
        previewImageUrl = previewImageUrl;
      }

      // ✅ 新增：上传/替换成功后触发父组件的刷新逻辑
      onRefresh();

    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      console.error(`[特征ID:${featureId}] ${isReplaceMode ? '替换' : '上传'}失败`, err);
      showMessage(`❌ ${isReplaceMode ? '图片替换' : '图片上传'}失败：${err.message}`, 'error');
      // 修复：上传失败时回滚到原始状态
      imagePath = originalImagePath;
      previewImageUrl = originalPreviewUrl;
    } finally {
      isUploading = false;
    }
  }

  // ===================== 状态管理 =====================
  let isModalOpen: boolean = false;
  let isDownloading: boolean = false;
  let isDeleting: boolean = false;
  let previewImageUrl: string = '';
  let downloadImageUrl: string = '';
  let isUploading: boolean = false;
  let uploadFile: File | null = null;
  let showUploadModal: boolean = false;
</script>

<!-- ===================== 模板部分 ===================== -->
<div class="inventory-image-wrapper">
  {#if !isEmptyPath}
    <!-- 有图片时：显示图片 + 删除 + 替换按钮 -->
    <img
      src={previewImageUrl || ERROR_PLACEHOLDER}
      alt={`特征ID${featureId}商品图片`}
      title="点击查看大图"
      class="inventory-image"
      on:error={handleImageError}
      on:click={openPreviewModal}
      loading="lazy"
    />
    <button
      class="delete-image-btn mini"
      on:click={(e) => { e.stopPropagation(); deleteImage(); }}
      disabled={isDeleting || isEmptyPath}
      title="删除图片（仅清空当前特征ID的路径，有引用则保留文件）"
    >
      🗑️
    </button>
    <button
      class="upload-image-btn mini"
      on:click={(e) => { e.stopPropagation(); openUploadModal(); }}
      disabled={isUploading || isInvalidFeatureId || isInvalidProductCode}
      title={uploadBtnTitle}
    >
      🔄
    </button>
  {:else}
    <!-- 无图片时：占位符 + 加号上传按钮 -->
    <div class="empty-image-placeholder">
      <span class="empty-text">{isInvalidFeatureId ? '无ID' : featureId}</span>
      <button
        class="upload-empty-btn"
        on:click={openUploadModal}
        disabled={isInvalidFeatureId || isInvalidProductCode || isUploading}
        title={uploadBtnTitle}
      >
        +
      </button>
    </div>
  {/if}
</div>

{#if isModalOpen}
  <!-- 图片预览弹窗 -->
  <div class="image-preview-modal" on:click={handleModalOverlayClick}>
    <div class="preview-content">
      <div class="feature-id-label">特征ID：{featureId}</div>
      {#if relatedProductId}
        <div class="product-id-label">商品货号：{relatedProductId}</div>
      {/if}

      <button class="close-btn" on:click={closePreviewModal} disabled={isDownloading || isDeleting}>
        &times;
      </button>

      <div class="preview-image-container">
        <img
          src={previewImageUrl}
          alt={`特征ID${featureId}商品图片预览`}
          class="blur-preview-image"
          on:error={handleImageError}
        />
      </div>

      <div class="preview-actions">
        <button
          class="download-btn"
          on:click={downloadOriginalImage}
          disabled={isDownloading || isDeleting || isEmptyPath}
        >
          {#if isDownloading}📥 下载中...{:else if isEmptyPath}📥 无有效图片{:else}📥 下载高清原图{/if}
        </button>
        <button
          class="delete-btn"
          on:click={(e) => { e.stopPropagation(); deleteImage(); }}
          disabled={isDeleting || isEmptyPath}
          title="删除图片（仅清空当前特征ID的路径，有引用则保留文件）"
        >
          {#if isDeleting}🗑️ 删除中...{:else}🗑️ 删除图片{/if}
        </button>
        <button
          class="upload-btn"
          on:click={(e) => { e.stopPropagation(); openUploadModal(); }}
          disabled={isUploading || isDeleting || isInvalidProductCode}
          title={uploadBtnTitle}
        >
          {#if isReplaceMode}🔄 替换图片{:else}📤 上传图片{/if}
        </button>
      </div>
    </div>
  </div>
{/if}

{#if showUploadModal}
  <!-- 上传弹窗：区分上传/替换标题 -->
  <div class="image-upload-modal" on:click={(e) => e.target === e.currentTarget && closeUploadModal()}>
    <div class="upload-content">
      <h3 class="upload-title">{isReplaceMode ? '替换商品图片' : '上传商品图片'}</h3>

      <!-- 自动填充并显示特征ID（只读） -->
      <div class="form-group">
        <label class="form-label">特征ID <span class="required">*</span></label>
        <input
          type="text"
          value={featureId}
          disabled
          class="form-input readonly-input"
          placeholder="特征ID"
        />
      </div>

      <!-- 自动填充并显示商品货号（只读） -->
      <div class="form-group">
        <label class="form-label">商品货号 <span class="required">*</span></label>
        <input
          type="text"
          value={relatedProductId}
          disabled
          class="form-input readonly-input"
          placeholder="商品货号"
        />
      </div>

      <!-- 替换模式下显示原有图片路径 -->
      {#if isReplaceMode}
        <div class="form-group">
          <label class="form-label">原有图片路径</label>
          <input
            type="text"
            value={imagePath}
            disabled
            class="form-input readonly-input"
            placeholder="无原有路径"
            style="color: #999;"
          />
          <span class="form-tip">替换时将先处理原有图片：有引用则仅清空路径，无引用则删除文件</span>
        </div>
      {/if}

      <!-- 文件选择 -->
      <div class="form-group">
        <label class="form-label">选择图片文件 <span class="required">*</span></label>
        <input
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp,image/bmp"
          class="file-input"
          on:change={handleFileChange}
          disabled={isUploading}
        />
        {#if uploadFile}
          <div class="file-info">
            已选择：{uploadFile.name} ({(uploadFile.size / 1024).toFixed(1)}KB)
            <span class="name-tip">（文件名将自动生成：货号_时间戳.扩展名）</span>
          </div>
        {/if}
      </div>

      <!-- 操作按钮 -->
      <div class="upload-actions">
        <button class="cancel-btn" on:click={closeUploadModal} disabled={isUploading}>取消</button>
        <button
          class="submit-upload-btn"
          on:click={uploadImage}
          disabled={!uploadFile || isUploading}
        >
          {#if isUploading}
            {isReplaceMode ? '🔄 替换中...' : '📤 上传中...'}
          {:else}
            {isReplaceMode ? '🔄 确认替换' : '📤 确认上传'}
          {/if}
        </button>
      </div>

      <!-- 关闭按钮 -->
      <button class="close-upload-btn" on:click={closeUploadModal} disabled={isUploading}>
        &times;
      </button>
    </div>
  </div>
{/if}

<!-- ===================== 样式部分 ===================== -->
<style>
  /* 基础样式 */
  .inventory-image-wrapper {
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 2px 0;
    min-height: 40px;
    position: relative;
  }

  .inventory-image {
    width: 40px;
    height: 40px;
    object-fit: cover;
    border-radius: 4px;
    border: 1px solid #e4e7ed;
    background-color: #f5f7fa;
    transition: all 0.2s ease;
    cursor: pointer;
    background-image: linear-gradient(45deg, #f0f0f0 25%, transparent 25%),
                      linear-gradient(-45deg, #f0f0f0 25%, transparent 25%),
                      linear-gradient(45deg, transparent 75%, #f0f0f0 75%),
                      linear-gradient(-45deg, transparent 75%, #f0f0f0 75%);
    background-size: 8px 8px;
    background-position: 0 0, 0 4px, 4px -4px, -4px 0px;
  }

  .inventory-image:hover:not([disabled]) {
    transform: scale(1.05);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  /* 空占位符样式 */
  .empty-image-placeholder {
    width: 40px;
    height: 40px;
    border-radius: 4px;
    border: 1px solid #e4e7ed;
    background-color: #fff;
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
  }

  .empty-text {
    font-size: 10px;
    color: #999;
    text-align: center;
    line-height: 1;
  }

  /* 加号上传按钮 */
  .upload-empty-btn {
    position: absolute;
    bottom: 0;
    right: 0;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background-color: #409eff;
    color: white;
    border: none;
    font-size: 12px;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 0;
    line-height: 1;
    opacity: 0.8;
    transition: opacity 0.2s;
  }

  .upload-empty-btn:disabled {
    background-color: #999;
    cursor: not-allowed;
    opacity: 0.5;
  }

  .upload-empty-btn:hover:not(:disabled) {
    opacity: 1;
  }

  /* 小尺寸上传/删除按钮 */
  .upload-image-btn.mini, .delete-image-btn.mini {
    position: absolute;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    color: white;
    border: none;
    font-size: 10px;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    transition: background-color 0.2s;
    z-index: 1;
  }

  .upload-image-btn.mini {
    top: -5px;
    right: 18px;
    background-color: #409eff;
  }

  .delete-image-btn.mini {
    top: -5px;
    right: -5px;
    background-color: #ff4444;
  }

  .upload-image-btn.mini:disabled, .delete-image-btn.mini:disabled {
    background-color: #999;
    cursor: not-allowed;
    opacity: 0.7;
  }

  .upload-image-btn.mini:hover:not(:disabled) {
    background-color: #1989fa;
  }

  .delete-image-btn.mini:hover:not(:disabled) {
    background-color: #cc0000;
  }

  /* 预览弹窗样式 */
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
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20px;
  }

  .feature-id-label, .product-id-label {
    position: absolute;
    top: -10px;
    color: #fff;
    font-size: 12px;
    background-color: rgba(0, 0, 0, 0.5);
    padding: 4px 8px;
    border-radius: 4px;
    z-index: 10;
  }

  .feature-id-label {
    left: 0;
  }

  .product-id-label {
    left: 120px;
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
    transition: background-color 0.2s;
  }

  .close-btn:disabled {
    background-color: #999;
    cursor: not-allowed;
  }

  .close-btn:hover:not(:disabled) {
    background-color: #cc0000;
  }

  .preview-image-container {
    max-width: 100%;
    max-height: 80vh;
    overflow: hidden;
    border-radius: 8px;
  }

  .blur-preview-image {
    width: 100%;
    height: 100%;
    object-fit: contain;
    filter: blur(1px);
    transition: filter 0.3s ease;
  }

  .preview-image-container:hover .blur-preview-image {
    filter: blur(0.5px);
  }

  .preview-actions {
    display: flex;
    gap: 16px;
    align-items: center;
  }

  .download-btn, .delete-btn, .upload-btn {
    padding: 12px 30px;
    border-radius: 8px;
    color: white;
    border: none;
    font-size: 16px;
    cursor: pointer;
    transition: background-color 0.2s;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .download-btn {
    background-color: #2196F3;
  }

  .delete-btn {
    background-color: #f44336;
  }

  .upload-btn {
    background-color: #409eff;
  }

  .download-btn:disabled, .delete-btn:disabled, .upload-btn:disabled {
    background-color: #999;
    cursor: not-allowed;
    opacity: 0.8;
  }

  .download-btn:hover:not(:disabled) {
    background-color: #1976D2;
  }

  .delete-btn:hover:not(:disabled) {
    background-color: #d32f2f;
  }

  .upload-btn:hover:not(:disabled) {
    background-color: #1989fa;
  }

  /* 上传弹窗样式 */
  .image-upload-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.7);
    display: flex;
    justify-content: center;
    align-items: center;
    z-index: 10000;
    padding: 20px;
  }

  .upload-content {
    position: relative;
    width: 100%;
    max-width: 500px;
    background-color: white;
    border-radius: 8px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  }

  .upload-title {
    font-size: 18px;
    color: #333;
    margin: 0 0 20px 0;
    text-align: center;
  }

  .form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }

  .form-label {
    font-size: 14px;
    color: #333;
    font-weight: 500;
  }

  .required {
    color: #ff4444;
  }

  .form-input {
    padding: 8px 12px;
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    font-size: 14px;
  }

  .readonly-input {
    background-color: #f5f7fa;
    color: #333;
    cursor: not-allowed;
  }

  .file-input {
    padding: 8px;
    border: 1px solid #e4e7ed;
    border-radius: 4px;
    cursor: pointer;
  }

  .file-info {
    font-size: 12px;
    color: #666;
    margin-top: 4px;
  }

  .name-tip {
    color: #409eff;
    font-size: 10px;
    margin-left: 8px;
  }

  /* 原有路径提示样式 */
  .form-tip {
    font-size: 10px;
    color: #999;
    margin-top: 4px;
  }

  .upload-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 8px;
  }

  .cancel-btn, .submit-upload-btn {
    padding: 10px 20px;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .cancel-btn {
    background-color: #f5f5f5;
    color: #666;
    border: 1px solid #e4e7ed;
  }

  .cancel-btn:disabled, .submit-upload-btn:disabled {
    background-color: #999;
    color: #fff;
    cursor: not-allowed;
    opacity: 0.8;
  }

  .cancel-btn:hover:not(:disabled) {
    background-color: #e5e5e5;
  }

  .submit-upload-btn {
    background-color: #409eff;
    color: white;
    border: none;
  }

  .submit-upload-btn:hover:not(:disabled) {
    background-color: #1989fa;
  }

  .close-upload-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background-color: #f5f5f5;
    color: #666;
    border: none;
    font-size: 20px;
    cursor: pointer;
    display: flex;
    justify-content: center;
    align-items: center;
    transition: background-color 0.2s;
  }

  .close-upload-btn:hover:not(:disabled) {
    background-color: #e5e5e5;
  }

  .close-upload-btn:disabled {
    color: #ccc;
    cursor: not-allowed;
  }
</style>