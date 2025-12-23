# app.py
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from read_utils import *
from other_utils import init_or_fix_excel_file
from write_utils import *
from stock_out_batch import *
from stock_in_batch import *
from backend.jjj.stock_in import *
from backend.jjj.stock_out import *
from backend.jjj.inventory import *
from backend.jjj.inventory_management import *
from config import *

app = Flask(__name__)
CORS(app, resources=r"/*")  # 允许跨域请求

# 1. 健康检查
@app.route("/api.ts/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "服务正常运行"}), 200

# 2. 获取商品类型选项
@app.route("/api.ts/product-types", methods=["GET"])
def api_product_types():
    return jsonify({
        "status": "success",
        "data": PRODUCT_TYPES
    }), 200

# 3. 获取楼层选项
@app.route("/api.ts/floors", methods=["GET"])
def api_floors():
    return jsonify({
        "status": "success",
        "data": FLOORS
    }), 200



# 4. 商品入库
@app.route("/api.ts/stock-in", methods=["POST"])
def api_stock_in():
    data = request.get_json()
    result, status_code = stock_in_product(data)
    return jsonify(result), status_code

# 5. 批量入库 - 新增的路由
@app.route("/api.ts/batch-stock-in", methods=["POST"])
def api_batch_stock_in():
    data = request.get_json()
    result, status_code = batch_stock_in(data)
    return jsonify(result), status_code

# 6. 商品出库
@app.route("/api.ts/stock-out", methods=["POST"])
def api_stock_out():
    data = request.get_json()
    result, status_code = stock_out_product(data)
    return jsonify(result), status_code

# 7. 查询库存列表
@app.route("/api.ts/inventory", methods=["GET"])
def api_get_inventory():
    result, status_code = get_inventory_list()
    return jsonify(result), status_code

# 8. 查询出库记录
@app.route("/api.ts/stock-out-records", methods=["GET"])
def api_get_stock_out_records():
    inventory_id = request.args.get("inventory_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    result, status_code = get_stock_out_records(inventory_id, start_date, end_date)
    return jsonify(result), status_code

# 9. 导出出库记录为CSV
@app.route("/api.ts/export-stock-out", methods=["GET"])
def api_export_stock_out():
    csv_data = export_stock_out_records()
    if csv_data:
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=stock_out_records.csv"}
        )
    else:
        return jsonify({"status": "error", "message": "导出失败"}), 500

# 10. 查看库存详情
@app.route("/api.ts/inventory/<int:inventory_id>", methods=["GET"])
def api_get_inventory_detail(inventory_id):
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    result, status_code = get_inventory_detail(inventory_id, page, page_size)
    return jsonify(result), status_code

# 11. 更新库存信息
@app.route("/api.ts/inventory/<int:inventory_id>", methods=["PUT"])
def api_update_inventory(inventory_id):
    data = request.get_json()
    result, status_code = update_inventory(inventory_id, data)
    return jsonify(result), status_code

# 12. 删除库存记录
@app.route("/api.ts/inventory/<int:inventory_id>", methods=["DELETE"])
def api_delete_inventory(inventory_id):
    result, status_code = delete_inventory(inventory_id)
    return jsonify(result), status_code

# 13. 批量出库
@app.route("/api.ts/batch-stock-out", methods=["POST"])
def api_batch_stock_out():
    data = request.get_json()
    result, status_code = batch_stock_out(data)
    return jsonify(result), status_code

# 14. 批量更新状态
@app.route("/api.ts/batch-update-status", methods=["POST"])
def api_batch_update_status():
    data = request.get_json()
    result, status_code = batch_update_inventory_status(data)
    return jsonify(result), status_code
# 获取最后地址信息
@app.route('/api.ts/last-address-info', methods=['POST'])
def handle_last_address_info():
    """处理获取最后地址信息请求"""
    try:
        data = request.get_json()
        return get_last_address_info(data)
    except Exception as e:
        error_msg = f"处理最后地址信息请求异常: {str(e)}"
        print(f"[异常] {error_msg}", flush=True)
        return jsonify({"status": "error", "message": "系统异常"}), 500

if __name__ == "__main__":
    # 启动时初始化文件
    print("启动服务，初始化Excel文件...")
    init_or_fix_excel_file()
    app.run(debug=True, host="0.0.0.0", port=5000)