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
    page_title="Yosaku Selection Pro (MYCOMW Engine)",
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

# 💾 ฐานข้อมูลภาระความร้อนน้ำมันมาตรฐานที่สภาวะอ้างอิง (Rating Condition: Te -10°C / Tc 35°C)
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

# 🧪 [MYCOM CORE] ฟังก์ชันแปลงคุณสมบัติทางเทอร์โมไดนามิกส์ R717 (Ammonia)
def nh3_temp_to_bar_abs(t_c):
    """แปลงอุณหภูมิอิ่มตัว (°C) -> ความดันสัมบูรณ์ (Bar Absolute) อิงตามตารางคุณสมบัติน้ำยา"""
    return (3.26631702e-08 * t_c**4 + 
            1.54531857e-05 * t_c**3 + 
            2.34641900e-03 * t_c**2 + 
            1.60674845e-01 * t_c + 
            4.29486480e+00)

def nh3_liquid_density(t_c):
    """คำนวณความหนาแน่นสารทำความเย็น R717 Liquid (kg/L)"""
    return 0.6386 - 0.00138 * t_c - 0.0000025 * (t_c ** 2)

# 📊 [MYCOMW EMULATOR] ฟังก์ชันคำนวณโหลดความร้อนน้ำมันแบบแปรผันตามสภาวะหน้างานจริง
def simulate_mycomw_oil_heat(model, te, tc, has_eco):
    """คำนวณค่า Detail Oil Heat Rejection (kW) ล้อตามพฤติกรรมโปรแกรม MYCOMW"""
    base_kw = MYCOM_BASE_OIL_REJECTION.get(model, 100.0)
    
    pe = nh3_temp_to_bar_abs(te)
    pc = nh3_temp_to_bar_abs(tc)
    compression_ratio = pc / pe if pe > 0 else 1.0
    
    # สภาวะอ้างอิงเทียบมาตรฐานฐานข้อมูล (-10 °C / 35 °C)
    pe_ref = nh3_temp_to_bar_abs(-10.0)
    pc_ref = nh3_temp_to_bar_abs(35.0)
    cr_ref = pc_ref / pe_ref
    
    p_diff_ratio = (pc - pe) / (pc_ref - pe_ref) if (pc_ref - pe_ref) > 0 else 1.0
    cr_ratio = compression_ratio / cr_ref
    
    # ภาระความร้อนของน้ำมันจะแปรผันตรงตาม Pressure Differential และ Compression Work
    simulated_kw = base_kw * (p_diff_ratio ** 0.75) * (cr_ratio ** 0.35)
    
    # หากระบบเปิดใช้ Economizer แก๊สบางส่วนจะเข้ามาช่วยลดอุณหภูมิหน้าพอร์ตด้านส่ง ทำให้ Oil Load ลดลงเล็กน้อย
    if has_eco:
        simulated_kw *= 0.86  
        
    return max(5.0, simulated_kw)

# --- ฟังก์ชันช่วยแสดงผลตารางวาล์ว ---
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
st.caption("🚀 เวอร์ชันอัจฉริยะ: จำลองสมการคำนวณ Oil Heat Rejection (kW) อัตโนมัติจากโปรแกรม MYCOMW.exe")
st.caption("⚙️ Mayekawa (Thailand) Co., Ltd.")

st.markdown("---")

# 🔘 ส่วนที่ 1: การเลือกรุ่นคอมเพรสเซอร์
st.subheader("📊 1. เลือกรุ่นคอมเพรสเซอร์หน้างาน")
selected_model = st.selectbox(
    "กรุณาเลือกรุ่นคอมเพรสเซอร์ MYCOM:",
    list(MYCOM_BASE_OIL_REJECTION.keys()),
    on_change=reset_calculation
)

st.markdown("---")

# 🔘 ส่วนที่ 2: ป้อนข้อมูลอุณหภูมิระบบตามที่ผู้ใช้งานระบุ (Te, Tc, Eco)
st.subheader("🌡️ 2. สภาวะทำงานเพื่อคำนวณโหลดความร้อนน้ำมัน (MYCOMW Parameters)")
col_t1, col_t2 = st.columns(2)
with col_t1:
    Evap_temp = st.number_input("อุณหภูมิระเหย Evaporating Temp Te (°C):", min_value=-50.0, max_value=20.0, value=-10.0, step=0.5, on_change=reset_calculation)
with col_t2:
    Cond_temp = st.number_input("อุณหภูมิควบแน่น Condensing Temp Tc (°C):", min_value=10.0, max_value=60.0, value=35.0, step=0.5, on_change=reset_calculation)

