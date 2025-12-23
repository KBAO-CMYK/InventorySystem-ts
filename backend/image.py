import os
import datetime
import functools
import pandas as pd
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# ===================== 图片上传配置（新增缓存配置） =====================
# 图片上传文件夹（项目根目录下的image文件夹）
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'image')
# 特征表路径（根据实际项目路径调整）
FEATURE_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'feature.csv')
# 允许的图片格式
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
# 最大文件大小限制（16MB）
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

# 缓存配置（可根据需求调整）
HTTP_CACHE_HOURS = 24  # 浏览器HTTP缓存时长（小时）
MEMORY_CACHE_MAX_SIZE = 100  # 服务器内存缓存最大图片数量（LRU）
MEMORY_CACHE_EXPIRE_HOURS = 12  # 内存缓存有效期（小时）

# 内存缓存存储（key: 图片相对路径, value: (缓存时间戳, 图片二进制数据)）
image_memory_cache = {}


# ===================== 缓存工具函数（新增特征ID关联清理） =====================
def init_image_cache():
    """初始化图片缓存：清理过期缓存 + 控制缓存大小"""
    try:
        cache_count = 0
        # 清理过期缓存
        for relative_path in list(image_memory_cache.keys()):
            cache_time, _ = image_memory_cache[relative_path]
            if datetime.datetime.now().timestamp() - cache_time > MEMORY_CACHE_EXPIRE_HOURS * 3600:
                del image_memory_cache[relative_path]
                print(f"[缓存] 清理过期缓存：{relative_path}", flush=True)
            else:
                cache_count += 1

        # 超出最大缓存数，删除最早的缓存（FIFO）
        if cache_count > MEMORY_CACHE_MAX_SIZE:
            delete_count = cache_count - MEMORY_CACHE_MAX_SIZE
            oldest_keys = list(image_memory_cache.keys())[:delete_count]
            for key in oldest_keys:
                del image_memory_cache[key]
                print(f"[缓存] 超出最大缓存数，删除最早缓存：{key}", flush=True)
        print(f"[缓存] 初始化完成，当前缓存数量：{len(image_memory_cache)}", flush=True)
    except Exception as e:
        print(f"[缓存] 初始化失败：{str(e)}", flush=True)


def clear_image_cache_by_product_code(product_code):
    """
    根据货号清理相关缓存（保证缓存一致性）
    兼容入参类型：单个货号字符串 / 货号列表（如 ['WJ15694']）
    :param product_code: 货号（str | list[str]）
    """
    try:
        deleted_keys = []
        # 核心修复：统一将入参转为列表，兼容单/多货号场景
        product_codes = []
        if isinstance(product_code, list):
            # 若传入列表，过滤空值+转为字符串
            product_codes = [str(pc).strip() for pc in product_code if pc and str(pc).strip()]
        elif isinstance(product_code, str) and product_code.strip():
            # 若传入单个字符串，转为列表统一处理
            product_codes = [product_code.strip()]
        else:
            # 空值/非字符串/空字符串，直接返回
            print(f"[缓存] 货号参数无效：{product_code}（需为非空字符串/字符串列表）", flush=True)
            return

        # 遍历所有缓存键，匹配货号并删除
        for cache_key in list(image_memory_cache.keys()):  # list()避免遍历中字典长度变化
            # 遍历每个货号，匹配缓存键
            for pc in product_codes:
                if pc in cache_key:  # 此时pc是字符串，避免"list in string"错误
                    del image_memory_cache[cache_key]
                    deleted_keys.append({"货号": pc, "缓存键": cache_key})
                    break  # 匹配到后跳出，避免重复删除

        # 清理lru_cache装饰器的缓存（原有逻辑保留）
        get_image_full_path.cache_clear()
        read_image_file.cache_clear()

        # 优化日志输出
        if deleted_keys:
            print(f"[缓存] 清理货号[{product_codes}]相关缓存成功：{deleted_keys}", flush=True)
        else:
            print(f"[缓存] 货号[{product_codes}]无相关缓存可清理", flush=True)

    except Exception as e:
        # 错误日志增加入参信息，便于定位问题
        print(f"[缓存] 清理货号[{product_code}]缓存失败：{str(e)}", flush=True)


