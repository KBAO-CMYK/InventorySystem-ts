<script lang="ts">
    import { onMount, createEventDispatcher } from 'svelte';
    const dispatch = createEventDispatcher();

    export let imageUrl: string | null;
    export let editorState: any;
    export let textElements: any[];
    export let fillRects: any[] = [];
    let isInternalUpdate = false;

    let isInternalUpdating = false; // 用于标记是否是裁剪导致的图片更新
    let imgRef: HTMLImageElement;
    let viewportContainer: HTMLDivElement;
    let rotateWrapper: HTMLDivElement;
    
    let isDragging = false;
    let dragMode: 'text' | 'crop-move' | 'crop-resize' | 'fill' | 'autofill' | 'crop-rotate' | null = null;
    let currentHandle: string | null = null;
    let selectedTextId: number | null = null;
    let selectedText: any = null;

    let fillStart = { x: 0, y: 0 };
    let currentFillRect = { x: 0, y: 0, width: 0, height: 0 };

    // 新增裁剪旋转相关状态
    let cropRotateStartAngle = 0; // 旋转开始时的角度
    let cropRotateStartMousePos = { x: 0, y: 0 }; // 旋转开始时的鼠标位置
    let cropRotateCenter = { x: 0, y: 0 }; // 裁剪框中心坐标（固定）
    let cropImageRotateDeg = 0; // 裁剪模式下的图片旋转角度（独立于全局rotateDeg）

    // 新增：用于跟踪上一次的客户端尺寸
    let previousClientWidth = 0;
    let previousClientHeight = 0;

    $: filterStyle = `brightness(${editorState.brightness || 100}%) contrast(${editorState.contrast || 100}%)`;

    $: if (!editorState.textColor) editorState.textColor = '#000000';
    $: if (!editorState.textSize) editorState.textSize = 24;

    $: if (selectedText) {
        editorState.textColor = selectedText.color;
        editorState.textSize = selectedText.size;
    }
    $: if (selectedText && editorState.textColor) {
        selectedText.color = editorState.textColor;
        textElements = textElements;
    }
    $: if (selectedText && editorState.textSize) {
        selectedText.size = editorState.textSize;
        textElements = textElements;
    }

    // 新增：裁剪框变化时更新旋转中心
    $: if (editorState.isCropping && editorState.cropArea) {
        cropRotateCenter = {
            x: editorState.cropArea.x + editorState.cropArea.width / 2,
            y: editorState.cropArea.y + editorState.cropArea.height / 2
        };
    }

    // 向外暴露保存方法（供父组件调用）
    export function saveImage() {
        const canvas = getFinalCanvas();
        if (!canvas) return;
        
        // 转换为Base64 URL
        const dataUrl = canvas.toDataURL('image/png', 1.0);
        
        // 更新显示的图片
        imageUrl = dataUrl;
        
        // 通知父组件保存完成
        dispatch('saveComplete', { dataUrl });
        
        return dataUrl;
    }

    // 向外暴露下载方法（供父组件调用）
    export function downloadImage(filename = 'edited-image.png') {
        const canvas = getFinalCanvas();
        if (!canvas) return;

        // 创建下载链接
        const link = document.createElement('a');
        link.href = canvas.toDataURL('image/png', 1.0);
        link.download = filename;
        
        // 触发下载
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // 通知父组件下载完成
        dispatch('downloadComplete', { filename });
    }

    // 获取最终渲染的画布（包含所有编辑效果）
    function getFinalCanvas() {
        if (!imgRef) return null;

        // 计算总旋转角度（全局+裁剪）
        const totalRotateDeg = editorState.rotateDeg + (editorState.isCropping ? cropImageRotateDeg : 0);
        
        // 获取原图尺寸
        const naturalW = imgRef.naturalWidth;
        const naturalH = imgRef.naturalHeight;
        
        // 计算旋转后的画布尺寸
        const isRotated90 = Math.abs(totalRotateDeg % 180) === 90;
        const canvasWidth = isRotated90 ? naturalH : naturalW;
        const canvasHeight = isRotated90 ? naturalW : naturalH;

        // 创建画布
        const canvas = document.createElement('canvas');
        canvas.width = canvasWidth;
        canvas.height = canvasHeight;
        const ctx = canvas.getContext('2d');
        if (!ctx) return null;

        // 计算缩放比例
        const scaleX = naturalW / imgRef.clientWidth;
        const scaleY = naturalH / imgRef.clientHeight;

        // 保存画布状态
        ctx.save();
        
        // 移动到画布中心
        ctx.translate(canvasWidth / 2, canvasHeight / 2);
        
        // 应用旋转
        ctx.rotate(totalRotateDeg * Math.PI / 180);
        
        // 移动回原位置
        ctx.translate(-naturalW / 2, -naturalH / 2);

        // 应用亮度/对比度滤镜
        ctx.filter = filterStyle;

        // 绘制原图
        ctx.drawImage(imgRef, 0, 0, naturalW, naturalH);

        // 绘制填充块
        fillRects.forEach(r => {
            ctx.fillStyle = r.color || 'white';
            ctx.fillRect(
                r.x * scaleX, 
                r.y * scaleY, 
                r.width * scaleX, 
                r.height * scaleY
            );
        });

        // 绘制文字
        textElements.forEach(text => {
            drawTextOnCanvas(ctx, text, scaleX, scaleY, totalRotateDeg);
        });

        ctx.restore(); 

        
        return canvas;
    }

    function handleGlobalKeyDown(e: KeyboardEvent) {
        if (e.key === 'Enter' && editorState.isCropping) {
            confirmCrop();
        }
    }

    $: if (editorState.isCropping && rotateWrapper && editorState.cropArea.width === 0) {
        editorState.cropArea = {
            x: 0,
            y: 0,
            width: rotateWrapper.clientWidth,
            height: rotateWrapper.clientHeight
        };
    }

    // 修复：正确计算旋转后的本地坐标（仅针对裁剪旋转）
    function getLocalCoords(e: MouseEvent) {
        const rect = imgRef.getBoundingClientRect();
        const original_cx = imgRef.offsetWidth / 2;
        const original_cy = imgRef.offsetHeight / 2;
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        let px = e.clientX - rect.left - cx;
        let py = e.clientY - rect.top - cy;
        
        // 计算总旋转角度，包括裁剪旋转（以确保坐标计算与视觉同步）
        const totalDeg = editorState.rotateDeg + (editorState.isCropping ? cropImageRotateDeg : 0);
        const totalRad = -totalDeg * Math.PI / 180;
        const lx = px * Math.cos(totalRad) - py * Math.sin(totalRad);
        const ly = px * Math.sin(totalRad) + py * Math.cos(totalRad);
        
        return { x: lx + original_cx, y: ly + original_cy };
    }

    function startDrag(e: MouseEvent, mode: 'text' | 'crop-move' | 'crop-resize' | 'fill' | 'autofill' | 'crop-rotate', id: number | null = null, handle: string | null = null) {
        if (mode === 'text' && id !== null) {
            const text = textElements.find(t => t.id === id);
            if (text?.isEditing) return;
        }

        isDragging = true;
        dragMode = mode;
        currentHandle = handle;
        selectedTextId = id;
        
        editorState.dragStartPos = { x: e.clientX, y: e.clientY };

        if (mode === 'fill' || mode === 'autofill') {
            fillStart = getLocalCoords(e);
            currentFillRect = { x: fillStart.x, y: fillStart.y, width: 0, height: 0 };
        } 
        // 新增裁剪旋转初始化
        else if (mode === 'crop-rotate') {
            cropRotateStartMousePos = { x: e.clientX, y: e.clientY };
            cropRotateStartAngle = cropImageRotateDeg;
            
            // 计算初始角度（鼠标相对于旋转中心的角度）
            const rect = imgRef.getBoundingClientRect();
            const centerX = rect.left + cropRotateCenter.x;
            const centerY = rect.top + cropRotateCenter.y;
            const dx = e.clientX - centerX;
            const dy = e.clientY - centerY;
            cropRotateStartAngle = Math.atan2(dy, dx) * 180 / Math.PI - cropImageRotateDeg;
        }

        e.preventDefault();
    }

    function onMouseMove(e: MouseEvent) {
        if (!isDragging) return;

        const dx = e.clientX - editorState.dragStartPos.x;
        const dy = e.clientY - editorState.dragStartPos.y;
        editorState.dragStartPos = { x: e.clientX, y: e.clientY };

        const rad = -editorState.rotateDeg * Math.PI / 180;
        const local_dx = dx * Math.cos(rad) - dy * Math.sin(rad);
        const local_dy = dx * Math.sin(rad) + dy * Math.cos(rad);

        // 新增：裁剪旋转处理
        if (dragMode === 'crop-rotate') {
            const rect = imgRef.getBoundingClientRect();
            const centerX = rect.left + cropRotateCenter.x;
            const centerY = rect.top + cropRotateCenter.y;
            
            // 计算鼠标相对于旋转中心的角度
            const dx = e.clientX - centerX;
            const dy = e.clientY - centerY;
            const currentAngle = Math.atan2(dy, dx) * 180 / Math.PI;
            
            // 更新裁剪旋转角度（平滑跟随鼠标）
            cropImageRotateDeg = currentAngle - cropRotateStartAngle;
            return;
        }

        if (dragMode === 'fill' || dragMode === 'autofill') {
            const current = getLocalCoords(e);
            currentFillRect = {
                x: Math.min(fillStart.x, current.x),
                y: Math.min(fillStart.y, current.y),
                width: Math.abs(current.x - fillStart.x),
                height: Math.abs(current.y - fillStart.y)
            };
        } else if (dragMode === 'crop-move') {
            editorState.cropArea.x += local_dx;
            editorState.cropArea.y += local_dy;
            // 同步更新旋转中心
            cropRotateCenter = {
                x: editorState.cropArea.x + editorState.cropArea.width / 2,
                y: editorState.cropArea.y + editorState.cropArea.height / 2
            };
        } else if (dragMode === 'crop-resize' && currentHandle) {
            const area = editorState.cropArea;
            if (currentHandle === 'left') {
                area.x += local_dx;
                area.width -= local_dx;
            } else if (currentHandle === 'right') {
                area.width += local_dx;
            } else if (currentHandle === 'top') {
                area.y += local_dy;
                area.height -= local_dy;
            } else if (currentHandle === 'bottom') {
                area.height += local_dy;
            } else if (currentHandle === 'lt') {
                area.x += local_dx;
                area.width -= local_dx;
                area.y += local_dy;
                area.height -= local_dy;
            } else if (currentHandle === 'rt') {
                area.width += local_dx;
                area.y += local_dy;
                area.height -= local_dy;
            } else if (currentHandle === 'lb') {
                area.x += local_dx;
                area.width -= local_dx;
                area.height += local_dy;
            } else if (currentHandle === 'rb') {
                area.width += local_dx;
                area.height += local_dy;
            }

            area.width = Math.max(20, area.width);
            area.height = Math.max(20, area.height);

            editorState.cropArea = { ...area };
            // 同步更新旋转中心
            cropRotateCenter = {
                x: area.x + area.width / 2,
                y: area.y + area.height / 2
            };
        } else if (dragMode === 'text' && selectedTextId !== null) {
            textElements = textElements.map(t =>
                t.id === selectedTextId
                    ? { ...t, position: { x: t.position.x + local_dx, y: t.position.y + local_dy } }
                    : t
            );
        }
    }

    // 修复：绘制文字时正确处理裁剪旋转角度
    function drawTextOnCanvas(ctx: CanvasRenderingContext2D, text: any, scaleX: number, scaleY: number, totalRotateDeg: number) {
    const lines = text.content.split('\n');
    const fontSize = text.size * scaleX;
    const lineHeight = fontSize * 1.2;
    
    // 关键修改：使用左对齐的坐标，加上文字宽度的偏移
    const canvasX = text.position.x * scaleX;
    const canvasY = text.position.y * scaleY;
    
    ctx.save();
    
    // 移动到文字位置（左上角）
    ctx.translate(canvasX, canvasY);
    
    // 应用旋转（反向抵消图片旋转）
    ctx.rotate(-totalRotateDeg * Math.PI / 180);
    
    ctx.fillStyle = text.color;
    ctx.font = `${fontSize}px Arial`;
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';  // 关键修改：改为左对齐
    
    // 计算多行文字的垂直分布
    const totalHeight = lines.length * lineHeight;
    const startY = -totalHeight / 2 + lineHeight / 2;
    
    lines.forEach((line: string, i: number) => {
        ctx.fillText(
            line,
            0,  // X坐标为0，因为textAlign是left
            startY + i * lineHeight
        );
    });
    
    ctx.restore();
}

    // 兼容旧的getBakedCanvas方法（避免影响其他功能）
    function getBakedCanvas() {
        return getFinalCanvas();
    }

    function applyRotation() {
        const canvas = getFinalCanvas();
        if (!canvas) return;

        imageUrl = canvas.toDataURL('image/png');
        fillRects = [];

        const oldW = imgRef?.clientWidth || 0;
        const oldH = imgRef?.clientHeight || 0;
        textElements = textElements.map(t => {
            const relX = t.position.x - oldW / 2;
            const relY = t.position.y - oldH / 2;
            const rad = editorState.rotateDeg * Math.PI / 180;
            const newRelX = relX * Math.cos(rad) - relY * Math.sin(rad);
            const newRelY = relX * Math.sin(rad) + relY * Math.cos(rad);
            const newW = editorState.rotateDeg % 180 !== 0 ? oldH : oldW;
            const newH = editorState.rotateDeg % 180 !== 0 ? oldW : oldH;
            return { ...t, position: { x: newRelX + newW / 2, y: newRelY + newH / 2 } };
        });

        editorState.brightness = 100;
        editorState.contrast = 100;
        editorState.rotateDeg = 0;
        // 重置裁剪旋转角度
        cropImageRotateDeg = 0;
    }

    function onMouseUp() {
        if (isDragging && (dragMode === 'fill' || dragMode === 'autofill')) {
            if (currentFillRect.width > 2 && currentFillRect.height > 2) {
                if (dragMode === 'fill') {
                    dispatch('fillComplete', { ...currentFillRect, color: 'white' });
                } else if (dragMode === 'autofill') {
                    const canvas = getFinalCanvas();
                    if (!canvas) return;
                    const ctx = canvas.getContext('2d')!;
                    const scaleX = canvas.width / imgRef.clientWidth;
                    const scaleY = canvas.height / imgRef.clientHeight;

                    const border = 6;
                    const rx = Math.round(currentFillRect.x * scaleX);
                    const ry = Math.round(currentFillRect.y * scaleY);
                    const rw = Math.round(currentFillRect.width * scaleX);
                    const rh = Math.round(currentFillRect.height * scaleY);

                    let sumR = 0, sumG = 0, sumB = 0, count = 0;

                    function sample(x: number, y: number, w: number, h: number) {
                        if (!canvas) return;
                        x = Math.max(0, x); y = Math.max(0, y);
                        w = Math.min(canvas.width - x, w);
                        h = Math.min(canvas.height - y, h);
                        if (w <= 0 || h <= 0) return;
                        const data = ctx.getImageData(x, y, w, h).data;
                        for (let i = 0; i < data.length; i += 4) {
                            sumR += data[i]; sumG += data[i + 1]; sumB += data[i + 2]; count++;
                        }
                    }

                    sample(rx - border, ry, border, rh);
                    sample(rx + rw, ry, border, rh);
                    sample(rx, ry - border, rw, border);
                    sample(rx, ry + rh, rw, border);

                    if (count > 0) {
                        const avgR = Math.round(sumR / count);
                        const avgG = Math.round(sumG / count);
                        const avgB = Math.round(sumB / count);
                        dispatch('fillComplete', { ...currentFillRect, color: `rgb(${avgR},${avgG},${avgB})` });
                    }
                }
            }
            currentFillRect = { x: 0, y: 0, width: 0, height: 0 };
        }
        isDragging = false;
        dragMode = null;
        currentHandle = null;
    }

    // 核心修复：裁剪时正确处理旋转后的坐标映射
    function confirmCrop() {
        if (!imgRef || !editorState.cropArea.width) return;

        // 1. 获取缩放比例 (原始像素 / 显示像素)
        const scaleX = imgRef.naturalWidth / imgRef.clientWidth;
        const scaleY = imgRef.naturalHeight / imgRef.clientHeight;

        // 2. 计算裁剪框在原图上的真实坐标（未旋转）
        const cropX = editorState.cropArea.x * scaleX;
        const cropY = editorState.cropArea.y * scaleY;
        const cropW = editorState.cropArea.width * scaleX;
        const cropH = editorState.cropArea.height * scaleY;

        // 3. 创建临时画布，先旋转原图再裁剪
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d')!;
        
        // 临时画布尺寸与原图一致
        tempCanvas.width = imgRef.naturalWidth;
        tempCanvas.height = imgRef.naturalHeight;
        
        // 旋转原图到裁剪角度
        tempCtx.translate(tempCanvas.width / 2, tempCanvas.height / 2);
        tempCtx.rotate(cropImageRotateDeg * Math.PI / 180);
        tempCtx.translate(-tempCanvas.width / 2, -tempCanvas.height / 2);
        
        // 绘制旋转后的原图
        tempCtx.drawImage(imgRef, 0, 0, tempCanvas.width, tempCanvas.height);

        // 4. 创建最终裁剪画布
        const finalCanvas = document.createElement('canvas');
        finalCanvas.width = cropW;
        finalCanvas.height = cropH;
        const finalCtx = finalCanvas.getContext('2d')!;

        // 5. 从旋转后的临时画布中裁剪目标区域
        finalCtx.drawImage(
            tempCanvas,
            cropX, cropY, cropW, cropH,  // 裁剪区域（旋转后的坐标）
            0, 0, cropW, cropH           // 绘制到最终画布
        );

        // 6. 更新文字位置（仅保留裁剪区域内的文字）
        const filteredTexts = textElements
            .filter(t => 
                t.position.x >= editorState.cropArea.x && 
                t.position.x <= editorState.cropArea.x + editorState.cropArea.width &&
                t.position.y >= editorState.cropArea.y && 
                t.position.y <= editorState.cropArea.y + editorState.cropArea.height
            )
            .map(t => ({
                ...t,
                position: { 
                    x: t.position.x - editorState.cropArea.x, 
                    y: t.position.y - editorState.cropArea.y 
                }
            }));

        // 7. 更新图片和状态
        isInternalUpdating = true;
        imageUrl = finalCanvas.toDataURL('image/png');
        textElements = filteredTexts;
        
        // 重置所有旋转状态
        editorState.isCropping = false;
        editorState.cropArea = { x: 0, y: 0, width: 0, height: 0 };
        cropImageRotateDeg = 0;
        fillRects = [];
    }

    function handleImageClick(e: MouseEvent) {
    if (editorState.isAddingText) {
        const coords = getLocalCoords(e);
        const newText = {
            id: Date.now(),
            content: '',
            // 关键修改：存储文字中心点坐标，而不是左上角
            position: coords,
            color: editorState.textColor,
            size: editorState.textSize,
            isEditing: true,
            anchor: 'center',  // 改为基于中心点
            spanEl: null as HTMLSpanElement | null,
            // 新增：计算文字宽度需要的上下文（用于准确定位）
            ctxInfo: {
                font: `${editorState.textSize}px Arial`,
                textAlign: 'center' as CanvasTextAlign
            }
        };
        textElements = [...textElements, newText];
        editorState.isAddingText = false;
    }
}

    function handleSingleClick(text: any, e: MouseEvent) {
        e.stopPropagation();
        selectedText = text;
        selectedTextId = text.id;
    }

    function handleDoubleClick(text: any) {
    text.isEditing = true;
    selectedText = text;
    setTimeout(() => {
        if (text.spanEl) {
            text.spanEl.focus();
            // 选中全部内容
            const range = document.createRange();
            range.selectNodeContents(text.spanEl);
            const sel = window.getSelection();
            sel?.removeAllRanges();
            sel?.addRange(range);
        }
    }, 0);
}

    function handleTextBlur(text:any) {
    text.isEditing = false;
   
    // 使用 textContent 避免 HTML 实体转义（如 &nbsp;、&amp;）
    text.content = text.spanEl?.textContent?.trim() || '';
    if (!text.content) {
        textElements = textElements.filter(t => t.id !== text.id);
    }
    selectedText = null;
    textElements = textElements; // 触发响应式更新
}

    let naturalWidth = 0;
    let naturalHeight = 0;
    let currentDisplayWidth = 0;
    let currentDisplayHeight = 0;

    function updateOnImageLoad() {
        if (!imgRef) return;
        naturalWidth = imgRef.naturalWidth;
        naturalHeight = imgRef.naturalHeight;
        currentDisplayWidth = imgRef.clientWidth;
        currentDisplayHeight = imgRef.clientHeight;

        if (editorState.lastNaturalWidth !== naturalWidth) {
            const ratioX = currentDisplayWidth / naturalWidth;
            const ratioY = currentDisplayHeight / naturalHeight;
            textElements = textElements.map(t => ({
                ...t,
                position: { x: t.position.x / ratioX, y: t.position.y / ratioY },
                size: t.size / ratioY
            }));
            fillRects = fillRects.map(r => ({
                ...r,
                x: r.x / ratioX,
                y: r.y / ratioY,
                width: r.width / ratioX,
                height: r.height / ratioY
            }));
            editorState.lastNaturalWidth = naturalWidth;
        }
    }

    function updateOnResize() {
        if (!imgRef || naturalWidth === 0) return;
        const newDisplayW = imgRef.clientWidth;
        const newDisplayH = imgRef.clientHeight;

        const ratioX = newDisplayW / naturalWidth;
        const ratioY = newDisplayH / naturalHeight;

        textElements = textElements.map(t => ({
            ...t,
            position: { x: t.position.x * ratioX, y: t.position.y * ratioY },
            size: t.size * ratioY
        }));

        fillRects = fillRects.map(r => ({
            ...r,
            x: r.x * ratioX,
            y: r.y * ratioY,
            width: r.width * ratioX,
            height: r.height * ratioY
        }));
    }

    onMount(() => {
        // 初始化上一次尺寸（在图片加载后）
        if (imgRef) {
            previousClientWidth = imgRef.clientWidth;
            previousClientHeight = imgRef.clientHeight;
        }

        const resizeObserver = new ResizeObserver(() => {
            if (!imgRef || !rotateWrapper) return;

            const newWidth = imgRef.clientWidth;
            const newHeight = imgRef.clientHeight;

            // 如果是首次或无变化，跳过
            if (previousClientWidth === 0 || (newWidth === previousClientWidth && newHeight === previousClientHeight)) {
                previousClientWidth = newWidth;
                previousClientHeight = newHeight;
                return;
            }

            // 计算缩放比例
            const scaleX = newWidth / previousClientWidth;
            const scaleY = newHeight / previousClientHeight;

            // 更新文字图层
            textElements = textElements.map(text => ({
                ...text,
                position: {
                    x: text.position.x * scaleX,
                    y: text.position.y * scaleY
                },
                size: text.size * scaleX  // 缩放字号以保持相对大小（使用 scaleX 假设横向为主）
            }));

            // 更新填充图层
            fillRects = fillRects.map(r => ({
                ...r,
                x: r.x * scaleX,
                y: r.y * scaleY,
                width: r.width * scaleX,
                height: r.height * scaleY
            }));

            // 更新裁剪区域（如果存在）
            if (editorState.cropArea) {
                editorState.cropArea = {
                    x: editorState.cropArea.x * scaleX,
                    y: editorState.cropArea.y * scaleY,
                    width: editorState.cropArea.width * scaleX,
                    height: editorState.cropArea.height * scaleY
                };
            }

            // 更新上一次尺寸
            previousClientWidth = newWidth;
            previousClientHeight = newHeight;
        });

        // 观察 rotateWrapper 的尺寸变化（覆盖 resize 和旋转）
        resizeObserver.observe(rotateWrapper);

        return () => {
            resizeObserver.disconnect();
        };
    });

    function handleImageLoad(event: Event & { currentTarget: EventTarget & Element; }) {
        updateOnImageLoad();
    }


  // 新增函数：处理文字输入时的宽度更新
