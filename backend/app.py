from flask import (Flask, request, jsonify, Response,
                   send_from_directory, make_response, current_app)
from flask_cors import CORS
from typing import List, Dict, Optional
from stock_in import *
from export import *
from lend_return import *
from image import *
from get_last_address_info import  get_last_address_info
from image2 import *
import logging
from flask import Flask, request, send_file, jsonify, abort
from undo_last_change import *


# ========== 初始化Flask应用 ==========
app = Flask(__name__)
# 允许跨域（覆盖所有接口）
CORS(app, resources=r"/*", supports_credentials=True)


# ========== 全局配置 ==========
# 1. 图片上传大小限制
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
# 2. 配置日志：统一异常日志的输出格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(module)s:%(funcName)s:%(lineno)d] - %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
app.logger = logging.getLogger(__name__)

# 全局中间件：排除DELETE请求的JSON解析（如果有全局解析逻辑）
@app.before_request
def skip_delete_json_parse():
    # 对DELETE请求，跳过JSON请求体解析
    if request.method == 'DELETE':
        # 标记跳过解析，避免后续中间件报错
        request._skip_json_parse = True
        return None



# ========== 统一API异常处理装饰器 ==========
def api_exception_handler(func):
    """
    统一处理API的异常和请求格式校验：
    1. 自动校验POST/PUT/DELETE请求的JSON格式（图片上传接口除外）
    2. 捕获所有未处理的异常，返回标准化错误响应
    3. 自动记录异常日志（含栈信息）
    """

    def wrapper(*args, **kwargs):
        try:
            # 图片上传接口是multipart/form-data，跳过JSON校验
            skip_json_check = request.path in ["/api/upload-image"]
            if not skip_json_check and request.method in ["POST", "PUT", "DELETE"] and not request.is_json:
                app.logger.warning(f"请求体非JSON格式 - 路径：{request.path}，方法：{request.method}")
                return jsonify({
                    "status": "error",
                    "message": "请求体必须为JSON格式"
                }), 400
            # 执行原接口逻辑
            return func(*args, **kwargs)
        except Exception as e:
            # 记录异常的详细栈信息，便于排查
            error_trace = traceback.format_exc()
            app.logger.error(f"接口执行失败: {str(e)}\n{error_trace}")
            return jsonify({
                "status": "error",
                "message": f"服务执行异常: {str(e)}"
            }), 500

    # 保留原函数的名称，避免Flask路由注册冲突
    wrapper.__name__ = func.__name__
    return wrapper

# ========== 原有业务接口（统一异常处理） ==========
# 1. 健康检查
@app.route("/api/health", methods=["GET"])
@api_exception_handler
def health_check():
    app.logger.info("健康检查请求")
    return jsonify({"status": "ok", "message": "服务正常运行"}), 200


# 2. 获取商品类型选项
@app.route("/api/product-types", methods=["GET"])
@api_exception_handler
def api_product_types():
    app.logger.info("获取商品类型选项")
    return jsonify({
        "status": "success",
        "data": PRODUCT_TYPES
    }), 200


# 3. 获取楼层选项
@app.route("/api/floors", methods=["GET"])
@api_exception_handler
def api_floors():
    app.logger.info("获取楼层选项")
    return jsonify({
        "status": "success",
        "data": FLOORS
    }), 200


# 4. 批量入库
@app.route("/api/batch-stock-in", methods=["POST"])
@api_exception_handler
def api_batch_stock_in():
    data = request.get_json()
    app.logger.info(f"批量入库请求 - 数据：{data}")
    result, status_code = batch_stock_in(data)
    return jsonify(result), status_code


# 5. 查询库存列表
@app.route("/api/inventory", methods=["GET"])
@api_exception_handler
def api_get_inventory():
    app.logger.info("查询库存列表请求")
    result, status_code = get_inventory_list()
    return jsonify(result), status_code


# 6. 查询操作记录
@app.route("/api/get_operation_records", methods=["GET"])
@api_exception_handler
def api_get_operation_records():
    operation_type = request.args.get("operation_type")
    inventory_id = request.args.get("inventory_id")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    app.logger.info(f"查询操作记录 - 类型：{operation_type}，库存ID：{inventory_id}，时间范围：{start_date}~{end_date}")
    result, status_code = get_operation_records(operation_type, inventory_id, start_date, end_date)
    return jsonify(result), status_code


# 7. 导出操作记录为CSV
@app.route("/api/export_operation_records", methods=["GET"])
@api_exception_handler
def api_export_operation_records():
    app.logger.info("导出操作记录为CSV")
    csv_data = export_operation_records()
    if csv_data:
        response = Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=stock_out_records.csv"}
        )
        return response
    else:
        app.logger.error("导出操作记录失败")
        return jsonify({"status": "error", "message": "导出失败"}), 500