def clear_image_cache_by_feature_id(feature_id):
    """新增：根据特征ID清理相关缓存（适配特征ID=0）"""
    try:
        # 先从特征表获取该特征ID对应的货号
        product_code = get_product_code_by_feature_id(feature_id)
        if product_code:
            clear_image_cache_by_product_code(product_code)
        # 额外清理含特征ID的缓存（如有）
        deleted_keys = []
        for cache_key in list(image_memory_cache.keys()):
            if f"feature_{feature_id}_" in cache_key:
                del image_memory_cache[cache_key]
                deleted_keys.append(cache_key)
        if deleted_keys:
            print(f"[缓存] 清理特征ID[{feature_id}]相关缓存：{deleted_keys}", flush=True)
    except Exception as e:
        print(f"[缓存] 清理特征ID[{feature_id}]缓存失败：{str(e)}", flush=True)


def clear_all_image_cache():
    """清空所有图片缓存（手动调用）"""
    try:
        image_memory_cache.clear()
        get_image_full_path.cache_clear()
        read_image_file.cache_clear()
        print(f"[缓存] 清空所有图片缓存成功", flush=True)
    except Exception as e:
        print(f"[缓存] 清空所有缓存失败：{str(e)}", flush=True)


# ===================== 特征表操作工具函数（核心新增） =====================
def get_product_code_by_feature_id(feature_id):
    """根据特征ID获取对应货号（适配特征ID=0）"""
    try:
        if not os.path.exists(FEATURE_CSV_PATH):
            print(f"[特征表] 特征表不存在：{FEATURE_CSV_PATH}", flush=True)
            return ""

        feature_df = pd.read_csv(FEATURE_CSV_PATH, encoding="utf-8-sig")
        feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce").fillna(-1).astype(int)
        target = feature_df[feature_df["商品特征ID"] == int(feature_id)]

        if target.empty:
            print(f"[特征表] 特征ID[{feature_id}]不存在", flush=True)
            return ""

        # 兼容货号为0的场景
        product_code = target.iloc[0].get("货号", "")
        return str(product_code).strip() if product_code is not None else ""
    except Exception as e:
        print(f"[特征表] 获取特征ID[{feature_id}]货号失败：{str(e)}", flush=True)
        return ""


def update_feature_image_path(feature_id, image_relative_path, host="127.0.0.1:5000"):
    """
    更新特征表的图片路径（核心修复：仅改图片路径，保留原关联商品ID）
    :param feature_id: 特征ID（支持0）
    :param image_relative_path: 图片相对路径（如image/货号_时间戳.jpg）
    :param host: 服务器地址（用于拼接图片访问URL）
    :return: 是否更新成功
    """
    try:
        if not os.path.exists(FEATURE_CSV_PATH):
            print(f"[特征表] 特征表不存在：{FEATURE_CSV_PATH}", flush=True)
            return False

        # 读取特征表并处理字段类型
        feature_df = pd.read_csv(FEATURE_CSV_PATH, encoding="utf-8-sig")
        feature_df["商品特征ID"] = pd.to_numeric(feature_df["商品特征ID"], errors="coerce").fillna(-1).astype(int)
        feature_mask = feature_df["商品特征ID"] == int(feature_id)

        if not feature_mask.any():
            print(f"[特征表] 特征ID[{feature_id}]不存在，无法更新图片路径", flush=True)
            return False

        # 关键：保留原有关联商品ID（防止篡改）
        original_product_id = feature_df.loc[feature_mask, "关联商品ID"].iloc[0]
        print(f"[特征表] 特征ID[{feature_id}]原关联商品ID：{original_product_id}", flush=True)

        # 仅更新图片相关字段，不修改任何关联ID
        feature_df.loc[feature_mask, "图片路径"] = image_relative_path
        feature_df.loc[feature_mask, "图片"] = f"http://{host}/{image_relative_path}"

        # 强制写回原有商品ID（双重防护）
        feature_df.loc[feature_mask, "关联商品ID"] = original_product_id

        # 保存特征表
        feature_df.to_csv(FEATURE_CSV_PATH, index=False, encoding="utf-8-sig")
        print(f"[特征表] 特征ID[{feature_id}]图片路径更新成功，路径：{image_relative_path}", flush=True)
        return True
    except Exception as e:
        print(f"[特征表] 更新特征ID[{feature_id}]图片路径失败：{str(e)}", flush=True)
        return False


# ===================== 基础工具函数（原有逻辑 + 缓存优化 + 特征ID适配） =====================
# 确保image文件夹存在（启动时/运行中都检查）
def ensure_upload_folder():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        print(f"[信息] 创建/检查图片上传文件夹: {UPLOAD_FOLDER}", flush=True)
    # 启动时初始化缓存
    init_image_cache()


