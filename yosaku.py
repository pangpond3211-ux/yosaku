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
    page_title="Yosaku Selection",
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

# สไตล์สีสำหรับตารางสถานะ
COLOR_MAP = {
    "เล็กเกินไป": "background-color: #ffcccc; color: #cc0000;",
    "เหมาะสม": "background-color: #d4edda; color: #155724; font-weight: bold;",
    "ใกล้เต็ม": "background-color: #fff3cd; color: #856404;",
    "ใหญ่เกินไป": "background-color: #ffffff; color: #6c757d;"
}

if "calculated" not in st.session_state:
    st.session_state.calculated = False

def reset_calculation():
    """ฟังก์ชันสำหรับสั่งให้ซ่อนผลลัพธ์ทันทีเมื่อมีการเปลี่ยนอินพุต"""
    st.session_state.calculated = False

def get_suitability_score(pct, is_single):
    if pct > 87: 
        return -1
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

# 🧪 ฟังก์ชันแปลงอุณหภูมิอิ่มตัว R717 (°C) -> ความดันสัมบูรณ์ (Bar Absolute) ด้วย Antoine Equation
def nh3_temp_to_bar_abs(t_c):
    #แปลงองศาเซลเซียสเป็นเคลวิน
    T_k = t_c + 273.15
    # สัมประสิทธิ์ Antoineสำหรับ Ammonia (R717) ช่วงอุณหภูมิใช้งานทั่วไป
    # P ในหน่วย bar
    A = 4.86962
    B = 1101.41
    C = -26.15
    
    try:
        p_bar = 10 ** (A - (B / (T_k + C)))
        return p_bar
    except ZeroDivisionError:
        return 0.0

# ========================================================
# ส่วนหัวของโปรแกรม (Header)
# ========================================================
if os.path.exists("logo.png"):
    st.image("logo.png", width=150)
else:
    st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")

st.title("💻⚙️ Yosaku Selection")
st.caption("พัฒนาโดย Chattrawat Khamsee | เวอร์ชัน Web App สำหรับมือถือ")
st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")

st.markdown("### 📊 สมการอ้างอิงการคำนวณ (Formula)")
st.latex(r"C_v = 1.17 \times \left( \frac{G}{1000 \times Y} \right) \times \sqrt{\frac{S}{HP - LP}} \times K")

st.markdown("""
**ความหมายตัวแปรตามมาตรฐานระบบ:**
* **G (Ref. flow rate):** อัตราการไหลของสารทำความเย็น (หน่วย kg/hr)
* **Y (Specific weight before valve):** ค่า Specific weight ของสารทำความเย็นก่อนเข้าวาล์ว
* **S (Specific weight after valve):** ค่า Specific weight ของสารทำความเย็นหลังออกจากวาล์ว
* **HP - LP (Pressure Drop):** ผลต่างความดันขาเข้าและขาออก (หน่วย Bar)
* **K:** ค่าปรับแก้ (K Factor)
""")

st.markdown("---")

st.subheader("📋 กรอกข้อมูลคุณสมบัติระบบ")
col_g1, col_g2 = st.columns(2)
with col_g1:
    G = st.number_input("G: Ref. flow rate (kg/hr):", min_value=0.0, value=1000.0, step=10.0, on_change=reset_calculation)
    Y = st.number_input("Y: Specific weight before valve:", min_value=0.01, value=0.583, step=0.01, format="%.3f", on_change=reset_calculation)
with col_g2:
    K = st.number_input("ค่าปรับแก้ K Factor:", min_value=0.0, value=1.0, step=0.1, on_change=reset_calculation)
    S = st.number_input("S: Specific weight after valve:", min_value=0.01, value=0.583, step=0.01, format="%.3f", on_change=reset_calculation)

st.markdown("---")