function updateTextWidth(text: any) {
    // 触发响应式更新
    textElements = textElements;
}

// 新增函数：获取文字的精确宽度（用于定位修正）
function getTextBoundingBox(text: any) {
    if (!text.spanEl) return { width: 0, height: 0 };
    
    // 临时创建一个span来测量文字宽度
    const tempSpan = document.createElement('span');
    tempSpan.style.font = `${text.size}px Arial`;
    tempSpan.style.position = 'absolute';
    tempSpan.style.visibility = 'hidden';
    tempSpan.style.whiteSpace = 'pre';
    tempSpan.textContent = text.content || '';
    
    document.body.appendChild(tempSpan);
    const width = tempSpan.offsetWidth;
    const height = tempSpan.offsetHeight;
    document.body.removeChild(tempSpan);
    
    return { width, height };
}
  
</script>

<svelte:window on:mousemove={onMouseMove} on:mouseup={onMouseUp} on:keydown={handleGlobalKeyDown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="editor-main" on:click={handleImageClick}>
    {#if imageUrl}
        <div class="viewport-container" bind:this={viewportContainer} style="position: relative;">
            <div class="rotate-wrapper" bind:this={rotateWrapper} style="transform: rotate({editorState.rotateDeg}deg); transition: transform 0.3s;">
                <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                <!-- svelte-ignore a11y_missing_attribute -->
                <img
                    bind:this={imgRef}
                    src={imageUrl}
                    class="edit-image"
                    draggable="false"
                    style="filter: {filterStyle}; 
                           transform: {editorState.isCropping ? `rotate(${cropImageRotateDeg}deg)` : 'none'}; 
                           transform-origin: {cropRotateCenter.x}px {cropRotateCenter.y}px;
                           transition: transform 0.05s ease;"
                    on:mousedown={(e) => {
                        if (editorState.isFillMode) startDrag(e, 'fill');
                        else if (editorState.isAutoFillMode) startDrag(e, 'autofill');
                    }}
                    on:load={handleImageLoad}
                />

                {#each fillRects as rect}
                    <div class="fill-block" style="left:{rect.x}px; top:{rect.y}px; width:{rect.width}px; height:{rect.height}px; background:{rect.color || 'white'};"></div>
                {/each}

                {#if isDragging && (dragMode === 'fill' || dragMode === 'autofill')}
                    <div class="fill-preview" 
                         style="left:{currentFillRect.x}px; top:{currentFillRect.y}px; width:{currentFillRect.width}px; height:{currentFillRect.height}px;
                                background:{dragMode === 'autofill' ? 'rgba(0,123,255,0.3)' : 'rgba(255,255,255,0.5)'};
                                border:1px dashed #007bff;">
                    </div>
                {/if}

                {#each textElements as text (text.id)}
    <div
        class="text-node"
        class:editing={text.isEditing}
        class:selected={selectedText?.id === text.id && !text.isEditing}
        style="left:{text.position.x}px; top:{text.position.y}px; color:{text.color}; font-size:{text.size}px; 
       transform: translateY(-50%) rotate({-editorState.rotateDeg}deg);" 
        on:mousedown|preventDefault={(e) => startDrag(e, 'text', text.id)}
        on:click={(e) => handleSingleClick(text, e)}
        on:dblclick|stopPropagation|preventDefault={() => handleDoubleClick(text)}
    >
        {#if text.isEditing}
            <span 
                contenteditable="true" 
                class="editable-area editing-active"  
                bind:this={text.spanEl} 
                bind:textContent={text.content} 
                on:blur={() => handleTextBlur(text)} 
                on:mousedown|stopPropagation
                on:input={() => updateTextWidth(text)} 
            ></span>
        {:else}
            <span 
                class="editable-area" 
                bind:this={text.spanEl}
            >{@html text.content.replace(/\n/g, '<br/>')}</span>
        {/if}
    </div>
{/each}

                {#if editorState.isCropping}
                    <div class="crop-mask" style="left:{editorState.cropArea.x}px; top:{editorState.cropArea.y}px; width:{editorState.cropArea.width}px; height:{editorState.cropArea.height}px;" on:mousedown={(e) => startDrag(e, 'crop-move')}>
                        <!-- 新增裁剪旋转按钮 -->
                        <div class="crop-rotate-handle" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-rotate')}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
                            </svg>
                        </div>
                        
                        <div class="crop-handle crop-handle--left" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'left')}></div>
                        <div class="crop-handle crop-handle--right" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'right')}></div>
                        <div class="crop-handle crop-handle--top" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'top')}></div>
                        <div class="crop-handle crop-handle--bottom" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'bottom')}></div>
                        <div class="crop-handle crop-corner--lt" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'lt')}></div>
                        <div class="crop-handle crop-corner--rt" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'rt')}></div>
                        <div class="crop-handle crop-corner--lb" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'lb')}></div>
                        <div class="crop-handle crop-corner--rb" on:mousedown|stopPropagation={(e) => startDrag(e, 'crop-resize', null, 'rb')}></div>
                    </div>
                {/if}
            </div>
        </div>
    {/if}