ensure_upload_folder()


def allowed_file(filename):
    """检查文件是否为允许的图片格式"""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_product_image(product_code, file, feature_id=None, host="127.0.0.1:5000"):
    """
    保存商品图片到image文件夹（保留原有命名规则：货号_时间戳.后缀）
    核心修改：
    1. 支持传入feature_id，保存后自动更新对应特征的图片路径（仅改路径，保留原关联商品ID）
    2. 保存前清理该货号/特征ID的旧图片缓存，保证缓存一致性
    3. 兼容货号/特征ID=0的合法场景
    :param product_code: 商品货号（支持0）
    :param file: 上传的文件对象
    :param feature_id: 特征ID（可选，支持0）
    :param host: 服务器地址（用于拼接图片URL）
    :return: 图片相对路径（如：image/货号_时间戳.jpg），失败返回空字符串
    """
    # 1. 基础参数校验
    if product_code is None:  # 仅判断None，0/空字符串为合法货号
        print(f"[警告] 图片保存失败：商品货号为None", flush=True)
        return ""
    if not file or not file.filename:
        print(f"[警告] 商品{product_code}无上传图片", flush=True)
        return ""
    if not allowed_file(file.filename):
        print(f"[警告] 商品{product_code}图片格式不支持：{file.filename}，允许格式：{ALLOWED_EXTENSIONS}", flush=True)
        return ""

    # 2. 文件大小检查（防止超过限制）
    if hasattr(file, 'content_length') and file.content_length > MAX_CONTENT_LENGTH:
        print(f"[警告] 商品{product_code}图片过大：{file.content_length / 1024 / 1024:.2f}MB，最大允许16MB", flush=True)
        return ""

    try:
        # 核心：保存新图片前，清理关联缓存（货号+特征ID）
        clear_image_cache_by_product_code(product_code)
        if feature_id is not None:
            clear_image_cache_by_feature_id(feature_id)

        # 安全处理文件名，避免恶意路径/特殊字符
        filename = secure_filename(file.filename)
        # 提取文件扩展名
        ext = filename.rsplit('.', 1)[1].lower()
        # 保留原有命名规则：货号+毫秒时间戳（兼容货号=0）
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')[:-3]  # 毫秒级时间戳
        new_filename = f"{product_code}_{timestamp}.{ext}"
        # 完整保存路径
        save_path = os.path.join(UPLOAD_FOLDER, new_filename)
        # 保存文件
        ensure_upload_folder()
        file.save(save_path)

        # 返回相对路径
        relative_path = f"image/{new_filename}"
        print(f"[信息] 商品{product_code}图片保存成功：{relative_path} | 绝对路径：{save_path}", flush=True)

        # 核心：如果传入feature_id，更新特征表图片路径（仅改路径，保留原关联商品ID）
        if feature_id is not None:
            update_feature_image_path(feature_id, relative_path, host)

        return relative_path
    except RequestEntityTooLarge:
        print(f"[错误] 商品{product_code}图片过大：超过16MB限制", flush=True)
        return ""
    except PermissionError:
        print(f"[错误] 商品{product_code}图片保存失败：无文件写入权限，路径：{save_path}", flush=True)
        return ""
    except Exception as e:
        print(f"[错误] 商品{product_code}图片保存失败：{str(e)}", flush=True)
        return ""


