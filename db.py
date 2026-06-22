import psycopg2
import psycopg2.extras
import json
import os
from contextlib import contextmanager
from typing import List, Dict, Optional

# 数据库连接字符串，从环境变量读取（Streamlit Secrets 或服务器环境变量）
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/ceramic_studio")

@contextmanager
def get_db():
    """支持事务的数据库上下文管理器（PostgreSQL）"""
    conn = psycopg2.connect(DATABASE_URL)
    # 使用 RealDictCursor 让查询结果返回字典（与原 sqlite3.Row 行为一致）
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------- 原料操作 ----------
def add_material(name, category, material_type, analysis, stock, price, supplier) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                'INSERT INTO raw_materials (name, category, material_type, chem_analysis, stock_kg, price_per_kg, supplier) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s)',
                (name, category, material_type, json.dumps(analysis), stock, price, supplier)
            )
            return True
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return False

def get_all_materials(search: str = None, material_type: str = None) -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        query = 'SELECT id, name, category, material_type, chem_analysis, stock_kg, price_per_kg, supplier FROM raw_materials WHERE 1=1'
        params = []
        if search:
            query += ' AND name LIKE %s'
            params.append(f'%{search}%')
        if material_type and material_type != '全部':
            query += ' AND material_type = %s'
            params.append(material_type)
        query += ' ORDER BY name'
        cur.execute(query, params)
        rows = cur.fetchall()
    return [{
        "id": row['id'], "name": row['name'], "category": row['category'],
        "material_type": row['material_type'], "analysis": row['chem_analysis'],
        "stock_kg": row['stock_kg'], "price_per_kg": row['price_per_kg'],
        "supplier": row['supplier']
    } for row in rows]

def update_material(mat_id, name, category, material_type, analysis, stock, price, supplier) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                'UPDATE raw_materials SET name=%s, category=%s, material_type=%s, chem_analysis=%s, stock_kg=%s, price_per_kg=%s, supplier=%s WHERE id=%s',
                (name, category, material_type, json.dumps(analysis), stock, price, supplier, mat_id)
            )
            return True
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return False

def delete_material(mat_id) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        # 检查是否被配方或成品引用
        cur.execute('SELECT COUNT(*) FROM formula_ingredients WHERE material_id=%s', (mat_id,))
        used_in_formula = cur.fetchone()['count']
        cur.execute('SELECT COUNT(*) FROM ceramic_items WHERE clay_id=%s', (mat_id,))
        used_as_clay = cur.fetchone()['count']
        if used_in_formula or used_as_clay:
            return False
        cur.execute('DELETE FROM raw_materials WHERE id=%s', (mat_id,))
        return True

def seed_default_materials():
    if not get_all_materials():
        defaults = [
            ("钾长石", "原料棚", "釉用原料", {"K2O":10.0,"Na2O":2.0,"Al2O3":18.0,"SiO2":68.0,"LOI":2.0}, 5.0, 15.0, "景德镇矿料厂"),
            ("碳酸钙", "实验室", "釉用原料", {"CaO":56.0,"LOI":44.0}, 2.0, 8.0, "本地化工市场"),
            ("高岭土", "负一料堆", "泥料", {"Al2O3":40.0,"SiO2":50.0,"LOI":10.0}, 10.0, 5.0, "龙腾泥料"),
            ("石英", "原料棚", "釉用原料", {"SiO2":100.0}, 8.0, 10.0, "景德镇矿料厂"),
            ("紫砂泥", "负一料堆", "泥料", {"SiO2":65.0,"Al2O3":20.0,"Fe2O3":8.0,"LOI":5.0}, 20.0, 20.0, "宜兴泥料厂"),
            ("氧化钴", "实验室", "添加剂", {"CoO":100.0}, 0.5, 300.0, "上海国药"),
        ]
        for name, cat, mtype, ana, stock, price, sup in defaults:
            add_material(name, cat, mtype, ana, stock, price, sup)

# ---------- 配方操作 ----------
def save_formula(name, version, notes, category, ingredients) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        # 检查版本重复
        cur.execute('SELECT id FROM formulas WHERE name=%s AND version=%s', (name, version))
        if cur.fetchone():
            return False
        cur.execute(
            'INSERT INTO formulas (name, version, notes, category) VALUES (%s, %s, %s, %s) RETURNING id',
            (name, version, notes, category)
        )
        formula_id = cur.fetchone()['id']
        for item in ingredients:
            cur.execute(
                'INSERT INTO formula_ingredients (formula_id, material_id, quantity) VALUES (%s, %s, %s)',
                (formula_id, item['material_id'], item['quantity'])
            )
        return True

