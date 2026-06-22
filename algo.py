OXIDE_MW = {
    'Li2O':29.88, 'Na2O':61.98, 'K2O':94.20, 'MgO':40.30, 'CaO':56.08,
    'SrO':103.62, 'BaO':153.33, 'ZnO':81.38, 'PbO':223.20, 'Al2O3':101.96,
    'B2O3':69.62, 'SiO2':60.08, 'TiO2':79.90, 'ZrO2':123.22, 'SnO2':150.71,
    'P2O5':141.94, 'Fe2O3':159.69, 'CuO':79.55, 'CoO':74.93, 'MnO':70.94, 'LOI':0
}
FLUX_OXIDES = ['Li2O','Na2O','K2O','MgO','CaO','SrO','BaO','ZnO','PbO']
INTER_OXIDES = ['Al2O3','B2O3']
GLASS_OXIDES = ['SiO2','TiO2','ZrO2','SnO2','P2O5']
COLOR_OXIDES = ['Fe2O3','CuO','CoO','MnO']

def calculate_seger(ingredients: list) -> dict:
    """返回详细塞格尔数据和格式化文本"""
    total_weights = {}
    for item in ingredients:
        weight = item['quantity']
        analysis = item['analysis']
        for oxide, pct in analysis.items():
            if oxide == 'LOI': continue
            total_weights[oxide] = total_weights.get(oxide, 0) + weight * (pct / 100.0)
    
    oxide_moles = {}
    for oxide, w in total_weights.items():
        mw = OXIDE_MW.get(oxide, 0)
        if mw > 0:
            oxide_moles[oxide] = w / mw
    
    flux_total = sum(oxide_moles.get(ox, 0) for ox in FLUX_OXIDES)
    if flux_total == 0:
        return {"error": "无熔剂氧化物，无法计算塞格尔釉式"}
    
    seger = {ox: moles/flux_total for ox, moles in oxide_moles.items()}
    # 格式化各列
    def format_group(oxides):
        parts = [f"{seger[ox]:.3f} {ox}" for ox in oxides if ox in seger and seger[ox] > 0.0001]
        return " | ".join(parts) if parts else "0.000"
    
    text = (
        f"熔剂 (R₂O+RO): {format_group(FLUX_OXIDES)}\n"
        f"中性 (R₂O₃): {format_group(INTER_OXIDES)}\n"
        f"玻璃形成 (RO₂): {format_group(GLASS_OXIDES)}\n"
        f"着色剂: {format_group(COLOR_OXIDES)}"
    )
    return {"seger": seger, "text": text, "flux_total": flux_total, "oxide_moles": oxide_moles}
