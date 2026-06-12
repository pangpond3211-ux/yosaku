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
    page_title="Yosaku Selection Pro (Advanced LI Mode)",
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

# 📊 [DYNAMIC ESTIMATOR] ระบบจำลองโหลดความร้อนน้ำมันตามสภาวะจริงของ MYCOMW
def estimate_oil_heat(model, te, tc, has_eco):
    """คำนวณแนวโน้มค่า Oil Heat Rejection (kW) ให้สอดคล้องตามสภาวะ Te, Tc และ Economizer"""
    base_kw = MYCOM_BASE_OIL_REJECTION.get(model, 100.0)
    pe = nh3_temp_to_bar_abs(te)
    pc = nh3_temp_to_bar_abs(tc)
    
    pe_ref = nh3_temp_to_bar_abs(-10.0)
    pc_ref = nh3_temp_to_bar_abs(35.0)
    
    p_diff_ratio = (pc - pe) / (pc_ref - pe_ref) if (pc_ref - pe_ref) > 0 else 1.0
    cr_ratio = (pc / pe) / (pc_ref / pe_ref) if pe > 0 else 1.0
    
    estimated_kw = base_kw * (p_diff_ratio ** 0.75) * (cr_ratio ** 0.35)
    
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
st.subheader("ระบบคำนวณวาล์วสำหรับ LIQUID INJECTION OIL COOLING (Advanced)")
st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")
st.markdown("---")

# 🔘 ส่วนที่ 1: ป้อนสภาวะหน้างานอ้างอิงจากโปรแกรม MYCOMW
st.subheader("🌡️ 1. ป้อนสภาวะการทำงานจริง (MYCOMW Conditions)")

col_input1, col_input2 = st.columns(2)
with col_input1:
    selected_model = st.selectbox("เลือกรุ่นคอมเพรสเซอร์ MYCOM:", list(MYCOM_BASE_OIL_REJECTION.keys()), on_change=reset_calculation)
    Evap_temp = st.number_input("อุณหภูมิระเหย Te (°C):", min_value=-50.0, max_value=20.0, value=-10.0, step=0.5, on_change=reset_calculation)
    discharge_sh = st.number_input("Discharge Superheat (K):", min_value=0.0, max_value=50.0, value=20.0, step=1.0, help="ระบุค่าความร้อนซูเปอร์ฮีตด้านส่ง โดยปกติมาตรฐาน MYCOMW จะอยู่ที่ 20 K", on_change=reset_calculation)

with col_input2:
    has_eco = st.checkbox("⚡ เปิดใช้งานระบบ Economizer (ECO Port)", value=False, on_change=reset_calculation)
    Cond_temp = st.number_input("อุณหภูมิควบแน่น Tc (°C):", min_value=10.0, max_value=60.0, value=35.0, step=0.5, on_change=reset_calculation)
    # 🆕 เพิ่มช่องป้อนค่า Liquid Subcooling (K)
    liquid_subcooling = st.number_input("Liquid Subcooling (K):", min_value=0.0, max_value=30.0, value=5.0, step=0.5, help="ระบุค่าความเย็นยวดยิ่งของน้ำยาเหลว (มักเกิดจากคอยล์คอนเดนเซอร์หรือชุด Subcooler) หากไม่มีให้ใส่ 0", on_change=reset_calculation)

st.markdown("---")

# 🔘 ส่วนที่ 2: ค่า Oil Heat Rejection
st.subheader("🔥 2. ภาระความร้อนน้ำมัน (Oil Heat Rejection)")

auto_computed_kw = estimate_oil_heat(selected_model, Evap_temp, Cond_temp, has_eco)

q_oil_kw = st.number_input(
    "Detail Oil Heat Rejection (kW):",
    min_value=5.0,
    max_value=1500.0,
    value=float(auto_computed_kw),
    step=0.1,
    format="%.2f",
    help="ระบบใส่ค่าแนะนำเบื้องต้นให้แล้ว หากมีค่าจริงจากใบสเปกสามารถพิมพ์ทับได้เลยครับ",
    on_change=reset_calculation
)