# ตัวเลือก Economizer ตามความต้องการของพี่
has_eco = st.checkbox("⚙️ คอมเพรสเซอร์เครื่องนี้เปิดใช้งานชุด Economizer (ECO Port)", value=False, on_change=reset_calculation)

# จัดการพอร์ตส่งไอสารทำความเย็นกลับอิงตามปุ่ม Economizer ข้างต้น
loc_return_port = "ส่งกลับฝั่ง Economizer (ECO Port)" if has_eco else "ส่งกลับฝั่ง Suction (LP Port)"

st.markdown("---")

# 🔘 ส่วนที่ 3: ระบบคำนวณภาระความร้อนน้ำมันอัตโนมัติ (แปลงข้อมูลจาก MYCOMW เป็นค่าใช้งานจริง)
st.subheader("🔥 3. ผลลัพธ์ภาระความร้อนน้ำมัน (Oil Heat Rejection)")

# คำนวณค่าจากสมการจำลองโมเดลคอมเพรสเซอร์
computed_oil_kw = simulate_mycomw_oil_heat(selected_model, Evap_temp, Cond_temp, has_eco)

# ทำระบบตรวจสอบแบบเผื่อเลือก (Manual Override) เผื่อพี่ต้องการกรอกตัวเลขจริงเป๊ะๆ จากหน้าพิมพ์เอกสาร MYCOMW
manual_override = st.checkbox("✍️ ติ๊กที่นี่หากต้องการปรับแก้/กรอกค่าโหลด kW ด้วยตนเอง (Manual Override)", value=False)

if manual_override:
    q_oil_kw = st.number_input(
        "ระบุค่า Oil Heat Rejection ปรับแต่งเอง (kW):",
        min_value=5.0, max_value=1500.0, value=float(computed_oil_kw), step=1.0,
        on_change=reset_calculation
    )
else:
    q_oil_kw = computed_oil_kw
    st.info(f"💡 **ประมวลผลสำเร็จ:** อ้างอิงสภาวะ Te {Evap_temp}°C / Tc {Cond_temp}°C {'ร่วมกับระบบ ECO' if has_eco else ''} -> โหลดระบายความร้อนน้ำมันคำนวณได้เป็น **{q_oil_kw:.2f} kW**")

st.markdown("---")

# 🔘 ส่วนที่ 4: สัมประสิทธิ์และหน่วยความดันระบายน้ำยา
st.subheader("🧪 4. ข้อมูลและหน่วยสำหรับคำนวณขนาดพอร์ตวาล์ว")
unit = st.radio("เลือกหน่วยความดันแสดงผลบนหน้าจอรายงาน:", ["Bar", "PSI"], horizontal=True, on_change=reset_calculation)

# คำนวณสัมประสิทธิ์ความหนาแน่นน้ำยาแอมโมเนีย
Y = nh3_liquid_density(Cond_temp)
if has_eco:
    loc_evap_t = (Cond_temp + Evap_temp) / 2.0
    S = nh3_liquid_density(loc_evap_t)
else:
    S = nh3_liquid_density(Evap_temp)

col_prop1, col_prop2 = st.columns(2)
with col_prop1:
    st.number_input("Y: ความหนาแน่นสารขาก่อนเข้าวาล์ว (kg/L):", value=float(Y), format="%.3f", disabled=True)
    K = st.number_input("ค่าปรับแก้ความปลอดภัย K Factor:", min_value=0.1, value=1.0, step=0.05, on_change=reset_calculation)
with col_prop2:
    st.number_input("S: ความหนาแน่นสารขาออกจากวาล์ว (kg/L):", value=float(S), format="%.3f", disabled=True)

st.markdown("---")

# ปุ่มประมวลผลหลัก
if st.button("🚀 CALCULATE VALVE SIZING", type="primary", use_container_width=True):
    st.session_state.calculated = True