# 8. 查看库存详情
@app.route("/api/inventory/<int:inventory_id>", methods=["GET"])
@api_exception_handler
def api_get_inventory_detail(inventory_id):
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 50, type=int)
    app.logger.info(f"查询库存详情 - 库存ID：{inventory_id}，页码：{page}，页大小：{page_size}")
    result, status_code = get_inventory_detail(inventory_id, page, page_size)
    return jsonify(result), status_code


# 9. 编辑库存记录
@app.route('/api/inventory/<int:inventory_id>/edit', methods=['POST'])
@api_exception_handler
def api_edit_inventory(inventory_id):
    edit_data = request.get_json()
    app.logger.info(f"编辑库存记录 - 库存ID：{inventory_id}，数据：{edit_data}")
    result, status_code = edit_inventory(inventory_id, edit_data)
    return jsonify(result), status_code


# 10. 删除库存记录
@app.route("/api/inventory/<inventory_id>", methods=["DELETE", "OPTIONS"])
def api_delete_inventory(inventory_id):
    """
    库存删除接口（核心：不解析DELETE请求体）
    """
    # 1. 处理OPTIONS预检请求（跨域必备）
    if request.method == "OPTIONS":
        response = jsonify({"status": "success", "message": "预检通过"})
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return response

    # 2. 处理DELETE请求（核心：不调用request.get_json()）
    try:
        # 直接调用业务函数，仅传URL路径中的inventory_id
        result, status_code = delete_inventory(inventory_id)
        # 统一返回跨域头
        response = jsonify(result)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response, status_code
    except Exception as e:
        # 异常日志
        print(f"接口层异常: {str(e)}")
        traceback.print_exc()
        response = jsonify({"status": "error", "message": "接口处理异常"})
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response, 500


# 11. 批量出库
@app.route("/api/batch-stock-out", methods=["POST"])
@api_exception_handler
def api_batch_stock_out():
    data = request.get_json()
    app.logger.info(f"批量出库请求 - 数据：{data}")
    result, status_code = batch_stock_out(data)
    return jsonify(result), status_code


# 12. 批量更新状态
@app.route("/api/batch-update-status", methods=["POST"])
@api_exception_handler
def api_batch_update_status():
    data = request.get_json()
    app.logger.info(f"批量更新库存状态 - 数据：{data}")
    result, status_code = batch_update_inventory_status(data)
    return jsonify(result), status_code


# 13. 获取最后地址信息
@app.route('/api/inventory/last-address-info', methods=['POST'])
@api_exception_handler
def handle_last_address_info():
    data = request.get_json()
    app.logger.info(f"获取最后地址信息 - 数据：{data}")
    return get_last_address_info(data)


# 14. 商品借出
@app.route("/api/inventory/lend", methods=["POST"])
@api_exception_handler
def api_product_lend():
    data = request.get_json()
    app.logger.info(f"商品借出请求 - 数据：{data}")
    result, status_code = product_lend(data)
    return jsonify(result), status_code


# 15. 商品归还
@app.route("/api/inventory/return", methods=["POST"])
@api_exception_handler
def api_product_return():
    data = request.get_json()
    app.logger.info(f"商品归还请求 - 数据：{data}")
    result, status_code = product_return(data)
    return jsonify(result), status_code


@app.route("/api/undo-last-change", methods=["POST"])
@api_exception_handler
def api_undo_last_change():
    """撤销操作API：默认恢复所有有备份的表（回退上一操作修改的所有表）"""
    current_app.logger.info("执行撤销最后一次操作请求（恢复所有有备份的表）")

    # 核心修改：不传table_name，默认恢复所有表
    undo_result = undo_last_change(confirm=False)  # 无table_name → 恢复所有表

    # 构造响应（包含调试信息）
    status_code = 200 if undo_result["success"] else 400
    api_response = {
        "success": undo_result["success"],
        "message": undo_result["message"],
        "data": {
            "restored_tables": undo_result["restored"],  # 显示恢复的所有表
            "debug_info": undo_result["debug_info"]
        }
    }

    return jsonify(api_response), status_code

