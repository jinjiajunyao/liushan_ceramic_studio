import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import json
import time
from datetime import datetime
from db import (
    init_db, seed_default_materials,
    add_material, get_all_materials, update_material, delete_material,
    save_formula, update_formula_override, get_formula_batches, get_all_formulas, get_formula_details, delete_formula,
    prepare_glaze_batch, update_batch_status, set_batch_ball_milling, finish_batch_milling, get_all_batches, deduct_glaze_stock,
    add_firing_record, get_all_firings,
    add_ceramic_item, get_all_items, update_item_status,
    update_batch_params,get_db
)
from algo import calculate_seger
OXIDE_NAMES_CN = {
    "SiO2": "二氧化硅", "Al2O3": "氧化铝", "B2O3": "氧化硼",
    "K2O": "氧化钾", "Na2O": "氧化钠", "Li2O": "氧化锂",
    "CaO": "氧化钙", "MgO": "氧化镁", "ZnO": "氧化锌",
    "BaO": "氧化钡", "SrO": "氧化锶", "PbO": "氧化铅",
    "TiO2": "氧化钛", "ZrO2": "氧化锆", "SnO2": "二氧化锡",
    "P2O5": "五氧化二磷", "Fe2O3": "氧化铁", "CuO": "氧化铜",
    "CoO": "氧化钴", "MnO": "氧化亚锰", "LOI": "烧失量"
}
from ui import render_oxide_inputs, material_card

# 初始化
seed_default_materials()

st.set_page_config(page_title="陶瓷工作室数字工作台", page_icon="🏺", layout="wide")

page = st.sidebar.radio("导航", ["📦 原料库", "📋️ 配方中心", "⚗️ 制备中心", "🔥 烧成中心", "🏺 成品仓库"])

# 通用 session_state 初始化
if 'recipe_items' not in st.session_state:
    st.session_state.recipe_items = []
if 'editing_mat_id' not in st.session_state:
    st.session_state.editing_mat_id = None
if 'selected_mat_id' not in st.session_state:
    st.session_state.selected_mat_id = None
if 'confirm_delete' not in st.session_state:
    st.session_state.confirm_delete = None  # 记录待删除的原料ID

