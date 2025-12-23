<script lang="ts">
  export let showEditModal: boolean = false;
  export let editingInventory: unknown | null = null;
  export let editForm: Record<string, any> = {}; // 表单对象（兼容任意键值）
  export let loading: boolean = false;
  export let productTypes: unknown[] = [];
  export let floors: unknown[] = [];
  export let showMessage: () => void = () => {};

  export let onClose: () => void = () => {};
  export let onSave: () => void = () => {};
</script>

{#if showEditModal && editingInventory}
<div class="modal-overlay" on:click={onClose}>
  <div class="modal-content large-modal" on:click|stopPropagation>
    <div class="modal-header">
      <h2>编辑库存 - {editingInventory.商品信息?.货号}</h2>
      <button class="modal-close" on:click={onClose}>×</button>
    </div>
    <div class="modal-body">
      <form on:submit|preventDefault={onSave}>
        <div class="form-row">
          <div class="form-group">
            <label for="edit_货号">货号 *</label>
            <input
              id="edit_货号"
              type="text"
              bind:value={editForm.货号}
              placeholder="请输入货号"
              required
            />
          </div>
          <div class="form-group">
            <label for="edit_类型">商品类型 *</label>
            <select id="edit_类型" bind:value={editForm.类型} required>
              <option value="">请选择商品类型</option>
              {#each productTypes as type}
                <option value={type}>{type}</option>
              {/each}
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_单价">单价</label>
            <input
              id="edit_单价"
              type="number"
              step="0.01"
              bind:value={editForm.单价}
              placeholder="请输入单价"
            />
          </div>
          <div class="form-group">
            <label for="edit_重量">重量</label>
            <input
              id="edit_重量"
              type="number"
              step="0.01"
              bind:value={editForm.重量}
              placeholder="请输入重量"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_厂家">厂家</label>
            <input
              id="edit_厂家"
              type="text"
              bind:value={editForm.厂家}
              placeholder="请输入厂家名称"
            />
          </div>
          <div class="form-group">
            <label for="edit_厂家地址">厂家地址</label>
            <input
              id="edit_厂家地址"
              type="text"
              bind:value={editForm.厂家地址}
              placeholder="请输入厂家地址"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_电话">电话</label>
            <input
              id="edit_电话"
              type="text"
              bind:value={editForm.电话}
              placeholder="请输入联系电话"
            />
          </div>
          <div class="form-group">
            <label for="edit_用途">用途</label>
            <input
              id="edit_用途"
              type="text"
              bind:value={editForm.用途}
              placeholder="请输入商品用途"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_规格">规格</label>
            <input
              id="edit_规格"
              type="text"
              bind:value={editForm.规格}
              placeholder="请输入商品规格"
            />
          </div>
          <div class="form-group">
            <label for="edit_备注">备注</label>
            <input
              id="edit_备注"
              type="text"
              bind:value={editForm.备注}
              placeholder="请输入备注信息"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_材质">材质</label>
            <input
              id="edit_材质"
              type="text"
              bind:value={editForm.材质}
              placeholder="请输入材质"
            />
          </div>
          <div class="form-group">
            <label for="edit_颜色">颜色</label>
            <input
              id="edit_颜色"
              type="text"
              bind:value={editForm.颜色}
              placeholder="请输入颜色"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_形状">形状</label>
            <input
              id="edit_形状"
              type="text"
              bind:value={editForm.形状}
              placeholder="请输入形状"
            />
          </div>
          <div class="form-group">
            <label for="edit_风格">风格</label>
            <input
              id="edit_风格"
              type="text"
              bind:value={editForm.风格}
              placeholder="请输入风格"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_图片路径">图片路径</label>
            <input
              id="edit_图片路径"
              type="text"
              bind:value={editForm.图片路径}
              placeholder="请输入图片路径"
            />
          </div>
          <div class="form-group">
            <label for="edit_批次">批次</label>
            <input
              id="edit_批次"
              type="number"
              bind:value={editForm.批次}
              placeholder="批次号"
              min="1"
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_地址类型">地址类型</label>
            <select id="edit_地址类型" bind:value={editForm.地址类型}>
              <option value={1}>1-楼层+架号（单位：框）</option>
              <option value={2}>2-楼层+框号（单位：包）</option>
              <option value={3}>3-楼层+架号+框号（单位：包）</option>
              <option value={4}>4-楼层+框号+包号（单位：个）</option>
              <option value={5}>5-楼层+架号+框号+包号（单位：个）</option>
              <option value={6}>6-楼层+包号（单位：个）</option>
            </select>
          </div>
          <div class="form-group">
            <label for="edit_楼层">楼层</label>
            <select id="edit_楼层" bind:value={editForm.楼层}>
              <option value="">请选择楼层</option>
              {#each floors as floor}
                <option value={floor}>{floor}楼</option>
              {/each}
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="edit_架号">架号</label>
            <input
              id="edit_架号"
              type="text"
              bind:value={editForm.架号}
              placeholder="请输入架号"
            />
          </div>
          <div class="form-group">
            <label for="edit_框号">框号</label>
            <input
              id="edit_框号"
              type="text"
              bind:value={editForm.框号}
              placeholder="请输入框号"
            />
          </div>
        </div>

        <div class="form-group">
          <label for="edit_包号">包号</label>
          <input
            id="edit_包号"
            type="text"
            bind:value={editForm.包号}
            placeholder="请输入包号"
          />
        </div>

        <div class="modal-actions">
          <button type="button" class="btn-outline" on:click={onClose}>取消</button>
          <button type="submit" class="btn-primary" disabled={loading}>
            {loading ? '保存中...' : '保存更改'}
          </button>
        </div>
      </form>
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

  .large-modal {
    max-width: 800px;
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

  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
  }

  .form-group {
    margin-bottom: 0;
  }

  label {
    display: block;
    margin-bottom: 8px;
    font-weight: 500;
    color: #555;
    font-size: 14px;
  }

  input, select {
    width: 100%;
    padding: 10px 12px;
    border: 2px solid #e0e0e0;
    border-radius: 8px;
    font-size: 14px;
    transition: all 0.3s ease;
    background: white;
    color: #333;
  }

  input:focus, select:focus {
    outline: none;
    border-color: #3498db;
    box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #eaeaea;
  }

  .btn-outline, .btn-primary {
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

  .btn-primary {
    background: linear-gradient(135deg, #3498db, #2980b9);
    color: white;
  }

  .btn-primary:hover:not(:disabled) {
    background: linear-gradient(135deg, #2980b9, #1f639b);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(52, 152, 219, 0.2);
  }

  .btn-outline:disabled, .btn-primary:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    transform: none;
    box-shadow: none;
  }

  @media (max-width: 768px) {
    .form-row {
      grid-template-columns: 1fr;
    }

    .modal-content {
      width: 95%;
      margin: 10px;
    }

    .large-modal {
      max-width: 95%;
    }
  }
</style>