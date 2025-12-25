<!-- Modified ImageAdjuster.svelte -->
<script lang="ts">
    export let editorState: any;

    function resetAdjustments() {
        editorState.brightness = 100;
        editorState.contrast = 100;
    }

    function toggleFillMode() {
        editorState.isFillMode = !editorState.isFillMode;
        if (editorState.isFillMode) {
            editorState.isCropping = false; // 互斥
            editorState.isAddingText = false;
            editorState.isAutoFillMode = false;  // 新增：互斥
        }
    }

    function toggleAutoFillMode() {
        editorState.isAutoFillMode = !editorState.isAutoFillMode;
        if (editorState.isAutoFillMode) {
            editorState.isFillMode = false;
            editorState.isCropping = false;
            editorState.isAddingText = false;
        }
    }
</script>

<div class="adjuster-container" style="display: flex; flex-direction: column; gap: 15px;">
    <section>
        <h4 style="margin-bottom: 10px;">图像调节</h4>
        <div class="control-group">
            <!-- svelte-ignore a11y_label_has_associated_control -->
            <label style="display: flex; justify-content: space-between; font-size: 14px;">
                亮度 <span>{editorState.brightness}%</span>
            </label>
            <input 
                type="range" 
                min="0" max="200" 
                bind:value={editorState.brightness} 
                style="width: 100%;"
            />
        </div>

        <div class="control-group" style="margin-top: 10px;">
            <!-- svelte-ignore a11y_label_has_associated_control -->
            <label style="display: flex; justify-content: space-between; font-size: 14px;">
                对比度 <span>{editorState.contrast}%</span>
            </label>
            <input 
                type="range" 
                min="0" max="200" 
                bind:value={editorState.contrast} 
                style="width: 100%;"
            />
        </div>
        
        <button class="btn-secondary" on:click={resetAdjustments} style="width: 100%; margin-top: 5px; font-size: 12px; cursor: pointer;">
            重置参数
        </button>
    </section>

    <section>
        <h4 style="margin-bottom: 10px;">擦除/填充</h4>
        <button 
            class="btn {editorState.isFillMode ? 'active' : ''}" 
            on:click={toggleFillMode}
            style="width: 100%;"
        >
            {editorState.isFillMode ? '✅ 停止填充' : '⬜ 框选填充白色'}
        </button>
        {#if editorState.isFillMode}
            <p style="font-size: 12px; color: #666; margin-top: 5px;">
                提示：在图片上拖拽框选，松开即可填充白色。
            </p>
        {/if}
        <button 
            class="btn {editorState.isAutoFillMode ? 'active' : ''}" 
            on:click={toggleAutoFillMode}
            style="width: 100%; margin-top: 10px;"
        >
            {editorState.isAutoFillMode ? '✅ 停止自动填充' : '🪄 框选自动识别填充'}
        </button>
        {#if editorState.isAutoFillMode}
            <p style="font-size: 12px; color: #666; margin-top: 5px;">
                提示：在图片上拖拽框选，松开即可自动识别并填充。
            </p>
        {/if}
    </section>
</div>

<style>
    .btn {
        padding: 10px;
        border: 1px solid #ddd;
        border-radius: 4px;
        background: #fff;
        cursor: pointer;
    }
    .btn.active {
        background: #007bff;
        color: white;
        border-color: #0056b3;
    }
    .btn-secondary {
        background: none;
        border: 1px dashed #ccc;
        color: #666;
        padding: 4px;
    }
    h4 {
        font-size: 14px;
        color: #333;
        border-left: 3px solid #007bff;
        padding-left: 8px;
    }
</style>