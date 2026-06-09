import streamlit as st
import pandas as pd
import math
import itertools
from datetime import datetime
import os

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

# ล็อกค่าคงที่ (Fixed Constants) ตามมาตรฐานของระบบ
Y_CONSTANT = 0.583
S_CONSTANT = 0.583
P_ATM = 1.013  # ค่าความดันบรรยากาศมาตรฐาน (Bar) สำหรับแปลง Gauge เป็น Absolute

# สไตล์สีสำหรับตารางสถานะ
COLOR_MAP = {
    "เล็กเกินไป": "background-color: #ffcccc; color: #cc0000;",
    "เหมาะสม": "background-color: #d4edda; color: #155724; font-weight: bold;",
    "ใกล้เต็ม": "background-color: #fff3cd; color: #856404;",
    "ใหญ่เกินไป": "background-color: #ffffff; color: #6c757d;"
}

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

# 🧪 ฟังก์ชันแปลงอุณหภูมิอิ่มตัว R717 (°C) -> ความดันสัมบูรณ์ (Bar Absolute)
def nh3_temp_to_bar_abs(t_c):
    return (3.26631702e-08 * t_c**4 + 
            1.54531857e-05 * t_c**3 + 
            2.34641900e-03 * t_c**2 + 
            1.60674845e-01 * t_c + 
            4.29486480e+00)

# ========================================================
# ส่วนหัวของโปรแกรม (Header)
# ========================================================
if os.path.exists("logo.png"):
    st.image("logo.png", width=150)
else:
    st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")

st.title("💻⚙️ Yosaku Selection")
st.caption("พัฒนาโดย Chattrawat Khamsee | เวอร์ชันความดันเกจ (Bar gauge)")

# 📖 ส่วนแสดงสมการหลักและคำอธิบายตัวแปรแบบเกจ
st.markdown("### 📊 สมการและตัวแปรอ้างอิงการคำนวณทั้งหมด (Reference Formulas)")

st.markdown("**1. สมการหลักในการหาค่า Cv ของวาล์ว:**")
st.latex(r"C_v = 1.17 \times \left( \frac{G}{1000 \times Y} \right) \times \sqrt{\frac{S}{HP - LP}} \times K")

st.markdown("**2. สมการคำนวณอัตราไหลมวล G จากสเปกคอมเพรสเซอร์ (R717):**")
st.latex(r"G = \frac{SV \times \eta_v \times P_s}{0.4882 \times T_s}")

st.markdown("""
**📝 ดัชนีอธิบายตัวแปรทั้งหมดในระบบ:**
* **$C_v$** : Valve Flow Coefficient (ค่าสัมประสิทธิ์การไหลของวาล์วที่ต้องการ)
* **$G$** : Refrigerant Flow Rate (อัตราการไหลเชิงมวลของสารทำความเย็น มีหน่วยเป็น **kg/hr**)
* **$Y$** : Specific weight before valve (น้ำหนักจำเพาะก่อนเข้าวาล์ว -> 🔒 *ล็อกค่าคงที่ที่ 0.583*)
* **$S$** : Specific weight after valve (น้ำหนักจำเพาะหลังออกจากวาล์ว -> 🔒 *ล็อกค่าคงที่ที่ 0.583*)
* **$HP$** : High Pressure / Inlet Pressure (ความดันขาเข้าวาล์ว มีหน่วยเป็น **Bar gauge** หรือ **psig**)
* **$LP$** : Low Pressure / Outlet Pressure (ความดันขาออกวาล์ว มีหน่วยเป็น **Bar gauge** หรือ **psig**)
* **$HP - LP$** : Pressure Drop (ผลต่างความดันตกคร่อมตัววาล์ว)
* **$K$** : Correction Factor (ค่าปรับแก้สภาวะการทำงานของวาล์ว หรือ K Factor)
* **$SV$** : Swept Volume (ปริมาตรกวาดตามทฤษฎีของคอมเพรสเซอร์ มีหน่วยเป็น **m³/hr**)
* **$\eta_v$** : Volumetric Efficiency (ประสิทธิภาพเชิงปริมาตรของคอมเพรสเซอร์ มีหน่วยเป็น **%**)
* **$P_s$** : Suction Absolute Pressure (ความดันสัมบูรณ์ทางดูด มีหน่วยเป็น **kPa A** โดยระบบจะนำค่าจากช่องป้อนความดันเกด $P_s$ บวกด้วย $1.013$ แล้วคูณ $100$ เพื่อแปลงหน่วยเข้าสูตรให้โดยอัตโนมัติ)
* **$T_s$** : Suction Temperature (อุณหภูมิแก๊สทางดูดสัมบูรณ์ มีหน่วยเป็นเคลวิน **K** คำนวณมาจาก $\text{°C} + 273.15$)
""")

