import math
import os
import itertools
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime

# ข้อมูลตาราง Orifice มาตรฐาน
ORIFICE_DATA = [
    ("JA", 0.04),
    ("JB", 0.08),
    ("JBC", 0.11),
    ("JC", 0.14),
    ("JD", 0.22),
    ("JE", 0.30),
    ("JF", 0.35),
    ("JG", 0.41),
    ("JH", 0.48)
]

def get_suitability_score(pct, is_single):
    if pct > 100:
        return -1
    penalty = 0 if is_single else 5
    # ยิ่งค่าเข้าใกล้ 85% มากเท่าไหร่ ส่วนต่าง abs(85 - pct) จะยิ่งน้อย ส่งผลให้คะแนนยิ่งสูง
    return 100 - abs(85 - pct) - penalty

def calculate_cv():
    try:
        G = float(entry_G.get())
        HP_input = float(entry_HP.get())
        LP_input = float(entry_LP.get())
        K = float(entry_K.get())
        
        unit = unit_var.get()
        if unit == "PSI":
            HP = HP_input / 14.5038
            LP = LP_input / 14.5038
        else:
            HP = HP_input
            LP = LP_input

        S = 0.583
        Y = 0.583
        
        pressure_drop = HP - LP
        
        if pressure_drop <= 0:
            messagebox.showerror("ข้อผิดพลาด", "ความดันขาเข้า (HP) ต้องมากกว่าความดันขาออก (LP)")
            return
            
        part_1 = 1.17 * (G / (1000 * Y))
        part_2 = math.sqrt(S / pressure_drop)
        cv_result = part_1 * part_2 * K
        
        display_dp = HP_input - LP_input
        label_dp_result.config(text=f"{display_dp:.3f} {unit}")
        label_cv_result.config(text=f"{cv_result:.4f}")
        
        # --- 1. คำนวณหา Top 5 ทางเลือกที่ดีที่สุด (เรียงตามความใกล้เคียง 85%) ---
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
                if name1 == name2:
                    label_text = f"2 x {name1} (เปิด {pct:.1f}%)"
                else:
                    label_text = f"1x {name1} + 1x {name2} (เปิดรวม {pct:.1f}%)"
                all_options.append((score, label_text))

        all_options.sort(key=lambda x: x[0], reverse=True)
        
        if all_options:
            # ดึงข้อมูลมาแสดงผล Top 5 อันดับแรก
            top_texts = [f"อันดับ {i+1}:  {label}" for i, (score, label) in enumerate(all_options[:5])]
            best_selection_text = "\n".join(top_texts)
            label_orifice_result.config(text=best_selection_text, fg="#28a745" if all_options[0][0] >= 60 else "#856404")
        else:
            qty_needed = math.ceil(cv_result / 0.48)
            best_selection_text = f"เล็กเกินไปทั้งหมด -> แนะนำใช้ {qty_needed} x JH"
            label_orifice_result.config(text=best_selection_text, fg="#dc3545")

        # --- 2. อัปเดตข้อมูลลงตารางที่ 1 & 2 (อิงตามเงื่อนไขใหม่ 75-85%) ---
        for name, max_cv in ORIFICE_DATA:
            # กรณีติดตั้ง 1 ตัว
            pct1 = (cv_result / max_cv) * 100
            if pct1 > 100: bg1, fg1, status1 = "#ffcccc", "#cc0000", "เล็กเกินไป"
            elif 75 <= pct1 <= 85: bg1, fg1, status1 = "#d4edda", "#155724", "เหมาะสม"
            elif 85 < pct1 <= 100: bg1, fg1, status1 = "#fff3cd", "#856404", "ใกล้เต็ม"
            else: bg1, fg1, status1 = "#ffffff", "#495057", "ใหญ่เกินไป"
                
            table_baseline_refs[name]['pct1'].config(text=f"{pct1:.1f} %", bg=bg1, fg=fg1)
            table_baseline_refs[name]['status1'].config(text=status1, bg=bg1, fg=fg1)
            
            # กรณีติดตั้ง 2 ตัวเหมือนกัน
            pct2 = (cv_result / (max_cv * 2)) * 100
            if pct2 > 100: bg2, fg2, status2 = "#ffcccc", "#cc0000", "เล็กเกินไป"
            elif 75 <= pct2 <= 85: bg2, fg2, status2 = "#d4edda", "#155724", "เหมาะสม"
            elif 85 < pct2 <= 100: bg2, fg2, status2 = "#fff3cd", "#856404", "ใกล้เต็ม"
            else: bg2, fg2, status2 = "#ffffff", "#495057", "ใหญ่เกินไป"
                
            table_baseline_refs[name]['pct2'].config(text=f"{pct2:.1f} %", bg=bg2, fg=fg2)
            table_baseline_refs[name]['status2'].config(text=status2, bg=bg2, fg=fg2)

        # --- 3. อัปเดตข้อมูลลงตารางที่ 3 (ตาราง Matrix การคละรุ่น) ---
        for name1, cv1 in ORIFICE_DATA:
            for name2, cv2 in ORIFICE_DATA:
                total_cv = cv1 + cv2
                pct = (cv_result / total_cv) * 100
                
                if pct > 100: bg, fg = "#ffcccc", "#cc0000"
                elif 75 <= pct <= 85: bg, fg = "#d4edda", "#155724"
                elif 85 < pct <= 100: bg, fg = "#fff3cd", "#856404"
                else: bg, fg = "#ffffff", "#6c757d"
                    
                table_matrix_refs[name1][name2].config(text=f"{pct:.1f}%", bg=bg, fg=fg)

        # บันทึกข้อมูลเตรียม Export Log
        global last_calculation_data
        last_calculation_data = {
            "G": G, "HP": HP_input, "LP": LP_input, "Unit": unit,
            "DP": display_dp, "K": K, "CV": cv_result, "Recommendation": best_selection_text
        }
        btn_export.config(state="normal")
        
    except ValueError:
        messagebox.showerror("ข้อผิดพลาด", "กรุณากรอกเฉพาะตัวเลขเท่านั้น และห้ามเว้นช่องว่าง")

