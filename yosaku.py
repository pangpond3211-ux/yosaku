import streamlit as st
import pandas as pd
import math
import itertools
from datetime import datetime

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

# 💾 ฐานข้อมูลเชิงวิศวกรรม: ค่าแนะนำ Detail Oil Heat Rejection (kW) เบื้องต้นของ MYCOM
MYCOM_OIL_REJECTION_DB = {
    # --- 160 Series ---
    "MYCOM 160 VMS": 32.0,
    "MYCOM 160 VMD": 45.0,
    "MYCOM 160 VLD": 58.0,
    
    # --- 170 J-Series ---
    "MYCOM 170JS-V": 55.0,
    "MYCOM 170JM-V": 65.0,
    "MYCOM 170JL-V": 75.0,
    
    # --- 200 Series ---
    "MYCOM 200 VSD": 65.0,
    "MYCOM 200 VMD": 88.0,
    "MYCOM 200 VLD": 110.0,
    
    # --- 220 J-Series ---
    "MYCOM 220JS-V": 105.0,
    "MYCOM 220JM-V": 125.0,
    "MYCOM 220JL-V": 145.0,
    
    # --- 250 Series ---
    "MYCOM 250 VSD": 135.0,
    "MYCOM 250 VMD": 170.0,
    "MYCOM 250 VLD": 210.0,
    
    # --- 280 J-Series ---
    "MYCOM 280JS-V": 195.0,
    "MYCOM 280JM-V": 230.0,
    "MYCOM 280JL-V": 265.0,
    
    # --- 320 Series ---
    "MYCOM 320 VSD": 245.0,
    "MYCOM 320 VMD": 295.0,
    "MYCOM 320 VLD": 350.0
}

# 🔹 ระบบจำสถานะคำนวณ
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
    """คำนวณ Specific Weight / Density ของ R717 Liquid (kg/L)"""
    return 0.6386 - 0.00138 * t_c - 0.0000025 * (t_c ** 2)

# --- ฟังก์ชันช่วยงานดีไซน์และแสดงผลตาราง ---
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
st.caption("🚀 เวอร์ชันความแม่นยำสูง: ดึงค่าเริ่มต้นอัตโนมัติ + รองรับการปรับแก้โหลด kW ตามสภาวะ Te/Tc จริงจาก MYCOMW")
st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")

st.markdown("---")

# 🔘 ส่วนที่ 1: เลือกรุ่นคอมเพรสเซอร์ & หยอดโหลดความร้อนน้ำมัน
st.subheader("📊 1. เลือกรุ่นคอมเพรสเซอร์ & โหลดความร้อนน้ำมัน (Oil Heat Load)")
selected_model = st.selectbox(
    "กรุณาเลือกรุ่นคอมเพรสเซอร์หน้างาน:",
    list(MYCOM_OIL_REJECTION_DB.keys()),
    on_change=reset_calculation
)

# ดึงค่าเริ่มต้น (Default) จากฐานข้อมูลประจำรุ่นมารองรับไว้ก่อน
q_oil_kw_default = MYCOM_OIL_REJECTION_DB[selected_model]

# เปิดกล่องรับข้อมูลให้ผู้ใช้งานแก้ไขตัวเลขตามความจริงของสภาวะ Te/Tc ได้เลยเพื่อความแม่นยำ 100%
q_oil_kw = st.number_input(
    f"Detail Oil Heat Rejection ของรุ่น {selected_model} (kW):",
    min_value=5.0,
    max_value=1500.0,
    value=float(q_oil_kw_default),
    step=1.0,
    help="ระบบใส่ค่าแนะนำเฉลี่ยให้เบื้องต้น แนะนำให้ตรวจสอบกับโปรแกรม MYCOMW ตามสภาวะดีไซน์จริง แล้วนำมาป้อนลงช่องนี้เพื่อความแม่นยำสูงสุด",
    on_change=reset_calculation
)

loc_return_port = st.selectbox(
    "พอร์ตที่ไอสารทำความเย็นจากชุด Oil Cooler วิ่งกลับเข้าคอมเพรสเซอร์:",
    ["ส่งกลับฝั่ง Suction (LP Port)", "ส่งกลับฝั่ง Economizer (ECO Port)"],
    on_change=reset_calculation
)

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

# 🔘 ส่วนที่ 3: สัมประสิทธิ์ทางเทอร์โมไดนามิกส์ (ระบบคำนวณอัตโนมัติ)
st.subheader("🧪 3. คุณสมบัติสารทำความเย็น (Fluid Properties)")

Y = nh3_liquid_density(Cond_temp)

if "ECO Port" in loc_return_port:
    loc_evap_t = (Cond_temp + Evap_temp) / 2.0
    S = nh3_liquid_density(loc_evap_t)
else:
    S = nh3_liquid_density(Evap_temp)

col_prop1, col_prop2 = st.columns(2)
with col_prop1:
    st.number_input("Y: ความหนาแน่นก่อนเข้าวาล์ว (kg/L):", value=float(Y), format="%.3f", disabled=True)
    K = st.number_input("ค่าปรับแก้ความปลอดภัย K Factor:", min_value=0.0, value=1.0, step=0.1, on_change=reset_calculation)
with col_prop2:
    st.number_input("S: ความหนาแน่นหลังออกจากวาล์ว (kg/L):", value=float(S), format="%.3f", disabled=True)

st.markdown("---")

# ปุ่มกดคำนวณหลัก
if st.button("🚀 CALCULATE VALVE SIZING", type="primary", use_container_width=True):
    st.session_state.calculated = True