if abs(q_oil_kw - auto_computed_kw) < 0.01:
    st.caption("ℹ️ *ระบบกำลังใช้ค่าภาระความร้อนน้ำมันที่ได้จากการคำนวณจำลองสภาวะโดยอัตโนมัติ*")
else:
    st.caption("⚠️ *ระบบกำลังใช้ค่าโหลดที่คุณป้อนปรับแต่งเองหน้างาน (Manual Override)*")

st.markdown("---")

# 🔘 ส่วนที่ 3: ตั้งค่าหน่วยและปัจจัยความปลอดภัย
st.subheader("🧪 3. สัมประสิทธิ์และหน่วยประมวลผล")
unit = st.radio("เลือกหน่วยความดันแสดงผลบนหน้ารายงาน:", ["Bar", "PSI"], horizontal=True, on_change=reset_calculation)
K = st.number_input("ค่าปรับแก้เพื่อความปลอดภัย (K Factor):", min_value=0.1, value=1.0, step=0.05, on_change=reset_calculation)

st.markdown("---")

# ปุ่มประมวลผลหลัก
if st.button("🚀 CALCULATE VALVE SIZING", type="primary", use_container_width=True):
    st.session_state.calculated = True

# --- กระบวนการคำนวณทางวิศวกรรม ---
if st.session_state.calculated:
    
    # 1. คำนวณแรงดันสัมบูรณ์ของระบบสารทำความเย็น
    HP_abs = nh3_temp_to_bar_abs(Cond_temp)
    LP_abs = nh3_temp_to_bar_abs(Evap_temp)
    
    # คำนวณแรงดันจุดกลางหน้าพอร์ตฉีดหล่อเย็นในห้องอัด
    PM_abs = math.sqrt(HP_abs * LP_abs) if LP_abs > 0 else LP_abs
    dp_bar = HP_abs - PM_abs  
    
    # 2. 🆕 คำนวณอุณหภูมิน้ำยาเหลวจริงหลังจากหักค่า Subcooling
    t_liquid = Cond_temp - liquid_subcooling
    
    # Y: ความหนาแน่นของน้ำยาเหลวก่อนเข้าวาล์วที่อุณหภูมิซับคูลจริง (t_liquid)
    Y = nh3_liquid_density(t_liquid)
    
    t_intermediate = (Cond_temp + Evap_temp) / 2.0
    S = nh3_liquid_density(t_intermediate)

    # 3. [SUBCOOLED ENTHALPY] คำนวณเอนทัลปีอ้างอิงค่า Liquid Subcooling
    # h_f_in: เอนทัลปีของน้ำยาเหลวที่อุณหภูมิ subcooled จริง ยิ่ง subcool มาก ค่านี้ยิ่งต่ำลง
    h_f_in = 200.0 + 4.63 * t_liquid + 0.0025 * (t_liquid ** 2)
    
    # h_g_out: เอนทัลปีของไอแอมโมเนียซูเปอร์ฮีตด้านส่งตามสเปก Discharge Superheat
    h_g_sat = 1444.0 + 0.92 * Cond_temp - 0.004 * (Cond_temp ** 2) 
    cp_ammonia_gas = 2.9  
    h_g_out = h_g_sat + (cp_ammonia_gas * discharge_sh) 
    
    dh_loc = h_g_out - h_f_in
    G = (q_oil_kw / dh_loc) * 3600 if dh_loc > 0 else 0.0

    # ตั้งค่าหน่วยแสดงผลทางวิศวกรรม
    display_dp = dp_bar * 14.5038 if unit == "PSI" else dp_bar
    p_label = "PSI" if unit == "PSI" else "Bar"

    if G <= 0 or HP_abs <= LP_abs:
        st.error("❌ ข้อผิดพลาด: ตรวจสอบระดับอุณหภูมิระบบ (อุณหภูมิควบแน่น Tc ต้องมีค่าสูงกว่าอุณหภูมิระเหย Te)")
        st.session_state.calculated = False
    else:
        # คำนวณค่า Valve Cv
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / dp_bar)
        cv_result = part_1 * part_2 * K

        # แสดงผลลัพธ์การคํานวณหลัก
        st.subheader("📊 สรุปผลการคำนวณขนาดพอร์ตวาล์ว Yosaku")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric(f"Pressure Drop ตกคร่อมวาล์ว (ΔP)", f"{display_dp:.3f} {p_label}")
        res_col2.metric("ค่า CV รวมที่ต้องการจริง", f"{cv_result:.4f}")
        
        st.success(f"📈 **วิเคราะห์เทคนิคจำลอง:** โหลดน้ำมัน **{q_oil_kw:.2f} kW** | คุม Subcooling **{liquid_subcooling:.1f} K** ($T_{{liquid}} = {t_liquid:.1f}^\\circ C$) | คุม Discharge SH **{discharge_sh:.1f} K** -> อัตราไหลน้ำยาที่ต้องใช้จริง G = **{G:.2f} kg/hr**")

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
        
        st.info("🏆 **รูปแบบขนาด Orifice แนะนำที่ดีที่สุด 5 อันดับแรก (ช่วงปลอดภัยสูงสุดคือเปิดประมาณ 80% - 85%)**")
        if all_options:
            recommendation_text = ""
            rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for i, (score, label) in enumerate(all_options[:5]):
                emoji = rank_emojis[i] if i < len(rank_emojis) else f"[{i+1}]"
                st.markdown(f"**{emoji}** {label}")
                recommendation_text += f"อันดับ {i+1}: {label}\n"
        else:
            qty_needed = math.ceil(cv_result / 0.48)
            recommendation_text = f"พอร์ตมาตรฐานขนาดคู่รองรับไม่เพียงพอ -> แนะนำเพิ่มพอร์ตขนานขนาดใหญ่เป็น {qty_needed} x JH"
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

        # --- ระบบจัดทำไฟล์ส่งออกรายงานเทคนิค ---
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_content = (
            f"=== รายงานบันทึกการคำนวณและเลือกขนาดวาล์ว Yosaku ({current_time}) ===\n"
            f"รุ่นคอมเพรสเซอร์ MYCOM: {selected_model}\n"
            f"ระบบหล่อเย็นคอมเพรสเซอร์: WITH LIQUID INJECTION OIL COOLING\n"
            f"สภาวะทำงานที่ระบุ: Te = {Evap_temp:.1f} °C, Tc = {Cond_temp:.1f} °C\n"
            f"ค่าควบคุมฝั่งน้ำยาเหลว: LIQUID SUBCOOLING = {liquid_subcooling:.1f} K (T_liquid = {t_liquid:.1f} °C)\n"
            f"ค่าควบคุมความร้อนระบบ: DISCHARGE SUPERHEAT = {discharge_sh:.1f} K\n"
            f"ค่าภาระความร้อนน้ำมันใช้งานจริง: {q_oil_kw:.2f} kW\n"
            f"คำนวณอัตราการไหลแอมโมเนียเหลว (G): {G:.2f} kg/h\n"
            f"แรงดันตกคร่อมวาล์วขณะเปิดทำงาน: {display_dp:.3f} {p_label}\n"
            f"ค่าความต้องการประมวลผลวาล์วรวม (Cv): {cv_result:.4f}\n"
            f"--------------------------------------------------\n"
            f"ผลลัพธ์การจัดสรรและคัดเลือก Orifice แนะนำ:\n{recommendation_text}"
            f"--------------------------------------------------\n"
        )
        st.download_button(
            label="📥 ดาวน์โหลดรายงานเทคนิค (Technical Spec Log)",
            data=log_content,
            file_name=f"Yosaku_Advanced_LI_Report_{selected_model.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