def clear_fields():
    entry_G.delete(0, tk.END)
    entry_HP.delete(0, tk.END)
    entry_LP.delete(0, tk.END)
    entry_K.delete(0, tk.END)
    entry_K.insert(0, "1.0")
    label_dp_result.config(text="0.000 Bar")
    label_cv_result.config(text="0.0000")
    label_orifice_result.config(text="-", fg="#333333")
    
    # ล้างตารางที่ 1 & 2
    for name, _ in ORIFICE_DATA:
        table_baseline_refs[name]['pct1'].config(text="-", bg="#ffffff", fg="#333333")
        table_baseline_refs[name]['status1'].config(text="-", bg="#ffffff", fg="#333333")
        table_baseline_refs[name]['pct2'].config(text="-", bg="#ffffff", fg="#333333")
        table_baseline_refs[name]['status2'].config(text="-", bg="#ffffff", fg="#333333")
        
    # ล้างตารางที่ 3 Matrix
    for name1, _ in ORIFICE_DATA:
        for name2, _ in ORIFICE_DATA:
            table_matrix_refs[name1][name2].config(text="-", bg="#ffffff", fg="#333333")
        
    btn_export.config(state="disabled")
    entry_G.focus()

def export_log():
    try:
        if not last_calculation_data:
            return
        current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"Yosaku_Log_{current_time_str}.txt"
        file_path = filedialog.asksaveasfilename(
            title="เลือกตำแหน่งบันทึกไฟล์ผลการคำนวณ",
            initialfile=default_filename,
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not file_path: return

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"=== บันทึกเมื่อ {current_time} ===\n")
            f.write(f"ชื่อโปรแกรม: Yosaku Selection\n")
            f.write(f"อัตราไหลมวล G: {last_calculation_data['G']} kg/h\n")
            f.write(f"ความดันขาเข้า HP: {last_calculation_data['HP']} {last_calculation_data['Unit']}\n")
            f.write(f"ความดันขาออก LP: {last_calculation_data['LP']} {last_calculation_data['Unit']}\n")
            f.write(f"Pressure Drop: {last_calculation_data['DP']} {last_calculation_data['Unit']}\n")
            f.write(f"ค่าปรับแก้ K Factor: {last_calculation_data['K']}\n")
            f.write(f"ผลลัพธ์ค่า CV วาล์วที่คำนวณได้: {last_calculation_data['CV']:.4f}\n")
            f.write(f"--- ทางเลือกที่เหมาะสมที่สุด (Top 5) ---\n")
            f.write(f"{last_calculation_data['Recommendation']}\n")
            f.write("-" * 50 + "\n\n")
        messagebox.showinfo("สำเร็จ", f"บันทึกข้อมูลเรียบร้อยแล้วที่:\n{file_path}")
    except Exception as e:
        messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถบันทึกไฟล์ได้: {e}")