st.markdown("---")

# ========================================================
# 📋 ส่วนกรอกข้อมูลคุณสมบัติระบบ
# ========================================================
st.subheader("📋 กรอกข้อมูลคุณสมบัติระบบ")

g_mode = st.radio(
    "เลือกวิธีระบุอัตราการไหลมวล (G):",
    ["ป้อนค่า G โดยตรง (kg/hr)", "คำนวณจากสเปกคอมเพรสเซอร์ (Swept Volume)"],
    horizontal=True
)

col_g1, col_g2 = st.columns(2)

if g_mode == "ป้อนค่า G โดยตรง (kg/hr)":
    with col_g1:
        G_input = st.number_input("G: Ref. flow rate [Suction] (kg/hr):", min_value=0.0, value=1000.0, step=10.0)
    with col_g2:
        K = st.number_input("ค่าปรับแก้ K Factor:", min_value=0.0, value=1.0, step=0.1)
else:
    with col_g1:
        SV = st.number_input("SV: Swept Volume (m³/hr):", min_value=0.0, value=435.0, step=5.0)
        eta_v = st.number_input("ηv: Volumetric Efficiency (%):", min_value=0.0, max_value=100.0, value=93.0, step=1.0)
        # เพิ่มช่องกรอกสเปกความดัน Ps แยกอิสระตามคำขอ
        Ps_gauge_input = st.number_input("Ps: Suction Pressure (Bar gauge):", min_value=-1.013, value=1.2, step=0.1, help="ความดันเกจฝั่งทางดูดของคอมเพรสเซอร์")
    with col_g2:
        T_s_c = st.number_input("Ts: Suction Temp (°C):", min_value=-50.0, max_value=100.0, value=-5.0, step=1.0, help="อุณหภูมิแก๊สจริงทางดูดรวม Superheat")
        K = st.number_input("ค่าปรับแก้ K Factor:", min_value=0.0, value=1.0, step=0.1)

st.markdown("---")

# 🔘 ส่วนเลือกวิธีการป้อนสภาวะความดัน
input_mode = st.radio(
    "เลือกวิธีระบุสภาวะความดัน:",
    ["วิธีที่ 1: ป้อนด้วยความดันโดยตรง (HP / LP)", "วิธีที่ 2: ป้อนด้วยอุณหภูมิแอมโมเนีย (Tc / Te)"],
    horizontal=False
)

unit = st.radio("เลือกหน่วยความดันแสดงผลบนหน้าจอ:", ["Bar", "PSI"], horizontal=True)

# กำหนดตัวแปรสำหรับรับค่าตามโหมด (ปรับเป็น Gauge ทั้งหมด)
col1, col2 = st.columns(2)
label_suffix = "(psig)" if unit == "PSI" else "(gauge)"

if input_mode == "วิธีที่ 1: ป้อนด้วยความดันโดยตรง (HP / LP)":
    with col1:
        HP_input = st.number_input(f"ความดันขาเข้า HP {label_suffix}:", min_value=-1.013, value=13.7 if unit == "Bar" else 198.7, step=0.1)
    with col2:
        LP_input = st.number_input(f"ความดันขาออก LP {label_suffix}:", min_value=-1.013, value=1.9 if unit == "Bar" else 27.5, step=0.1)
else:
    with col1:
        Cond_temp = st.number_input("อุณหภูมิควบแน่น Condensing Temp Tc (°C):", min_value=-50.0, max_value=60.0, value=38.0, step=1.0)
    with col2:
        Evap_temp = st.number_input("อุณหภูมิระเหย Evaporating Temp Te (°C):", min_value=-50.0, max_value=60.0, value=-10.0, step=1.0)

