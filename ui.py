import streamlit as st
from typing import Dict, List

def render_oxide_inputs(prefix: str, current_values: Dict[str, float] = None) -> Dict[str, float]:
    """渲染化学成分输入组件"""
    st.markdown("##### 化学成分 (%)")
    common = [
        ("SiO2","二氧化硅"), ("Al2O3","氧化铝"), ("B2O3","氧化硼"), ("K2O","氧化钾"),
        ("Na2O","氧化钠"), ("Li2O","氧化锂"), ("CaO","氧化钙"), ("MgO","氧化镁"),
        ("ZnO","氧化锌"), ("BaO","氧化钡"), ("SrO","氧化锶"), ("PbO","氧化铅"),
        ("TiO2","氧化钛"), ("ZrO2","氧化锆"), ("SnO2","二氧化锡"), ("P2O5","五氧化二磷"),
        ("Fe2O3","氧化铁"), ("CuO","氧化铜"), ("CoO","氧化钴"), ("MnO","氧化亚锰"),
        ("LOI","烧失量")
    ]
    result = {}
    cols = st.columns(3)
    for i, (ox, cn) in enumerate(common):
        col = cols[i % 3]
        default = current_values.get(ox, 0.0) if current_values else 0.0
        val = col.number_input(
            f"{ox} ({cn})", value=default, min_value=0.0, max_value=100.0,
            step=0.1, format="%.2f", key=f"{prefix}_ox_{ox}"
        )
        if val > 0:
            result[ox] = val
    return result

def material_card(mat: Dict, selected_id: int, key_prefix: str) -> bool:
    """原料卡片按钮，返回是否被点击"""
    label = f"**{mat['name']}**  {mat['stock_kg']:.1f}kg"
    if mat['stock_kg'] < 1.0:
        label += " ⚠️"
    is_sel = selected_id == mat['id']
    return st.button(
        label, key=f"{key_prefix}_{mat['id']}",
        type="primary" if is_sel else "secondary",
        width='stretch'
    )

def formula_card(formula: Dict, key: str, is_loaded: bool = False) -> bool:
    """配方卡片按钮，返回是否点击加载"""
    label = f"📋 {formula['name']} ({formula['version']})"
    if is_loaded:
        label += " ✅"
    return st.button(label, key=key, width='stretch')
