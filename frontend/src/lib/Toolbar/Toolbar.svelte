<script lang="ts">
    import Upload from '../Upload/Upload.svelte';
    import { createEventDispatcher } from 'svelte';
    
    const dispatch = createEventDispatcher();
    export let editorState: any;

    function handleRotate() {
        editorState.rotateDeg = (editorState.rotateDeg + 90) % 360;
    }

    function toggleCrop() {
        editorState.isCropping = !editorState.isCropping;
    }
</script>

<div class="toolbar-inner" style="padding: 20px; display: flex; flex-direction: column; gap: 20px;">
    <section>
        <h4>图片管理</h4>
        <Upload on:upload={(e) => dispatch('imageUpload', e.detail)} />
        <button class="btn {editorState.isCropping ? 'active' : ''}" on:click={toggleCrop} style="width:100%; margin-top:10px;">
            {editorState.isCropping ? '✅ 退出裁剪' : '✂️ 裁剪图片'}
        </button>
        <button class="btn" on:click={handleRotate} style="width:100%; margin-top:10px;">
            🔄 旋转 90°
        </button>
    </section>

    <section>
        <h4>文字属性</h4>
        <button class="btn {editorState.isAddingText ? 'active' : ''}" on:click={() => editorState.isAddingText = true}>
            T 点击添加文字
        </button>
        <div style="margin-top:15px;">
            <label>颜色: <input type="color" bind:value={editorState.textColor} /></label>
        </div>
        <div style="margin-top:10px;">
            <label>字号: <input type="number" bind:value={editorState.textSize} style="width: 60px;" />px</label>
        </div>
    </section>
</div>

<style>
    .btn { padding: 10px; cursor: pointer; background: #f0f0f0; border: 1px solid #ccc; border-radius: 4px; }
    .btn.active { background: #007bff; color: white; }
    h4 { border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 10px; }
</style>