# --- ประมวลผลลัพธ์วิศวกรรมหลังกดปุ่ม ---
if st.session_state.calculated:
    
    # 🧮 คำนวณหาค่า G ตามพลังงานความร้อนที่ผู้ใช้กำหนด (ผันแปรตามสภาวะ Te/Tc)
    h_f_in = 200.0 + 4.63 * Cond_temp + 0.0025 * (Cond_temp ** 2)
    
    if "ECO Port" in loc_return_port:
        t_loc_evap = (Cond_temp + Evap_temp) / 2.0
        h_g_out = 1461.9 + 1.05 * t_loc_evap - 0.0085 * (t_loc_evap ** 2)
    else:
        h_g_out = 1461.9 + 1.05 * Evap_temp - 0.0085 * (Evap_temp ** 2)
        
    dh_loc = h_g_out - h_f_in
    if dh_loc > 0:
        G = (q_oil_kw / dh_loc) * 3600
    else:
        G = 0.0

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

    if G <= 0:
        st.error("❌ ข้อผิดพลาด: ค่าความร้อนหรืออุณหภูมิระบบไม่ถูกต้อง ไม่สามารถหาค่าอัตราการไหลได้")
        st.session_state.calculated = False
    elif HP <= LP:
        st.error("❌ ข้อผิดพลาด: ความดันขาเข้าคอนเดนเซอร์ (HP) ต้องสูงกว่าความดันขาออก (LP)")
        st.session_state.calculated = False
    else:
        display_dp = (HP - LP) * 14.5038 if unit == "PSI" else (HP - LP)
        
        # สูตรวิศวกรรมหลักในการหาค่า Cv ของวาล์วหรี่น้ำยา
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / (HP - LP))
        cv_result = part_1 * part_2 * K

        # แสดงผลลัพธ์หลักบน UI
        st.subheader("📊 ผลการคำนวณและเลือกขนาดพอร์ตวาล์ว")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Pressure Drop (ΔP)", f"{display_dp:.3f} {unit}")
        res_col2.metric("ค่า CV รวมที่ต้องการจริง", f"{cv_result:.4f}")
        
        hp_g_show = (HP * 14.5038) - ATM_PSI if unit == "PSI" else HP - ATM_BAR
        lp_g_show = (LP * 14.5038) - ATM_PSI if unit == "PSI" else LP - ATM_BAR
        st.info(f"💡 **ผลลัพธ์การประมวลผล:** โหลดน้ำมัน **{q_oil_kw:.1f} kW** -> แปลงเป็นอัตราไหลแอมโมเนียหล่อเย็น G = **{G:.2f} kg/hr**")

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
        
        st.success("🏆 **รูปแบบขนาด Orifice แนะนำที่ดีที่สุด 5 อันดับแรก (แนะนำให้อยู่ในช่วงประมาณ 80% - 85%)**")
        if all_options:
            recommendation_text = ""
            rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for i, (score, label) in enumerate(all_options[:5]):
                emoji = rank_emojis[i] if i < len(rank_emojis) else f"[{i+1}]"
                st.markdown(f"**{emoji}** {label}")
                recommendation_text += f"อันดับ {i+1}: {label}\n"
        else:
            qty_needed = math.ceil(cv_result / 0.48)
            recommendation_text = f"ไม่มีขนาดเดี่ยวหรือคู่ที่เปิดอยู่ในเกณฑ์ปลอดภัย -> แนะนำให้ขนานพอร์ตใหญ่เพิ่มเป็น {qty_needed} x JH"
            st.error(f"⚠️ {recommendation_text}")

        def get_status_text(pct):
            if pct > 100: return "เล็กเกินไป"
            elif 75 <= pct <= 85: return "เหมาะสม"
            elif 85 < pct <= 100: return "ใกล้เต็ม"
            else: return "ใหญ่เกินไป"

        # --- ตารางวิเคราะห์เปรียบเทียบพอร์ตมาตรฐาน ---
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

        # --- ตารางเมทริกซ์คละรุ่นแบบละเอียด ---
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

        # --- ระบบจัดทำไฟล์รายงาน (Log File) ---
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = (
            f"=== บันทึกรายงานการคัดเลือกขนาดวาล์ว Yosaku ({current_time}) ===\n"
            f"รุ่นคอมเพรสเซอร์ MYCOM ที่เลือก: {selected_model}\n"
            f"ค่า Detail Oil Heat Rejection ที่ใช้จริง: {q_oil_kw:.1f} kW\n"
            f"พอร์ตส่งไอกลับคอมเพรสเซอร์: {loc_return_port}\n"
            f"คำนวณอัตราการไหลน้ำยาแอมโมเนียได้ (G): {G:.2f} kg/h\n"
            f"สภาวะแรงดันควบคุม: HP={hp_g_show:.3f} {p_label}, LP={lp_g_show:.3f} {p_label}\n"
            f"ผลรวมค่าความต้องการ CV ทางวิศวกรรม: {cv_result:.4f}\n"
            f"--------------------------------------------------\n"
            f"ผลการคัดเลือก Orifice แนะนำ:\n{recommendation_text}"
            f"--------------------------------------------------\n"
        )
        st.download_button(
            label="📥 ดาวน์โหลดรายงานเทคนิค (Technical Spec Log)",
            data=log_content,
            file_name=f"Yosaku_OilCooler_{selected_model.replace(' ', '_').replace('-', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
