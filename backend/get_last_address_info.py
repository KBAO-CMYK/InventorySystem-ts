from inventory_management import *
import logging
import time
from collections import defaultdict

import time
import pandas as pd  # 确保已导入pandas（原代码依赖）

def get_last_address_info(data):
    """
    获取最后地址信息（核心逻辑）：
    1. 从inventory表取库存ID最大的记录，提取「关联位置ID」；
    2. 从location表通过「关联位置ID」匹配「地址ID」，获取地址类型/楼层/架号/框号/包号；
    【仅内部临时统一ID格式，不修改原DataFrame，避免影响其他函数】
    """
    try:
        # 修正后：datetime.now() 可正常调用
        print(f"\n=== 获取最后地址信息请求开始 | 时间: {datetime.now()} ===", flush=True)

        # 1. 读取CSV数据（仅读取，不修改原数据）
        csv_data = read_csv_data()
        # 【关键修改1】复制DataFrame副本，避免修改原数据影响其他函数
        inventory_df = csv_data.get("inventory", pd.DataFrame()).copy()
        location_df = csv_data.get("location", pd.DataFrame()).copy()

        # 2. 校验inventory表基础条件
        if inventory_df.empty:
            print(f"[信息] 获取最后地址信息：inventory表数据为空，返回默认值", flush=True)
            return {
                "status": "success",
                "data": {"地址类型": "", "楼层": "", "架号": "", "框号": "", "包号": ""}
            }, 200

        # 校验inventory表必要字段（匹配实际字段名）
        inv_required_cols = ["库存ID", "关联位置ID"]
        inv_missing_cols = [col for col in inv_required_cols if col not in inventory_df.columns]
        if inv_missing_cols:
            print(f"[错误] inventory.csv缺少必要字段：{', '.join(inv_missing_cols)}", flush=True)
            return {
                "status": "error",
                "message": f"inventory.csv格式错误：缺少字段 {', '.join(inv_missing_cols)}，请检查CSV表头"
            }, 400

        # 3. 取inventory表中库存ID最大的记录
        # 确保库存ID为数值类型（避免字符串排序异常）
        inventory_df["库存ID"] = pd.to_numeric(inventory_df["库存ID"], errors="coerce")
        # 过滤掉库存ID为空的记录
        inv_valid_df = inventory_df.dropna(subset=["库存ID"])
        if inv_valid_df.empty:
            print(f"[信息] 获取最后地址信息：inventory表中无有效库存ID记录，返回默认值", flush=True)
            return {
                "status": "success",
                "data": {"地址类型": "", "楼层": "", "架号": "", "框号": "", "包号": ""}
            }, 200

        # 按库存ID倒序取最后一条
        inv_latest_record = inv_valid_df.sort_values("库存ID", ascending=False).iloc[0]
        location_id = inv_latest_record.get("关联位置ID")
        latest_inv_id = inv_latest_record["库存ID"]

        # 4. 校验关联位置ID是否有效
        if pd.isna(location_id) or str(location_id).strip() == "":
            print(f"[信息] 获取最后地址信息：inventory表最新记录（库存ID：{latest_inv_id}）的关联位置ID为空，返回默认值",
                  flush=True)
            return {
                "status": "success",
                "data": {"地址类型": "", "楼层": "", "架号": "", "框号": "", "包号": ""}
            }, 200

        # 【关键修改2】仅临时清洗当前要匹配的location_id，不修改原DataFrame的字段
        target_location_id = str(location_id).strip()
        print(f"[信息] 从inventory表获取最新记录：库存ID={latest_inv_id}，关联位置ID={target_location_id}", flush=True)

        # 5. 校验location表基础条件
        if location_df.empty:
            print(f"[信息] 获取最后地址信息：location表数据为空，返回默认值", flush=True)
            return {
                "status": "success",
                "data": {"地址类型": "", "楼层": "", "架号": "", "框号": "", "包号": ""}
            }, 200

        # 校验location表必要字段（匹配实际字段名）
        loc_required_cols = ["地址ID", "地址类型", "楼层", "架号", "框号", "包号"]
        loc_missing_cols = [col for col in loc_required_cols if col not in location_df.columns]
        if loc_missing_cols:
            print(f"[错误] location.csv缺少必要字段：{', '.join(loc_missing_cols)}", flush=True)
            return {
                "status": "error",
                "message": f"location.csv格式错误：缺少字段 {', '.join(loc_missing_cols)}，请检查CSV表头"
            }, 400

        # 6. 从location表匹配地址ID（仅临时转换要匹配的列，不修改原数据）
        # 【关键修改3】临时创建清洗后的地址ID列（不覆盖原列），用于匹配
        location_df["_temp_address_id"] = location_df["地址ID"].astype(str).str.strip()
        loc_filtered_df = location_df[location_df["_temp_address_id"] == target_location_id]
        # 匹配后删除临时列，不影响原数据
        location_df.drop(columns=["_temp_address_id"], inplace=True)

        if loc_filtered_df.empty:
            print(f"[信息] 获取最后地址信息：location表中无地址ID={target_location_id}的记录，返回默认值", flush=True)
            return {
                "status": "success",
                "data": {"地址类型": "", "楼层": "", "架号": "", "框号": "", "包号": ""}
            }, 200

        # 取匹配到的地址记录（地址ID唯一，取第一条）
        loc_record = loc_filtered_df.iloc[0]

        # 7. 提取并清洗地址信息
        address_type = str(loc_record.get("地址类型", "")).strip() if pd.notna(loc_record.get("地址类型")) else ""
        floor = str(loc_record.get("楼层", "")).strip() if pd.notna(loc_record.get("楼层")) else ""
        shelf_no = str(loc_record.get("架号", "")).strip() if pd.notna(loc_record.get("架号")) else ""
        box_no = str(loc_record.get("框号", "")).strip() if pd.notna(loc_record.get("框号")) else ""
        package_no = str(loc_record.get("包号", "")).strip() if pd.notna(loc_record.get("包号")) else ""

        print(
            f"[成功] 获取最后地址信息：库存ID={latest_inv_id} → 地址ID={target_location_id} - 地址类型={address_type}, 楼层={floor}, 架号={shelf_no}, 框号={box_no}, 包号={package_no}",
            flush=True
        )

        return {
            "status": "success",
            "data": {
                "地址类型": address_type,
                "楼层": floor,
                "架号": shelf_no,
                "框号": box_no,
                "包号": package_no
            }
        }, 200

    except Exception as e:
        error_msg = f"获取最后地址信息异常: {str(e)}"
        print(f"[异常] {error_msg}", flush=True)
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"系统异常: {str(e)}"}, 500