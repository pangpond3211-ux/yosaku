import streamlit as st
import pandas as pd
import math
import itertools
from datetime import datetime

# ตั้งค่าหน้าตาของ Web App ให้เหมาะกับมือถือ
st.set_page_config(
    page_title="Yosaku Selection",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ข้อมูลตาราง Orifice มาตรฐาน
ORIFICE_DATA = [
    ("JA", 0.04), ("JB", 0.08), ("JBC", 0.11), 
    ("JC", 0.14), ("JD", 0.22), ("JE", 0.30), 
    ("JF", 0.35), ("JG", 0.41), ("JH", 0.48)
]

# ฟังก์ชันคำนวณคะแนนความเหมาะสม (ไม่เกิน 87%)
def get_suitability_score(pct, is_single):
    if pct > 87:  
        return -1
    penalty = 0 if is_single else 5
    return 100 - abs(85 - pct) - penalty

def style_baseline_df(df):
    styles = pd.DataFrame('', index=df.index, columns=df.columns)
    for i, row in df.iterrows():
        s1 = row["สถานะ (1 ตัว)"]
        style1 = {
            "เล็กเกินไป": "background-color: #ffcccc; color: #cc0000;",
            "เหมาะสม": "background-color: #d4edda; color: #155724; font-weight: bold;",
            "ใกล้เต็ม": "background-color: #fff3cd; color: #856404;",
            "ใหญ่เกินไป": "background-color: #ffffff; color: #6c757d;"
        }.get(s1, "")
        styles.at[i, "% เปิด (1 ตัว)"] = style1
        styles.at[i, "สถานะ (1 ตัว)"] = style1
        
        s2 = row["สถานะ (2 ตัว)"]
        style2 = {
            "เล็กเกินไป": "background-color: #ffcccc; color: #cc0000;",
            "เหมาะสม": "background-color: #d4edda; color: #155724; font-weight: bold;",
            "ใกล้เต็ม": "background-color: #fff3cd; color: #856404;",
            "ใหญ่เกินไป": "background-color: #ffffff; color: #6c757d;"
        }.get(s2, "")
        styles.at[i, "% เปิด (2 ตัว)"] = style2
        styles.at[i, "สถานะ (2 ตัว)"] = style2
    return styles

def color_matrix_cells(val):
    if pd.isna(val): return ""
    if val > 100: return "background-color: #ffcccc; color: #cc0000;"
    elif 75 <= val <= 85: return "background-color: #d4edda; color: #155724; font-weight: bold;"
    elif 85 < val <= 100: return "background-color: #fff3cd; color: #856404;"
    else: return "background-color: #ffffff; color: #6c757d;"

# ========================================================
# ส่วนหัวของโปรแกรม (Header) พร้อมระบบรองรับโลโก้เซฟตี้
# ========================================================
try:
    st.image("logo.png", width=130)
except:
    pass # ถ้ายังไม่ได้อัปโหลดรูป logo.png ขึ้น GitHub โปรแกรมจะไม่พัง

st.title("🎯 Yosaku Selection")
st.caption("พัฒนาโดย Chattrawat Khamsee | เวอร์ชัน Web App สำหรับมือถือ")

# 📖 ส่วนแสดงสมการและที่มา
with st.expander("📖 ดูสมการและทฤษฎีที่ใช้คำนวณ (Formula & Derivation)"):
    st.markdown("โปรแกรมนี้คำนวณหาค่าสัมประสิทธิ์การไหล ($C_v$) ของ Orifice ตามสูตรมาตรฐานวิศวกรรม:")
    st.latex(r"C_v = 1.17 \times \left( \frac{G}{1000 \times Y} \right) \times \sqrt{\frac{S}{\Delta P}} \times K")
    st.markdown("""
    **คำอธิบายตัวแปรตำแหน่งต่าง ๆ:**
    * $\Delta P = HP - LP$ : ความดันตกคร่อมวาล์ว (Pressure Drop) ในหน่วย $\text{Bar}$
    * $G$ : อัตราการไหลมวล (Mass Flow Rate) $[\text{kg/h}]$
    * $Y$ : ค่าการขยายตัว (Expansion Factor) = $0.583$
    * $S$ : ความถ่วงจำเพาะ (Specific Gravity) = $0.583$
    * $K$ : ค่าปรับแก้ (K Factor) จากผู้ใช้
    """)

# ส่วนรับข้อมูล (Inputs)
unit = st.radio("เลือกหน่วยความดัน:", ["Bar", "PSI"], horizontal=True)

col1, col2 = st.columns(2)
with col1:
    G = st.number_input("อัตราไหลมวล G (kg/h):", min_value=0.0, value=0.0, step=10.0)
    LP_input = st.number_input("ความดันขาออก LP:", min_value=0.0, value=0.0, step=0.1)

with col2:
    HP_input = st.number_input("ความดันขาเข้า HP:", min_value=0.0, value=0.0, step=0.1)
    K = st.number_input("ค่าปรับแก้ K Factor:", min_value=0.0, value=1.0, step=0.1)

# ปุ่มคำนวณ
if st.button("🚀 CALCULATE", type="primary", use_container_width=True):
    if HP_input <= LP_input and G > 0:
        st.error("❌ ข้อผิดพลาด: ความดันขาเข้า (HP) ต้องมากกว่าความดันขาออก (LP)")
    elif G <= 0:
        st.warning("⚠️ กรุณากรอกอัตราไหลมวล G ให้มากกว่า 0")
    else:
        # แปลงหน่วยความดัน
        HP = HP_input / 14.5038 if unit == "PSI" else HP_input
        LP = LP_input / 14.5038 if unit == "PSI" else LP_input
        
        pressure_drop = HP - LP
        S, Y = 0.583, 0.583
        
        # สูตรคำนวณ Cv
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / pressure_drop)
        cv_result = part_1 * part_2 * K
        display_dp = HP_input - LP_input

        # แสดงผลลัพธ์หลัก
        st.subheader("📊 ผลการคำนวณ")
        res_col1, res_col2 = st.columns(2)
        res_col1.metric("Pressure Drop", f"{display_dp:.3f} {unit}")
        res_col2.metric("ผลรวมค่า CV ที่คำนวณได้", f"{cv_result:.4f}")

        # --- 1. คำนวณหา Top 5 ทางเลือกที่ดีที่สุด (ดึงค่า % ออกมาแยกสลอต) ---
        all_options = []
        for name, max_cv in ORIFICE_DATA:
            pct = (cv_result / max_cv) * 100
            score = get_suitability_score(pct, is_single=True)
            if score > 0:
                all_options.append((score, f"1 x {name}", pct))
                
        for (name1, cv1), (name2, cv2) in itertools.combinations_with_replacement(ORIFICE_DATA, 2):
            total_cv = cv1 + cv2
            pct = (cv_result / total_cv) * 100
            score = get_suitability_score(pct, is_single=False)
            if score > 0:
                label_text = f"2 x {name1}" if name1 == name2 else f"1x {name1} + 1x {name2}"
                all_options.append((score, label_text, pct))

        all_options.sort(key=lambda x: x[0], reverse=True)
        
        st.success("🏆 **ชุดประกอบแนะนำที่ดีที่สุด 5 อันดับแรก (เข้าใกล้ 85% และไม่เกิน 87%)**")
        if all_options:
            recommendation_text = ""
            chart_data = [] # เก็บข้อมูลไปวาดกราฟ
            
            for i, (score, label, pct) in enumerate(all_options[:5]):
                full_label = f"{label} (เปิด {pct:.1f}%)"
                st.write(f"**อันดับ {i+1}:** {full_label}")
                recommendation_text += f"อันดับ {i+1}: {full_label}\n"
                
                # บันทึกข้อมูลลงลิสต์สำหรับสร้างกราฟ
                chart_data.append({
                    "ชุดประกอบแนะนำ": f"อันดับ {i+1}: {label}",
                    "เปอร์เซ็นต์การเปิด (%)": pct
                })
            
            # 📈 ส่วนแสดงกราฟเปรียบเทียบเปอร์เซ็นต์การเปิด
            st.write("")
            st.subheader("📈 กราฟเปรียบเทียบ % การเปิดของ 5 อันดับแรก")
            df_chart = pd.DataFrame(chart_data)
            # แสดงกราฟแท่งสีเขียวเพื่อให้แมตช์กับธีมวิศวกรรม
            st.bar_chart(df_chart, x="ชุดประกอบแนะนำ", y="เปอร์เซ็นต์การเปิด (%)", color="#2e7d32")
            
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

        # --- 3. สร้างตารางที่ 3: เมทริกซ์การคละรุ่น พร้อมใส่สีไฮไลต์ ---
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
        log_content = (
            f"=== บันทึกเมื่อ {current_time} ===\n"
            f"ชื่อโปรแกรม: Yosaku Selection (Web App)\n"
            f"อัตราไหลมวล G: {G} kg/h\n"
            f"ความดันขาเข้า HP: {HP_input} {unit}\n"
            f"ความดันขาออก LP: {LP_input} {unit}\n"
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