# --- กระบวนการประมวลผลหลังกดคำนวณ ---
if st.session_state.calculated:
    
    # 🧮 ส่วนที่ 4.1: คำนวณหาค่าอัตราไหลน้ำยา G (kg/hr) ตามเอนทัลปีสารที่เปลี่ยนไปจริง
    h_f_in = 200.0 + 4.63 * Cond_temp + 0.0025 * (Cond_temp ** 2)
    
    if has_eco:
        t_loc_evap = (Cond_temp + Evap_temp) / 2.0
        h_g_out = 1461.9 + 1.05 * t_loc_evap - 0.0085 * (t_loc_evap ** 2)
    else:
        h_g_out = 1461.9 + 1.05 * Evap_temp - 0.0085 * (Evap_temp ** 2)
        
    dh_loc = h_g_out - h_f_in
    if dh_loc > 0:
        G = (q_oil_kw / dh_loc) * 3600
    else:
        G = 0.0

    # แปลงแรงดันเกจสำหรับโชว์รายงานข้อมูลหน้างาน
    HP_abs = nh3_temp_to_bar_abs(Cond_temp)
    LP_abs = nh3_temp_to_bar_abs(Evap_temp)
    dp_bar = HP_abs - LP_abs
    
    display_dp = dp_bar * 14.5038 if unit == "PSI" else dp_bar
    p_label = "PSI" if unit == "PSI" else "Bar"

    if G <= 0 or HP_abs <= LP_abs:
        st.error("❌ ข้อผิดพลาด: ตรวจสอบอุณหภูมิหน้างานอีกครั้ง (อุณหภูมิควบแน่น Tc ต้องสูงกว่าอุณหภูมิระเหย Te)")
        st.session_state.calculated = False
    else:
        # สูตรหลักการคำนวณค่าสัมประสิทธิ์วาล์ว (Cv Sizing Formula)
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / dp_bar)
        cv_result = part_1 * part_2 * K

        # แสดงผลลัพธ์หลักบน UI
        st.subheader("📊 สรุปผลการคำนวณและเลือกขนาดพอร์ตวาล์ว")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric(f"Pressure Drop รวม (ΔP)", f"{display_dp:.3f} {p_label}")
        res_col2.metric("ค่า CV ที่ระบบต้องการรวม", f"{cv_result:.4f}")
        
        st.success(f"📈 **สรุปการวิเคราะห์เชิงเทคนิค:** โหลดน้ำมันจากสภาวะดีไซน์ **{q_oil_kw:.2f} kW** ส่งผลให้เกิดอัตราการไหลน้ำยาแอมโมเนียระบายความร้อน G = **{G:.2f} kg/hr**")

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
        
        st.info("🏆 **รูปแบบขนาด Orifice แนะนำที่ดีที่สุด 5 อันดับแรก (เกณฑ์ปลอดภัย: คุมเปอร์เซ็นต์เปิดช่วง 80% - 85%)**")
        if all_options:
            recommendation_text = ""
            rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            for i, (score, label) in enumerate(all_options[:5]):
                emoji = rank_emojis[i] if i < len(rank_emojis) else f"[{i+1}]"
                st.markdown(f"**{emoji}** {label}")
                recommendation_text += f"อันดับ {i+1}: {label}\n"
        else:
            qty_needed = math.ceil(cv_result / 0.48)
            recommendation_text = f"ไม่มีขนาดเดี่ยวหรือคู่ที่เปิดอยู่ในเกณฑ์ปลอดภัย -> แนะนำให้ขนานพอร์ตเพิ่มเป็น {qty_needed} x JH"
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
        hp_g_show = (HP_abs * 14.5038) - ATM_PSI if unit == "PSI" else HP_abs - ATM_BAR
        lp_g_show = (LP_abs * 14.5038) - ATM_PSI if unit == "PSI" else LP_abs - ATM_BAR
        p_label_g = "PSI G" if unit == "PSI" else "Bar G"
        
        log_content = (
            f"=== บันทึกรายงานการคัดเลือกขนาดวาล์ว Yosaku ({current_time}) ===\n"
            f"รุ่นคอมเพรสเซอร์ MYCOM ที่เลือก: {selected_model}\n"
            f"สภาวะควบคุมฝั่งอุณหภูมิ: Te = {Evap_temp:.1f} °C, Tc = {Cond_temp:.1f} °C\n"
            f"สถานะระบบ Economizer: {'เปิดใช้งาน (ECO Port)' if has_eco else 'ปิดใช้งาน (Single Stage)'}\n"
            f"ค่าภาระความร้อนน้ำมันคำนวณจริง: {q_oil_kw:.2f} kW\n"
            f"คำนวณอัตราการไหลน้ำยาแอมโมเนียระบายความร้อนได้ (G): {G:.2f} kg/h\n"
            f"แรงดันเกจหน้างานโดยประมาณ: HP={hp_g_show:.3f} {p_label_g}, LP={lp_g_show:.3f} {p_label_g}\n"
            f"ผลรวมค่าความต้องการ CV ทางวิศวกรรม: {cv_result:.4f}\n"
            f"--------------------------------------------------\n"
            f"ผลการคัดเลือก Orifice แนะนำ:\n{recommendation_text}"
            f"--------------------------------------------------\n"
        )
        st.download_button(
            label="📥 ดาวน์โหลดรายงานเทคนิค (Technical Spec Log)",
            data=log_content,
            file_name=f"Yosaku_MYCOMW_Calculated_{selected_model.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
