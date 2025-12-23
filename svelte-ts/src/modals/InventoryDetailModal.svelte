<script lang="ts">
  import { api } from '../lib/api.js';

  // 简化版类型标注（快速适配，后续可细化）
  export let showInventoryDetailModal: boolean = false;
  export let selectedInventory: unknown | null = null;
  export let detailLoading: boolean = false;
  export let inventoryOperations: unknown[] = [];
  export let showMessage: () => void = () => {};

  export let onClose: () => void = () => {};

  // 函数参数标注为unknown，内部做类型守卫（可选）
  function getCurrentStock(item: unknown): number {
    if (typeof item === 'object' && item !== null && '当前库存数量' in item) {
      return (item as Record<string, number>).当前库存数量 || 0;
    }
    return 0;
  }


  function getTotalInQuantity(item: unknown): number {
    if (typeof item === 'object' && item !== null && '累计入库数量' in item) {
      return (item as Record<string, number>).累计入库数量 || 0;
    }
    return 0;
  }

  function getTotalOutQuantity(item: unknown): number {
    if (typeof item === 'object' && item !== null && '累计出库数量' in item) {
      return (item as Record<string, number>).累计出库数量 || 0;
    }
    return 0;
  }
</script>

{#if showInventoryDetailModal && selectedInventory}
<div class="modal-overlay" on:click={onClose}>
  <div class="modal-content large-modal" on:click|stopPropagation>
    <div class="modal-header">
      <h2>库存详情 - {selectedInventory.商品信息?.货号 || selectedInventory.库存ID}</h2>
      <button class="modal-close" on:click={onClose}>×</button>
    </div>
    <div class="modal-body">
      {#if detailLoading}
        <div class="loading-state">加载中...</div>
      {:else}
        <div class="detail-section">
          <h3>基本信息</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <label>库存ID:</label>
              <span>{selectedInventory.库存ID}</span>
            </div>
            <div class="detail-item">
              <label>货号:</label>
              <span>{selectedInventory.商品信息?.货号 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>商品类型:</label>
              <span>{selectedInventory.商品信息?.类型 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>累计入库:</label>
              <span>{getTotalInQuantity(selectedInventory)}</span>
            </div>
            <div class="detail-item">
              <label>累计出库:</label>
              <span>{getTotalOutQuantity(selectedInventory)}</span>
            </div>
            <div class="detail-item">
              <label>当前库存:</label>
              <span>{getCurrentStock(selectedInventory)}</span>
            </div>
            <div class="detail-item">
              <label>状态:</label>
              <span class:status-normal={selectedInventory.状态 === '正常'}
                    class:status-out={selectedInventory.状态 === '已出库'}
                    class:status-error={selectedInventory.状态 === '异常'}>
                {selectedInventory.状态}
              </span>
            </div>
            <div class="detail-item">
              <label>单价:</label>
              <span>{selectedInventory.特征信息?.单价 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>重量:</label>
              <span>{selectedInventory.特征信息?.重量 || '-'}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h3>商品信息</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <label>用途:</label>
              <span>{selectedInventory.商品信息?.用途 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>备注:</label>
              <span>{selectedInventory.商品信息?.备注 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>图片路径:</label>
              <span>{selectedInventory.特征信息?.图片路径 || '-'}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h3>商品特征</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <label>规格:</label>
              <span>{selectedInventory.特征信息?.规格 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>材质:</label>
              <span>{selectedInventory.特征信息?.材质 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>颜色:</label>
              <span>{selectedInventory.特征信息?.颜色 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>形状:</label>
              <span>{selectedInventory.特征信息?.形状 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>风格:</label>
              <span>{selectedInventory.特征信息?.风格 || '-'}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h3>位置信息</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <label>地址类型:</label>
              <span>{selectedInventory.位置信息?.地址类型 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>楼层:</label>
              <span>{selectedInventory.位置信息?.楼层 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>架号:</label>
              <span>{selectedInventory.位置信息?.架号 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>框号:</label>
              <span>{selectedInventory.位置信息?.框号 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>包号:</label>
              <span>{selectedInventory.位置信息?.包号 || '-'}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h3>厂家信息</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <label>厂家:</label>
              <span>{selectedInventory.厂家信息?.厂家 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>厂家地址:</label>
              <span>{selectedInventory.厂家信息?.厂家地址 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>电话:</label>
              <span>{selectedInventory.厂家信息?.电话 || '-'}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h3>库存信息</h3>
          <div class="detail-grid">
            <div class="detail-item">
              <label>单位:</label>
              <span>{selectedInventory.单位 || '-'}</span>
            </div>
            <div class="detail-item">
              <label>次品数量:</label>
              <span>{selectedInventory.次品数量 || 0}</span>
            </div>
            <div class="detail-item">
              <label>批次:</label>
              <span>{selectedInventory.批次 || 1}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h3>操作记录</h3>
          {#if inventoryOperations.length > 0}
            <div class="table-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>操作类型</th>
                    <th>操作时间</th>
                    <th>操作数量</th>
                    <th>操作人</th>
                    <th>备注</th>
                  </tr>
                </thead>
                <tbody>
                  {#each inventoryOperations as operation}
                    <tr>
                      <td>{operation.操作类型}</td>
                      <td>{operation.操作时间}</td>
                      <td>{operation.操作数量}</td>
                      <td>{operation.操作人}</td>
                      <td>{operation.备注 || '-'}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {:else}
            <div class="no-data">暂无操作记录</div>
          {/if}
        </div>
      {/if}

      <div class="modal-actions">
        <button type="button" class="btn-outline" on:click={onClose}>关闭</button>
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

  .loading-state {
    text-align: center;
    padding: 60px 20px;
    color: #3498db;
    font-size: 16px;
  }

  .detail-section {
    margin-bottom: 30px;
    padding-bottom: 20px;
    border-bottom: 1px solid #eaeaea;
  }

  .detail-section:last-child {
    border-bottom: none;
  }

  .detail-section h3 {
    margin-bottom: 20px;
    color: #2c3e50;
    font-size: 1.2rem;
    font-weight: 600;
    display: flex;
    align-items: center;
  }

  .detail-section h3::before {
    content: '';
    width: 4px;
    height: 16px;
    background: #3498db;
    margin-right: 10px;
    border-radius: 2px;
  }

  .detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 20px;
  }

  .detail-item {
    display: flex;
    flex-direction: column;
    background: #f8f9fa;
    padding: 12px 16px;
    border-radius: 8px;
    border: 1px solid #e4e7ed;
  }

  .detail-item label {
    font-weight: 600;
    color: #495057;
    margin-bottom: 8px;
    font-size: 14px;
  }

  .detail-item span {
    color: #2c3e50;
    font-size: 15px;
    line-height: 1.5;
  }

  .status-normal {
    color: #27ae60;
    font-weight: 500;
    padding: 4px 8px;
    background: rgba(39, 174, 96, 0.1);
    border-radius: 4px;
  }

  .status-out {
    color: #e74c3c;
    font-weight: 500;
    padding: 4px 8px;
    background: rgba(231, 76, 60, 0.1);
    border-radius: 4px;
  }

  .status-error {
    color: #f39c12;
    font-weight: 500;
    padding: 4px 8px;
    background: rgba(243, 156, 18, 0.1);
    border-radius: 4px;
  }

  .table-container {
    overflow-x: auto;
    border-radius: 8px;
    border: 1px solid #e4e7ed;
    margin-top: 15px;
  }

  .data-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 14px;
  }

  .data-table th {
    background: #f8f9fa;
    padding: 12px;
    text-align: left;
    font-weight: 600;
    color: #2c3e50;
    border-bottom: 2px solid #e4e7ed;
    white-space: nowrap;
  }

  .data-table td {
    padding: 12px;
    border-bottom: 1px solid #e4e7ed;
    color: #495057;
  }

  .data-table tr:hover {
    background: #f8f9fa;
  }

  .no-data {
    text-align: center;
    padding: 40px 20px;
    color: #7f8c8d;
    font-style: italic;
    font-size: 14px;
    background: #f8f9fa;
    border-radius: 8px;
    border: 1px dashed #e4e7ed;
    margin-top: 15px;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #eaeaea;
  }

  .btn-outline {
    padding: 10px 30px;
    background: transparent;
    border: 2px solid #bdc3c7;
    color: #7f8c8d;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
  }

  .btn-outline:hover {
    background: #f8f9fa;
    border-color: #3498db;
    color: #3498db;
    transform: translateY(-2px);
  }

  @media (max-width: 768px) {
    .detail-grid {
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