input_mode = st.radio(
    "เลือกวิธีระบุสภาวะความดัน:",
    ["วิธีที่ 1: ป้อนด้วยความดันเกจโดยตรง (HP / LP)", "วิธีที่ 2: ป้อนด้วยอุณหภูมิแอมโมเนีย (Tc / Te)"],
    horizontal=False,
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
else:
    with col1:
        Cond_temp = st.number_input("อุณหภูมิควบแน่น Condensing Temp Tc (°C):", min_value=-50.0, max_value=60.0, value=38.0, step=1.0, on_change=reset_calculation)
    with col2:
        Evap_temp = st.number_input("อุณหภูมิระเหย Evaporating Temp Te (°C):", min_value=-50.0, max_value=60.0, value=-10.0, step=1.0, on_change=reset_calculation)

if st.button("🚀 CALCULATE", type="primary", use_container_width=True):
    st.session_state.calculated = True

# --- ส่วนการคำนวณและแสดงผลลัพธ์ ---
if st.session_state.calculated:
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
        st.warning("⚠️ กรุณากรอกอัตราไหลสารทำความเย็น G ให้มากกว่า 0")
        st.session_state.calculated = False
    elif HP <= LP:
        st.error("❌ ข้อผิดพลาด: ความดันขาเข้า (HP) ต้องมากกว่าความดันขาออก (LP)")
        st.session_state.calculated = False
    else:
        display_dp = (HP - LP) * 14.5038 if unit == "PSI" else (HP - LP)
        
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / (HP - LP))
        cv_result = part_1 * part_2 * K

        st.subheader("📊 ผลการคำนวณ")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Pressure Drop", f"{display_dp:.3f} {unit}")
        res_col2.metric("ผลรวมค่า CV ที่คำนวณได้", f"{cv_result:.4f}")
        
        hp_g_show = (HP * 14.5038) - ATM_PSI if unit == "PSI" else HP - ATM_BAR
        lp_g_show = (LP * 14.5038) - ATM_PSI if unit == "PSI" else LP - ATM_BAR
        st.info(f"💡 **สภาวะในระบบ:** G = {G} kg/hr | HP = {hp_g_show:.3f} {p_label} | LP = {lp_g_show:.3f} {p_label} (Y={Y}, S={S})")

        # --- 1. คำนวณหา Top 5 ทางเลือกที่ดีที่สุด ---
        all_options = []
        recommendation_text = ""  # แก้ไข: ประกาศตัวแปรล่วงหน้าเพื่อป้องกันบั๊ก String เคลียร์ค่า
        
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

        # --- 2. สร้างตารางที่ 1 & 2 ---
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
            "% เปิด (1 ตัว)": "{:.1f}%",
            "% เปิด (2 ตัว)": "{:.1f}%"
        })
        st.dataframe(styled_base, use_container_width=True, hide_index=True)

        # --- 3. สร้างตารางที่ 3: เมทริกซ์การคละรุ่น ---
        st.subheader("🗺️ ตารางวิเคราะห์เปอร์เซ็นต์เปิดรวม แบบจับคู่คละรุ่น 2 ตัว")
        st.caption("📱 *สำหรับผู้ใช้งานมือถือ: สามารถใช้นิ้วปัดขวาที่ตัวตารางเพื่อเลื่อนดู Orifice รุ่นอื่น ๆ ได้*")
        
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

        # --- 4. ระบบดาวน์โหลด Log ---
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = (
            f"=== บันทึกเมื่อ {current_time} ===\n"
            f"วิธีป้อนข้อมูล: {input_mode}\n"
            f"Ref. flow rate G: {G} kg/h (Suction from Compressor)\n"
            f"ความดันที่ป้อนหน้างาน: HP={hp_g_show:.3f} {p_label}, LP={lp_g_show:.3f} {p_label}\n"
            f"ความดันคำนวณจริงเบื้องหลัง: HP={HP:.3f} Bar A, LP={LP:.3f} Bar A\n"
            f"ค่าสัมประสิทธิ์ที่ใช้: Y={Y}, S={S}, K={K}\n"
            f"ผลลัพธ์ค่า CV วาล์วที่คำนวณได้: {cv_result:.4f}\n"
            f"--- ทางเลือกที่เหมาะสมที่สุด (Top 5) ---\n"
            f"{recommendation_text}"
            f"{'-'*50}\n"
        )
        st.download_button(
            label="📥 ดาวน์โหลดไฟล์ผลการคำนวณ (Log)",
            data=log_content,
            file_name=f"Yosaku_Log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