# ==================== 原料库 ====================
if page == "📦 原料库":
    st.header("📦 原料库")
    
    
    col_list, col_detail = st.columns([1, 1])
    
    with col_list:


        # 搜索和筛选
        col_s1, col_s2, col_s3  = st.columns([1, 1, 1,], vertical_alignment="bottom")
        with col_s1:
            search_term = st.text_input("🔍 搜索原料名称", placeholder="输入关键字...", key="mat_search")
        with col_s2:
            type_filter = st.selectbox("类型", ["全部","泥料","釉用原料","添加剂","其它"], key="mat_type")
        with col_s3:
            if st.button("➕ 新增原料", use_container_width=True):
                st.session_state.editing_mat_id = "NEW"
                st.session_state.selected_mat_id = None
                st.rerun()

        materials = get_all_materials(search=search_term, material_type=type_filter)
        
        # 网格展示
        for i in range(0, len(materials), 3):
            c1, c2, c3 = st.columns(3)
            for col, idx in zip([c1,c2,c3], range(i, min(i+3, len(materials)))):
                with col:
                    mat = materials[idx]
                    if material_card(mat, st.session_state.selected_mat_id, "mat_card"):
                        st.session_state.selected_mat_id = mat['id']
                        st.session_state.editing_mat_id = None
                        st.rerun()
    
    with col_detail:
        target_id = st.session_state.editing_mat_id or st.session_state.selected_mat_id
        
        if target_id is None:
            st.info("👈 从左侧选择一种原料，或点击新增。")
        
        elif target_id == "NEW":
            st.subheader("➕ 新原料")
            with st.form("add_material_form"):
                # ----- 第一行：三列 -----
                col1, col2, col3 = st.columns(3)
                with col1:
                    name = st.text_input("名称")
                with col2:
                    cat = st.selectbox("存放位置", ["负一料堆","实验室","工房二楼","电窑房","原料棚"])
                with col3:
                    mtype = st.selectbox("原料类型", ["釉用原料","泥料","添加剂","其它"])

                # ----- 第二行：三列 -----
                col4, col5, col6 = st.columns(3)
                with col4:
                    stock = st.number_input("入库量 (kg)", min_value=0.0, step=0.1, format="%.2f")
                with col5:
                    price = st.number_input("单价 (元/kg)", min_value=0.0, step=1.0, format="%.2f")
                with col6:
                    supplier = st.text_input("供应商")
                st.markdown("---")
                # 成分分析（单独一行）
                analysis = render_oxide_inputs("new", {})

                # 按钮（两列）
                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.form_submit_button("💾 保存"):
                    if not name:
                        st.error("名称不能为空")
                    elif add_material(name, cat, mtype, analysis, stock, price, supplier):
                        st.success("添加成功！")
                        st.session_state.editing_mat_id = None
                        st.rerun()
                    else:
                        st.error("名称已存在，请更换")
                if col_btn2.form_submit_button("取消"):
                    st.session_state.editing_mat_id = None
                    st.rerun()
        
        else:
            mat = next((m for m in materials if m['id'] == target_id), None)
            if not mat:
                st.error("原料不存在")
                st.session_state.selected_mat_id = None
                st.rerun()
            
            # 查看/编辑模式
            if st.session_state.editing_mat_id == mat['id']:
                st.subheader("✏️ 编辑原料")
                with st.form(f"edit_mat_{mat['id']}"):
                    # ----- 第一行：名称、位置、类型 -----
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        e_name = st.text_input("名称", value=mat['name'])
                    with col2:
                        e_cat = st.selectbox(
                            "位置",
                            ["负一料堆", "实验室", "工房二楼", "电窑房", "原料棚"],
                            index=(["负一料堆", "实验室", "工房二楼", "电窑房", "原料棚"].index(mat['category'])
                                   if mat['category'] in ["负一料堆", "实验室", "工房二楼", "电窑房", "原料棚"] else 0)
                        )
                    with col3:
                        e_type = st.selectbox(
                            "类型",
                            ["釉用原料", "泥料", "添加剂", "其它"],
                            index=(["釉用原料", "泥料", "添加剂", "其它"].index(mat['material_type'])
                                   if mat['material_type'] in ["釉用原料", "泥料", "添加剂", "其它"] else 0)
                        )

                    # ----- 第二行：库存、单价、供应商 -----
                    col4, col5, col6 = st.columns(3)
                    with col4:
                        e_stock = st.number_input("库存 (kg)", value=float(mat['stock_kg']), min_value=0.0, step=0.1)
                    with col5:
                        e_price = st.number_input("单价", value=float(mat['price_per_kg']), min_value=0.0)
                    with col6:
                        e_supplier = st.text_input("供应商", value=mat['supplier'])
                    st.markdown("---")
                    # 成分分析（单独一行）
                    e_analysis = render_oxide_inputs(f"edit_{mat['id']}", mat['analysis'])
                    
                    c1, c2, c3 = st.columns(3)
                    if c1.form_submit_button("💾 保存"):
                        if update_material(mat['id'], e_name, e_cat, e_type, e_analysis, e_stock, e_price, e_supplier):
                            st.success("已更新")
                            st.session_state.editing_mat_id = None
                            st.rerun()
                        else:
                            st.error("名称重复，保存失败")
                    if c2.form_submit_button("取消"):
                        st.session_state.editing_mat_id = None
                        st.rerun()
                    if c3.form_submit_button("🗑️ 删除"):
                        st.session_state.confirm_delete = mat['id']
                        st.rerun()
            else:
                # 查看详情
                col_name, col_btn = st.columns([3,1])
                with col_name:
                    st.subheader(mat['name'])
                with col_btn:
                    if st.button("✏️ 编辑"):
                        st.session_state.editing_mat_id = mat['id']
                        st.rerun()
                
                st.write(
    f"**类型**: {mat['material_type']} | **位置**: {mat['category']} | "
    f"**库存**: {mat['stock_kg']:.2f} kg | **单价**: ¥{mat['price_per_kg']:.1f}/kg | "
    f"**供应商**: {mat['supplier'] or '未知'}"
)
                if mat['stock_kg'] < 1.0:
                    st.warning("⚠️ 库存偏低，请及时补充")
                with st.expander("化学成分", expanded=True):
                    if mat['analysis']:
        # 氧化物英文 -> 中文映射
                        filtered = {k: v for k, v in mat['analysis'].items() if v > 0}

                        if not filtered:
                            st.write("无有效成分数据")
                        else:
                            chinese_labels = [OXIDE_NAMES_CN.get(ox, ox) for ox in filtered.keys()]
                            values_list = list(filtered.values())
            # 构建只有一行的 DataFrame，列名是中文成分名
                            df_horizontal = pd.DataFrame([values_list], columns=chinese_labels)
                            st.dataframe(df_horizontal, width='stretch', hide_index=True)

                            st.markdown("---")  # 表格和饼图之间的分隔线

            # ---- 2. 饼图（在表格下方） ----
                            labels = chinese_labels
                            values = values_list
                            total_val = sum(values)
                            threshold = 0.03  # 5% 以下的成分不直接显示标签
                            custom_text = [
                                f"{label}<br>{val:.1f}%"
                                if (val / total_val * 100) >= 3
                                else ""   # 占比小于 5% 的标签留空
                                for label, val in zip(labels, values)
                            ]

                            fig = go.Figure(data=[go.Pie(
                                labels=labels,
                                values=values,
                                hole=0.45,
                                text=custom_text,
                                textinfo='text',          # 使用我们自定义的文本
                                textfont_size=13,
                                marker=dict(line=dict(color='white', width=1)),
                                hoverinfo='label+percent' # 鼠标悬停时显示完整信息
                            )])

                            fig.update_layout(
                                margin=dict(t=10, b=10, l=10, r=10),
                                height=600,
                                showlegend=True,          # 显示图例，方便看全所有成分
                                legend=dict(
                                    orientation="h",      # 水平排列图例
                                    yanchor="bottom",
                                    y=-0.3,
                                    xanchor="center",
                                    x=0.5
                                )
                            )

                            st.plotly_chart(fig, width='stretch')
                    else:
                        st.write("无数据")
                    
    
    # 删除确认弹窗
    if st.session_state.confirm_delete:
        mat_id = st.session_state.confirm_delete
        st.error(f"确定要删除原料 #{mat_id} 吗？此操作不可撤销。")
        col_d1, col_d2 = st.columns(2)
        if col_d1.button("确认删除"):
            success = delete_material(mat_id)
            if success:
                st.success("已删除")
                st.session_state.selected_mat_id = None
            else:
                st.error("该原料正被配方或成品引用，无法删除")
            st.session_state.confirm_delete = None
            st.rerun()
        if col_d2.button("取消"):
            st.session_state.confirm_delete = None
            st.rerun()

