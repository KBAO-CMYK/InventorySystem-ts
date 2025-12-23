<script lang="ts">
  // 接收外部传入的props
  export let onClear: () => void | Promise<void>; // 清空选中状态的回调函数（兼容同步/异步）
  export let disabled: boolean = false; // 是否禁用按钮（无选中项时）
  export let loading: boolean = false; // 加载状态
  export let buttonText: string = '清空选中'; // 按钮文本（可自定义）
</script>

<button
  class="btn-clear-selection"
  on:click={onClear}
  disabled={disabled || loading}
  title="清空所有复选框选中状态"
>
  {loading ? '处理中...' : buttonText}
</button>

<style>
  .btn-clear-selection {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    /* 配色与其他按钮统一，区分功能 */
    background: linear-gradient(135deg, #7f8c8d, #6c7b7d);
    color: white;
  }

  .btn-clear-selection:hover:not(:disabled) {
    background: linear-gradient(135deg, #6c7b7d, #59696b);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(127, 140, 141, 0.2);
  }

  .btn-clear-selection:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
</style>