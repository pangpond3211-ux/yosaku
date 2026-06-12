import streamlit as st
import pandas as pd
import math
import itertools
from datetime import datetime

# ========================================================
# [CONFIG] ตั้งค่าความดันบรรยากาศอ้างอิงหน้างาน
# ========================================================
ATM_BAR = 1.013    # มาตรฐานทั่วไปใช้ 1.013 Bar
ATM_PSI = 14.70    # มาตรฐานฝั่ง PSI

# ตั้งค่าหน้าตาของ Web App
st.set_page_config(
    page_title="Yosaku Selection Pro (Easiest & Accurate)",
    page_icon="⚙️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ข้อมูลตาราง Orifice มาตรฐานของวาล์ว Yosaku
ORIFICE_DATA = [
    ("JA", 0.04), ("JB", 0.08), ("JBC", 0.11), 
    ("JC", 0.14), ("JD", 0.22), ("JE", 0.30), 
    ("JF", 0.35), ("JG", 0.41), ("JH", 0.48)
]

COLOR_MAP = {
    "เล็กเกินไป": "background-color: #ffcccc; color: #cc0000;",
    "เหมาะสม": "background-color: #d4edda; color: #155724; font-weight: bold;",
    "ใกล้เต็ม": "background-color: #fff3cd; color: #856404;",
    "ใหญ่เกินไป": "background-color: #ffffff; color: #6c757d;"
}

# 💾 ฐานข้อมูลภาระความร้อนน้ำมันมาตรฐานประจำรุ่น (Rating Condition: Te -10°C / Tc 35°C)
MYCOM_BASE_OIL_REJECTION = {
    # --- 160 Series ---
    "MYCOM 160 VMS": 32.0, "MYCOM 160 VMD": 45.0, "MYCOM 160 VLD": 58.0,
    # --- 170 J-Series ---
    "MYCOM 170JS-V": 55.0, "MYCOM 170JM-V": 65.0, "MYCOM 170JL-V": 75.0,
    # --- 200 Series ---
    "MYCOM 200 VSD": 65.0, "MYCOM 200 VMD": 88.0, "MYCOM 200 VLD": 110.0,
    # --- 220 J-Series ---
    "MYCOM 220JS-V": 105.0, "MYCOM 220JM-V": 125.0, "MYCOM 220JL-V": 145.0,
    # --- 250 Series ---
    "MYCOM 250 VSD": 135.0, "MYCOM 250 VMD": 170.0, "MYCOM 250 VLD": 210.0,
    # --- 280 J-Series ---
    "MYCOM 280JS-V": 195.0, "MYCOM 280JM-V": 230.0, "MYCOM 280JL-V": 265.0,
    # --- 320 Series ---
    "MYCOM 320 VSD": 245.0, "MYCOM 320 VMD": 295.0, "MYCOM 320 VLD": 350.0
}

if "calculated" not in st.session_state:
    st.session_state.calculated = False

def reset_calculation():
    st.session_state.calculated = False

# 🧪 [THERMO FORMULA] ฟังก์ชันคำนวณคุณสมบัติน้ำยา R717 (Ammonia)
def nh3_temp_to_bar_abs(t_c):
    """แปลงอุณหภูมิอิ่มตัว (°C) -> ความดันสัมบูรณ์ (Bar Absolute)"""
    return (3.26631702e-08 * t_c**4 + 
            1.54531857e-05 * t_c**3 + 
            2.34641900e-03 * t_c**2 + 
            1.60674845e-01 * t_c + 
            4.29486480e+00)

def nh3_liquid_density(t_c):
    """คำนวณความหนาแน่นสารทำความเย็น R717 Liquid (kg/L)"""
    return 0.6386 - 0.00138 * t_c - 0.0000025 * (t_c ** 2)

# 📊 [DYNAMIC ESTIMATOR] ระบบจำลองโหลดความร้อนน้ำมันตามสภาวะจริง
def estimate_oil_heat(model, te, tc, has_eco):
    """คำนวณแนวโน้มค่า Oil Heat Rejection (kW) ให้สอดคล้องตามสภาวะ Te, Tc และ Economizer"""
    base_kw = MYCOM_BASE_OIL_REJECTION.get(model, 100.0)
    pe = nh3_temp_to_bar_abs(te)
    pc = nh3_temp_to_bar_abs(tc)
    
    # สภาวะอ้างอิงมาตรฐาน (-10°C / 35°C)
    pe_ref = nh3_temp_to_bar_abs(-10.0)
    pc_ref = nh3_temp_to_bar_abs(35.0)
    
    p_diff_ratio = (pc - pe) / (pc_ref - pe_ref) if (pc_ref - pe_ref) > 0 else 1.0
    cr_ratio = (pc / pe) / (pc_ref / pe_ref) if pe > 0 else 1.0
    
    # คำนวณโหลดแปรผันตามแรงดันและอัตราการอัด
    estimated_kw = base_kw * (p_diff_ratio ** 0.75) * (cr_ratio ** 0.35)
    
    # ปรับลดโหลดน้ำมันลงเล็กน้อยหากเปิดใช้ Economizer (เนื่องจากแก๊สเย็นเข้ามาช่วยซับความร้อนบางส่วน)
    if has_eco:
        estimated_kw *= 0.86
        
    return max(5.0, estimated_kw)

# --- ฟังก์ชันจัดการแสดงผลและตาราง ---
def get_suitability_score(pct, is_single):
    if pct > 87: return -1
    penalty = 0 if is_single else 5
    return 100 - abs(85 - pct) - penalty

def style_baseline_df(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        for config in ["1 ตัว", "2 ตัว"]:
            status_val = row[f"สถานะ ({config})"]
            style_style = COLOR_MAP.get(status_val, "")
            styles.at[i, f"% เปิด ({config})"] = style_style
            styles.at[i, f"สถานะ ({config})"] = style_style
    return styles

def color_matrix_cells(val):
    if pd.isna(val): return ""
    if val > 100: return "background-color: #ffcccc; color: #cc0000;"
    elif 75 <= val <= 85: return "background-color: #d4edda; color: #155724; font-weight: bold;"
    elif 85 < val <= 100: return "background-color: #fff3cd; color: #856404;"
    else: return "background-color: #ffffff; color: #6c757d;"


# ========================================================
# ส่วนแสดงผลหลักบนหน้าเว็บ (UI)
# ========================================================
st.title("💻⚙️ Yosaku Selection Pro")
st.subheader("โปรแกรมเลือกขนาดวาล์วสำหรับชุดระบายความร้อนน้ำมัน (Oil Cooler)")
st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")
st.markdown("---")

# 🔘 ส่วนที่ 1: ป้อนสภาวะหน้างาน (ง่ายและเร็ว)
st.subheader("🌡️ 1. ป้อนข้อมูลสภาวะทำงานจริงหน้างาน (Operating Conditions)")

col_input1, col_input2 = st.columns(2)
with col_input1:
    selected_model = st.selectbox("เลือกรุ่นคอมเพรสเซอร์ MYCOM:", list(MYCOM_BASE_OIL_REJECTION.keys()), on_change=reset_calculation)
    Evap_temp = st.number_input("อุณหภูมิระเหย Te (°C):", min_value=-50.0, max_value=20.0, value=-10.0, step=0.5, on_change=reset_calculation)

with col_input2:
    has_eco = st.checkbox("⚡ เปิดใช้งานระบบ Economizer (ECO Port)", value=False, on_change=reset_calculation)
    st.write("") # เว้นระยะ
    Cond_temp = st.number_input("อุณหภูมิควบแน่น Tc (°C):", min_value=10.0, max_value=60.0, value=35.0, step=0.5, on_change=reset_calculation)

st.markdown("---")

# 🔘 ส่วนที่ 2: ค่า Oil Heat Rejection (คำนวณให้อัตโนมัติ + ปรับแก้เองได้เพื่อให้แม่นยำ 100%)
st.subheader("🔥 2. ภาระความร้อนน้ำมัน (Oil Heat Rejection)")

# ระบบคำนวณค่าไกด์ไลน์จากสภาวะด้านบนให้อัตโนมัติ (Easiest)
auto_computed_kw = estimate_oil_heat(selected_model, Evap_temp, Cond_temp, has_eco)

# เปิดช่องให้กรอกตัวเลขจริงจากโปรแกรม MYCOMW ทับได้ทันทีเพื่อความเป๊ะ (Most Accurate)
q_oil_kw = st.number_input(
    "Detail Oil Heat Rejection (kW):",
    min_value=5.0,
    max_value=1500.0,
    value=float(auto_computed_kw),
    step=0.1,
    format="%.2f",
    help="ระบบคำนวณค่าแนะนำเบื้องต้นให้แล้ว หากพี่มีใบ Data Sheet จากโปรแกรม MYCOMW สามารถพิมพ์ตัวเลขจริงทับลงไปในช่องนี้ได้เลยครับ เพื่อความแม่นยำ 100%",
    on_change=reset_calculation
)

if abs(q_oil_kw - auto_computed_kw) < 0.01:
    st.caption("ℹ️ *ปัจจุบันระบบใช้ค่าโหลดจากการคำนวณอัตโนมัติอ้างอิงตามสภาวะ Te/Tc*")
else:
    st.caption("⚠️ *ปัจจุบันระบบใช้ค่าโหลดที่คุณกรอกปรับแต่งเอง (Manual Override)*")

st.markdown("---")

# 🔘 ส่วนที่ 3: ตัวเลือกหน่วยและการคำนวณเสริม
st.subheader("🧪 3. ค่าสัมประสิทธิ์และหน่วยแสดงผล")
unit = st.radio("เลือกหน่วยแรงดันในหน้าจอรายงาน:", ["Bar", "PSI"], horizontal=True, on_change=reset_calculation)
K = st.number_input("ค่าปรับแก้ความปลอดภัย (K Factor):", min_value=0.1, value=1.0, step=0.05, on_change=reset_calculation)

st.markdown("---")

# ปุ่มกดคำนวณหลัก
if st.button("🚀 CALCULATE VALVE SIZING", type="primary", use_container_width=True):
    st.session_state.calculated = True

# --- กระบวนการประมวลผลทางวิศวกรรม ---
if st.session_state.calculated:
    
    # 1. คำนวณความหนาแน่นสารทำความเย็น R717
    Y = nh3_liquid_density(Cond_temp)
    if has_eco:
        t_loc_evap = (Cond_temp + Evap_temp) / 2.0
        S = nh3_liquid_density(t_loc_evap)
    else:
        S = nh3_liquid_density(Evap_temp)

    # 2. คำนวณหาค่า Enthalpy เพื่อแปลง kW เป็นอัตราไหลน้ำยา G (kg/hr)
    h_f_in = 200.0 + 4.63 * Cond_temp + 0.0025 * (Cond_temp ** 2)
    if has_eco:
        t_loc_evap = (Cond_temp + Evap_temp) / 2.0
        h_g_out = 1461.9 + 1.05 * t_loc_evap - 0.0085 * (t_loc_evap ** 2)
    else:
        h_g_out = 1461.9 + 1.05 * Evap_temp - 0.0085 * (Evap_temp ** 2)
        
    dh_loc = h_g_out - h_f_in
    G = (q_oil_kw / dh_loc) * 3600 if dh_loc > 0 else 0.0

    # 3. คำนวณความดันสัมบูรณ์และ Pressure Drop
    HP_abs = nh3_temp_to_bar_abs(Cond_temp)
    LP_abs = nh3_temp_to_bar_abs(Evap_temp)
    dp_bar = HP_abs - LP_abs
    
    display_dp = dp_bar * 14.5038 if unit == "PSI" else dp_bar
    p_label = "PSI" if unit == "PSI" else "Bar"

    if G <= 0 or HP_abs <= LP_abs:
        st.error("❌ ข้อผิดพลาด: กรุณาตรวจสอบอุณหภูมิ Tc และ Te (ค่าความดันขาออกต้องไม่สูงกว่าขาเข้า)")
        st.session_state.calculated = False
    else:
        # สูตรวิศวกรรมหลักในการหาค่า Cv ของวาล์วหรี่น้ำยา
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / dp_bar)
        cv_result = part_1 * part_2 * K

        # แสดงผลลัพธ์หลักบน UI
        st.subheader("📊 สรุปผลการคัดเลือกพอร์ตวาล์ว Yosaku")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric(f"Pressure Drop รวม (ΔP)", f"{display_dp:.3f} {p_label}")
        res_col2.metric("ค่า CV รวมที่ต้องการจริง", f"{cv_result:.4f}")
        
        st.success(f"📈 **ข้อมูลทางเทคนิคหลัก:** โหลดน้ำมันทำงาน **{q_oil_kw:.2f} kW** ทำให้อัตราไหลแอมโมเนียระบายความร้อนหมุนเวียน G = **{G:.2f} kg/hr**")

        # --- ค้นหาชุด Orifice แนะนำ 5 ลำดับแรก ---
        all_options = []
        for name, max_cv in ORIFICE_DATA:
            pct = (cv_result / max_cv) * 100
            score = get_suitability_score(pct, is_single=True)
            if score > 0:
                all_options.append((score, f"1 x {name} (เปอร์เซ็นต์เปิด {pct:.1f}%)"))
                
        for (name1, cv1), (name2, cv2) in itertools.combinations_with_replacement(ORIFICE_DATA, 2):
            total_cv = cv1 + cv2
            pct = (cv_result / total_cv) * 100
            score = get_suitability_score(pct, is_single=False)
            if score > 0:
                label_text = f"2 x {name1} (เปอร์เซ็นต์เปิด {pct:.1f}%)" if name1 == name2 else f"1x {name1} + 1x {name2} (เปิดร่วม {pct:.1f}%)"
                all_options.append((score, label_text))

        all_options.sort(key=lambda x: x[0], reverse=True)
        
        st.info("🏆 **ขนาด Orifice แนะนำที่ดีที่สุด 5 อันดับแรก (คุมเปอร์เซ็นต์เปิดช่วงเซฟโซน 80% - 85%)**")
        if all_options:
            recommendation_text = ""
            rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for i, (score, label) in enumerate(all_options[:5]):
                emoji = rank_emojis[i] if i < len(rank_emojis) else f"[{i+1}]"
                st.markdown(f"**{emoji}** {label}")
                recommendation_text += f"อันดับ {i+1}: {label}\n"
        else:
            qty_needed = math.ceil(cv_result / 0.48)
            recommendation_text = f"พอร์ตมาตรฐานรองรับไม่พอ -> แนะนำเพิ่มพอร์ตขนานขนาดใหญ่เป็น {qty_needed} x JH"
            st.error(f"⚠️ {recommendation_text}")

        def get_status_text(pct):
            if pct > 100: return "เล็กเกินไป"
            elif 75 <= pct <= 85: return "เหมาะสม"
            elif 85 < pct <= 100: return "ใกล้เต็ม"
            else: return "ใหญ่เกินไป"

        # --- ตารางอ้างอิงเปรียบเทียบพอร์ตมาตรฐาน ---
        st.subheader("📋 ตารางอ้างอิงเปอร์เซ็นต์เปิด: แบบติดตั้งตัวเดียว VS ติดตั้งขนาน 2 ตัว")
        baseline_rows = []
        for name, max_cv in ORIFICE_DATA:
            pct1 = (cv_result / max_cv) * 100
            pct2 = (cv_result / (max_cv * 2)) * 100
            baseline_rows.append({
                "Orifice": name, "Max Cv": max_cv,
                "% เปิด (1 ตัว)": pct1, "สถานะ (1 ตัว)": get_status_text(pct1),
                "% เปิด (2 ตัว)": pct2, "สถานะ (2 ตัว)": get_status_text(pct2)
            })
        df_base = pd.DataFrame(baseline_rows)
        styled_base = df_base.style.apply(style_baseline_df, axis=None).format({
            "% เปิด (1 ตัว)": "{:.1f}%", "% เปิด (2 ตัว)": "{:.1f}%"
        })
        st.dataframe(styled_base, use_container_width=True, hide_index=True)

        # --- ตารางเมทริกซ์คละรุ่นผสม ---
        st.subheader("🗺️ ตารางเมทริกซ์เปอร์เซ็นต์เปิดรวม (จับคู่คละรุ่นผสม 2 ตัว)")
        matrix_dict = {}
        for name1, cv1 in ORIFICE_DATA:
            matrix_dict[name1] = {}
            for name2, cv2 in ORIFICE_DATA:
                pct = (cv_result / (cv1 + cv2)) * 100
                matrix_dict[name1][name2] = pct
        df_matrix = pd.DataFrame(matrix_dict).T
        try:
            styled_matrix = df_matrix.style.map(color_matrix_cells).format("{:.1f}%")
        except AttributeError:
            styled_matrix = df_matrix.style.applymap(color_matrix_cells).format("{:.1f}%")
        st.dataframe(styled_matrix, use_container_width=True)

        # --- ดาวน์โหลดรายงานข้อมูลเทคนิค ---
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hp_g_show = (HP_abs * 14.5038) - ATM_PSI if unit == "PSI" else HP_abs - ATM_BAR
        lp_g_show = (LP_abs * 14.5038) - ATM_PSI if unit == "PSI" else LP_abs - ATM_BAR
        p_label_g = "PSI G" if unit == "PSI" else "Bar G"
        
        log_content = (
            f"=== บันทึกรายงานการคัดเลือกขนาดวาล์ว Yosaku ({current_time}) ===\n"
            f"รุ่นคอมเพรสเซอร์ MYCOM: {selected_model}\n"
            f"สภาวะระบบ: Te = {Evap_temp:.1f} °C, Tc = {Cond_temp:.1f} °C\n"
            f"ระบบ Economizer: {'เปิดใช้งาน' if has_eco else 'ปิดใช้งาน'}\n"
            f"ค่าภาระความร้อนน้ำมันที่คำนวณใช้งาน: {q_oil_kw:.2f} kW\n"
            f"อัตราไหลแอมโมเนียระบายความร้อน (G): {G:.2f} kg/h\n"
            f"ค่าความต้องการ CV รวมทางวิศวกรรม: {cv_result:.4f}\n"
            f"--------------------------------------------------\n"
            f"ผลการคัดเลือก Orifice แนะนำ:\n{recommendation_text}"
            f"--------------------------------------------------\n"
        )
        st.download_button(
            label="📥 ดาวน์โหลดรายงานเทคนิค (Technical Spec Log)",
            data=log_content,
            file_name=f"Yosaku_Report_{selected_model.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
