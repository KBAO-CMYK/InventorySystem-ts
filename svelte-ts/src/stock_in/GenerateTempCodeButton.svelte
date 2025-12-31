<script lang="ts">
  // 必须导入并初始化事件派发器（核心修复点）
  import { createEventDispatcher } from 'svelte';
  const dispatch = createEventDispatcher();

  // 组件Props定义
  export let disabled: boolean = false;
  export let prefix: string = "TEMP-"; // 临时货号前缀，可自定义

  // 生成基于时间的临时货号
  function generateTempCode() {
    // 获取当前时间，格式：YYYYMMDDHHmmss（年月日时分秒），保证唯一性
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    const hour = String(now.getHours()).padStart(2, "0");
    const minute = String(now.getMinutes()).padStart(2, "0");
    const second = String(now.getSeconds()).padStart(2, "0");

    // 拼接临时货号（格式：前缀+时间戳）
    const tempCode = `${prefix}${year}${month}${day}${hour}${minute}${second}`;

    // 派发生成货号的事件，将货号传递给父组件
    dispatch("generate", tempCode);
  }
</script>

<button
  type="button"
  class="btn-default temp-code-btn"
  disabled={disabled}
  on:click={generateTempCode}
>
  生成临时货号
</button>

<style>
  .temp-code-btn {
    margin-left: 8px;
    padding: 4px 8px;
    font-size: 12px;
    cursor: pointer;
    border: 1px solid #ddd;
    border-radius: 4px;
    background-color: #f5f5f5;
  }

  .temp-code-btn:hover {
    background-color: #eee;
  }

  .temp-code-btn:disabled {
    cursor: not-allowed;
    opacity: 0.6;
    background-color: #f9f9f9;
  }
</style>