# stock_out.py
from flask import jsonify, Response
import pandas as pd
import io
import csv
from datetime import datetime
from read_utils import *
from other_utils import *
from write_utils import *
from config import *

def stock_out_product(data):
    """商品出库功能"""
    try:
        if not data:
            return {"status": "error", "message": "请求数据不能为空"}, 400

        # 校验必填字段
        required_fields = ["inventory_id", "out_quantity", "operator"]
        missing_fields = [field for field in required_fields if field not in data or not str(data[field]).strip()]
        if missing_fields:
            return {
                "status": "error",
                "message": f"缺少必填字段: {', '.join(missing_fields)}"
            }, 400

        # 允许出库数量为负数
        try:
            out_quantity = float(data["out_quantity"])
        except (ValueError, TypeError):
            return {"status": "error", "message": "出库数量必须是数字"}, 400

        # 读取数据
        csv_data = read_csv_data()
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        stock_out_records_df = csv_data.get("stock_out_records", pd.DataFrame())

        # 查找库存记录
        inventory_id = int(data["inventory_id"])
        mask = inventory_df["ID"] == inventory_id
        if not inventory_df[mask].any().any():
            return {"status": "error", "message": "未找到对应的库存记录"}, 404

        # 转换为Python原生类型计算
        in_quantity = convert_to_serializable(inventory_df.loc[mask, "入库数量"].iloc[0])
        out_total = convert_to_serializable(inventory_df.loc[mask, "出库总数量"].iloc[0])
        current_stock = in_quantity - out_total

        # 处理出库时间
        out_time = data.get("out_time")
        if not out_time:
            out_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            try:
                datetime.strptime(out_time, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    datetime.strptime(out_time, "%Y-%m-%d %H")
                    out_time = out_time + ":00:00"
                except ValueError:
                    return {"status": "error", "message": "时间格式不正确，请使用 YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DD HH"}, 400

        # 更新库存记录
        inventory_df.loc[mask, "出库总数量"] += out_quantity

        # 更新库存状态
        update_inventory_status(inventory_id, csv_data)

        # 创建出库记录
        new_stock_out_record = pd.DataFrame([{
            "ID": generate_auto_id_df(stock_out_records_df),
            "inventory_id": inventory_id,
            "出库时间": out_time,
            "出库数量": out_quantity,
            "操作人员": str(data["operator"]).strip(),
            "备注": str(data.get("remark", "")).strip()
        }])
        stock_out_records_df = pd.concat([stock_out_records_df, new_stock_out_record], ignore_index=True)
        csv_data["stock_out_records"] = stock_out_records_df

        # 写入文件
        if not write_csv_data(csv_data):
            return {"status": "error", "message": "数据保存失败"}, 500

        # 计算新的当前库存
        new_current_stock = in_quantity - (out_total + out_quantity)

        return {
            "status": "success",
            "message": "出库成功！",
            "data": {
                "stock_out_id": int(new_stock_out_record.iloc[0]["ID"]),
                "inventory_id": int(inventory_id),
                "current_stock": float(new_current_stock),
                "status": inventory_df.loc[mask, "状态"].iloc[0]
            }
        }, 200

    except Exception as e:
        print(f"出库操作异常: {str(e)}")
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500

def get_stock_out_records(inventory_id=None, start_date=None, end_date=None):
    """查询出库记录"""
    try:
        csv_data = read_csv_data()

        stock_out_records_df = csv_data.get("stock_out_records", pd.DataFrame())
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        feature_df = csv_data.get("feature", pd.DataFrame())

        # 先过滤数据
        if inventory_id:
            stock_out_records_df = stock_out_records_df[stock_out_records_df["inventory_id"] == int(inventory_id)]
        if start_date:
            stock_out_records_df = stock_out_records_df[stock_out_records_df["出库时间"] >= start_date]
        if end_date:
            stock_out_records_df = stock_out_records_df[stock_out_records_df["出库时间"] <= end_date]

        # 构建索引字典
        inventory_dict = dict(zip(inventory_df["ID"], df_to_serializable_list(inventory_df)))
        manufacturer_dict = dict(zip(manufacturer_df["inventory_id"], df_to_serializable_list(manufacturer_df)))
        feature_dict = dict(zip(feature_df["inventory_id"], df_to_serializable_list(feature_df)))

        # 批量处理记录
        records_with_details = []
        stock_out_list = df_to_serializable_list(stock_out_records_df)

        for record in stock_out_list:
            inv_id = record.get("inventory_id")

            # 快速获取关联数据
            inventory_info = inventory_dict.get(inv_id, {})
            manufacturer_info = manufacturer_dict.get(inv_id, {})
            feature_info = feature_dict.get(inv_id, {})

            # 组装库存信息
            inventory_detail = {
                "商品编号": inventory_info.get("商品编号", ""),
                "入库时间": inventory_info.get("入库时间", ""),
                "入库数量": inventory_info.get("入库数量", 0.0),
                "出库总数量": inventory_info.get("出库总数量", 0.0),
                "状态": inventory_info.get("状态", ""),
                "库存数量": inventory_info.get("库存数量", 0.0),
                "地址类型": inventory_info.get("地址类型", 1),
                "楼层": inventory_info.get("楼层", 1),
                "架号": inventory_info.get("架号", ""),
                "框号": inventory_info.get("框号", ""),
                "包号": inventory_info.get("包号", ""),
                "单位": inventory_info.get("单位", "框")
            }

            record["inventory_info"] = inventory_detail
            record["manufacturer_info"] = manufacturer_info
            record["feature_info"] = feature_info

            records_with_details.append(record)

        return {
            "status": "success",
            "data": records_with_details
        }, 200

    except Exception as e:
        print(f"查询出库记录异常: {str(e)}")
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500

def export_stock_out_records():
    """导出出库记录为CSV"""
    try:
        csv_data = read_csv_data()

        # 创建CSV输出
        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow([
            "出库记录ID", "库存ID", "商品编号", "入库时间", "入库数量", "出库总数量", "状态", "库存数量",
            "地址类型", "楼层", "架号", "框号", "包号", "单位",
            "厂家货号", "厂家", "厂家地址", "电话",
            "商品类型", "单价", "重量", "用途", "规格", "备注", "材质", "颜色", "形状", "风格",
            "出库时间", "出库数量", "操作人员", "备注"
        ])

        # 构建索引字典
        inventory_dict = dict(zip(csv_data["inventory"]["ID"], df_to_serializable_list(csv_data["inventory"])))
        manufacturer_dict = dict(zip(csv_data["manufacturer"]["inventory_id"], df_to_serializable_list(csv_data["manufacturer"])))
        feature_dict = dict(zip(csv_data["feature"]["inventory_id"], df_to_serializable_list(csv_data["feature"])))

        # 批量处理
        stock_out_list = df_to_serializable_list(csv_data["stock_out_records"])
        for record in stock_out_list:
            inv_id = record.get("inventory_id")
            inventory_info = inventory_dict.get(inv_id, {})
            manufacturer_info = manufacturer_dict.get(inv_id, {})
            feature_info = feature_dict.get(inv_id, {})

            writer.writerow([
                record.get("ID", ""),
                inv_id,
                inventory_info.get("商品编号", ""),
                inventory_info.get("入库时间", ""),
                inventory_info.get("入库数量", 0.0),
                inventory_info.get("出库总数量", 0.0),
                inventory_info.get("状态", ""),
                inventory_info.get("库存数量", 0.0),
                inventory_info.get("地址类型", 1),
                inventory_info.get("楼层", 1),
                inventory_info.get("架号", ""),
                inventory_info.get("框号", ""),
                inventory_info.get("包号", ""),
                inventory_info.get("单位", "框"),
                manufacturer_info.get("厂家货号", ""),
                manufacturer_info.get("厂家", ""),
                manufacturer_info.get("厂家地址", ""),
                manufacturer_info.get("电话", ""),
                feature_info.get("商品类型", ""),
                feature_info.get("单价", 0.0),
                feature_info.get("重量", 0.0),
                feature_info.get("用途", ""),
                feature_info.get("规格", ""),
                feature_info.get("备注", ""),
                feature_info.get("材质", ""),
                feature_info.get("颜色", ""),
                feature_info.get("形状", ""),
                feature_info.get("风格", ""),
                record.get("出库时间", ""),
                record.get("出库数量", 0),
                record.get("操作人员", ""),
                record.get("备注", "")
            ])

        # 返回CSV文件
        output.seek(0)
        return output.getvalue()

    except Exception as e:
        print(f"导出出库记录异常: {str(e)}")
        return None