import tkinter as tk

root = tk.Tk()
root.title("テストウィンドウ")
root.geometry("300x200")
tk.Label(root, text="こんにちは、世界！").pack(pady=20)
root.mainloop()