# ========================================================
# ปุ่มคำนวณและประมวลผลลัพธ์
# ========================================================
if st.button("🚀 CALCULATE", type="primary", use_container_width=True):
    # 1. แปลงความดันฝั่งใช้งานให้กลายเป็นหน่วย Bar Absolute (เพื่อใช้ในสูตรคณิตศาสตร์หลัก)
    if input_mode == "วิธีที่ 1: ป้อนด้วยความดันโดยตรง (HP / LP)":
        if unit == "PSI":
            HP_gauge = HP_input / 14.5038
            LP_gauge = LP_input / 14.5038
        else:
            HP_gauge = HP_input
            LP_gauge = LP_input
        HP_abs = HP_gauge + P_ATM
        LP_abs = LP_gauge + P_ATM
    else:
        # ฟังก์ชันคำนวณอุณหภูมิคืนค่ามาเป็นความดันสัมบูรณ์ (Bar A)
        HP_abs = nh3_temp_to_bar_abs(Cond_temp)
        LP_abs = nh3_temp_to_bar_abs(Evap_temp)
        HP_gauge = HP_abs - P_ATM
        LP_gauge = LP_abs - P_ATM

    # 2. คำนวณหาค่า G ตามโหมดที่เลือก
    if g_mode == "ป้อนค่า G โดยตรง (kg/hr)":
        G = G_input
    else:
        # แปลงค่า Ps จากช่องกรอก Bar gauge -> kPa Absolute เพื่อเข้าสูตรคอมเพรสเซอร์
        Ps_abs_bar = Ps_gauge_input + P_ATM
        Ps_kpa = Ps_abs_bar * 100.0
        Ts_k = T_s_c + 273.15
        G = (SV * (eta_v / 100.0) * Ps_kpa) / (0.4882 * Ts_k)

    # ตรวจสอบความถูกต้องทางวิศวกรรมขั้นต้น
    if G <= 0:
        st.warning("⚠️ อัตราไหลสารทำความเย็น G มีค่าน้อยกว่าหรือเท่ากับ 0 (กรุณาตรวจสอบข้อมูลสเปก)")
    elif HP_abs <= LP_abs:
        st.error("❌ ข้อผิดพลาด: ความดันขาเข้า (HP) ต้องมากกว่าความดันขาออก (LP)")
    else:
        # คำนวณผลต่างความดันตกคร่อม (Pressure Drop ตัวแปรเกจหรือสัมบูรณ์ลบกันได้ค่าเท่ากัน)
        display_dp = (HP_abs - LP_abs) * 14.5038 if unit == "PSI" else (HP_abs - LP_abs)
        display_hp = HP_gauge * 14.5038 if unit == "PSI" else HP_gauge
        display_lp = LP_gauge * 14.5038 if unit == "PSI" else LP_gauge
        
        # สูตรหลักคำนวณ Cv
        part_1 = 1.17 * (G / (1000 * Y_CONSTANT))
        part_2 = math.sqrt(S_CONSTANT / (HP_abs - LP_abs))
        cv_result = part_1 * part_2 * K

        # แสดงผลลัพธ์หลักบนหน้าจอ
        st.subheader("📊 ผลการคำนวณ")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Pressure Drop (ΔP)", f"{display_dp:.3f} {unit}")
        res_col2.metric("ผลรวมค่า CV ที่คำนวณได้", f"{cv_result:.4f}")
        
        if g_mode != "ป้อนค่า G โดยตรง (kg/hr)":
            st.metric("💡 อัตราไหลมวล G จากสเปกคอมเพรสเซอร์", f"{G:.2f} kg/hr")
        
        st.info(f"💡 **สภาวะระบบเกจ:** G = {G:.2f} kg/hr | HP = {display_hp:.2f} {unit} gauge | LP = {display_lp:.2f} {unit} gauge")

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
        matrix_dict = {}
        for name1, cv1 in ORIFICE_DATA:
            matrix_dict[name1] = {}
            for name2, cv2 in ORIFICE_DATA:
                pct = (cv_result / (cv1 + cv2)) * 100
                matrix_dict[name1][name2] = pct
                
        df_matrix = pd.DataFrame(matrix_dict).T
        styled_matrix = df_matrix.style.map(color_matrix_cells).format("{:.1f}%")
        st.dataframe(styled_matrix, use_container_width=True)

        # --- 4. ระบบดาวน์โหลด Log สำหรับจัดเก็บข้อมูล ---
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_content = (
            f"=== บันทึกเมื่อ {current_time} ===\n"
            f"วิธีระบุค่า G: {g_mode}\n"
        )
        if g_mode != "ป้อนค่า G โดยตรง (kg/hr)":
            log_content += f"ข้อมูลคอมเพรสเซอร์: SV={SV} m3/hr, nv={eta_v}%, Ps={Ps_gauge_input} Bar gauge, Ts={T_s_c} °C\n"
            
        log_content += (
            f"วิธีป้อนข้อมูลความดัน: {input_mode}\n"
            f"Ref. flow rate G: {G:.2f} kg/h\n"
            f"สภาวะการทำงานเกจ: HP={display_hp:.3f} {unit} G, LP={display_lp:.3f} {unit} G\n"
            f"ค่าสัมประสิทธิ์ล็อกคงที่: Y={Y_CONSTANT}, S={S_CONSTANT}, K={K}\n"
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
