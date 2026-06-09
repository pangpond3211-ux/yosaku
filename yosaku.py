import streamlit as st
import pandas as pd
import math
import itertools
from datetime import datetime
import os

# ตั้งค่าหน้าตาของ Web App ให้เหมาะกับมือถือ
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

def get_suitability_score(pct, is_single):
    if pct > 87:  # ⚠️ เกิน 87% ขึ้นไป ให้ตัดออกจาก Choice แนะนำทันที
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

# 🧪 ฟังก์ชันคำนวณความดันสัมบูรณ์ R717 (Bar Abs) จากอุณหภูมิอิ่มตัว
def nh3_temp_to_bar_abs(t_c):
    return (3.26631702e-08 * t_c**4 + 
            1.54531857e-05 * t_c**3 + 
            2.34641900e-03 * t_c**2 + 
            1.60674845e-01 * t_c + 
            4.29486480e+00)

# 🧪 ฟังก์ชันคำนวณ Specific Gravity (Saturated Liquid Density / 1000) ของ R717 จากอุณหภูมิ
def nh3_temp_to_sg(t_c):
    # สมการพหุนามประเมินความหนาแน่นสัมพัทธ์ของแอมโมเนียเหลวอิ่มตัว
    return (-4.02651515e-06 * t_c**2 - 1.42173485e-03 * t_c + 0.639121212)

# ========================================================
# ส่วนหัวของโปรแกรม (Header)
# ========================================================
if os.path.exists("logo.png"):
    st.image("logo.png", width=150)
else:
    st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")

st.title("💻⚙️ Yosaku Selection")
st.caption("พัฒนาโดย Chattrawat Khamsee | เวอร์ชัน Web App สำหรับมือถือ")

# 📖 ส่วนแสดงสมการและที่มา (พับเก็บได้)
with st.expander("📖 ดูสมการและทฤษฎีที่ใช้คำนวณ (Formula & Derivation)"):
    st.markdown("โปรแกรมนี้คำนวณหาค่าสัมประสิทธิ์การไหล ($C_v$) ของ Orifice ตามสูตรมาตรฐานวิศวกรรม:")
    st.latex(r"C_v = 1.17 \times \left( \frac{G}{1000 \times Y} \right) \times \sqrt{\frac{S}{\Delta P}} \times K")
    st.markdown("""
    **คำอธิบายตัวแปรตำแหน่งต่าง ๆ:**
    * $\Delta P = HP - LP$ : ความดันตกคร่อมวาล์ว (Pressure Drop) ในหน่วย ${Bar}$
    * $G$ : อัตราการไหลมวล (Mass Flow Rate) $[{kg/h}]$
    * $Y$ : Specific weight ของน้ำยาก่อนเข้าวาล์ว (อ้างอิงฝั่ง Condensing / High Pressure)
    * $S$ : Specific weight ของน้ำยาหลังออกจากวาล์ว (อ้างอิงฝั่ง Evaporating / Low Pressure)
    * $K$ : ค่าปรับแก้ (K Factor) จากผู้ใช้งาน
    """)

# 🔘 ส่วนเลือกวิธีการป้อนสภาวะทางกายภาพ
input_mode = st.radio(
    "เลือกวิธีระบุสภาวะความดันและคุณสมบัติน้ำยา:",
    ["ป้อนด้วยความดันโดยตรง (Manual Pressure & Y, S)", "ป้อนด้วยอุณหภูมิแอมโมเนีย (Auto R717 Temp)"],
    horizontal=False
)

unit = st.radio("เลือกหน่วยความดันแสดงผล:", ["Bar", "PSI"], horizontal=True)

# กำหนดขอบเขตกรอกข้อมูลแยกตามโหมด
if input_mode == "ป้อนด้วยความดันโดยตรง (Manual Pressure & Y, S)":
    col1, col2 = st.columns(2)
    with col1:
        G = st.number_input("อัตราไหลมวล G (kg/h):", min_value=0.0, value=0.0, step=10.0)
        LP_input = st.number_input("ความดันขาออก LP:", min_value=0.0, value=0.0, step=0.1)
        Y_input = st.number_input("Specific weight ก่อนวาล์ว (Y):", min_value=0.01, value=0.583, step=0.01, format="%.3f")
    with col2:
        HP_input = st.number_input("ความดันขาเข้า HP:", min_value=0.0, value=0.0, step=0.1)
        K = st.number_input("ค่าปรับแก้ K Factor:", min_value=0.0, value=1.0, step=0.1)
        S_input = st.number_input("Specific weight หลังวาล์ว (S):", min_value=0.01, value=0.583, step=0.01, format="%.3f")
else:
    col1, col2 = st.columns(2)
    with col1:
        G = st.number_input("อัตราไหลมวล G (kg/h):", min_value=0.0, value=0.0, step=10.0)
        Evap_temp = st.number_input("อุณหภูมิระเหย Evaporating Temp (°C):", min_value=-50.0, max_value=60.0, value=-10.0, step=1.0)
    with col2:
        Cond_temp = st.number_input("อุณหภูมิควบแน่น Condensing Temp (°C):", min_value=-50.0, max_value=60.0, value=40.0, step=1.0)
        K = st.number_input("ค่าปรับแก้ K Factor:", min_value=0.0, value=1.0, step=0.1)