# --- UI Setup ---
root = tk.Tk()
root.title("Yosaku Selection by Chattrawat Khamsee")

window_width = 960
window_height = 980

screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
center_x = int(screen_width/2 - window_width / 2)
center_y = max(0, int(screen_height/2 - window_height / 2) - 20) 
root.geometry(f'{window_width}x{window_height}+{center_x}+{center_y}')
root.resizable(False, True) 
root.configure(bg="#f5f5f5")

last_calculation_data = {}
table_baseline_refs = {} 
table_matrix_refs = {}

font_title = ("Helvetica", 16, "bold")
font_label = ("Helvetica", 11)
font_entry = ("Helvetica", 12)
font_table_header = ("Helvetica", 9, "bold")

# --- ส่วนจัดการเรื่อง Logo และ Icon (เก็บจุดนี้ไว้เพียงจุดเดียว) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
logo_filename = os.path.join(current_dir, "logo.png") 
logo_ui_tk = None

try:
    from PIL import Image, ImageTk
    if os.path.exists(logo_filename):
        img_pil = Image.open(logo_filename)
        icon_tk = ImageTk.PhotoImage(img_pil)
        root.iconphoto(False, icon_tk)
        
        img_w, img_h = img_pil.size
        target_h = 40
        target_w = int((target_h / img_h) * img_w)
        img_resized = img_pil.resize((target_w, target_h), Image.Resampling.LANCZOS)
        logo_ui_tk = ImageTk.PhotoImage(img_resized)
    else:
        print(f"⚠️ หาไฟล์ไม่พบ: โปรแกรมพยายามมองหาที่ -> {logo_filename}")
except ImportError:
    print("❌ แจ้งเตือน: กรุณาติดตั้ง Pillow โดยรันคำสั่ง 'pip install pillow' ใน Terminal")
except Exception as e:
    print(f"⚠️ เกิดข้อผิดพลาดในการโหลดรูปภาพ: {e}")

# --- Header ---
frame_header = tk.Frame(root, bg="#f5f5f5")
frame_header.pack(fill="x", padx=40, pady=5)

if logo_ui_tk:
    lbl_logo = tk.Label(frame_header, image=logo_ui_tk, bg="#f5f5f5")
    lbl_logo.image = logo_ui_tk
    lbl_logo.pack(side="left", padx=(0, 15))

tk.Label(frame_header, text="Yosaku Selection", font=font_title, bg="#f5f5f5", fg="#0056b3").pack(side="left")

# --- Inputs ---
frame_unit = tk.Frame(root, bg="#f5f5f5")
frame_unit.pack(pady=2)
unit_var = tk.StringVar(value="Bar")
tk.Label(frame_unit, text="เลือกหน่วยความดัน:", font=("Helvetica", 10), bg="#f5f5f5").pack(side="left", padx=5)
tk.Radiobutton(frame_unit, text="Bar", variable=unit_var, value="Bar", bg="#f5f5f5", font=("Helvetica", 10)).pack(side="left", padx=5)
tk.Radiobutton(frame_unit, text="PSI", variable=unit_var, value="PSI", bg="#f5f5f5", font=("Helvetica", 10)).pack(side="left", padx=5)

frame_input = tk.Frame(root, bg="#f5f5f5")
frame_input.pack(pady=2)

tk.Label(frame_input, text="อัตราไหลมวล G (kg/h):", font=font_label, bg="#f5f5f5").grid(row=0, column=0, sticky="e", pady=2, padx=5)
entry_G = tk.Entry(frame_input, font=font_entry, width=12, justify="center")
entry_G.grid(row=0, column=1, pady=2)
entry_G.focus()

tk.Label(frame_input, text="ความดันขาเข้า HP:", font=font_label, bg="#f5f5f5").grid(row=0, column=2, sticky="e", pady=2, padx=5)
entry_HP = tk.Entry(frame_input, font=font_entry, width=12, justify="center")
entry_HP.grid(row=0, column=3, pady=2)

