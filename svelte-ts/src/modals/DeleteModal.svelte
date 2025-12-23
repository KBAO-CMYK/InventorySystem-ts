<script lang="ts">
   export let showDeleteModal: boolean = false;
   export let selectedInventory: unknown | null = null; // 未知类型 | null
   export let loading: boolean = false;
   export let showMessage: () => void = () => {};
   export let onClose: () => void = () => {};
   export let onConfirm: () => void = () => {};
</script>

{#if showDeleteModal && selectedInventory}
<div class="modal-overlay" on:click={onClose}>
  <div class="modal-content" on:click|stopPropagation>
    <div class="modal-header">
      <h2>确认删除</h2>
      <button class="modal-close" on:click={onClose}>×</button>
    </div>
    <div class="modal-body">
      <div class="delete-confirm">
        <p>确定要删除商品 <strong>{selectedInventory.商品信息?.货号 || selectedInventory.库存ID}</strong> 吗？</p>
        <p class="warning-text">此操作不可撤销！</p>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn-outline" on:click={onClose}>取消</button>
        <button type="button" class="btn-danger" on:click={onConfirm} disabled={loading}>
          {loading ? '删除中...' : '确认删除'}
        </button>
      </div>
    </div>
  </div>
</div>
{/if}

<style>
  .modal-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    backdrop-filter: blur(3px);
    animation: fadeIn 0.3s ease;
  }

  @keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  .modal-content {
    background: white;
    border-radius: 16px;
    width: 90%;
    max-width: 500px;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    animation: slideUp 0.4s ease;
  }

  @keyframes slideUp {
    from {
      opacity: 0;
      transform: translateY(30px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 24px 30px;
    border-bottom: 1px solid #eaeaea;
    background: linear-gradient(135deg, #f8f9fa, #e9ecef);
    border-radius: 16px 16px 0 0;
  }

  .modal-header h2 {
    margin: 0;
    color: #2c3e50;
    font-size: 1.4rem;
    font-weight: 600;
  }

  .modal-close {
    background: none;
    border: none;
    font-size: 28px;
    cursor: pointer;
    color: #7f8c8d;
    padding: 0;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    transition: all 0.3s ease;
  }

  .modal-close:hover {
    background: #f8f9fa;
    color: #e74c3c;
  }

  .modal-body {
    padding: 30px;
  }

  .delete-confirm {
    text-align: center;
    padding: 30px 20px;
  }

  .delete-confirm p {
    margin: 0 0 15px 0;
    color: #2c3e50;
    font-size: 16px;
    line-height: 1.6;
  }

  .warning-text {
    color: #e74c3c;
    font-weight: 600;
    margin-top: 10px;
    font-size: 15px;
  }

  .modal-actions {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #eaeaea;
  }

  .btn-outline, .btn-danger {
    padding: 12px 30px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
    min-width: 120px;
  }

  .btn-outline {
    background: transparent;
    border: 2px solid #bdc3c7;
    color: #7f8c8d;
  }

  .btn-outline:hover:not(:disabled) {
    background: #f8f9fa;
    border-color: #3498db;
    color: #3498db;
    transform: translateY(-2px);
  }

  .btn-danger {
    background: linear-gradient(135deg, #e74c3c, #c0392b);
    color: white;
  }

  .btn-danger:hover:not(:disabled) {
    background: linear-gradient(135deg, #c0392b, #a93226);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(231, 76, 60, 0.2);
  }

  .btn-outline:disabled, .btn-danger:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }
</style>