# ปุ่มคำนวณ
if st.button("🚀 CALCULATE", type="primary", use_container_width=True):
    if G <= 0:
        st.warning("⚠️ กรุณากรอกอัตราไหลมวล G ให้มากกว่า 0")
    elif input_mode == "ป้อนด้วยความดันโดยตรง (Manual Pressure & Y, S)" and HP_input <= LP_input:
        st.error("❌ ข้อผิดพลาด: ความดันขาเข้า (HP) ต้องมากกว่าความดันขาออก (LP)")
    elif input_mode == "ป้อนด้วยอุณหภูมิแอมโมเนีย (Auto R717 Temp)" and Cond_temp <= Evap_temp:
        st.error("❌ ข้อผิดพลาด: อุณหภูมิควบแน่นต้องมากกว่าอุณหภูมิระเหย")
    else:
        # ประมวลผลตัวแปรตามโหมดที่เลือก
        if input_mode == "ป้อนด้วยความดันโดยตรง (Manual Pressure & Y, S)":
            HP = HP_input / 14.5038 if unit == "PSI" else HP_input
            LP = LP_input / 14.5038 if unit == "PSI" else LP_input
            Y = Y_input
            S = S_input
            display_dp = HP_input - LP_input
        else:
            HP = nh3_temp_to_bar_abs(Cond_temp)
            LP = nh3_temp_to_bar_abs(Evap_temp)
            Y = nh3_temp_to_sg(Cond_temp)
            S = nh3_temp_to_sg(Evap_temp)
            display_dp = (HP - LP) * 14.5038 if unit == "PSI" else (HP - LP)
            
        # สูตรหลักคำนวณ Cv 
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / (HP - LP))
        cv_result = part_1 * part_2 * K

        # แสดงผลลัพธ์หลักและสภาวะน้ำยาที่ใช้จริง
        st.subheader("📊 ผลการคำนวณ")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Pressure Drop", f"{display_dp:.3f} {unit}")
        res_col2.metric("ผลรวมค่า CV ที่คำนวณได้", f"{cv_result:.4f}")
        
        # เพิ่มกล่องแสดงผลคุณสมบัติทางกายภาพขนาดย่อมสำหรับสแกนดูบนมือถือ
        st.info(f"💡 **สภาวะแวดล้อมทางวิศวกรรมที่ใช้คำนวณ:**\n"
                f"* ความดันเทียบเท่า: HP = {HP * 14.5038 if unit == 'PSI' else HP:.2f} {unit} | "
                f"LP = {LP * 14.5038 if unit == 'PSI' else LP:.2f} {unit}\n"
                f"* Specific Weight จริง: ก่อนวาล์ว (Y) = **{Y:.4f}** | หลังวาล์ว (S) = **{S:.4f}**")

        # --- 1. คำนวณหา Top 5 ทางเลือกที่ดีที่สุด ---
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

        # ฟังก์ชันแปลงเปอร์เซ็นต์เป็นข้อความสถานะ
        def get_status_text(pct):
            if pct > 100: return "เล็กเกินไป"
            elif 75 <= pct <= 85: return "เหมาะสม"
            elif 85 < pct <= 100: return "ใกล้เต็ม"
            else: return "ใหญ่เกินไป"

        # --- 2. สร้างตารางที่ 1 & 2 พร้อมใส่สีไฮไลต์ ---
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
        matrix_dict = {}
        for name1, cv1 in ORIFICE_DATA:
            matrix_dict[name1] = {}
            for name2, cv2 in ORIFICE_DATA:
                pct = (cv_result / (cv1 + cv2)) * 100
                matrix_dict[name1][name2] = pct
                
        df_matrix = pd.DataFrame(matrix_dict).T
        styled_matrix = df_matrix.style.map(color_matrix_cells).format("{:.1f}%")
        st.dataframe(styled_matrix, use_container_width=True)

        # --- 4. ระบบดาวน์โหลด Log สำหรับมือถือ ---
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if input_mode == "ป้อนด้วยความดันโดยตรง (Manual Pressure & Y, S)":
            input_details = (
                f"ความดันขาเข้า HP: {HP_input} {unit}\n"
                f"ความดันขาออก LP: {LP_input} {unit}\n"
                f"Specific Weight - Y: {Y}, S: {S}\n"
            )
        else:
            input_details = (
                f"อุณหภูมิควบแน่น Condensing Temp: {Cond_temp} °C (เทียบเท่า {HP:.3f} Bar abs)\n"
                f"อุณหภูมิระเหย Evaporating Temp: {Evap_temp} °C (เทียบเท่า {LP:.3f} Bar abs)\n"
                f"Auto calculated - Y: {Y:.4f}, S: {S:.4f}\n"
            )

        log_content = (
            f"=== บันทึกเมื่อ {current_time} ===\n"
            f"ชื่อโปรแกรม: Yosaku Selection (Web App)\n"
            f"วิธีป้อนข้อมูล: {input_mode}\n"
            f"อัตราไหลมวล G: {G} kg/h\n"
            f"{input_details}"
            f"Pressure Drop: {display_dp:.3f} {unit}\n"
            f"ค่าปรับแก้ K Factor: {K}\n"
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