def parse_uploaded_images(uploaded_files, feature_code_mapping, host="127.0.0.1:5000"):
    """
    解析上传的图片文件，生成【特征ID→图片路径】的映射（核心修改）
    保留原有字段名规则（image_货号），但通过 feature_code_mapping 关联到特征ID
    新增：保存图片后自动更新特征表，保留原关联商品ID
    :param uploaded_files: Flask request.files 对象
    :param feature_code_mapping: dict {特征ID(int): 货号(str)} - 特征ID与货号的映射关系（支持0）
    :param host: 服务器地址
    :return: dict {特征ID(int): 图片相对路径} - 一个特征ID仅保留一张图片
    """
    feature_images = {}
    if not uploaded_files:
        print(f"[警告] 无上传的图片文件", flush=True)
        return feature_images
    if not feature_code_mapping or not isinstance(feature_code_mapping, dict):
        print(f"[警告] 特征ID-货号映射关系为空/格式错误", flush=True)
        return feature_images

    # 第一步：先解析所有货号对应的图片（保留原有逻辑，兼容货号=0）
    code_images = {}
    for field_name, file in uploaded_files.items():
        if not field_name.startswith('image_') or not file.filename:
            continue
        # 提取货号（原有逻辑不变，兼容货号=0）
        product_code = field_name[len('image_'):].strip()
        if product_code is None:
            print(f"[警告] 图片字段名格式错误：{field_name}（货号为None）", flush=True)
            continue
        # 保存图片（不传入feature_id，后续统一更新）
        img_path = save_product_image(product_code, file, host=host)
        if img_path:
            code_images[product_code] = img_path  # 一个货号仅保留最新的一张

    # 第二步：映射为特征ID→图片路径（核心：一个特征ID对应一张，支持ID=0）
    for feature_id, product_code in feature_code_mapping.items():
        if product_code in code_images:
            feature_id_int = int(feature_id)  # 兼容字符串类型的特征ID
            feature_images[feature_id_int] = code_images[product_code]
            # 额外更新特征表（双重保障）
            update_feature_image_path(feature_id_int, code_images[product_code], host)
            print(f"[信息] 特征ID[{feature_id_int}]关联货号[{product_code}]的图片：{code_images[product_code]}",
                  flush=True)

    return feature_images


# ===================== 图片读取相关功能（修改版：添加缓存逻辑） =====================
@functools.lru_cache(maxsize=MEMORY_CACHE_MAX_SIZE)
def get_image_full_path(relative_path):
    """
    保留原有路径校验逻辑，添加LRU缓存优化
    :param relative_path: 图片相对路径（如image/货号_时间戳.jpg）
    :return: 完整文件路径，路径非法返回None
    """
    if relative_path is None or not isinstance(relative_path, str):  # 仅判断None/非字符串，空字符串单独处理
        print(f"[警告] 图片相对路径非法：None/非字符串类型", flush=True)
        return None
    if not relative_path.startswith('image/'):
        print(f"[警告] 图片相对路径格式错误：{relative_path}（必须以image/开头）", flush=True)
        return None

    filename = relative_path.replace('image/', '', 1)
    full_path = os.path.normpath(os.path.join(UPLOAD_FOLDER, filename))

    if not full_path.startswith(UPLOAD_FOLDER):
        print(f"[警告] 图片路径越权：{full_path}（不在允许的目录内）", flush=True)
        return None
    if not os.path.exists(full_path):
        print(f"[警告] 图片文件不存在：{full_path}", flush=True)
        return None
    if not os.path.isfile(full_path):
        print(f"[警告] 路径不是文件：{full_path}", flush=True)
        return None

    return full_path


def check_image_exists(relative_path):
    """保留原有逻辑"""
    full_path = get_image_full_path(relative_path)
    return full_path is not None


def read_image_file(relative_path, mode='rb'):
    """
    保留原有逻辑，新增内存缓存优化：优先从缓存读取，无缓存则读取文件并写入缓存
    :param relative_path: 图片相对路径
    :param mode: 读取模式
    :return: 图片二进制数据/None
    """
    # 1. 优先从内存缓存读取
    if relative_path in image_memory_cache:
        cache_time, cache_data = image_memory_cache[relative_path]
        # 检查缓存是否过期
        if datetime.datetime.now().timestamp() - cache_time < MEMORY_CACHE_EXPIRE_HOURS * 3600:
            print(f"[缓存] 从内存读取图片：{relative_path} | 大小：{len(cache_data) / 1024:.2f}KB", flush=True)
            return cache_data
        else:
            # 过期则删除缓存
            del image_memory_cache[relative_path]
            print(f"[缓存] 图片缓存过期，删除：{relative_path}", flush=True)

    # 2. 原有文件读取逻辑
    full_path = get_image_full_path(relative_path)
    if not full_path:
        return None

    if not os.access(full_path, os.R_OK):
        print(f"[错误] 读取图片失败：无读取权限，路径：{full_path}", flush=True)
        return None

    try:
        with open(full_path, mode) as f:
            content = f.read()

        # 3. 将读取结果写入内存缓存
        image_memory_cache[relative_path] = (datetime.datetime.now().timestamp(), content)
        # 控制缓存大小（超出则删除最早的）
        if len(image_memory_cache) > MEMORY_CACHE_MAX_SIZE:
            oldest_key = next(iter(image_memory_cache.keys()))
            del image_memory_cache[oldest_key]
            print(f"[缓存] 超出最大缓存数，删除最早缓存：{oldest_key}", flush=True)

        print(f"[信息] 读取图片成功：{relative_path} | 大小：{len(content) / 1024:.2f}KB（已写入缓存）", flush=True)
        return content
    except PermissionError:
        print(f"[错误] 读取图片失败：无读取权限，路径：{full_path}", flush=True)
        return None
    except Exception as e:
        print(f"[错误] 读取图片失败 {relative_path}：{str(e)}", flush=True)
        return None


