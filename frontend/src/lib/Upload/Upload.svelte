<script lang="ts">
    import { createEventDispatcher, onMount, onDestroy } from 'svelte';
    import { browser } from '$app/environment';

    const dispatch = createEventDispatcher<{ upload: File }>();

    let fileInput: HTMLInputElement;
    let dragOver = false;
    let isUploading = false;
    let receivedExternalFile: File | null = null;
    let externalFileTip = '';

    function handleFileSelect(e: Event) {
        const target = e.target as HTMLInputElement;
        if (target.files && target.files[0]) {
            processFile(target.files[0]);
        }
    }

    // 核心逻辑：文件校验 + 派发上传事件（复用原有逻辑）
    function processFile(file: File) {
        receivedExternalFile = null;
        externalFileTip = '';

        if (!file.type.startsWith('image/')) {
            alert('请选择图片文件（支持JPG、PNG、GIF等格式）');
            return;
        }

        if (file.size > 10 * 1024 * 1024) { // 10MB限制
            alert('图片大小不能超过10MB');
            return;
        }

        isUploading = true;
        dispatch('upload', file);
        setTimeout(() => {
            isUploading = false;
            if (fileInput) {
                fileInput.value = '';
            }
        }, 500);
    }

    // 新增：处理从前端A接收的图片
    function handleMessageFromA(e: MessageEvent) {
        // 安全校验：仅接收前端A的来源（生产环境替换为前端A的实际域名）
        const allowedOrigins = ['http://localhost:5173', 'http://127.0.0.1:5173', 'http://192.168.110.40:5173'];
        if (!allowedOrigins.includes(e.origin)) {
            console.warn('拒绝接收非信任来源的消息：', e.origin);
            return;
        }

        // 校验消息类型（与前端A约定的 type: 'PENDING_IMAGE'）
        if (e.data?.type !== 'PENDING_IMAGE') return;

        try {
            const { data: imageData, fileName, productCode } = e.data;
            let file: File;

            // 处理 File/Blob 类型（前端A可能传File或Blob）
            if (imageData instanceof File) {
                file = imageData;
            } else if (imageData instanceof Blob) {
                // Blob转换为File（补充文件名/类型）
                file = new File([imageData], fileName || `external-image-${Date.now()}.png`, {
                    type: imageData.type || 'image/png'
                });
            } else {
                throw new Error('接收的图片数据类型无效（非File/Blob）');
            }

            // 记录外部图片并自动处理
            receivedExternalFile = file;
            externalFileTip = `已接收【${productCode || '未知商品'}】的图片：${file.name}`;
            console.log('从前端A接收图片：', file);

            // 自动复用原有逻辑处理图片
            processFile(file);
        } catch (err) {
            console.error('处理前端A图片失败：', err);
            alert(`接收前端A图片失败：${(err as Error).message}`);
        }
    }

    function handleDragOver(e: DragEvent) {
        e.preventDefault();
        dragOver = true;
    }

    function handleDragLeave() {
        dragOver = false;
    }

    function handleDrop(e: DragEvent) {
        e.preventDefault();
        dragOver = false;
        if (e.dataTransfer?.files && e.dataTransfer.files[0]) {
            processFile(e.dataTransfer.files[0]);
        }
    }

    function handleKeyDown(e: KeyboardEvent) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    }

    onMount(() => {
      if (browser) {
        // 1. 先注册监听（原有逻辑保留）
        window.addEventListener('message', handleMessageFromA);

        // 2. 告诉前端A：我已准备好接收消息
        if (window.opener) { // 确保是前端A打开的窗口
          window.opener.postMessage(
            { type: 'EDITOR_READY' },
            '*' // 生产环境替换为前端A域名，如 http://localhost:5173
          );
        }
      }
    });

    onDestroy(() => {
        // 同理：仅在客户端移除监听
        if (browser) {
            window.removeEventListener('message', handleMessageFromA);
        }
    });

</script>

<div class="upload-wrapper">
    <div
        class="upload-container {dragOver ? 'upload-container--dragover' : ''}"
        role="button"
        tabindex="0"
        on:dragover={handleDragOver}
        on:dragleave={handleDragLeave}
        on:drop={handleDrop}
        on:click={() => fileInput.click()}
        on:keydown={handleKeyDown}
        title="点击或拖拽图片到此处上传"
    >
        <input
            class="upload-file-input"
            type="file"
            accept="image/*"
            bind:this={fileInput}
            on:change={handleFileSelect}
        />

        {#if isUploading}
            <div class="upload-loading">
                <div class="loading-spinner"></div>
                <p class="upload-tip">上传中...</p>
            </div>
        {:else if receivedExternalFile}
            <!-- 新增：显示接收的外部图片提示 -->
            <div class="upload-content">
                <div class="upload-icon">✅</div>
                <p class="upload-tip">{externalFileTip}</p>
                <p class="upload-sub-tip">已自动处理图片，可重新选择/拖拽</p>
            </div>
        {:else}
            <div class="upload-content">
                <div class="upload-icon">📤</div>
                <p class="upload-tip">点击或拖拽图片到此处</p>
                <p class="upload-sub-tip">支持 JPG、PNG、GIF 等格式</p>
                <p class="upload-sub-tip">最大 10MB</p>
            </div>
        {/if}
    </div>
</div>