# ========== 图片相关接口（优化版） ==========
@app.route("/api/upload-image", methods=["POST"])
@api_exception_handler
def upload_image():
    """适配修改后的图片工具函数"""
    # 1. 获取参数（新增featureId）
    product_code = request.form.get("product_code")
    feature_id = request.form.get("featureId", 0)  # 默认0，适配库存ID=0场景
    if not product_code:
        return jsonify({"status": "error", "message": "商品货号不能为空"}), 400

    # 2. 处理文件
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "未上传文件"}), 400
    file = request.files["file"]

    # 3. 保存图片并更新特征表（传入feature_id，自动保留原关联商品ID）
    img_path = save_product_image(
        product_code=product_code,
        file=file,
        feature_id=feature_id,
        host=request.host  # 自动获取当前服务器地址
    )

    if img_path:
        return jsonify({
            "status": "success",
            "message": "图片上传成功",
            "data": {"relative_path": img_path, "access_url": f"http://{request.host}/{img_path}"}
        }), 200
    else:
        return jsonify({"status": "error", "message": "图片保存失败"}), 500


@app.route("/image/<path:filename>")
@api_exception_handler
def serve_image(filename):
    """提供上传图片的静态访问（优化异常处理）"""
    try:
        app.logger.info(f"静态访问图片 - 文件名：{filename}，目录：{UPLOAD_FOLDER}")
        return send_from_directory(UPLOAD_FOLDER, filename)
    except FileNotFoundError:
        app.logger.error(f"静态图片访问失败 - 文件不存在：{filename}")
        return jsonify({
            "status": "error",
            "message": "图片不存在"
        }), 404
    except PermissionError:
        app.logger.error(f"静态图片访问失败 - 无权限：{filename}")
        return jsonify({
            "status": "error",
            "message": "图片访问权限不足"
        }), 403
    except Exception as e:
        app.logger.error(f"静态图片访问失败 - 文件名：{filename}，错误：{str(e)}")
        return jsonify({
            "status": "error",
            "message": "图片访问失败"
        }), 404


@app.route('/api/get_image')
@api_exception_handler
def get_image():
    """图片读取接口（优化版，增加日志和跨域头）"""
    # 获取前端传入的图片相对路径
    img_path = request.args.get('path', '')
    app.logger.info(f"读取图片请求 - 路径：{img_path}")

    if not img_path:
        app.logger.warning(f"图片读取失败 - 路径为空")
        return jsonify({"code": 400, "msg": "图片路径为空"}), 400

    # 读取图片内容
    img_content = read_image_file(img_path)
    if not img_content:
        app.logger.error(f"图片读取失败 - 文件不存在/读取错误：{img_path}")
        return jsonify({"code": 404, "msg": "图片不存在或读取失败"}), 404

    # 构建响应返回图片（添加跨域头）
    mime_type = get_image_mime_type(img_path)
    response = make_response(img_content)
    response.headers['Content-Type'] = mime_type
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'public, max-age=86400'  # 缓存1天
    app.logger.info(f"图片读取成功 - 路径：{img_path}，大小：{len(img_content)}字节")
    return response


@app.route('/api/get_product_images/<product_code>')
@api_exception_handler
def get_product_images(product_code):
    """根据货号查询图片列表（优化日志）"""
    app.logger.info(f"查询商品图片 - 货号：{product_code}")
    images = get_product_images(product_code)
    return jsonify({
        "code": 200,
        "msg": "success",
        "data": images
    }), 200


@app.route("/api/batch_delete_image", methods=["POST"])
@api_exception_handler
def batch_delete_image_route():
    """
    批量图片删除接口路由
    请求格式：application/json
    """
    # 解析JSON请求数据
    try:
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValueError("请求体非JSON对象")
    except Exception as e:
        app.logger.error(f"[批量删除失败] 请求体解析错误：{str(e)}")
        return jsonify({
            "status": "error",
            "message": "请求体格式错误（需为JSON对象）",
            "total": 0,
            "success_count": 0,
            "fail_count": 0,
            "details": []
        }), 400

    # 调用业务逻辑
    result, status_code = batch_delete_images_logic(data, app.logger)

    # 返回JSON响应
    return jsonify(result), status_code



# ---------------------- 日志配置 ----------------------
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler("app.log", maxBytes=1024 * 1024 * 10, backupCount=5, encoding="utf-8")
handler.setLevel(logging.INFO)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
handler.flush = lambda: handler.stream.flush()  # 强制日志即时刷新
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)

# ========== 服务启动 ==========
if __name__ == "__main__":
    # 启动时初始化Excel文件
    app.logger.info("启动服务，初始化Excel文件...")
    init_or_fix_excel_file()

    # 打印关键配置信息
    app.logger.info(f"[服务配置] 图片上传目录: {UPLOAD_FOLDER}")
    app.logger.info(f"[服务配置] 最大上传文件大小: {MAX_CONTENT_LENGTH / 1024 / 1024}MB")
    app.logger.info(f"[服务配置] 允许的图片格式: {ALLOWED_EXTENSIONS}")

    # 启动服务（生产环境建议关闭debug=True，修改host为0.0.0.0允许外部访问）
    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000,
        threaded=True  # 开启多线程处理请求
    )