# stock_in.py
from flask import jsonify
import pandas as pd
from datetime import datetime
from read_utils import *
from other_utils import *
from write_utils import *
from config import *
import time


def stock_in_product(data):
    """商品入库功能"""
    try:
        start_total = time.time()
        print(f"\n=== 单条入库请求开始 | 时间: {datetime.now()} ===", flush=True)

        if not data:
            print("[错误] 单条入库：请求数据为空", flush=True)
            return {"status": "error", "message": "请求数据不能为空"}, 400

        # 校验必填字段
        start_check = time.time()
        required_fields = ["product_code", "product_type", "address_type", "floor", "quantity"]
        missing_fields = [field for field in required_fields if field not in data or not str(data[field]).strip()]
        if missing_fields:
            print(f"[错误] 单条入库：缺少必填字段 - {', '.join(missing_fields)}", flush=True)
            return {
                "status": "error",
                "message": f"缺少必填字段: {', '.join(missing_fields)}"
            }, 400
        print(f"[性能] 单条入库：字段校验耗时 {time.time() - start_check:.4f}秒", flush=True)

        # 校验商品类型是否有效
        product_type = str(data["product_type"]).strip()
        if product_type not in PRODUCT_TYPES:
            print(f"[错误] 单条入库：无效商品类型 - {product_type}", flush=True)
            return {
                "status": "error",
                "message": f"无效的商品类型。请选择以下类型之一: {', '.join(PRODUCT_TYPES)}"
            }, 400

        # 校验楼层是否有效
        try:
            floor = int(data["floor"])
            if floor not in FLOORS:
                print(f"[错误] 单条入库：无效楼层 - {floor}", flush=True)
                return {
                    "status": "error",
                    "message": f"无效的楼层。请选择以下楼层之一: {', '.join(map(str, FLOORS))}"
                }, 400
        except (ValueError, TypeError):
            print(f"[错误] 单条入库：楼层格式错误 - {data.get('floor')}", flush=True)
            return {
                "status": "error",
                "message": "楼层必须是整数"
            }, 400

        # 允许数量为负数
        try:
            quantity = float(data["quantity"])
        except (ValueError, TypeError):
            print(f"[错误] 单条入库：数量格式错误 - {data.get('quantity')}", flush=True)
            return {"status": "error", "message": "数量必须是数字"}, 400

        # 读取数据
        start_read = time.time()
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        stock_capacity_df = csv_data.get("stock_capacity", pd.DataFrame())
        print(f"[性能] 单条入库：CSV读取耗时 {time.time() - start_read:.4f}秒", flush=True)

        # 检查楼层容量（只有正数入库才检查容量）
        if quantity > 0:
            start_cap = time.time()
            inventory_list = inventory_df.to_dict('records')
            floor_capacity, stock_capacity_df = update_stock_capacity(floor, inventory_list, stock_capacity_df)
            csv_data["stock_capacity"] = stock_capacity_df
            print(f"[性能] 单条入库：楼层{floor}容量计算耗时 {time.time() - start_cap:.4f}秒", flush=True)

            used_boxes = floor_capacity["楼层容量"] - floor_capacity["楼层剩余容量"]
            if floor_capacity["楼层剩余容量"] <= 0:
                print(f"[错误] 单条入库：{floor}楼库存用尽（已用{used_boxes}框/总{floor_capacity['楼层容量']}框）", flush=True)
                return {
                    "status": "error",
                    "message": f"警告：{floor}楼库存已用尽，无法继续入库！当前{floor}楼库存状态：已用{used_boxes}框 / 总容量{floor_capacity['楼层容量']}框"
                }, 400

        address_type = data["address_type"]

        # 校验地址字段
        address_errors = []
        if address_type in [1, 3, 5] and (not data.get("shelf_no") or not str(data["shelf_no"]).strip()):
            address_errors.append("架号")
        if address_type in [2, 3, 4, 5] and (not data.get("box_no") or not str(data["box_no"]).strip()):
            address_errors.append("框号")
        if address_type in [4, 5, 6] and (not data.get("package_no") or not str(data["package_no"]).strip()):
            address_errors.append("包号")

        if address_errors:
            print(f"[错误] 单条入库：地址类型{address_type}缺少字段 - {', '.join(address_errors)}", flush=True)
            return {
                "status": "error",
                "message": f"地址类型 {address_type} 需要以下字段: {', '.join(address_errors)}"
            }, 400

        # 处理商品编号
        product_code = str(data["product_code"]).strip()
        if not product_code:
            print(f"[错误] 单条入库：商品编号为空", flush=True)
            return {"status": "error", "message": "商品编号不能为空"}, 400

        unit = get_unit_by_addr_type(address_type)

        # 处理入库时间
        in_time = data.get("in_time")
        if not in_time:
            in_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            try:
                datetime.strptime(in_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    datetime.strptime(in_time, "%Y-%m-%d %H")
                    in_time = in_time + ":00:00"
                except ValueError:
                    print(f"[错误] 单条入库：时间格式错误 - {in_time}", flush=True)
                    return {"status": "error", "message": "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH"}, 400

        # 生成库存记录ID
        start_id = time.time()
        inventory_id = generate_auto_id_df(inventory_df)
        manufacturer_id = generate_auto_id_df(manufacturer_df)
        feature_id = generate_auto_id_df(feature_df)
        print(f"[性能] 单条入库：ID生成耗时 {time.time() - start_id:.4f}秒", flush=True)

        # 处理字段
        unit_price = float(data.get("unit_price", 0)) if data.get("unit_price") else 0.0
        weight = float(data.get("weight", 0)) if data.get("weight") else 0.0
        factory_sku = data.get("factory_sku", "")
        factory_name = data.get("factory_name", "")
        factory_address = data.get("factory_address", "")
        factory_phone = data.get("factory_phone", "")
        usage = data.get("usage", "")
        specification = data.get("specification", "")
        note = data.get("note", "")

        # 计算状态和库存数量
        current_stock = quantity
        if current_stock > 0:
            status = "已入库"
        elif current_stock == 0:
            status = "已出库"
        else:
            status = "未知库存"

        # 构建库存记录 (inventory.csv)
        new_inventory = pd.DataFrame([{
            "ID": inventory_id,
            "商品编号": product_code,
            "入库时间": in_time,
            "入库数量": quantity,
            "出库总数量": 0,
            "状态": status,
            "库存数量": current_stock,
            "地址类型": address_type,
            "楼层": floor,
            "架号": str(data.get("shelf_no", "")).strip(),
            "框号": str(data.get("box_no", "")).strip(),
            "包号": str(data.get("package_no", "")).strip(),
            "单位": unit
        }])

        # 构建厂家记录 (manufacturer.csv)
        new_manufacturer = pd.DataFrame([{
            "ID": manufacturer_id,
            "inventory_id": inventory_id,
            "厂家货号": factory_sku,
            "厂家": factory_name,
            "厂家地址": factory_address,
            "电话": factory_phone
        }])

        # 构建特征记录 (feature.csv)
        new_feature = pd.DataFrame([{
            "ID": feature_id,
            "inventory_id": inventory_id,
            "商品类型": product_type,
            "单价": unit_price,
            "重量": weight,
            "用途": usage,
            "规格": specification,
            "备注": note,
            "材质": data.get("material", ""),
            "颜色": data.get("color", ""),
            "形状": data.get("shape", ""),
            "风格": data.get("style", "")
        }])

        # 合并数据
        start_concat = time.time()
        inventory_df = pd.concat([inventory_df, new_inventory], ignore_index=True)
        manufacturer_df = pd.concat([manufacturer_df, new_manufacturer], ignore_index=True)
        feature_df = pd.concat([feature_df, new_feature], ignore_index=True)
        print(f"[性能] 单条入库：DataFrame合并耗时 {time.time() - start_concat:.4f}秒", flush=True)

        csv_data["inventory"] = inventory_df
        csv_data["manufacturer"] = manufacturer_df
        csv_data["feature"] = feature_df

        # 写入文件
        start_write = time.time()
        if not write_csv_data(csv_data):
            print(f"[错误] 单条入库：数据保存失败", flush=True)
            return {"status": "error", "message": "数据保存失败"}, 500
        print(f"[性能] 单条入库：CSV写入耗时 {time.time() - start_write:.4f}秒", flush=True)

        # 总耗时统计
        total_time = time.time() - start_total
        print(f"=== 单条入库请求结束 | 总耗时: {total_time:.4f}秒 ===\n", flush=True)

        response_data = {
            "status": "success",
            "message": "入库成功！",
            "data": {
                "inventory_id": int(inventory_id),
                "manufacturer_id": int(manufacturer_id),
                "feature_id": int(feature_id),
                "product_code": product_code,
                "quantity": float(quantity),
                "unit_price": float(unit_price),
                "weight": float(weight),
                "factory_sku": factory_sku,
                "factory_name": factory_name,
                "specification": specification,
                "note": note,
                "feature_info": {
                    "material": data.get("material", ""),
                    "color": data.get("color", ""),
                    "shape": data.get("shape", ""),
                    "style": data.get("style", "")
                }
            }
        }

        return response_data, 200

    except Exception as e:
        error_msg = f"入库操作异常: {str(e)}"
        print(f"[异常] {error_msg}", flush=True)
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500


