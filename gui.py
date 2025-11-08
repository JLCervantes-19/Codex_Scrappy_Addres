#!/usr/bin/env python3
# gui.py
"""Interfaz gráfica para resolver CAPTCHA manualmente"""

import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk


class CaptchaGUI:
    """GUI para mostrar CAPTCHA y permitir resolución manual"""
    
    def __init__(self, image_path, on_submit):
        self.root = tk.Tk()
        self.root.title("Resolver CAPTCHA - ADRES")
        self.on_submit = on_submit
        self._setup_ui(image_path)

    def _setup_ui(self, image_path):
        """Configura la interfaz de usuario"""
        # Cargar y escalar imagen
        img = self._load_and_scale_image(image_path)
        self.tkimg = ImageTk.PhotoImage(img)
        
        # Label con imagen
        lbl = ttk.Label(self.root, image=self.tkimg)
        lbl.pack(padx=8, pady=8)

        # Frame de entrada
        frm = ttk.Frame(self.root)
        frm.pack(padx=8, pady=(0, 8), fill="x")
        ttk.Label(frm, text="Ingrese los números del CAPTCHA:").pack(anchor="w")
        
        self.entry = ttk.Entry(frm, font=("Segoe UI", 14))
        self.entry.pack(fill="x", pady=6)
        self.entry.focus()

        # Botones
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(padx=8, pady=(0, 12))
        
        submit_btn = ttk.Button(btn_frame, text="Enviar", command=self._submit)
        submit_btn.grid(row=0, column=0, padx=6)
        
        cancel_btn = ttk.Button(btn_frame, text="Cancelar", command=self._cancel)
        cancel_btn.grid(row=0, column=1, padx=6)

        # Bindings
        self.entry.bind("<Return>", lambda e: self._submit())
        
        # Mantener ventana arriba temporalmente
        self.root.attributes("-topmost", True)
        self.root.after(200, lambda: self.root.attributes("-topmost", False))

    def _load_and_scale_image(self, image_path, max_width=800):
        """Carga y escala la imagen si es necesario"""
        img = Image.open(image_path)
        if img.width > max_width:
            ratio = max_width / img.width
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        return img

    def _submit(self):
        """Maneja el envío del CAPTCHA"""
        value = self.entry.get().strip()
        if not value:
            messagebox.showwarning("Aviso", "Ingresa el código del CAPTCHA antes de enviar.")
            return
        self.on_submit(value)
        self.root.destroy()

    def _cancel(self):
        """Maneja la cancelación"""
        self.on_submit(None)
        self.root.destroy()

    def show(self):
        """Muestra la ventana"""
        self.root.mainloop()