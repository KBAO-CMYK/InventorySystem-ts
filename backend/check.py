from flask import jsonify, Response
import pandas as pd
import io
import csv
from datetime import datetime
import threading  # 新增：并发控制
from utils import *
from config import *
from inventory_management import *
from get import *

# ===================== 新增：全局库存锁（保证校验+操作的原子性） =====================
inventory_locks = {}


def get_inventory_lock(inventory_id):
    if inventory_id not in inventory_locks:
        inventory_locks[inventory_id] = threading.Lock()
    return inventory_locks[inventory_id]


# ===================== 核心：适配第一条入库-1的校验函数 =====================
def check_stock_quantity(inventory_id, operation_type, operation_quantity, csv_data):
    """
    库存数量校验规则：
    1. 第一条入库操作数量=-1 → 该库存的出库/借/还跳过充足性校验；
    2. 基础格式校验（数字类型）仍保留；
    3. 非第一条入库-1的场景，出库/借仍需校验充足性。
    :param inventory_id: 库存ID（int，支持0）
    :param operation_type: 操作类型（str，出库/借/还/入库）
    :param operation_quantity: 操作数量（float/int）
    :param csv_data: 已读取的CSV数据
    :return: (是否校验通过, 提示信息, 当前库存数量)
    """
    current_stock = 0.0
    valid_types = ["出库", "借", "还", "入库"]

    # 1. 操作类型合法性校验
    if operation_type not in valid_types:
        return False, f"操作类型错误，仅支持：{','.join(valid_types)}", current_stock

    # 2. 基础格式校验（必须是数字）
    try:
        op_quantity = float(operation_quantity)
    except (ValueError, TypeError):
        return False, f"{operation_type}数量格式错误，必须为数字（当前值：{operation_quantity}）", current_stock

    # 3. 判断是否为「第一条入库-1」的特殊库存
    is_special_stock = False  # 标记是否为特殊库存
    with get_inventory_lock(inventory_id):
        operation_df = csv_data.get("operation_record", pd.DataFrame())
        inv_ops = operation_df[operation_df["关联库存ID"] == inventory_id] if not operation_df.empty else pd.DataFrame()

        # 检查第一条记录是否是入库且数量=-1
        if len(inv_ops) > 0:
            first_op = inv_ops.iloc[0]
            if first_op["操作类型"] == "入库" and float(first_op["操作数量"]) == -1:
                is_special_stock = True

    # 4. 特殊库存：出库/借/还仅校验格式（数量>0），跳过充足性校验
    if is_special_stock and operation_type in ["出库", "借", "还"]:
        if op_quantity <= 0:
            return False, f"{operation_type}数量必须大于0（当前值：{op_quantity}）", current_stock
        # 特殊库存直接返回通过，当前库存标记为-1（未知）
        return True, f"库存ID {inventory_id} 为特殊库存（第一条入库=-1），{operation_type}跳过充足性校验", -1.0

    # 5. 常规库存：第一条入库-1（无历史记录）的入库操作
    if operation_type == "入库" and len(inv_ops) == 0 and op_quantity == -1:
        return True, f"库存ID {inventory_id} 第一条入库数量=-1，跳过校验", -1.0

    # 6. 常规库存：非第一条入库-1的入库操作（数量必须>0）
    if operation_type == "入库":
        if op_quantity <= 0 and op_quantity != -1:
            return False, f"入库数量必须大于0（当前值：{op_quantity}）", current_stock
        return True, f"入库数量校验通过", current_stock

    # 7. 常规库存：出库/借需校验充足性
    with get_inventory_lock(inventory_id):
        try:
            if not inv_ops.empty:
                total_in = sum(inv_ops[inv_ops["操作类型"] == "入库"]["操作数量"])
                total_out = sum(inv_ops[inv_ops["操作类型"] == "出库"]["操作数量"])
                total_lend = sum(inv_ops[inv_ops["操作类型"] == "借"]["操作数量"])
                total_return = sum(inv_ops[inv_ops["操作类型"] == "还"]["操作数量"])
                current_stock = total_in - total_out - total_lend + total_return

            if operation_type in ["出库", "借"]:
                if current_stock < op_quantity:
                    return False, f"{operation_type}失败：库存ID {inventory_id} 当前库存{current_stock}，需{op_quantity}，库存不足", current_stock

            return True, f"{operation_type}数量校验通过，库存ID {inventory_id} 当前库存：{current_stock}", current_stock
        except Exception as e:
            return False, f"库存数量校验异常：{str(e)}", current_stock