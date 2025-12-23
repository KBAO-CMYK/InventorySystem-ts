# inventory_management.py
from flask import jsonify, request
import pandas as pd
from read_utils import *
from other_utils import *
from write_utils import *
from config import *


def get_inventory_list():
    """查询库存列表"""
    try:
        csv_data = read_csv_data()

        inventory_df = csv_data.get("inventory", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        stock_out_records_df = csv_data.get("stock_out_records", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())

        # 批量转换为可序列化格式
        inventory_list = df_to_serializable_list(inventory_df)
        manufacturer_list = df_to_serializable_list(manufacturer_df)
        stock_out_list = df_to_serializable_list(stock_out_records_df)
        feature_list = df_to_serializable_list(feature_df)

        # 构建索引字典
        manufacturer_index = {}
        for mfr in manufacturer_list:
            inv_id = mfr.get("inventory_id")
            if inv_id not in manufacturer_index:
                manufacturer_index[inv_id] = mfr

        stock_out_index = {}
        for record in stock_out_list:
            inv_id = record.get("inventory_id")
            if inv_id not in stock_out_index:
                stock_out_index[inv_id] = []
            stock_out_index[inv_id].append(record)

        feature_index = {}
        for feature in feature_list:
            inv_id = feature.get("inventory_id")
            if inv_id not in feature_index:
                feature_index[inv_id] = feature

        # 组装最终数据
        inventory_with_details = []
        for inv in inventory_list:
            inv_id = inv.get("ID")
            manufacturer_dict = manufacturer_index.get(inv_id, {})
            stock_out_records = stock_out_index.get(inv_id, [])
            feature_dict = feature_index.get(inv_id, {})

            # 计算当前库存
            in_quantity = inv.get("入库数量", 0)
            out_total = inv.get("出库总数量", 0)
            current_stock = float(in_quantity) - float(out_total)
            inv["当前库存数量"] = current_stock

            inv["manufacturer_info"] = manufacturer_dict
            inv["stock_out_records"] = stock_out_records
            inv["feature_info"] = feature_dict

            inventory_with_details.append(inv)

        return {
            "status": "success",
            "data": inventory_with_details
        }, 200

    except Exception as e:
        print(f"查询库存异常: {str(e)}")
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500


def get_inventory_detail(inventory_id, page=1, page_size=50):
    """查询库存详情"""
    try:
        csv_data = read_csv_data()

        inventory_df = csv_data.get("inventory", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())
        stock_out_records_df = csv_data.get("stock_out_records", pd.DataFrame())

        # 校验核心字段是否存在
        required_fields = {
            "inventory": ["ID", "入库数量", "出库总数量"],
            "manufacturer": ["inventory_id"],
            "feature": ["inventory_id"],
            "stock_out_records": ["inventory_id", "出库时间", "出库数量"]
        }
        for sheet_name, fields in required_fields.items():
            df = csv_data.get(sheet_name, pd.DataFrame())
            missing_fields = [f for f in fields if f not in df.columns]
            if missing_fields:
                return {
                    "status": "error",
                    "message": f"数据表格[{sheet_name}]缺少必填字段：{', '.join(missing_fields)}"
                }, 500

        # 筛选目标库存
        inventory_df["ID"] = pd.to_numeric(inventory_df["ID"], errors="coerce").fillna(-1).astype(int)
        target_inventory = inventory_df[inventory_df["ID"] == inventory_id]

        if target_inventory.empty:
            return {"status": "error", "message": f"未找到ID为{inventory_id}的库存记录"}, 404

        # 关联查询所有关联数据
        manufacturer_df["inventory_id"] = pd.to_numeric(manufacturer_df["inventory_id"], errors="coerce").fillna(-1).astype(int)
        target_manufacturers = manufacturer_df[manufacturer_df["inventory_id"] == inventory_id].copy()

        feature_df["inventory_id"] = pd.to_numeric(feature_df["inventory_id"], errors="coerce").fillna(-1).astype(int)
        target_features = feature_df[feature_df["inventory_id"] == inventory_id].copy()

        stock_out_records_df["inventory_id"] = pd.to_numeric(stock_out_records_df["inventory_id"],
                                                             errors="coerce").fillna(-1).astype(int)
        target_stock_outs = stock_out_records_df[stock_out_records_df["inventory_id"] == inventory_id].copy()

        # 出库记录分页
        page = max(1, page)
        page_size = max(10, min(page_size, 100))
        total_out_records = len(target_stock_outs)
        total_pages = (total_out_records + page_size - 1) // page_size

        # 分页截取
        if not target_stock_outs.empty:
            target_stock_outs["出库时间"] = pd.to_datetime(target_stock_outs["出库时间"], errors="coerce")
            target_stock_outs = target_stock_outs.sort_values("出库时间", ascending=False)
            start = (page - 1) * page_size
            end = start + page_size
            paginated_outs = target_stock_outs.iloc[start:end]
        else:
            paginated_outs = pd.DataFrame()

        def serialize_df(df):
            if df.empty:
                return []
            return df.map(convert_to_serializable).to_dict('records')

        # 数据序列化
        inventory_dict = serialize_df(target_inventory)[0]
        manufacturer_list = serialize_df(target_manufacturers)
        feature_list = serialize_df(target_features)
        stock_out_list = serialize_df(paginated_outs)

        # 补充核心统计信息
        stock_out_stats = {
            "total_out_times": total_out_records,
            "total_out_quantity": convert_to_serializable(
                target_stock_outs["出库数量"].sum()) if not target_stock_outs.empty else 0,
            "last_out_time": convert_to_serializable(
                target_stock_outs["出库时间"].max()) if not target_stock_outs.empty else ""
        }

        # 计算当前库存
        in_quantity = float(convert_to_serializable(inventory_dict.get("入库数量", 0)))
        out_total = float(convert_to_serializable(inventory_dict.get("出库总数量", 0)))
        inventory_dict["当前库存数量"] = round(in_quantity - out_total, 2)

        # 处理多厂家/多特征的警告提示
        warnings = []
        if len(manufacturer_list) > 1:
            warnings.append(f"该库存关联{len(manufacturer_list)}个厂家记录，请确认数据是否正常")
        if len(feature_list) > 1:
            warnings.append(f"该库存关联{len(feature_list)}个特征记录，请确认数据是否正常")

        # 组装响应数据
        response_data = {
            "status": "success",
            "data": {
                "inventory": inventory_dict,
                "manufacturers": manufacturer_list,
                "features": feature_list,
                "stock_out_records": stock_out_list,
                "stock_out_stats": stock_out_stats
            },
            "pagination": {
                "total": total_out_records,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages
            }
        }

        if warnings:
            response_data["warnings"] = warnings

        return response_data, 200

    except IndexError as e:
        print(f"库存详情查询索引异常：{str(e)}")
        return {"status": "error", "message": "库存数据索引错误，请检查数据完整性"}, 500
    except TypeError as e:
        print(f"库存详情查询类型异常：{str(e)}")
        return {"status": "error", "message": "数据类型转换错误，请检查字段格式"}, 500
    except Exception as e:
        print(f"获取库存详情异常: {str(e)}")
        return {"status": "error", "message": f"系统异常：{str(e)}"}, 500


def update_inventory(inventory_id, data):
    """更新库存信息"""
    try:
        if not data:
            return {"status": "error", "message": "请求数据不能为空"}, 400

        # 校验必填字段
        required_fields = ["product_code", "product_type"]
        missing_fields = [field for field in required_fields if field not in data or not str(data[field]).strip()]
        if missing_fields:
            return {
                "status": "error",
                "message": f"缺少必填字段: {', '.join(missing_fields)}"
            }, 400

        # 校验商品类型是否有效
        product_type = str(data["product_type"]).strip()
        if product_type not in PRODUCT_TYPES:
            return {
                "status": "error",
                "message": f"无效的商品类型。请选择以下类型之一: {', '.join(PRODUCT_TYPES)}"
            }, 400

        # 读取数据
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())

        # 查找库存记录
        mask = inventory_df["ID"] == inventory_id
        if not inventory_df[mask].any().any():
            return {"status": "error", "message": "未找到对应的库存记录"}, 404

        # 处理商品编号
        product_code = str(data["product_code"]).strip()

        if not product_code:
            return {"status": "error", "message": "商品编号不能为空"}, 400

        # 更新库存记录 (inventory.csv)
        inventory_df.loc[mask, "商品编号"] = product_code
        inventory_df.loc[mask, "架号"] = data.get("shelf_no", "")
        inventory_df.loc[mask, "框号"] = data.get("box_no", "")
        inventory_df.loc[mask, "包号"] = data.get("package_no", "")
        inventory_df.loc[mask, "地址类型"] = data.get("address_type", 1)
        inventory_df.loc[mask, "楼层"] = data.get("floor", 1)
        inventory_df.loc[mask, "单位"] = get_unit_by_addr_type(data.get("address_type", 1))

        # 更新库存状态
        update_inventory_status(inventory_id, csv_data)

        # 更新厂家记录 (manufacturer.csv)
        manufacturer_mask = manufacturer_df["inventory_id"] == inventory_id
        if manufacturer_df[manufacturer_mask].any().any():
            manufacturer_df.loc[manufacturer_mask, "厂家货号"] = data.get("factory_sku", "")
            manufacturer_df.loc[manufacturer_mask, "厂家"] = data.get("factory_name", "")
            manufacturer_df.loc[manufacturer_mask, "厂家地址"] = data.get("factory_address", "")
            manufacturer_df.loc[manufacturer_mask, "电话"] = data.get("factory_phone", "")
        else:
            # 如果没有厂家记录，创建新的
            new_manufacturer = pd.DataFrame([{
                "ID": generate_auto_id_df(manufacturer_df),
                "inventory_id": inventory_id,
                "厂家货号": data.get("factory_sku", ""),
                "厂家": data.get("factory_name", ""),
                "厂家地址": data.get("factory_address", ""),
                "电话": data.get("factory_phone", "")
            }])
            manufacturer_df = pd.concat([manufacturer_df, new_manufacturer], ignore_index=True)

        # 更新特征记录 (feature.csv)
        feature_mask = feature_df["inventory_id"] == inventory_id
        if feature_df[feature_mask].any().any():
            feature_df.loc[feature_mask, "商品类型"] = product_type
            feature_df.loc[feature_mask, "单价"] = float(data.get("unit_price", 0)) if data.get("unit_price") else 0.0
            feature_df.loc[feature_mask, "重量"] = float(data.get("weight", 0)) if data.get("weight") else 0.0
            feature_df.loc[feature_mask, "用途"] = data.get("usage", "")
            feature_df.loc[feature_mask, "规格"] = data.get("specification", "")
            feature_df.loc[feature_mask, "备注"] = data.get("note", "")
            feature_df.loc[feature_mask, "材质"] = data.get("material", "")
            feature_df.loc[feature_mask, "颜色"] = data.get("color", "")
            feature_df.loc[feature_mask, "形状"] = data.get("shape", "")
            feature_df.loc[feature_mask, "风格"] = data.get("style", "")
        else:
            # 如果没有特征记录，创建新的
            new_feature = pd.DataFrame([{
                "ID": generate_auto_id_df(feature_df),
                "inventory_id": inventory_id,
                "商品类型": product_type,
                "单价": float(data.get("unit_price", 0)) if data.get("unit_price") else 0.0,
                "重量": float(data.get("weight", 0)) if data.get("weight") else 0.0,
                "用途": data.get("usage", ""),
                "规格": data.get("specification", ""),
                "备注": data.get("note", ""),
                "材质": data.get("material", ""),
                "颜色": data.get("color", ""),
                "形状": data.get("shape", ""),
                "风格": data.get("style", "")
            }])
            feature_df = pd.concat([feature_df, new_feature], ignore_index=True)

        csv_data["inventory"] = inventory_df
        csv_data["manufacturer"] = manufacturer_df
        csv_data["feature"] = feature_df

        # 写入文件
        if not write_csv_data(csv_data):
            return {"status": "error", "message": "数据保存失败"}, 500

        return {
            "status": "success",
            "message": "库存信息更新成功！",
            "data": {
                "inventory_id": int(inventory_id),
                "product_code": product_code
            }
        }, 200

    except Exception as e:
        print(f"更新库存信息异常: {str(e)}")
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500