</div>

<style>
    .editor-main { display: flex; justify-content: center; align-items: center; width: 100%; height: 100%; cursor: default; }
    .rotate-wrapper { position: relative; line-height: 0; }
    .edit-image { max-width: 80vw; max-height: 75vh; pointer-events: auto; user-select: none; }

    .fill-block { position: absolute; pointer-events: none; z-index: 160; }
    .fill-preview { position: absolute; pointer-events: none; z-index: 11; }

    .crop-mask { position: absolute; border: 1px solid #fff; outline: 5000px solid rgba(0,0,0,0.5); cursor: move; z-index: 100; }
    .crop-handle { position: absolute; width: 8px; height: 8px; background: #fff; border: 1px solid #007bff; border-radius: 50%; }
    .crop-corner--lt { top: -4px; left: -4px; cursor: nw-resize; }
    .crop-corner--rt { top: -4px; right: -4px; cursor: ne-resize; }
    .crop-corner--lb { bottom: -4px; left: -4px; cursor: sw-resize; }
    .crop-corner--rb { bottom: -4px; right: -4px; cursor: se-resize; }
    .crop-handle--left { left: -4px; top: 50%; transform: translateY(-50%); cursor: ew-resize; }
    .crop-handle--right { right: -4px; top: 50%; transform: translateY(-50%); cursor: ew-resize; }
    .crop-handle--top { top: -4px; left: 50%; transform: translateX(-50%); cursor: ns-resize; }
    .crop-handle--bottom { bottom: -4px; left: 50%; transform: translateX(-50%); cursor: ns-resize; }

       .text-node { 
    position: absolute; 
    white-space: nowrap;  /* 改为nowrap确保单行不换行 */
    z-index: 150; 
    user-select: none; 
    pointer-events: auto; 
    cursor: move; 
    line-height: 1.2; 
    padding: 2px 4px;  /* 减少padding */
    border-radius: 2px;
    transform-origin: left center;  /* 关键：以左侧为中心点旋转 */
    min-height: 1.2em;
}

.text-node.editing { 
    cursor: text; 
    background: rgba(0, 123, 255, 0.08);  /* 编辑时的背景色 */
    border: 1px dashed rgba(0, 123, 255, 0.5);
}

.text-node.selected:not(.editing) { 
    box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.4);
    background: rgba(0, 123, 255, 0.05);
}

.editable-area { 
    outline: none; 
    min-width: 4px;  /* 最小宽度减小 */
    display: inline-block; 
    pointer-events: none; 
    caret-color: currentColor; 
    background: transparent;
    text-align: left;  /* 左对齐 */
    vertical-align: middle;
    white-space: pre;  /* 保持空格和换行 */
}

.text-node.editing .editable-area { 
    pointer-events: auto; 
    background: rgba(0, 123, 255, 0.05);
    padding: 1px 3px;
    border-radius: 2px;
}

.editable-area::selection { 
    background: rgba(0, 123, 255, 0.3); 
}

/* 新增：编辑状态的专用样式 */
.editing-active {
    min-width: 40px;  /* 编辑时有最小宽度 */
    border-right: 2px solid rgba(0, 123, 255, 0.5);  /* 光标位置指示 */
    animation: cursor-blink 1s step-end infinite;
}

@keyframes cursor-blink {
    0%, 50% { border-right-color: rgba(0, 123, 255, 0.5); }
    51%, 100% { border-right-color: transparent; }
}

    /* 新增裁剪旋转按钮样式 */
    .crop-rotate-handle {
        position: absolute;
        top: -25px;
        left: -25px;
        width: 24px;
        height: 24px;
        background: #007bff;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        z-index: 101;
    }
    .crop-rotate-handle:active {
        cursor: grabbing;
    }
    .crop-rotate-handle svg {
        width: 14px;
        height: 14px;
        fill: white;
    }
</style>