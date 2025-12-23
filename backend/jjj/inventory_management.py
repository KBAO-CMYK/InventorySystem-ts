# inventory_management.py
from flask import jsonify, request
import pandas as pd
from read_utils import *
from other_utils import *
from write_utils import *
from config import *

def delete_inventory(inventory_id):
    """删除库存记录"""
    try:
        csv_data = read_csv_data()

        # 查找库存记录
        inventory_df = csv_data.get("inventory", pd.DataFrame())
        mask = inventory_df["ID"] == inventory_id
        if not inventory_df[mask].any().any():
            return {"status": "error", "message": "未找到对应的库存记录"}, 404

        # 检查是否有出库记录
        stock_out_records_df = csv_data.get("stock_out_records", pd.DataFrame())
        has_stock_out_records = not stock_out_records_df[stock_out_records_df["inventory_id"] == inventory_id].empty

        if has_stock_out_records:
            return {
                "status": "error",
                "message": "该库存存在出库记录，无法删除。请先删除相关的出库记录。"
            }, 400

        # 删除库存记录
        inventory_df = inventory_df[~mask]

        # 删除对应的厂家记录
        manufacturer_df = csv_data.get("manufacturer", pd.DataFrame())
        manufacturer_df = manufacturer_df[manufacturer_df["inventory_id"] != inventory_id]

        # 删除对应的特征记录
        feature_df = csv_data.get("feature", pd.DataFrame())
        feature_df = feature_df[feature_df["inventory_id"] != inventory_id]

        csv_data["inventory"] = inventory_df
        csv_data["manufacturer"] = manufacturer_df
        csv_data["feature"] = feature_df

        # 更新库存容量
        inventory_list = inventory_df.to_dict('records')
        stock_capacity_df = csv_data.get("stock_capacity", pd.DataFrame())

        for floor in FLOORS:
            update_stock_capacity(floor, inventory_list, stock_capacity_df)

        csv_data["stock_capacity"] = stock_capacity_df

        # 写入文件
        if not write_csv_data(csv_data):
            return {"status": "error", "message": "数据保存失败"}, 500

        return {
            "status": "success",
            "message": "库存记录删除成功！"
        }, 200

    except Exception as e:
        print(f"删除库存记录异常: {str(e)}")
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500


def batch_update_inventory_status(inventory_ids, csv_data):
    """批量更新库存状态 - 优化版本"""
    try:
        inventory_df = csv_data.get("inventory", pd.DataFrame())

        if inventory_df.empty:
            return

        # 批量处理库存状态更新
        for inventory_id in inventory_ids:
            try:
                # 查找库存记录
                mask = inventory_df["ID"] == inventory_id
                if not inventory_df[mask].any().any():
                    continue

                # 计算当前库存
                in_quantity = float(inventory_df.loc[mask, "入库数量"].iloc[0])
                out_total = float(inventory_df.loc[mask, "出库总数量"].iloc[0])
                current_stock = in_quantity - out_total

                # 更新状态和库存数量
                if current_stock > 0:
                    status = "已入库"
                elif current_stock == 0:
                    status = "已出库"
                else:
                    status = "未知库存"

                inventory_df.loc[mask, "状态"] = status
                inventory_df.loc[mask, "库存数量"] = current_stock

            except Exception as e:
                print(f"更新库存ID {inventory_id} 状态失败: {str(e)}")
                continue

    except Exception as e:
        print(f"批量更新库存状态失败: {str(e)}")
        raise