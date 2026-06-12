import streamlit as st
import pandas as pd
import math
import itertools
from datetime import datetime
import os

# ========================================================
# [CONFIG] ตั้งค่าความดันบรรยากาศอ้างอิงของบริษัท (หน้างาน)
# ========================================================
ATM_BAR = 1.013    # มาตรฐานทั่วไปใช้ 1.013 Bar
ATM_PSI = 14.70    # มาตรฐานฝั่ง PSI

# ตั้งค่าหน้าตาของ Web App
st.set_page_config(
    page_title="Yosaku Selection Pro",
    page_icon="👨‍🔧",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ข้อมูลตาราง Orifice มาตรฐาน
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

# 🔹 ระบบจำสถานะและฟังก์ชันเคลียร์ค่าเมื่ออินพุตเปลี่ยน (Reset Callback)
if "calculated" not in st.session_state:
    st.session_state.calculated = False

def reset_calculation():
    st.session_state.calculated = False

# 🧪 [MYCOM CORE] ฟังก์ชันคำนวณคุณสมบัติทางเทอร์โมไดนามิกส์ของ R717 (Ammonia)
def nh3_temp_to_bar_abs(t_c):
    """แปลงอุณหภูมิอิ่มตัว (°C) -> ความดันสัมบูรณ์ (Bar Absolute)"""
    return (3.26631702e-08 * t_c**4 + 
            1.54531857e-05 * t_c**3 + 
            2.34641900e-03 * t_c**2 + 
            1.60674845e-01 * t_c + 
            4.29486480e+00)

def nh3_liquid_density(t_c):
    """คำนวณ Specific Weight / Density ของ R717 Liquid (kg/L) อ้างอิงจากอุณหภูมิ"""
    return 0.6386 - 0.00138 * t_c - 0.0000025 * (t_c ** 2)

def nh3_calc_g_from_load(capacity_kw, t_c, t_e):
    """คำนวณอัตราการไหล G (kg/hr) จากโหลดความเย็นหลัก"""
    h_f = 200.0 + 4.63 * t_c + 0.0025 * (t_c ** 2)
    h_g = 1461.9 + 1.05 * t_e - 0.0085 * (t_e ** 2)
    refrigerating_effect = h_g - h_f
    if refrigerating_effect <= 0:
        return 0.0
    return (capacity_kw / refrigerating_effect) * 3600

# --- ฟังก์ชันช่วยงานตาราง ---
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
# ส่วนหัวของโปรแกรม (Header)
# ========================================================
st.title("💻⚙️ Yosaku Selection Pro")
st.caption("เวอร์ชันอัปเกรด: รองรับการเลือกวาล์วหล่อเย็นน้ำมัน Liquid Oil Cooler (MYCOM DSH 20K)")
st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")

st.markdown("---")

# 🔘 ส่วนที่ 1: เลือกวิธีระบุอัตราการไหล G (เพิ่มโหมด LOC Oil Cooler)
st.subheader("📊 1. วิธีหาค่าอัตราการไหลสารทำความเย็น (Ref. Flow Rate G)")
g_mode = st.radio(
    "เลือกวัตถุประสงค์ของวาล์วที่ต้องการคำนวณ:",
    [
        "ป้อนค่าอัตราการไหล G (kg/hr) โดยตรง [จากช่อง Refri. flow ของระบบหรือ Oil Cooler]", 
        "คำนวณ G จากขนาดโหลดทำความเย็นหน้างาน (Main Cooling Capacity)",
        "คำนวณ G สำหรับวาล์วระบบหล่อเย็นน้ำมันคอมเพรสเซอร์ (Liquid Oil Cooler - LOC) 🛢️"
    ],
    on_change=reset_calculation
)

# ตัวแปรสำหรับระบบ LOC
q_oil_kw = 0.0
loc_return_port = "ส่งกลับฝั่ง Suction (LP)"

if g_mode == "ป้อนค่าอัตราการไหล G (kg/hr) โดยตรง [จากช่อง Refri. flow ของระบบหรือ Oil Cooler]":
    G_input_val = st.number_input("G: Ref. flow rate (kg/hr):", min_value=0.0, value=1000.0, step=10.0, on_change=reset_calculation)
    st.caption("💡 *หากคำนวณวาล์ว Oil Cooler พี่สามารถเอาตัวเลขจากช่อง Refri. flow rate for Oil Cooler ในใบ MYCOM มาพิมพ์ใส่ตรงนี้ได้เลยครับ*")

elif g_mode == "คำนวณ G จากขนาดโหลดทำความเย็นหน้างาน (Main Cooling Capacity)":
    col_cap1, col_cap2 = st.columns(2)
    with col_cap1:
        load_unit = st.radio("หน่วยของโหลดความเย็น:", ["kW (กิโลวัตต์)", "TR (ตันความเย็น)"], on_change=reset_calculation)
    with col_cap2:
        load_value = st.number_input("ระบุขนาดโหลดความเย็นหน้างาน:", min_value=0.0, value=300.0, step=10.0, on_change=reset_calculation)

else:
    # 🛢️ โหมดคำนวณเฉพาะสำหรับวาล์วป้อนน้ำยา Liquid Oil Cooler (LOC)
    col_loc1, col_loc2 = st.columns(2)
    with col_loc1:
        q_oil_kw = st.number_input("Oil Cooler Heat Load (kW) จากสเปก MYCOM:", min_value=0.0, value=45.0, step=1.0, on_change=reset_calculation)
    with col_loc2:
        loc_return_port = st.selectbox(
            "พอร์ตที่ไอสารทำความเย็นจาก LOC วิ่งกลับเข้าคอมเพรสเซอร์:",
            ["ส่งกลับฝั่ง Suction (LP Port)", "ส่งกลับฝั่ง Economizer (ECO Port)"],
            on_change=reset_calculation
        )
    st.caption("⚠️ *ระบบจะคำนวณอัตราการไหล G อัตโนมัติภายใต้เงื่อนไขควบคุมอุณหภูมิน้ำมันเสถียร (Discharge Superheat 20K)*")

st.markdown("---")

# 🔘 ส่วนที่ 2: สภาวะความดัน/อุณหภูมิระบบ
st.subheader("🌡️ 2. สภาวะความดันและอุณหภูมิในระบบ")
input_mode = st.radio(
    "เลือกวิธีระบุสภาวะความดัน:",
    ["วิธีที่ 1: ป้อนด้วยความดันเกจโดยตรง (HP / LP)", "วิธีที่ 2: ป้อนด้วยอุณหภูมิแอมโมเนีย (Tc / Te)"],
    on_change=reset_calculation
)

unit = st.radio("เลือกหน่วยความดันแสดงผล:", ["Bar", "PSI"], horizontal=True, on_change=reset_calculation)

p_label = "Bar G" if unit == "Bar" else "PSI G"
min_p = -ATM_BAR if unit == "Bar" else -ATM_PSI
hp_default = (14.7 - ATM_BAR) if unit == "Bar" else 0.0
lp_default = (2.91 - ATM_BAR) if unit == "Bar" else -11.79
p_step = 0.001 if unit == "Bar" else 0.1

col1, col2 = st.columns(2)
if input_mode == "วิธีที่ 1: ป้อนด้วยความดันเกจโดยตรง (HP / LP)":
    with col1:
        HP_input = st.number_input(f"ความดันขาเข้า HP ({p_label}):", min_value=float(min_p), value=float(hp_default), step=p_step, format="%.3f", on_change=reset_calculation)
    with col2:
        LP_input = st.number_input(f"ความดันขาออก LP ({p_label}):", min_value=float(min_p), value=float(lp_default), step=p_step, format="%.3f", on_change=reset_calculation)
    
    HP_bar_a = (HP_input + ATM_PSI) / 14.5038 if unit == "PSI" else HP_input + ATM_BAR
    LP_bar_a = (LP_input + ATM_PSI) / 14.5038 if unit == "PSI" else LP_input + ATM_BAR
    Cond_temp = (HP_bar_a / 4.29)**(1/1.2) if HP_bar_a > 4.29 else 0.0
    Evap_temp = (LP_bar_a / 4.29)**(1/1.2) if LP_bar_a > 4.29 else -10.0
else:
    with col1:
        Cond_temp = st.number_input("อุณหภูมิควบแน่น Condensing Temp Tc (°C):", min_value=-50.0, max_value=60.0, value=38.0, step=1.0, on_change=reset_calculation)
    with col2:
        Evap_temp = st.number_input("อุณหภูมิระเหย Evaporating Temp Te (°C):", min_value=-50.0, max_value=60.0, value=-10.0, step=1.0, on_change=reset_calculation)

st.markdown("---")

# 🔘 ส่วนที่ 3: สัมประสิทธิ์และระบบคำนวณอัตโนมัติ
st.subheader("🧪 3. คุณสมบัติสารทำความเย็น (Fluid Properties)")
auto_prop = st.checkbox("🔮 เปิดระบบคำนวณค่า Y และ S อัตโนมัติ (ตามสภาวะจริงหน้างาน)", value=True, on_change=reset_calculation)

col_g1, col_g2 = st.columns(2)
with col_g1:
    if auto_prop:
        Y = nh3_liquid_density(Cond_temp)
        st.number_input("Y: Specific weight before valve (คำนวณออโต้):", value=float(Y), format="%.3f", disabled=True)
    else:
        Y = st.number_input("Y: Specific weight before valve:", min_value=0.01, value=0.583, step=0.01, format="%.3f", on_change=reset_calculation)
    K = st.number_input("ค่าปรับแก้ K Factor:", min_value=0.0, value=1.0, step=0.1, on_change=reset_calculation)

with col_g2:
    if auto_prop:
        if g_mode == "คำนวณ G สำหรับวาล์วระบบหล่อเย็นน้ำมันคอมเพรสเซอร์ (Liquid Oil Cooler - LOC) 🛢️" and "ECO Port" in loc_return_port:
            # ถ้ากลับพอร์ต ECO อุณหภูมิระเหยในชุด LOC จะอยู่กึ่งกลางระหว่าง Tc และ Te (Intermediate Temp)
            loc_evap_t = (Cond_temp + Evap_temp) / 2.0
            S = nh3_liquid_density(loc_loc_t) if 'loc_loc_t' in locals() else nh3_liquid_density(loc_evap_t)
        else:
            S = nh3_liquid_density(Evap_temp)
        st.number_input("S: Specific weight after valve (คำนวณออโต้):", value=float(S), format="%.3f", disabled=True)
    else:
        S = st.number_input("S: Specific weight after valve:", min_value=0.01, value=0.583, step=0.01, format="%.3f", on_change=reset_calculation)

st.markdown("---")

# ปุ่มคำนวณหลัก
if st.button("🚀 CALCULATE", type="primary", use_container_width=True):
    st.session_state.calculated = True

# --- ประมวลผลและแสดงผลลัพธ์ ---
if st.session_state.calculated:
    # 1. จัดการคำนวณค่า G ตามเงื่อนไขที่เลือก
    if g_mode == "ป้อนค่าอัตราการไหล G (kg/hr) โดยตรง [จากช่อง Refri. flow ของระบบหรือ Oil Cooler]":
        G = G_input_val
    elif g_mode == "คำนวณ G จากขนาดโหลดทำความเย็นหน้างาน (Main Cooling Capacity)":
        kw_val = load_value if load_unit == "kW (กิโลวัตต์)" else load_value * 3.51685
        G = nh3_calc_g_from_load(kw_val, Cond_temp, Evap_temp)
    else:
        # 🛢️ คำนวณหาค่า G สำหรับ Liquid Oil Cooler
        # หาค่า Enthalpy ของเหลวทางเข้าขยายตัวจากคอนเดนเซอร์ (h_f @ Tc)
        h_f_in = 200.0 + 4.63 * Cond_temp + 0.0025 * (Cond_temp ** 2)
        
        # ตรวจสอบจุดส่งไอแอมโมเนียกลับเพื่อหาค่า h_g ขาออกของ LOC
        if "ECO Port" in loc_return_port:
            t_loc_evap = (Cond_temp + Evap_temp) / 2.0  # ประมาณค่าอุณหภูมิแรงดันกลาง Economizer
            h_g_out = 1461.9 + 1.05 * t_loc_evap - 0.0085 * (t_loc_evap ** 2)
        else:
            h_g_out = 1461.9 + 1.05 * Evap_temp - 0.0085 * (Evap_temp ** 2)
            
        dh_loc = h_g_out - h_f_in
        if dh_loc > 0:
            G = (q_oil_kw / dh_loc) * 3600  # แปลงเป็น kg/hr
        else:
            G = 0.0

    # 2. แปลงความดันใช้งานเข้าสูตรหลัก
    if input_mode == "วิธีที่ 1: ป้อนด้วยความดันเกจโดยตรง (HP / LP)":
        if unit == "PSI":
            HP = (HP_input + ATM_PSI) / 14.5038
            LP = (LP_input + ATM_PSI) / 14.5038
        else:
            HP = HP_input + ATM_BAR
            LP = LP_input + ATM_BAR
    else:
        HP = nh3_temp_to_bar_abs(Cond_temp)
        LP = nh3_temp_to_bar_abs(Evap_temp)

    # ตรวจสอบความถูกต้องทางวิศวกรรม
    if G <= 0:
        st.error("❌ ข้อผิดพลาด: ไม่สามารถคำนวณหาค่าอัตราไหล G สำหรับ Oil Cooler ได้ กรุณาตรวจสอบค่าโหลดความร้อน")
        st.session_state.calculated = False
    elif HP <= LP:
        st.error("❌ ข้อผิดพลาด: ความดันขาเข้า (HP) ต้องมากกว่าความดันขาออก (LP)")
        st.session_state.calculated = False
    else:
        display_dp = (HP - LP) * 14.5038 if unit == "PSI" else (HP - LP)
        
        # สูตรหลักคำนวณ Cv
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / (HP - LP))
        cv_result = part_1 * part_2 * K

        # แสดงผลลัพธ์หลัก
        st.subheader("📊 ผลการคำนวณ")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Pressure Drop Across Valve", f"{display_dp:.3f} {unit}")
        res_col2.metric("ผลรวมค่า CV ที่คำนวณได้", f"{cv_result:.4f}")
        
        hp_g_show = (HP * 14.5038) - ATM_PSI if unit == "PSI" else HP - ATM_BAR
        lp_g_show = (LP * 14.5038) - ATM_PSI if unit == "PSI" else LP - ATM_BAR
        st.info(f"💡 **สภาวะคำนวณจริง:** LOC Flow Rate G = {G:.2f} kg/hr | HP = {hp_g_show:.3f} {p_label} | LP = {lp_g_show:.3f} {p_label} (Y={Y:.3f}, S={S:.3f})")

        # --- คำนวณหา Top 5 แนะนำ ---
        all_options = []
        for name, max_cv in ORIFICE_DATA:
            pct = (cv_result / max_cv) * 100
            score = get_suitability_score(pct, is_single=True)
            if score > 0:
                all_options.append((score, f"1 x {name} (เปิด {pct:.1f}%)"))
                
        for (name1, cv1), (name2, cv2) in itertools.combinations_with_replacement(ORIFICE_DATA, 2):
            total_cv = cv1 + cv2
            pct = (cv_result / total_cv) * 100
            score = get_suitability_score(pct, is_single=False)
            if score > 0:
                label_text = f"2 x {name1} (เปิด {pct:.1f}%)" if name1 == name2 else f"1x {name1} + 1x {name2} (เปิดรวม {pct:.1f}%)"
                all_options.append((score, label_text))

        all_options.sort(key=lambda x: x[0], reverse=True)
        
        st.success("🏆 **ชุดประกอบแนะนำที่ดีที่สุด 5 อันดับแรก (แนะนำที่ 80% - 85%)**")
        if all_options:
            recommendation_text = ""
            rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for i, (score, label) in enumerate(all_options[:5]):
                emoji = rank_emojis[i] if i < len(rank_emojis) else f"[{i+1}]"
                st.markdown(f"**{emoji}** {label}")
                recommendation_text += f"อันดับ {i+1}: {label}\n"
        else:
            qty_needed = math.ceil(cv_result / 0.48)
            recommendation_text = f"ไม่มีชุดประกอบที่เปิดไม่เกิน 87% -> แนะนำใช้ขนานเพิ่มเป็น {qty_needed} x JH"
            st.error(f"⚠️ {recommendation_text}")

        def get_status_text(pct):
            if pct > 100: return "เล็กเกินไป"
            elif 75 <= pct <= 85: return "เหมาะสม"
            elif 85 < pct <= 100: return "ใกล้เต็ม"
            else: return "ใหญ่เกินไป"

        # --- ตารางเดี่ยว VS ขนานรุ่นเดียวกัน ---
        st.subheader("📋 ตารางอ้างอิงสถานะแบบ 1 ตัว VS ขนาน 2 ตัวรุ่นเดียวกัน")
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

        # --- ตารางเมทริกซ์คละรุ่น ---
        st.subheader("🗺️ ตารางวิเคราะห์เปอร์เซ็นต์เปิดรวม แบบจับคู่คละรุ่น 2 ตัว")
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

        # --- ระบบดาวน์โหลด Log ---
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = (
            f"=== บันทึกคำนวณวาล์ว Liquid Oil Cooler เมื่อ {current_time} ===\n"
            f"วัตถุประสงค์วาล์ว: {g_mode}\n"
            f"พอร์ตส่งไอสารทำความเย็นกลับ: {loc_return_port if g_mode not in ['ป้อนค่าอัตราการไหล G (kg/hr) โดยตรง [จากช่อง Refri. flow ของระบบหรือ Oil Cooler]', 'คำนวณ G จากขนาดโหลดทำความเย็นหน้างาน (Main Cooling Capacity)'] else 'N/A'}\n"
            f"อัตราการไหลที่ใช้คำนวณ G: {G:.2f} kg/h\n"
            f"ความดันใช้งานหน้างาน: HP={hp_g_show:.3f} {p_label}, LP={lp_g_show:.3f} {p_label}\n"
            f"คุณสมบัติแอมโมเนียคำนวณออโต้: Y={Y:.3f}, S={S:.3f}\n"
            f"ผลลัพธ์ค่า CV วาล์วที่คำนวณได้: {cv_result:.4f}\n"
            f"--- ทางเลือกที่เหมาะสมที่สุด (Top 5) ---\n"
            f"{recommendation_text}"
            f"{'-'*50}\n"
        )
        st.download_button(
            label="📥 ดาวน์โหลดไฟล์ผลการคำนวณวาล์ว Oil Cooler (Log)",
            data=log_content,
            file_name=f"Yosaku_LOC_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