def update_formula_override(formula_id, name, version, notes, category, ingredients) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE formulas SET name=%s, version=%s, notes=%s, category=%s WHERE id=%s',
                    (name, version, notes, category, formula_id))
        cur.execute('DELETE FROM formula_ingredients WHERE formula_id=%s', (formula_id,))
        for item in ingredients:
            cur.execute('INSERT INTO formula_ingredients (formula_id, material_id, quantity) VALUES (%s, %s, %s)',
                        (formula_id, item['material_id'], item['quantity']))
        return True

def get_all_formulas(search: str = None, category: str = None) -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        query = 'SELECT id, name, version, notes, category, created_at FROM formulas WHERE 1=1'
        params = []
        if search:
            query += ' AND name LIKE %s'
            params.append(f'%{search}%')
        if category and category != '全部':
            query += ' AND category = %s'
            params.append(category)
        query += ' ORDER BY created_at DESC'
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(row) for row in rows]

def get_formula_details(formula_id) -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT fi.quantity, rm.name, rm.chem_analysis, rm.id as material_id, rm.stock_kg '
            'FROM formula_ingredients fi JOIN raw_materials rm ON fi.material_id = rm.id '
            'WHERE fi.formula_id = %s', (formula_id,)
        )
        rows = cur.fetchall()
    return [{
        "quantity": row['quantity'], "name": row['name'],
        "analysis": row['chem_analysis'],
        "material_id": row['material_id'], "stock_kg": row['stock_kg']
    } for row in rows]

def get_formula_batches(formula_id) -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            'SELECT gb.id, gb.batch_code, gb.total_weight_g, gb.stock_kg, gb.status, gb.created_at, f.name '
            'FROM glaze_batches gb JOIN formulas f ON gb.formula_id = f.id '
            'WHERE gb.formula_id = %s ORDER BY gb.created_at DESC',
            (formula_id,)
        )
        rows = cur.fetchall()
    return [dict(row) for row in rows]

def delete_formula(formula_id) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM glaze_batches WHERE formula_id=%s', (formula_id,))
        used = cur.fetchone()['count']
        if used:
            return False
        # 外键已设级联删除，但为安全仍先删成分
        cur.execute('DELETE FROM formula_ingredients WHERE formula_id=%s', (formula_id,))
        cur.execute('DELETE FROM formulas WHERE id=%s', (formula_id,))
        return True