tk.Label(frame_input, text="ความดันขาออก LP:", font=font_label, bg="#f5f5f5").grid(row=1, column=0, sticky="e", pady=2, padx=5)
entry_LP = tk.Entry(frame_input, font=font_entry, width=12, justify="center")
entry_LP.grid(row=1, column=1, pady=2)

tk.Label(frame_input, text="ค่าปรับแก้ K Factor:", font=font_label, bg="#f5f5f5").grid(row=1, column=2, sticky="e", pady=2, padx=5)
entry_K = tk.Entry(frame_input, font=font_entry, width=12, justify="center")
entry_K.grid(row=1, column=3, pady=2)
entry_K.insert(0, "1.0")

# --- Buttons ---
frame_buttons = tk.Frame(root, bg="#f5f5f5")
frame_buttons.pack(pady=4)

btn_calc = tk.Button(frame_buttons, text="CALCULATE", font=("Helvetica", 11, "bold"), bg="#28a745", fg="white", width=12, command=calculate_cv, bd=0, pady=4)
btn_calc.grid(row=0, column=0, padx=5)

btn_clr = tk.Button(frame_buttons, text="CLEAR", font=("Helvetica", 11, "bold"), bg="#dc3545", fg="white", width=12, command=clear_fields, bd=0, pady=4)
btn_clr.grid(row=0, column=1, padx=5)

btn_export = tk.Button(frame_buttons, text="📥 SAVE TO LOG", font=("Helvetica", 10, "bold"), bg="#17a2b8", fg="white", width=14, command=export_log, bd=0, pady=4)
btn_export.grid(row=0, column=2, padx=5)
btn_export.config(state="disabled")

# --- Results Panel ---
frame_result = tk.Frame(root, bg="#e9ecef", bd=1, relief="solid", padx=15, pady=4)
frame_result.pack(fill="x", padx=40, pady=4)

tk.Label(frame_result, text="Pressure Drop:", font=font_label, bg="#e9ecef").grid(row=0, column=0, sticky="w")
label_dp_result = tk.Label(frame_result, text="0.000 Bar", font=("Helvetica", 11, "bold"), bg="#e9ecef", fg="#495057")
label_dp_result.grid(row=0, column=1, sticky="w", padx=10)

tk.Label(frame_result, text="ผลรวมค่า CV ที่คำนวณได้:", font=font_label, bg="#e9ecef").grid(row=0, column=2, sticky="w", padx=20)
label_cv_result = tk.Label(frame_result, text="0.0000", font=("Helvetica", 12, "bold"), bg="#e9ecef", fg="#0056b3")
label_cv_result.grid(row=0, column=3, sticky="w", padx=10)

tk.Label(frame_result, text="★ ชุดประกอบแนะนำที่ดีที่สุด 5 อันดับแรก (เรียงตามความใกล้เคียง 85%):", font=("Helvetica", 10, "bold"), bg="#e9ecef", fg="#2b5e2b").grid(row=1, column=0, columnspan=2, sticky="nw", pady=4)
label_orifice_result = tk.Label(frame_result, text="-", font=("Helvetica", 11, "bold"), bg="#e9ecef", fg="#28a745", justify="left")
label_orifice_result.grid(row=1, column=2, columnspan=2, sticky="nw", padx=10, pady=4)

# =========================================================
# --- ตารางที่ 1 & 2: Baseline (1 ตัว VS 2 ตัวเหมือนกัน) ---
# =========================================================
frame_baseline = tk.LabelFrame(root, text=" ตารางอ้างอิงสถานะแบบ 1 ตัวปกติ VS แบบต่อขนาน 2 ตัวรุ่นเดียวกัน ", font=("Helvetica", 10, "bold"), bg="#ffffff", fg="#333333", padx=10, pady=2)
frame_baseline.pack(fill="x", padx=40, pady=5)

tk.Label(frame_baseline, text="ข้อมูลพื้นฐาน Orifice", font=font_table_header, bg="#d6d8db", fg="#333333", relief="groove").grid(row=0, column=0, columnspan=2, sticky="nsew")
tk.Label(frame_baseline, text="กรณีติดตั้ง 1 ตัว", font=font_table_header, bg="#b8daff", fg="#004085", relief="groove").grid(row=0, column=2, columnspan=2, sticky="nsew")
tk.Label(frame_baseline, text="กรณีติดตั้ง 2 ตัว (รุ่นเดียวกัน)", font=font_table_header, bg="#c3e6cb", fg="#155724", relief="groove").grid(row=0, column=4, columnspan=2, sticky="nsew")