def batch_get_feature_image_by_ids(feature_ids, feature_image_mapping):
    """
    批量根据特征ID查询关联的图片（同步适配ID=0、路径校验等逻辑）
    :param feature_ids: 商品特征ID列表（支持0，元素可为字符串/数字类型）
    :param feature_image_mapping: dict {特征ID(int): 图片相对路径(str)} - 特征ID与图片路径的映射关系
    :return: dict {特征ID(str): 图片相对路径(str)} - 批量查询结果（无有效路径则值为空字符串）
    """
    # 初始化返回结果
    result = {str(fid): "" for fid in feature_ids}
    if not feature_ids:
        print(f"[警告] 批量查询特征图片失败：特征ID列表为空", flush=True)
        return result

    if not feature_image_mapping:
        print(f"[警告] 批量查询特征图片失败：映射表为空", flush=True)
        for fid in feature_ids:
            print(f"[警告] 特征ID[{fid}]无对应的图片路径映射（映射表为空）", flush=True)
        return result

    # 批量处理每个特征ID（兼容0值）
    for fid in feature_ids:
        # 1. 参数校验 - 同步支持ID=0，仅判断None
        if fid is None:
            print(f"[警告] 批量查询特征图片失败：特征ID为None", flush=True)
            continue

        try:
            feature_id_int = int(fid)  # 0转int后合法，非数字会抛异常
        except (ValueError, TypeError):
            print(f"[警告] 批量查询特征图片失败：特征ID格式错误（非数字）：{fid}", flush=True)
            continue

        # 2. 检查映射关系（支持ID=0）
        if feature_id_int not in feature_image_mapping:
            print(f"[警告] 特征ID[{feature_id_int}]无对应的图片路径映射", flush=True)
            continue

        # 3. 获取并校验图片路径
        feature_image_path = feature_image_mapping[feature_id_int]
        # 校验路径是否为None（空字符串单独处理）
        if feature_image_path is None:
            print(f"[警告] 特征ID[{feature_id_int}]对应的图片路径为None", flush=True)
            continue

        # 4. 校验路径格式合法性（扩展名）
        if not allowed_file(os.path.basename(feature_image_path)):
            print(f"[警告] 特征ID[{feature_id_int}]对应的图片路径格式不合法：{feature_image_path}", flush=True)
            continue

        # 5. 校验文件物理存在性
        # 拼接绝对路径（与单个查询函数逻辑完全一致）
        absolute_path = os.path.join(UPLOAD_FOLDER, feature_image_path.replace("image/", ""))
        if not os.path.exists(absolute_path):
            print(f"[警告] 特征ID[{feature_id_int}]对应的图片文件不存在：{absolute_path}", flush=True)
            continue

        # 6. 所有校验通过，赋值有效路径
        result[str(fid)] = feature_image_path
        print(f"[信息] 特征ID[{feature_id_int}]找到图片路径：{feature_image_path}", flush=True)

    return result


def get_image_mime_type(relative_path):
    """保留原有逻辑：根据图片路径获取MIME类型"""
    if relative_path is None or not '.' in relative_path:  # 仅判断None，空字符串/0（路径不会是0）单独处理
        return 'application/octet-stream'

    ext = relative_path.rsplit('.', 1)[1].lower()
    mime_map = {
        'png': 'image/png',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'webp': 'image/webp'
    }
    return mime_map.get(ext, 'application/octet-stream')


# ===================== 缓存管理辅助函数（新增，供外部调用） =====================
def get_image_cache_info():
    """获取缓存状态信息（供监控/调试）"""
    return {
        "cache_count": len(image_memory_cache),
        "max_cache_size": MEMORY_CACHE_MAX_SIZE,
        "expire_hours": MEMORY_CACHE_EXPIRE_HOURS,
        "cached_paths": list(image_memory_cache.keys())
    }

