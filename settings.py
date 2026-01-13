import tkinter as tk
from tkinter import messagebox
import json
import os

CONFIG_FILE = "config.json"

def load_threshold():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('threshold', 0.95)
        except Exception:
            return 0.95
    return 0.95

def save_threshold(value):
    try:
        val = float(value)
        if 0 <= val <= 1:
            with open(CONFIG_FILE, 'w') as f:
                json.dump({"threshold": val}, f, indent=4)
            return True
        else:
            messagebox.showerror("Error", "Threshold must be between 0 and 1")
            return False
    except ValueError:
        messagebox.showerror("Error", "Invalid number format")
        return False

class SettingsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Pose Confidence Settings")
        self.root.geometry("300x200")
        self.root.resizable(False, False)

        tk.Label(root, text="Pose Similarity Threshold", font=("Arial", 12, "bold")).pack(pady=10)
        tk.Label(root, text="(0.0 - 1.0)").pack()

        self.threshold_var = tk.StringVar(value=str(load_threshold()))
        self.entry = tk.Entry(root, textvariable=self.threshold_var, font=("Arial", 12), justify='center')
        self.entry.pack(pady=10)

        self.save_btn = tk.Button(root, text="Save Settings", command=self.save_action, 
                                  bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), padx=10, pady=5)
        self.save_btn.pack(pady=10)

    def save_action(self):
        if save_threshold(self.threshold_var.get()):
            messagebox.showinfo("Success", "Threshold updated successfully!")
            # self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SettingsApp(root)
    root.mainloop()