# ==================== 配方中心 ====================
elif page == "📋️ 配方中心":
    st.header("📋️ 配方中心")
    all_mats = get_all_materials()
    if not all_mats:
        st.warning("请先录入原料")
    else:
        # ---------- session_state 初始化 ----------
        if 'selected_formula_id' not in st.session_state:
            st.session_state.selected_formula_id = None
        if 'editing_formula_id' not in st.session_state:
            st.session_state.editing_formula_id = None
        if 'formula_ingredients' not in st.session_state:
            st.session_state.formula_ingredients = []
        if 'temp_new_ingredients' not in st.session_state:
            st.session_state.temp_new_ingredients = []

        # ---------- 左侧列表 ----------
        col_list, col_detail = st.columns([1, 1])
        with col_list:
            # 分类筛选和搜索
            col_s1, col_s2, col_s3 = st.columns([1, 1, 1],vertical_alignment="bottom")
            with col_s1:
                category_filter = st.selectbox(
                    "分类",
                    ["全部", "青釉", "天蓝釉", "月白釉", "钧红釉", "炉钧釉", "黑釉", "结晶釉","泥浆"],
                    key="formula_cat"
                )
            with col_s2:
                f_search = st.text_input("🔍 搜索配方名称", placeholder="配方名...", key="f_search")
            with col_s3:
                if st.button("➕ 新建配方", width='stretch'):
                    st.session_state.editing_formula_id = "NEW"
                    st.session_state.selected_formula_id = None
                    st.session_state.formula_ingredients = []
                    st.rerun()

            formulas = get_all_formulas(
                search=f_search if f_search else None,
                category=None if category_filter == '全部' else category_filter
            )

            # 网格展示
            if not formulas:
                st.info("暂无配方")
            else:
                for i in range(0, len(formulas), 3):
                    c1, c2, c3 = st.columns(3)
                    for col, idx in zip([c1, c2, c3], range(i, min(i + 3, len(formulas)))):
                        with col:
                            f = formulas[idx]
                            is_selected = (
                                st.session_state.selected_formula_id == f['id']
                                and st.session_state.editing_formula_id is None
                            )
                            btn_label = f"**{f['name']}** ({f['version']})  [{f.get('category','')}]"
                            if st.button(
                                btn_label,
                                key=f"fcard_{f['id']}",
                                width='stretch',
                                type="primary" if is_selected else "secondary"
                            ):
                                st.session_state.selected_formula_id = f['id']
                                st.session_state.editing_formula_id = None
                                st.session_state.formula_ingredients = get_formula_details(f['id'])
                                st.rerun()

        # ---------- 右侧详情/编辑 ----------
        with col_detail:
            target_id = st.session_state.editing_formula_id or st.session_state.selected_formula_id

            if target_id is None:
                st.info("👈 从左侧选择配方查看，或点击新建")

            elif target_id == "NEW":
                # ========== 新建配方 ==========
                st.subheader("➕ 新建配方")

                with st.form("new_formula_form"):
                    # ---- 配方基本信息 ----
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        f_name = st.text_input("配方名称")
                    with c2:
                        f_version = st.text_input("版本", "v1.0")
                    with c3:
                        f_category = st.selectbox(
                            "釉方分类",
                            ["青釉", "天蓝釉", "月白釉", "钧红釉", "炉钧釉", "黑釉", "结晶釉","泥浆"]
                        )
                    f_notes = st.text_area("备注")


                    # ---- 快速多选添加 ----
                    st.markdown("##### ⚡ 快速选择原料（可多选）")
                    mat_names = [m['name'] for m in all_mats]
                    selected = st.multiselect(
                        "选择原料",
                        mat_names,
                        key="quick_new",
                        label_visibility="collapsed"
                    )
                    add_selected_btn = st.form_submit_button("添加所选原料")


                    # ---- 成分清单（可编辑比例、可删除） ----
                    to_remove = None
                    for i, item in enumerate(st.session_state.temp_new_ingredients):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        c1.write(item['name'])
                        new_qty = c2.number_input(
                            "比例",
                            value=float(item['quantity']),
                            key=f"new_q_{i}",
                            label_visibility="collapsed"
                        )
                        item['quantity'] = new_qty
                        if c3.form_submit_button("✕", key=f"new_del_{i}"):
                            to_remove = i

                    # ---- 保存 / 取消 ----

                    col1, col2 = st.columns(2)
                    with col1:
                        save_btn = st.form_submit_button("💾 保存")
                    with col2:
                        cancel_btn = st.form_submit_button("取消")

                    # ========== 表单提交后的逻辑处理 ==========
                    if add_selected_btn:
                        if selected:
                            for name in selected:
                                mat = next(m for m in all_mats if m['name'] == name)
                                existing = next(
                                    (x for x in st.session_state.temp_new_ingredients if x['material_id'] == mat['id']),
                                    None
                                )
                                if not existing:
                                    st.session_state.temp_new_ingredients.append({
                                        'material_id': mat['id'],
                                        'name': mat['name'],
                                        'quantity': 10.0,
                                        'analysis': mat['analysis'],
                                        'stock_kg': mat['stock_kg']
                                    })
                            st.rerun()
                        else:
                            st.warning("请至少勾选一种原料")

                    if to_remove is not None:
                        st.session_state.temp_new_ingredients.pop(to_remove)
                        st.rerun()

                    if save_btn:
                        if not f_name:
                            st.error("名称不能为空")
                        elif not st.session_state.temp_new_ingredients:
                            st.error("请添加至少一种原料")
                        else:
                            success = save_formula(
                                f_name, f_version, f_notes, f_category,
                                st.session_state.temp_new_ingredients
                            )
                            if success:
                                st.success("配方保存成功！")
                                st.session_state.temp_new_ingredients = []
                                st.session_state.editing_formula_id = None
                                st.rerun()
                            else:
                                st.error("名称与版本已存在，请更换")

                    if cancel_btn:
                        st.session_state.temp_new_ingredients = []
                        st.session_state.editing_formula_id = None
                        st.rerun()

            else:
                # ========== 查看/编辑已有配方 ==========
                formula = next((f for f in get_all_formulas() if f['id'] == target_id), None)
                if not formula:
                    st.error("配方不存在")
                    st.session_state.selected_formula_id = None
                    st.rerun()

                # 编辑模式
                if st.session_state.editing_formula_id == formula['id']:
                    st.subheader("✏️ 编辑配方")
                    if not st.session_state.formula_ingredients:
                        st.session_state.formula_ingredients = get_formula_details(formula['id'])

                    with st.form(f"edit_form_{formula['id']}"):
                        # 第1行：基本信息
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            e_name = st.text_input("名称", value=formula['name'])
                        with c2:
                            e_version = st.text_input("版本", value=formula['version'])
                        with c3:
                            e_category = st.selectbox(
                                "釉方分类",
                                ["青釉", "天蓝釉", "月白釉", "钧红釉", "炉钧釉", "黑釉", "结晶釉","泥浆"],
                                index=["青釉", "天蓝釉", "月白釉", "钧红釉", "炉钧釉", "黑釉", "结晶釉","泥浆"].index(
                                    formula.get('category', '青釉')
                                )
                            )
                        e_notes = st.text_area("备注", value=formula['notes'])

                        st.markdown("##### 📋 成分清单")

                        # 处理删除操作
                        to_remove = None
                        for i, item in enumerate(st.session_state.formula_ingredients):
                            c1, c2, c3 = st.columns([3, 2, 1])
                            c1.write(item['name'])
                            new_qty = c2.number_input(
                                "比例",
                                value=float(item['quantity']),
                                key=f"edit_q_{i}",
                                label_visibility="collapsed"
                            )
                            item['quantity'] = new_qty
                            if c3.form_submit_button("✕", key=f"edit_del_{i}"):
                                to_remove = i

                        if to_remove is not None:
                            st.session_state.formula_ingredients.pop(to_remove)
                            st.rerun()

                        # 添加新原料（一行布局）
                        st.markdown("##### ➕ 添加原料到配方")
                        col_a1, col_a2, col_a3 = st.columns([1, 1, 1])
                        with col_a1:
                            # 不显示库存
                            mat_opt = {m['name']: m for m in all_mats}
                            sel = st.selectbox("选择原料", list(mat_opt.keys()), label_visibility="collapsed")
                        with col_a2:
                            qty = st.number_input("比例", min_value=0.1, value=50.0, step=1.0, label_visibility="collapsed")
                        with col_a3:
                            add_btn = st.form_submit_button("➕ 添加")

                        # 保存和取消
                        st.markdown("---")
                        col_s1, col_s2 = st.columns(2)
                        with col_s1:
                            save_btn = st.form_submit_button("💾 保存修改")
                        with col_s2:
                            cancel_btn = st.form_submit_button("取消")

                        # ===================== 表单提交后的逻辑处理 =====================
                        if add_btn:
                            mat = mat_opt[sel]
                            existing = next(
                                (x for x in st.session_state.formula_ingredients if x['material_id'] == mat['id']),
                                None
                            )
                            if existing:
                                existing['quantity'] += qty
                            else:
                                st.session_state.formula_ingredients.append({
                                    'material_id': mat['id'],
                                    'name': mat['name'],
                                    'quantity': qty,
                                    'analysis': mat['analysis'],
                                    'stock_kg': mat['stock_kg']
                                })
                            st.rerun()

                        if save_btn:
                            success = update_formula_override(
                                formula['id'], e_name, e_version, e_notes, e_category,
                                st.session_state.formula_ingredients
                            )
                            if success:
                                st.success("配方已更新")
                                st.session_state.editing_formula_id = None
                                st.session_state.formula_ingredients = []
                                st.rerun()
                            else:
                                st.error("保存失败，可能版本重复")

                        if cancel_btn:
                            st.session_state.editing_formula_id = None
                            st.session_state.formula_ingredients = []
                            st.rerun()

                else:
                # 查看模式
                    col_title, col_btn = st.columns([3, 2])
                    with col_title:
                        st.subheader(f"{formula['name']} ({formula['version']})")
                    with col_btn:
                    # 编辑与删除并排
                        c_edit, c_del = st.columns(2)
                        with c_edit:
                            if st.button("✏️ 编辑"):
                                st.session_state.editing_formula_id = formula['id']
                                st.session_state.formula_ingredients = get_formula_details(formula['id'])
                                st.rerun()
                        with c_del:
                            if st.button("🗑️ 删除", key=f"del_formula_{formula['id']}"):
                                if delete_formula(formula['id']):
                                    st.success("配方已删除")
                                    st.session_state.selected_formula_id = None
                                    st.session_state.editing_formula_id = None
                                    st.session_state.formula_ingredients = []
                                    st.rerun()
                                else:
                                    st.error("无法删除：该配方已有生产记录")

                # 后面保持原来的分类、备注、成分表、釉式、关联批次等不变
                    st.write(f"**分类**: {formula.get('category', '无')} | **创建时间**: {formula['created_at'][:10]}")
                    if formula['notes']:
                        st.write(f"**备注**: {formula['notes']}")

                    ingredients = get_formula_details(formula['id'])
                    if ingredients:
                        total = sum(i['quantity'] for i in ingredients)
                        st.write(f"总份数: **{total:.1f}**")
                        names = [i['name'] for i in ingredients]
                        qtys = [i['quantity'] for i in ingredients]
                        df_comp = pd.DataFrame([qtys], columns=names)
                        st.dataframe(df_comp, width='stretch', hide_index=True)

                        seger_result = calculate_seger(ingredients)
                        if 'error' not in seger_result:
                            st.code(seger_result['text'])

                    st.markdown("---")
                    st.subheader("⚗️ 关联釉水批次")
                    batches = get_formula_batches(formula['id'])
                    if batches:
                        for b in batches:
                            st.write(f"- {b['batch_code']} | 总量 {b['total_weight_g']}g | 库存 {b['stock_kg']:.2f}kg | 状态 {b['status']}")
                    else:
                        st.info("暂无生产记录")

                    if st.button("⚗️ 用此配方制备釉水"):
                        st.session_state.prepare_from_formula = formula['id']
                        st.rerun()

