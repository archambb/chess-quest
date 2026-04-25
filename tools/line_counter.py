import os
import tkinter as tk
from tkinter import filedialog, messagebox


def count_lines_in_py_files(folder_path):
    total_lines = 0
    total_files = 0

    for file in os.listdir(folder_path):
        if file.endswith(".py"):
            full_path = os.path.join(folder_path, file)
            if os.path.isfile(full_path):
                total_files += 1
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        total_lines += sum(1 for _ in f)
                except Exception as e:
                    print(f"[WARN] Could not read {file}: {e}")

    return total_files, total_lines



def choose_folder():
    folder_path = filedialog.askdirectory()
    if not folder_path:
        return

    file_count, line_count = count_lines_in_py_files(folder_path)
    result_var.set(f"🗂️ {file_count} Python files\n📏 {line_count} total lines")


# ─────────────────────────────────────
# GUI Setup
# ─────────────────────────────────────
root = tk.Tk()
root.title("Python File Line Counter")
root.geometry("320x200")
root.resizable(False, False)

frame = tk.Frame(root, padx=20, pady=20)
frame.pack(expand=True)

btn = tk.Button(frame, text="Select Folder", command=choose_folder)
btn.pack(pady=(0, 10))

result_var = tk.StringVar()
result_label = tk.Label(frame, textvariable=result_var, justify="left", font=("Courier", 12))
result_label.pack()

root.mainloop()
