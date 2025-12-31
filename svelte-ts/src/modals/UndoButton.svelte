<script lang="ts">
  // 接收父组件传递的 props
  export let api: any;
  export let showMessage: (msg: string, type: string) => void;
  export let parentLoading: boolean;
  export let loadInventoryList: () => Promise<void>;
  export let buttonText: string = "撤销上一步操作";
  export let apiBaseUrl: string = "http://localhost:5000";

  // 组件内部加载状态
  let undoLoading = false;

  // 撤销操作核心逻辑
  async function handleUndo() {
    // 防止重复点击
    if (undoLoading || parentLoading) return;

    undoLoading = true;
    try {
      // 优先使用父组件传递的 api 实例中的方法，否则直接请求
      let response;
      if (api && typeof api.undoLastChange === "function") {
        response = await api.undoLastChange();
      } else {
        // 直接调用后端撤销接口
        response = await fetch(`${apiBaseUrl}/api/undo-last-change`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });
        response = await response.json();
      }

      // 处理响应结果
      if (response.success || response.status === "success") {
        showMessage(response.message || "撤销操作成功！", "success");
        // 撤销成功后刷新父组件的库存数据
        await loadInventoryList();
      } else {
        showMessage(response.message || "暂无可撤销的操作", "warning");
      }
    } catch (error) {
      console.error("撤销操作失败:", error);
      showMessage(
        `撤销失败：${(error as Error).message || "未知错误"}`,
        "error"
      );
    } finally {
      undoLoading = false;
    }
  }
</script>

<!-- 撤销按钮 -->
<button
  class="btn-outline undo-button"
  on:click={handleUndo}
  disabled={undoLoading || parentLoading}
  title="撤销上一步的修改/删除/借出/归还操作"
>
  {#if undoLoading}
    <span>撤销中...</span>
  {:else}
    <span>{buttonText}</span>
  {/if}
</button>

<!-- 普通 CSS 样式（移除了 SCSS 语法） -->
<style>
  .undo-button {
    padding: 8px 16px;
    border: 2px solid #bdc3c7;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
    background: transparent;
    color: #7f8c8d;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .undo-button:hover:not(:disabled) {
    background: #f8f9fa;
    border-color: #3498db;
    color: #3498db;
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(52, 152, 219, 0.2);
  }

  .undo-button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
</style>