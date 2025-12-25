<script lang="ts">
    import { createEventDispatcher } from 'svelte';
    // 引入 CSS 样式（关键修改）
    import '$lib/styles/global.css';
    
    const dispatch = createEventDispatcher();
    
    export let disabled: boolean;
    
    function handleSave() {
        dispatch('save');
    }
    
    function handleDownload() {
        dispatch('download');
    }
</script>

<div class="save-download-container">
    <button 
        class="save-btn"
        on:click={handleSave}
        disabled={disabled}
    >
        保存
    </button>
    <button 
        class="download-btn"
        on:click={handleDownload}
        disabled={disabled}
    >
        下载
    </button>
</div>

<!-- 移除原有的 <link> 标签 -->