# ==================== 制备中心 ====================
elif page == "⚗️ 制备中心":
    st.header("⚗️ 制备中心")
    
    tab1, tab2, tab3 = st.tabs(["🆕 新建制备", "⏳ 待球磨 & 球磨中", "📦 釉浆库存"])
    
    all_formulas = get_all_formulas()
    all_mats = get_all_materials()
    all_batches = get_all_batches()
    
    # ======================= Tab 1: 新建制备 =======================
    with tab1:
        st.subheader("新建釉料制备")
        if not all_formulas:
            st.warning("请先在「配方中心」创建配方")
        else:
            # ---------- 辅助函数：计算原料需求 ----------
            def compute_ingredient_needs(ingredients, target_dry_g):
                base_total = sum(i['quantity'] for i in ingredients)
                if base_total == 0:
                    return []
                needs = []
                for item in ingredients:
                    need_g = target_dry_g * (item['quantity'] / base_total)
                    needs.append({
                        'name': item['name'],
                        'material_id': item['material_id'],
                        'quantity': item['quantity'],
                        'need_g': need_g,
                        'need_kg': need_g / 1000.0,
                        'stock_kg': item.get('stock_kg', 0.0)
                    })
                return needs

            # ---------- 初始化 session_state ----------
            if 'prep_mill_type' not in st.session_state:
                st.session_state.prep_mill_type = "200kg"
            if 'prep_ingredients_data' not in st.session_state:
                st.session_state.prep_ingredients_data = []
            if 'prep_confirms' not in st.session_state:
                st.session_state.prep_confirms = {}
            if 'prep_formula_id' not in st.session_state:
                st.session_state.prep_formula_id = None

            # ---------- 球磨机型号映射 ----------
            mill_map = {
                "1800kg": 1_800_000,
                "200kg": 200_000,
                "100kg": 100_000,
                "10kg": 10_000,
                "200g": 200
            }

            # ---------- 当配方或球磨机变化时的自动回调 ----------
            def on_recipe_or_mill_change():
                fid = st.session_state.get("prep_formula_id")
                mill = st.session_state.get("prep_mill_type", "200kg")
                if not fid:
                    st.session_state.prep_ingredients_data = []
                    return
                ingredients = get_formula_details(fid)
                target_dry = mill_map[mill]
                st.session_state.prep_ingredients_data = compute_ingredient_needs(ingredients, target_dry)
                # 清空旧配方的确认状态
                old_confirms = list(st.session_state.prep_confirms.keys())
                for k in old_confirms:
                    if k.startswith(f"{fid}_") is False:  # 保留其他配方确认（理论上同一时间只做一个配方）
                        del st.session_state.prep_confirms[k]

            # ---------- 选择配方 ----------
            formula_opt = [f"{f['name']} ({f['version']})" for f in all_formulas]
            # 默认选中第一个（如果 session 中没有保存）
            if 'prep_formula_select' not in st.session_state and formula_opt:
                st.session_state.prep_formula_select = formula_opt[0]

            selected_f_str = st.selectbox(
                "选择配方",
                formula_opt,
                key="prep_formula_select",
                on_change=on_recipe_or_mill_change
            )
            # 解析选中的配方 ID
            if selected_f_str:
                f_name, f_ver = selected_f_str.rsplit(" (", 1)
                f_ver = f_ver.rstrip(")")
                sel_formula = next(f for f in all_formulas
                                   if f['name'] == f_name and f['version'] == f_ver)
                st.session_state.prep_formula_id = sel_formula['id']
            else:
                sel_formula = None
                st.session_state.prep_formula_id = None

            # ---------- 球磨、存放 ----------
            col_a, col_b = st.columns(2)
            with col_a:
                mill_type = st.selectbox(
                    "球磨机型号",
                    list(mill_map.keys()),
                    key="prep_mill_type",
                    on_change=on_recipe_or_mill_change
                )
            with col_b:
                location = st.selectbox("存放位置", ["实验室", "负一楼", "工房"], key="prep_loc")

            # ---------- 日期、标签、批次 ----------
            col_c, col_d, col_e = st.columns(3)
            with col_c:
                milling_date = st.date_input("制备日期", datetime.now(), key="prep_date")
            with col_d:
                label = st.text_input("标签编号",
                                      f"L{datetime.now().strftime('%m%d%H%M')}",
                                      key="prep_label")
            with col_e:
                batch_code = st.text_input("批次号",
                                           f"B{datetime.now().strftime('%Y%m%d%H%M')}",
                                           key="prep_batch")

            # 如果配方还没选，停止后续展示
            if not sel_formula:
                st.stop()

            # 首次进入或数据为空时自动计算一次
            if not st.session_state.prep_ingredients_data:
                on_recipe_or_mill_change()

            # ---------- 原料确认区域 ----------
            st.markdown("---")
            st.markdown("**📋 配方原料确认**")
            data = st.session_state.prep_ingredients_data
            if data:
                # 计算总份数用于百分比显示
                ingredients = get_formula_details(st.session_state.prep_formula_id)
                base_total = sum(i['quantity'] for i in ingredients)
                num_cols = len(data)
                cols = st.columns(num_cols)
                for i, (col, ing) in enumerate(zip(cols, data)):
                    with col:
                        pct = (ing['quantity'] / base_total) * 100
                        current_mill = st.session_state.get("prep_mill_type", "200kg")
                        if current_mill in ["200g", "10kg"]:
                            # 小型球磨，显示克
                            need_display = f"{ing['need_g']:.0f} g"
                        else:
                            # 大型球磨，显示千克
                            need_display = f"{ing['need_kg']:.3f} kg"

                        # 名称 + 百分比（小字）
                        st.markdown(
                            f"**{ing['name']}** <small>({pct:.1f}%)</small>",
                            unsafe_allow_html=True
                        )
                        # 需求量（大字体）
                        st.markdown(f"<h4>{need_display}</h4>", unsafe_allow_html=True)
                        # 库存信息
                        st.caption(f"库存 {ing['stock_kg']:.2f} kg")
                        # 缺料警告
                        if ing['stock_kg'] < ing['need_kg']:
                            st.error("❌ 缺料")

                        # 确认按钮
                        material_id = ing['material_id']
                        fid = st.session_state.prep_formula_id
                        conf_key = f"{fid}_{material_id}"
                        is_confirmed = st.session_state.prep_confirms.get(conf_key, False)
                        btn_label = "✅" if is_confirmed else "确认"

                        # 切换确认状态的函数
                        def toggle_confirm(mid=material_id):
                            ck = f"{st.session_state.prep_formula_id}_{mid}"
                            st.session_state.prep_confirms[ck] = not st.session_state.prep_confirms.get(ck, False)

                        st.button(btn_label, key=f"confirm_btn_{conf_key}",
                                  on_click=toggle_confirm)

            # ---------- 制备完成按钮（底部） ----------
            st.markdown("---")
            if st.button("🚀 制备完成", type="primary"):
                fid = st.session_state.get("prep_formula_id")
                cur_data = st.session_state.prep_ingredients_data
                if not fid or not cur_data:
                    st.error("请先选择配方并确认原料信息")
                else:
                    # 检查全部原料已确认
                    all_confirmed = all(
                        st.session_state.prep_confirms.get(f"{fid}_{ing['material_id']}", False)
                        for ing in cur_data
                    )
                    if not all_confirmed:
                        st.error("请确认所有原料已准备完毕（点击每个原料下方的“确认”按钮）")
                    elif not st.session_state.get("prep_batch"):  # 修复：key 改为 prep_batch
                        st.error("批次号不能为空")
                    else:
                    # 库存检查
                        stock_ok = all(ing['stock_kg'] >= ing['need_kg'] for ing in cur_data)
                        if not stock_ok:
                            st.error("部分原料库存不足，请补充")
                        else:
                            deduct_list = [{
                                'material_id': ing['material_id'],
                                'name': ing['name'],
                                'deduct_kg': ing['need_kg']
                            } for ing in cur_data]
                        
                        # 修复：使用位置参数传参，并使用正确的 session_state key
                            err = prepare_glaze_batch(
                                fid,                                               # formula_id
                                st.session_state.prep_batch,                       # batch_code (修复 key)
                                mill_map[st.session_state.prep_mill_type],         # target_dry_weight_g
                                0,                                                 # water_weight_kg
                                st.session_state.prep_mill_type,                   # mill_type
                                0,                                                 # ball_mill_hours
                                str(st.session_state.prep_date),                   # milling_date
                                st.session_state.prep_location,                    # storage_location
                                st.session_state.prep_label,                       # label_code
                                deduct_list                                        # ingredients_deduction
                            )
                        
                            if err:
                                st.error(err)
                            else:
                                st.success("制备已记录！请前往「待球磨」完善水量与球磨时间")
                                # 清理本次制备的所有临时状态
                                keys_to_clear = [k for k in st.session_state
                                                 if k.startswith('prep_') or k.startswith('confirm_btn_')]
                                for k in keys_to_clear:
                                    del st.session_state[k]
                                time.sleep(1)
                                st.rerun()

    # ======================= Tab 2: 待球磨 & 球磨中 =======================
    with tab2:
        st.subheader("⏳ 待球磨批次")
        pending_batches = [b for b in all_batches if b['status'] == '待球磨']
        milling_batches = [b for b in all_batches if b['status'] == '球磨中']
        if not pending_batches:
            st.info("所有批次均已处理")
        for b in pending_batches:
            with st.expander(f"{b['batch_code']} | {b['name']} | {b.get('mill_type','')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"干料: {b['total_weight_g']}g，水: {b['water_weight_kg']}kg")
                    st.write(f"存放: {b.get('storage_location','')}，标签: {b.get('label_code','')}")
                with col2:
                    st.write(f"状态: **待球磨**")

                # ---- 编辑水量和球磨时间 ----
                with st.form(f"edit_batch_{b['id']}"):
                    st.markdown("**⚙️ 调整参数**")
                    new_water = st.number_input("加水量 (kg)", min_value=0.0,
                                                value=float(b.get('water_weight_kg', 0.0)),
                                                step=0.1)
                    new_hours = st.number_input("球磨时间 (h)", min_value=0.0,
                                                value=float(b.get('ball_mill_hours', 0.0)),
                                                step=0.5)
                    if st.form_submit_button("💾 保存参数"):
                        update_batch_params(b['id'], water_kg=new_water, ball_mill_hours=new_hours)
                        st.success("参数已更新")
                        st.rerun()

                # ---- 开始球磨按钮（使用保存的时间） ----
                if st.button("▶️ 开始球磨", key=f"start_{b['id']}"):
                    # 重新从数据库获取最新数据，确保球磨时间是最新保存的
                    with get_db() as conn:
                        latest = conn.execute(
                            'SELECT ball_mill_hours FROM glaze_batches WHERE id=?',
                            (b['id'],)
                        ).fetchone()
                    if not latest or latest['ball_mill_hours'] <= 0:
                        st.warning("请先设置球磨时间再开始")
                    else:
                        set_batch_ball_milling(b['id'], latest['ball_mill_hours'])
                        st.success("已转为「球磨中」")
                        st.rerun()

        st.subheader("⚙️ 球磨中批次")
        if not milling_batches:
            st.info("目前没有正在球磨的批次")
        for b in milling_batches:
            with st.expander(f"{b['batch_code']} | {b['name']} | {b.get('mill_type','')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"干料: {b['total_weight_g']}g，水: {b['water_weight_kg']}kg")
                    st.write(f"球磨时间: {b['ball_mill_hours']}h")
                with col2:
                    st.write("状态: **球磨中**")
                    if st.button("✅ 完成球磨，入库", key=f"finish_{b['id']}"):
                        finish_batch_milling(b['id'])
                        st.success("已入库！")
                        st.rerun()
    
    # ======================= Tab 3: 釉浆库存 =======================
    with tab3:
        st.subheader("📦 已入库釉浆库存")
        stock_batches = [b for b in all_batches if b['status'] == '已入库']
        if not stock_batches:
            st.info("暂无库存")
        else:
            for b in stock_batches:
                with st.expander(f"{b['batch_code']} | {b['name']} | 库存 {b['stock_kg']:.2f}kg"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.write(f"干料: {b['total_weight_g']}g，水: {b['water_weight_kg']}kg")
                        st.write(f"球磨: {b['ball_mill_hours']}h，型号: {b.get('mill_type','')}")
                        st.write(f"存放: {b.get('storage_location','')}，标签: {b.get('label_code','')}")
                    with col_b:
                        st.write("**扣减消耗**")
                        deduct = st.number_input("消耗量 (kg)", min_value=0.01,
                                                 max_value=float(b['stock_kg']),
                                                 step=0.1, key=f"deduct_{b['id']}")
                        if st.button("确认扣减", key=f"do_deduct_{b['id']}"):
                            if deduct > b['stock_kg']:
                                st.error("超出库存")
                            else:
                                result = deduct_glaze_stock(b['id'], deduct)
                                if result:
                                    st.error(result)
                                else:
                                    st.success("扣减成功")
                                    st.rerun()
# ==================== 烧成记录 ====================
elif page == "🔥 烧成中心":
    st.header("🔥 烧成中心")
    
    st.subheader("📜 历史记录")
    firings = get_all_firings()
    if not firings:
        st.info("暂无记录")
    else:
        df = pd.DataFrame(firings)
        st.dataframe(
            df[['firing_date','kiln_name','atmosphere','target_temp','result_notes']].rename(
                columns={'firing_date':'日期','kiln_name':'窑炉','atmosphere':'气氛','target_temp':'目标温度','result_notes':'结果'}
            ),
            width='stretch', hide_index=True
        )
        # 查看动态数据
        sel = st.selectbox("选择记录查看详细曲线", range(len(firings)),
                           format_func=lambda i: f"{firings[i]['firing_date']} - {firings[i]['kiln_name']}")
        dyn = firings[sel]['dynamic_records'] or []
        if dyn:
            st.dataframe(pd.DataFrame(dyn), width='stretch')
        else:
            st.info("无动态数据")
    
    st.markdown("---")
    st.subheader("➕ 新增记录")
    if 'temp_dyn' not in st.session_state:
        st.session_state.temp_dyn = []
    
    with st.form("add_firing"):
        date = st.date_input("日期", datetime.now())
        kiln = st.text_input("窑炉名称", "主窑")
        atmos = st.selectbox("气氛", ["氧化","还原","中性"])
        temp = st.text_input("目标温度/温锥", "1280℃")
        notes = st.text_area("结果备注")
        
        st.markdown("**动态烧成数据（表格录入）**")
        if not st.session_state.temp_dyn:
            st.session_state.temp_dyn = [{"时间":"","温度(℃)":"","气压(MPa)":"","闸板":"","火嘴":""}]
        edited = st.data_editor(
            st.session_state.temp_dyn,
            num_rows="dynamic",
            width='stretch',
            key="dyn_editor"
        )
        st.session_state.temp_dyn = edited
        
        submitted = st.form_submit_button("💾 保存记录")
        if submitted:
            filtered = [row for row in edited if any(str(v).strip() for v in row.values())]
            add_firing_record(str(date), kiln, atmos, temp, filtered, notes)
            st.session_state.temp_dyn = []
            st.success("记录已保存")
            st.rerun()

# ==================== 成品仓库 ====================
elif page == "🏺 成品仓库":
    st.header("🏺 成品仓库")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        item_search = st.text_input("🔍 搜索作品名/编号")
    with col_f2:
        item_status_f = st.selectbox("状态筛选", ["全部","在库","已售","瑕疵","自留"])
    
    items = get_all_items(search=item_search if item_search else None,
                          status=None if item_status_f=="全部" else item_status_f)
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader("➕ 新入成品")
        with st.form("add_item"):
            code = st.text_input("作品编号", f"CER-{datetime.now().strftime('%Y%m%d')}-01")
            name = st.text_input("作品名称")
            clays = get_all_materials(material_type="泥料")
            clay_opts = {c['name']: c['id'] for c in clays}
            clay_sel = st.selectbox("泥料", list(clay_opts.keys())) if clay_opts else None
            
            batches = get_all_batches()
            batch_opts = {f"{b['batch_code']} ({b['name']})": b['id'] for b in batches if b['stock_kg']>0}
            batch_sel = st.selectbox("釉水批次", list(batch_opts.keys())) if batch_opts else None
            
            firings = get_all_firings()
            fire_opts = {f"{f['firing_date']} {f['kiln_name']} ({f['atmosphere']})": f['id'] for f in firings}
            fire_sel = st.selectbox("烧成记录", list(fire_opts.keys())) if fire_opts else None
            
            status = st.selectbox("状态", ["在库","已售","瑕疵","自留"])
            price = st.number_input("定价 (元)", min_value=0.0, step=10.0)
            loc = st.text_input("存放位置")
            notes = st.text_area("备注")
            
            if st.form_submit_button("入库"):
                err = add_ceramic_item(
                    code, name,
                    clay_opts.get(clay_sel) if clay_sel else None,
                    batch_opts.get(batch_sel) if batch_sel else None,
                    fire_opts.get(fire_sel) if fire_sel else None,
                    status, price, loc, notes
                )
                if err:
                    st.error(err)
                else:
                    st.success("入库成功")
                    st.rerun()
    
    with col_right:
        st.subheader("🏺 在库作品")
        if not items:
            st.info("暂无作品")
        else:
            for item in items:
                emoji = {"在库":"📦","已售":"💰","瑕疵":"💔","自留":"🏠"}.get(item['status'],"🏺")
                with st.expander(f"{emoji} [{item['item_code']}] {item['name']} ({item['status']})"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.markdown("**溯源信息**")
                        st.write(f"泥料: {item['clay_name'] or '未知'}")
                        st.write(f"釉水: {item['batch_code'] or '未知'}")
                        st.write(f"烧成: {item['firing_date']} {item['kiln_name']} {item['atmosphere']}")
                    with col_b:
                        st.markdown("**状态**")
                        st.write(f"存放: {item['storage_location'] or '无'}")
                        st.write(f"定价: ¥{item['price']:.2f}")
                        if item['notes']:
                            st.write(f"备注: {item['notes']}")
                    
                    new_status = st.radio("修改状态", ["在库","已售","瑕疵","自留"],
                                          index=["在库","已售","瑕疵","自留"].index(item['status']),
                                          horizontal=True, key=f"status_{item['id']}")
                    if new_status != item['status']:
                        if st.button("✅ 更新状态", key=f"update_{item['id']}"):
                            update_item_status(item['id'], new_status)
                            st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption("陶瓷工作室数字工作台 v2.0 · 数据存储于本地 SQLite")
