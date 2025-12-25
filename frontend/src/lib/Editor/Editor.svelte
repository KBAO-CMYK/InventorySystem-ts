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
    let dragMode: 'text' | 'crop-move' | 'crop-resize' | 'fill' | 'autofill' | null = null;
    let currentHandle: string | null = null;
    let selectedTextId: number | null = null;
    let selectedText: any = null;

    let fillStart = { x: 0, y: 0 };
    let currentFillRect = { x: 0, y: 0, width: 0, height: 0 };

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

    function getLocalCoords(e: MouseEvent) {
        const rect = imgRef.getBoundingClientRect();
        const cx = rect.width / 2;
        const cy = rect.height / 2;
        let px = e.clientX - rect.left - cx;
        let py = e.clientY - rect.top - cy;
        const rad = -editorState.rotateDeg * Math.PI / 180;
        const lx = px * Math.cos(rad) - py * Math.sin(rad);
        const ly = px * Math.sin(rad) + py * Math.cos(rad);
        return { x: lx + cx, y: ly + cy };
    }

    function startDrag(e: MouseEvent, mode: 'text' | 'crop-move' | 'crop-resize' | 'fill' | 'autofill', id: number | null = null, handle: string | null = null) {
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
        } else if (dragMode === 'text' && selectedTextId !== null) {
            textElements = textElements.map(t =>
                t.id === selectedTextId
                    ? { ...t, position: { x: t.position.x + local_dx, y: t.position.y + local_dy } }
                    : t
            );
        }
    }

    function drawTextOnCanvas(ctx: CanvasRenderingContext2D, text: any, scaleX: number, scaleY: number, offsetX: number, offsetY: number) {
        const lines = text.content.split('<br>');
        // 文字大小按比例缩放
        const fontSize = text.size * scaleX;  // 使用 scaleX 作为统一比例基准
        ctx.fillStyle = text.color;
        ctx.font = `${fontSize}px Arial`;
        ctx.textBaseline = 'top';

        lines.forEach((line: string, i: number) => {
            const plainLine = line.replace(/<[^>]+>/g, '');
            ctx.fillText(
                plainLine,
                offsetX + text.position.x * scaleX,
                offsetY + text.position.y * scaleX + i * fontSize * 1.2  // 行距也按比例
            );
        });
    }

    function getBakedCanvas() {
        if (!imgRef) return null;

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d')!;
        const naturalW = imgRef.naturalWidth;
        const naturalH = imgRef.naturalHeight;
        const displayW = imgRef.clientWidth;
        const displayH = imgRef.clientHeight;

        const isSwapped = editorState.rotateDeg % 180 !== 0;
        canvas.width = isSwapped ? naturalH : naturalW;
        canvas.height = isSwapped ? naturalW : naturalH;

        const ratioX = naturalW / displayW;
        const ratioY = naturalH / displayH;

        // 旋转画布
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.rotate(editorState.rotateDeg * Math.PI / 180);
        ctx.translate(-naturalW / 2, -naturalH / 2);

        // 应用亮度对比度
        ctx.filter = filterStyle;

        // 绘制原图
        ctx.drawImage(imgRef, 0, 0, naturalW, naturalH);

        // 绘制填充块（白色或自动填充）
        fillRects.forEach(r => {
            ctx.fillStyle = r.color || 'white';
            ctx.fillRect(r.x * ratioX, r.y * ratioY, r.width * ratioX, r.height * ratioY);
        });

        // 绘制文字（修复后）
        textElements.forEach(text => {
            drawTextOnCanvas(ctx, text, ratioX, ratioY, 0, 0);
        });

        return canvas;
    }

    function applyRotation() {
        const baked = getBakedCanvas();
        if (!baked) return;

        imageUrl = baked.toDataURL('image/png');
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
    }

    function onMouseUp() {
        if (isDragging && (dragMode === 'fill' || dragMode === 'autofill')) {
            if (currentFillRect.width > 2 && currentFillRect.height > 2) {
                if (dragMode === 'fill') {
                    dispatch('fillComplete', { ...currentFillRect, color: 'white' });
                } else if (dragMode === 'autofill') {
                    const canvas = getBakedCanvas();
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

    function confirmCrop() {
        if (!imgRef || !editorState.cropArea.width) return;

        // 1. 获取缩放比例 (原始像素 / 显示像素)
        const scaleX = imgRef.naturalWidth / imgRef.clientWidth;
        const scaleY = imgRef.naturalHeight / imgRef.clientHeight;

        // 2. 将裁剪框坐标转换为图片的真实像素坐标
        const realCropX = editorState.cropArea.x * scaleX;
        const realCropY = editorState.cropArea.y * scaleY;
        const realCropW = editorState.cropArea.width * scaleX;
        const realCropH = editorState.cropArea.height * scaleY;

        const canvas = document.createElement('canvas');
        canvas.width = realCropW;
        canvas.height = realCropH;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // 3. 绘制裁剪区域
        ctx.drawImage(imgRef, realCropX, realCropY, realCropW, realCropH, 0, 0, realCropW, realCropH);

        // 4. 更新文字位置：仅做减法偏移，不改大小（因为文字大小本身就是基于像素的）
        textElements = textElements
            .filter(t => 
                t.position.x >= realCropX && t.position.x <= realCropX + realCropW &&
                t.position.y >= realCropY && t.position.y <= realCropY + realCropH
            )
            .map(t => ({
                ...t,
                position: { 
                    x: t.position.x - realCropX, 
                    y: t.position.y - realCropY 
                }
            }));

        // 5. 关键：先设置标志位，再更新图片地址触发 load 事件
        isInternalUpdating = true; 
        imageUrl = canvas.toDataURL('image/png');
        
        // 6. 重置状态
        editorState.isCropping = false;
        editorState.cropArea = { x: 0, y: 0, width: 0, height: 0 };
        fillRects = []; 
    }

    function handleImageClick(e: MouseEvent) {
        if (editorState.isAddingText) {
            const coords = getLocalCoords(e);
            const newText = {
                id: Date.now(),
                content: '',
                position: coords,
                color: editorState.textColor,
                size: editorState.textSize,
                isEditing: true,
                anchor: 'left',
                spanEl: null as HTMLSpanElement | null
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
        text.anchor = 'left';
        if (text.spanEl) {
            const width = text.spanEl.getBoundingClientRect().width / 2;
            text.position.x -= width;
        }
        textElements = textElements;
        selectedText = null;
        setTimeout(() => {
            if (text.spanEl) {
                text.spanEl.focus();
                const sel = window.getSelection();
                if (sel) {
                    const range = document.createRange();
                    if (text.content.trim() === '') {
                        range.setStart(text.spanEl, 0);
                        range.collapse(true);
                    } else {
                        range.selectNodeContents(text.spanEl);
                    }
                    sel.removeAllRanges();
                    sel.addRange(range);
                }
            }
        }, 0);
    }

    function handleTextBlur(text: any) {
        text.isEditing = false;
        text.anchor = 'center';
        if (text.spanEl) {
            const width = text.spanEl.getBoundingClientRect().width / 2;
            text.position.x += width;
        }
        if (text.content.trim() === '') {
            textElements = textElements.filter(t => t.id !== text.id);
        } else {
            textElements = textElements;
        }
        selectedText = null;
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
        window.addEventListener('keydown', handleGlobalKeyDown);
    });


  function handleImageLoad(event: Event & { currentTarget: EventTarget & Element; }) {
    throw new Error('Function not implemented.');
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
                    style="filter: {filterStyle};"
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
                        style="left:{text.position.x}px; top:{text.position.y}px; color:{text.color}; font-size:{text.size}px; transform: {text.anchor === 'left' ? 'translate(0, -50%)' : 'translate(-50%, -50%)'};"
                        on:mousedown|preventDefault={(e) => startDrag(e, 'text', text.id)}
                        on:click={(e) => handleSingleClick(text, e)}
                        on:dblclick|stopPropagation|preventDefault={() => handleDoubleClick(text)}
                    >
                        {#if text.isEditing}
                            <span contenteditable="true" class="editable-area" bind:this={text.spanEl} bind:innerHTML={text.content} on:blur={() => handleTextBlur(text)} on:mousedown|stopPropagation></span>
                        {:else}
                            <span class="editable-area" bind:this={text.spanEl}>{@html text.content}</span>
                        {/if}
                    </div>
                {/each}

                {#if editorState.isCropping}
                    <div class="crop-mask" style="left:{editorState.cropArea.x}px; top:{editorState.cropArea.y}px; width:{editorState.cropArea.width}px; height:{editorState.cropArea.height}px;" on:mousedown={(e) => startDrag(e, 'crop-move')}>
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

    .text-node { position: absolute; white-space: nowrap; z-index: 150; user-select: none; pointer-events: auto; cursor: move; line-height: 1.2; padding: 4px; border-radius: 4px; }
    .text-node.editing { cursor: text; }
    .text-node.selected { box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.4); }

    .editable-area { outline: none; min-width: 20px; padding: 2px 4px; display: inline-block; pointer-events: none; caret-color: currentColor; background: transparent; }
    .text-node.editing .editable-area { pointer-events: auto; background: rgba(0, 123, 255, 0.1); }
    .editable-area::selection { background: rgba(0, 123, 255, 0.3); }
</style>