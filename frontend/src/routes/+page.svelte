<script lang="ts">
    import Toolbar from '$lib/Toolbar/Toolbar.svelte';
    import Editor from '$lib/Editor/Editor.svelte';
    import ImageAdjuster from '$lib/Editor/ImageAdjuster.svelte';
    import SaveDownload from '$lib/SaveDownload/SaveDownload.svelte';
    import Upload from '$lib/Upload/Upload.svelte';

    let imageUrl: string | null = null;
    let textElements: any[] = [];
    let fillRects: any[] = [];
    let isSaving = false;

    let editorState = {
        textColor: '#000000',
        textSize: 28,
        isCropping: false,
        cropArea: { x: 0, y: 0, width: 0, height: 0 },
        rotateDeg: 0,
        dragStartPos: { x: 0, y: 0 },
        isAddingText: false,
        croppedImageUrl: null,
        brightness: 100,
        contrast: 100,
        isFillMode: false,
        isAutoFillMode: false
    };
    async function getEditedImageBlob(): Promise<Blob | null> {
        const canvas = await getMergedCanvas();
        if (!canvas) return null;
        return new Promise((resolve) => {
            canvas.toBlob((blob) => resolve(blob), 'image/png');
        });
    }

    async function getMergedCanvas() {
    const img = document.querySelector('.edit-image') as HTMLImageElement;
    if (!img) return null;

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    const width = img.naturalWidth;
    const height = img.naturalHeight;
    
    if (editorState.rotateDeg % 180 !== 0) {
        canvas.width = height;
        canvas.height = width;
    } else {
        canvas.width = width;
        canvas.height = height;
    }

    // 关键：先填充整个画布为白色（确保裁剪/旋转后空白处为白色）
    ctx.fillStyle = 'white';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.rotate((editorState.rotateDeg * Math.PI) / 180);

    ctx.filter = `brightness(${editorState.brightness}%) contrast(${editorState.contrast}%)`;
    ctx.drawImage(img, -width / 2, -height / 2);
    ctx.filter = 'none';

    const scaleX = width / img.clientWidth;
    const scaleY = height / img.clientHeight;

    // 先绘制文字
    ctx.textBaseline = 'middle';  // 与编辑界面的 translate(0, -50%) 匹配，确保垂直居中
textElements.forEach(text => {
    ctx.save();
    const canvasX = -width / 2 + text.position.x * scaleX;
    const canvasY = -height / 2 + text.position.y * scaleY;
    ctx.translate(canvasX, canvasY);
    ctx.rotate(-(editorState.rotateDeg * Math.PI / 180));
    ctx.fillStyle = text.color;
    ctx.font = `${text.size * scaleX}px Arial`;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';  // 关键修改：左对齐
    
    const lines = text.content.replace(/<[^>]*>/g, '').split('\n');
    const fontSize = text.size * scaleX;
    const lineHeight = fontSize * 1.2;
    const totalHeight = lines.length * lineHeight;
    const startY = -totalHeight / 2 + lineHeight / 2;
    
    lines.forEach((line: string, i: number) => {
        ctx.fillText(line, 0, startY + i * lineHeight);
    });
    
    ctx.restore();
});

    // 后绘制填充（覆盖文字）
    fillRects.forEach(rect => {
        ctx.fillStyle = rect.color || 'white';
        ctx.fillRect(-width / 2 + rect.x * scaleX, -height / 2 + rect.y * scaleY, rect.width * scaleX, rect.height * scaleY);
    });

    ctx.restore();

    return canvas;
}

    async function handleDownload() {
        const canvas = await getMergedCanvas();
        if (canvas) {
            const link = document.createElement('a');
            link.download = 'edited_image.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        }
    }

    // ========== 替换原有保存逻辑：传给前端A ==========
    async function handleSendToFrontA() {
        if (isSaving) return;
        isSaving = true;

        try {
            // 1. 获取编辑后的图片Blob
            const editedBlob = await getEditedImageBlob();
            if (!editedBlob) {
                alert('未检测到编辑后的图片！');
                isSaving = false;
                return;
            }

            // 2. 检测前端A窗口（window.open打开的父窗口）
            if (!window.opener) {
                alert('未检测到商品编辑页面，请从商品编辑页打开图片编辑器！');
                isSaving = false;
                return;
            }

            // 3. 方式1：传Blob 需前端A配合监听
            window.opener.postMessage(
                {
                    type: 'EDITED_IMAGE',
                    data: editedBlob,
                    fileName: `edited_${Date.now()}.png`
                },
                '*' // 生产环境建议指定前端A的域名，如 'http://localhost:5173'
            );

            alert('编辑后的图片已传回商品编辑页！');
            setTimeout(() => {
            // 兼容window.open打开的窗口关闭（当前窗口是通过前端A open的，close有效）
            window.close();
            }, 500);

        } catch (err) {
            alert('图片回传失败：' + (err as Error).message);
        } finally {
            isSaving = false;
        }
    }

    function handleImageUpload(file: File) {
        const reader = new FileReader();
        reader.onload = (event) => {
            imageUrl = event.target?.result as string;
            textElements = [];
            fillRects = [];
            editorState.rotateDeg = 0;
            editorState.croppedImageUrl = null;
            editorState.brightness = 100;
            editorState.contrast = 100;
        };
        reader.readAsDataURL(file);
    }
</script>

<div class="main-layout">
    <div class="top-right-actions">
        <SaveDownload 
            disabled={!imageUrl || isSaving} 
            on:save={handleSendToFrontA}
            on:download={handleDownload} 
        />
    </div>

    <aside class="sidebar">
        <div class="sidebar-scroll">
            <Toolbar bind:editorState on:imageUpload={(e) => handleImageUpload(e.detail)} />
            <div class="adjuster-section">
                <ImageAdjuster bind:editorState />
            </div>
        </div>
    </aside>
    
    <main class="editor-container">
        {#if imageUrl}
            <Editor 
                {imageUrl} 
                bind:editorState 
                bind:textElements 
                bind:fillRects
                on:fillComplete={(e) => fillRects = [...fillRects, e.detail]}
            />
        {:else}
            <div class="empty-state">
                <Upload on:upload={(e) => handleImageUpload(e.detail)} />
                <div class="empty-info">
                    <h3>开始编辑图片</h3>
                    <p>支持拖拽上传、亮度/对比度调节、文字添加、裁剪、旋转、框选填充等功能</p>
                </div>
            </div>
        {/if}
    </main>
</div>

<style>
    .main-layout { 
        display: flex; 
        width: 100vw; 
        height: 100vh; 
        background: #f5f5f7; 
        position: relative; 
    }
    
    .top-right-actions {
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 1000;
        background: white;
        padding: 10px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }

    .sidebar { 
        width: 280px; 
        border-right: 1px solid #ddd; 
        background: #fff; 
        display: flex; 
        flex-direction: column; 
    }
    .sidebar-scroll { 
        flex: 1; 
        overflow-y: auto; 
    }
    .adjuster-section { 
        padding: 20px; 
        border-top: 1px solid #eee; 
    }
    .editor-container { 
        flex: 1; 
        display: flex; 
        align-items: center; 
        justify-content: center; 
        overflow: auto; 
        padding: 40px; 
    }
    
    .empty-state { 
        text-align: center; 
        background: white; 
        padding: 60px; 
        border-radius: 12px; 
        box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    }
    .empty-info h3 { 
        margin: 20px 0 10px; 
    }
</style>