headers = ["Orifice", "Max Cv", "% เปิด", "สถานะวิเคราะห์", "% เปิด/ตัว", "สถานะวิเคราะห์"]
for col_idx, text in enumerate(headers):
    lbl = tk.Label(frame_baseline, text=text, font=("Helvetica", 8, "bold"), bg="#e9ecef", fg="#333333", relief="groove", padx=4, pady=2)
    lbl.grid(row=1, column=col_idx, sticky="nsew")

for i in range(6):
    frame_baseline.grid_columnconfigure(i, weight=1 if i in [0,1,2,4] else 2)

for row_idx, (name, max_cv) in enumerate(ORIFICE_DATA, start=2):
    tk.Label(frame_baseline, text=name, font=("Helvetica", 9, "bold"), bg="#f8f9fa", relief="groove", pady=2).grid(row=row_idx, column=0, sticky="nsew")
    tk.Label(frame_baseline, text=f"{max_cv:.2f}", font=("Helvetica", 9), bg="#f8f9fa", relief="groove", pady=2).grid(row=row_idx, column=1, sticky="nsew")
    
    p1 = tk.Label(frame_baseline, text="-", font=("Helvetica", 9), bg="#ffffff", relief="groove", pady=2)
    p1.grid(row=row_idx, column=2, sticky="nsew")
    s1 = tk.Label(frame_baseline, text="-", font=("Helvetica", 8), bg="#ffffff", relief="groove", pady=2)
    s1.grid(row=row_idx, column=3, sticky="nsew")
    
    p2 = tk.Label(frame_baseline, text="-", font=("Helvetica", 9), bg="#ffffff", relief="groove", pady=2)
    p2.grid(row=row_idx, column=4, sticky="nsew")
    s2 = tk.Label(frame_baseline, text="-", font=("Helvetica", 8), bg="#ffffff", relief="groove", pady=2)
    s2.grid(row=row_idx, column=5, sticky="nsew")
    
    table_baseline_refs[name] = {'pct1': p1, 'status1': s1, 'pct2': p2, 'status2': s2}

# =========================================================
# --- ตารางที่ 3: เมทริกซ์การคละรุ่น (Mixed Pairing Matrix) ---
# =========================================================
frame_matrix = tk.LabelFrame(root, text=" ตารางวิเคราะห์เปอร์เซ็นต์เปิดรวม แบบจับคู่คละรุ่น 2 ตัว (Cross-Matching) ", font=("Helvetica", 10, "bold"), bg="#ffffff", fg="#333333", padx=10, pady=2)
frame_matrix.pack(fill="both", expand=True, padx=40, pady=5)

tk.Label(frame_matrix, text="ตัวที่ 1 \ (ตัวที่ 2) ➡️", font=("Helvetica", 8, "bold"), bg="#d6d8db", fg="#333333", relief="groove").grid(row=0, column=0, sticky="nsew")
for col_idx, (name, _) in enumerate(ORIFICE_DATA, start=1):
    tk.Label(frame_matrix, text=name, font=("Helvetica", 8, "bold"), bg="#b8daff", fg="#004085", relief="groove", width=8).grid(row=0, column=col_idx, sticky="nsew")

frame_matrix.grid_columnconfigure(0, weight=2)
for i in range(1, len(ORIFICE_DATA) + 1):
    frame_matrix.grid_columnconfigure(i, weight=1)

for row_idx, (name1, cv1) in enumerate(ORIFICE_DATA, start=1):
    tk.Label(frame_matrix, text=f"{name1} ({cv1:.2f})", font=("Helvetica", 8, "bold"), bg="#c3e6cb", fg="#155724", relief="groove", pady=2).grid(row=row_idx, column=0, sticky="nsew")
    table_matrix_refs[name1] = {}
    for col_idx, (name2, cv2) in enumerate(ORIFICE_DATA, start=1):
        cell_lbl = tk.Label(frame_matrix, text="-", font=("Helvetica", 8), bg="#ffffff", relief="groove", pady=2)
        cell_lbl.grid(row=row_idx, column=col_idx, sticky="nsew")
        table_matrix_refs[name1][name2] = cell_lbl

root.mainloop()