# ---------- 釉料批次 ----------
def prepare_glaze_batch(formula_id, batch_code, target_dry_weight_g, water_weight_kg,
                        mill_type, ball_mill_hours, milling_date, storage_location, label_code,
                        ingredients_deduction) -> Optional[str]:
    with get_db() as conn:
        cur = conn.cursor()
        # 检查批次号唯一
        cur.execute('SELECT id FROM glaze_batches WHERE batch_code=%s', (batch_code,))
        if cur.fetchone():
            return f"批次号 {batch_code} 已存在"
        # 检查原料库存
        for item in ingredients_deduction:
            cur.execute('SELECT stock_kg FROM raw_materials WHERE id=%s', (item['material_id'],))
            stock = cur.fetchone()
            if not stock or stock['stock_kg'] < item['deduct_kg']:
                return f"原料 {item['name']} 库存不足 (需 {item['deduct_kg']:.3f}kg，现有 {stock['stock_kg']:.2f}kg)"
        # 计算釉浆总量
        dry_kg = target_dry_weight_g / 1000.0
        total_stock = dry_kg + water_weight_kg
        cur.execute('''
            INSERT INTO glaze_batches
            (batch_code, formula_id, total_weight_g, water_weight_kg, stock_kg,
             ball_mill_hours, mill_type, storage_location, label_code,
             milling_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (batch_code, formula_id, target_dry_weight_g, water_weight_kg, total_stock,
              ball_mill_hours, mill_type, storage_location, label_code,
              milling_date, '待球磨'))
        # 扣减原料库存
        for item in ingredients_deduction:
            cur.execute('UPDATE raw_materials SET stock_kg = stock_kg - %s WHERE id=%s',
                        (item['deduct_kg'], item['material_id']))
        return None

def update_batch_status(batch_id, new_status):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE glaze_batches SET status=%s WHERE id=%s', (new_status, batch_id))

def update_batch_params(batch_id, water_kg, ball_mill_hours):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE glaze_batches SET water_weight_kg=%s, ball_mill_hours=%s WHERE id=%s",
            (water_kg, ball_mill_hours, batch_id)
        )

def set_batch_ball_milling(batch_id, ball_mill_hours):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE glaze_batches SET status=%s, ball_mill_hours=%s WHERE id=%s',
                    ('球磨中', ball_mill_hours, batch_id))

def finish_batch_milling(batch_id):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE glaze_batches SET status=%s WHERE id=%s', ('已入库', batch_id))

def get_all_batches(status: str = None) -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        query = '''
            SELECT gb.id, gb.batch_code, f.name, gb.total_weight_g,
                   gb.water_weight_kg, gb.stock_kg, gb.ball_mill_hours,
                   gb.mill_type, gb.storage_location, gb.label_code,
                   gb.milling_date, gb.status, gb.created_at
            FROM glaze_batches gb
            JOIN formulas f ON gb.formula_id = f.id
        '''
        params = []
        if status and status != '全部':
            query += ' WHERE gb.status = %s'
            params.append(status)
        query += ' ORDER BY gb.created_at DESC'
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(row) for row in rows]

def deduct_glaze_stock(batch_id, deduct_kg) -> Optional[str]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('SELECT stock_kg FROM glaze_batches WHERE id=%s', (batch_id,))
        stock = cur.fetchone()
        if not stock or stock['stock_kg'] < deduct_kg:
            return "库存不足"
        new_stock = stock['stock_kg'] - deduct_kg
        if new_stock <= 0.0001:
            cur.execute('UPDATE glaze_batches SET stock_kg=0, status=%s WHERE id=%s',
                        ('已用完', batch_id))
        else:
            cur.execute('UPDATE glaze_batches SET stock_kg=%s WHERE id=%s',
                        (new_stock, batch_id))
        return None

# ---------- 烧成记录 ----------
def add_firing_record(date, kiln, atmo, temp, dynamic_records, notes):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO firing_records (firing_date, kiln_name, atmosphere, target_temp, dynamic_records, result_notes) '
            'VALUES (%s, %s, %s, %s, %s, %s)',
            (date, kiln, atmo, temp, json.dumps(dynamic_records), notes)
        )

def get_all_firings() -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM firing_records ORDER BY firing_date DESC')
        rows = cur.fetchall()
    return [dict(row) for row in rows]

# ---------- 成品 ----------
def add_ceramic_item(item_code, name, clay_id, batch_id, firing_id, status, price, location, notes) -> Optional[str]:
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                'INSERT INTO ceramic_items (item_code, name, clay_id, glaze_batch_id, firing_id, status, price, storage_location, notes) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (item_code, name, clay_id, batch_id, firing_id, status, price, location, notes)
            )
            return None
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            return f"作品编号 {item_code} 已存在，请更换"

def get_all_items(search: str = None, status: str = None) -> List[Dict]:
    with get_db() as conn:
        cur = conn.cursor()
        query = '''
            SELECT ci.id, ci.item_code, ci.name, ci.status, ci.price, ci.storage_location, ci.notes,
                   rm.name as clay_name, gb.batch_code, fr.firing_date, fr.kiln_name, fr.atmosphere, fr.target_temp
            FROM ceramic_items ci
            LEFT JOIN raw_materials rm ON ci.clay_id = rm.id
            LEFT JOIN glaze_batches gb ON ci.glaze_batch_id = gb.id
            LEFT JOIN firing_records fr ON ci.firing_id = fr.id
            WHERE 1=1
        '''
        params = []
        if search:
            query += ' AND (ci.name LIKE %s OR ci.item_code LIKE %s)'
            params.extend([f'%{search}%', f'%{search}%'])
        if status and status != '全部':
            query += ' AND ci.status = %s'
            params.append(status)
        query += ' ORDER BY ci.created_at DESC'
        cur.execute(query, params)
        rows = cur.fetchall()
    return [dict(row) for row in rows]

def update_item_status(item_id, new_status):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute('UPDATE ceramic_items SET status=%s WHERE id=%s', (new_status, item_id))
