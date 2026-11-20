import csv
import datetime
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk

from pointage_store import (
    enregistrer_entree,
    enregistrer_sortie,
    get_resume_parking,
    lister_pointages,
)
from vision_ocr import detecter_voiture_et_plaque, formater_plaque_tunisienne


def _charger_font(taille: int):
    chemins = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/tahoma.ttf",
    ]
    for p in chemins:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, taille)
            except OSError:
                pass
    return ImageFont.load_default()


def _dessiner_plaque_pil(img_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int, texte: str) -> np.ndarray:
    """يرسم لوحة ترقيم واضحة مع دعم الحروف العربية."""
    pil = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    draw.rectangle([x1, y1, x2, y2], fill=(250, 250, 252), outline=(15, 23, 42), width=2)
    font = _charger_font(14)
    bbox = draw.textbbox((0, 0), texte, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = x1 + max(4, ((x2 - x1) - tw) // 2)
    ty = y1 + max(2, ((y2 - y1) - th) // 2)
    draw.text((tx, ty), texte, fill=(15, 23, 42), font=font)
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def generer_scene_entree(plaque: str = "123 تونس 4567") -> np.ndarray:
    """مشهد احترافي لسيارة في ممر الدخول مع إطار أخضر ولوحة ترقيم واضحة."""
    img = np.full((280, 460, 3), (214, 226, 238), dtype=np.uint8)
    img[:122, :] = (168, 202, 228)
    img[122:162, :] = (82, 152, 86)
    img[162:, :] = (74, 79, 86)
    cv2.line(img, (0, 226), (460, 226), (226, 232, 240), 2)

    cv2.ellipse(img, (230, 233), (125, 10), 0, 0, 360, (48, 52, 58), -1)

    cv2.rectangle(img, (115, 122), (345, 212), (88, 98, 112), -1)
    cv2.rectangle(img, (150, 80), (310, 125), (76, 86, 98), -1)
    cv2.rectangle(img, (160, 87), (226, 119), (222, 236, 246), -1)
    cv2.rectangle(img, (236, 87), (300, 119), (222, 236, 246), -1)

    cv2.rectangle(img, (124, 172), (146, 188), (180, 240, 255), -1)
    cv2.rectangle(img, (314, 172), (336, 188), (180, 240, 255), -1)
    cv2.circle(img, (168, 215), 26, (24, 26, 30), -1)
    cv2.circle(img, (168, 215), 12, (130, 136, 145), -1)
    cv2.circle(img, (292, 215), 26, (24, 26, 30), -1)
    cv2.circle(img, (292, 215), 12, (130, 136, 145), -1)

    cv2.rectangle(img, (102, 70), (358, 242), (34, 197, 94), 3)
    cv2.rectangle(img, (102, 46), (185, 70), (22, 163, 74), -1)
    cv2.putText(img, "ENTREE", (112, 63), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2)

    return _dessiner_plaque_pil(img, 168, 170, 292, 200, plaque[:18])


def generer_scene_sortie(plaque: str = "123 تونس 4567") -> np.ndarray:
    """مشهد ممر الخروج مع حاجز ولوحة واضحة."""
    img = np.full((280, 460, 3), (198, 214, 228), dtype=np.uint8)
    img[:122, :] = (176, 200, 220)
    img[122:, :] = (105, 110, 118)
    cv2.rectangle(img, (0, 162), (460, 214), (132, 138, 146), -1)

    cv2.rectangle(img, (60, 122), (82, 225), (30, 41, 59), -1)
    cv2.line(img, (82, 154), (345, 154), (36, 36, 220), 8)
    cv2.line(img, (128, 154), (168, 154), (255, 255, 255), 8)
    cv2.line(img, (216, 154), (256, 154), (255, 255, 255), 8)

    cv2.rectangle(img, (60, 96), (132, 122), (220, 38, 38), -1)
    cv2.putText(img, "SORTIE", (68, 114), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 255, 255), 2)

    return _dessiner_plaque_pil(img, 118, 228, 342, 260, f"Sortie : {plaque[:18]}")


class SmartParkingApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Parking Intelligent — Monitoring / Gestion du Parking")
        self.root.geometry("1340x830")
        self.root.minsize(1120, 730)
        self.root.configure(bg="#e8eef5")

        self.cap = None
        self.camera_active = False
        self.capacite_parking = 30
        self.plaque_courante = "123 تونس 4567"
        self.photo_entree = None
        self.photo_sortie = None
        self.boutons_menu = {}
        self._records_cache = []

        self._configurer_styles()
        self._construire_interface()
        self.afficher_scene_entree(generer_scene_entree(self.plaque_courante), self.plaque_courante)
        self.afficher_scene_sortie(generer_scene_sortie(self.plaque_courante), self.plaque_courante)
        self.rafraichir_tout()
        self._tick_horloge()

    def _configurer_styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Parking.Treeview",
            background="#ffffff",
            foreground="#1e293b",
            rowheight=28,
            fieldbackground="#ffffff",
            font=("Segoe UI", 9),
        )
        style.configure(
            "Parking.Treeview.Heading",
            background="#f1f5f9",
            foreground="#0f172a",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )
        style.map("Parking.Treeview", background=[("selected", "#bfdbfe")], foreground=[("selected", "#0f172a")])

    def _activer_bouton_menu(self, nom_menu):
        for cle, btn in self.boutons_menu.items():
            if cle == nom_menu:
                btn.configure(bg="#1976d2", fg="#ffffff", font=("Segoe UI", 9, "bold"))
            else:
                btn.configure(bg="#0b2239", fg="#cbd5e1", font=("Segoe UI", 9, "normal"))

    def _tick_horloge(self):
        if hasattr(self, "lbl_horloge") and self.lbl_horloge.winfo_exists():
            self.lbl_horloge.configure(text=datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
            self.root.after(1000, self._tick_horloge)

    def _construire_interface(self):
        sidebar = tk.Frame(self.root, bg="#0b2239", width=215)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar,
            text="P  Parking Intelligent",
            font=("Segoe UI", 12, "bold"),
            fg="#ffffff",
            bg="#0b2239",
            pady=14,
            padx=14,
            anchor="w",
        ).pack(fill="x")

        items_menu = [
            ("Tableau de bord", self.menu_tableau_de_bord),
            ("Caméras", self.menu_cameras),
            ("Historique", self.menu_historique),
            ("Pointages", self.menu_pointages),
            ("Rapports", self.menu_rapports),
            ("Paramètres", self.menu_parametres),
            ("À propos", self.menu_a_propos),
        ]

        for label, cmd in items_menu:
            btn = tk.Button(
                sidebar,
                text=f"   {label}",
                command=cmd,
                anchor="w",
                bg="#0b2239",
                fg="#cbd5e1",
                activebackground="#1565c0",
                activeforeground="#ffffff",
                bd=0,
                font=("Segoe UI", 9),
                pady=9,
                cursor="hand2",
            )
            btn.pack(fill="x", padx=8, pady=2)
            self.boutons_menu[label] = btn

        self._activer_bouton_menu("Tableau de bord")

        tk.Frame(sidebar, bg="#0b2239").pack(fill="both", expand=True)

        online_box = tk.Frame(sidebar, bg="#0f2d4a", padx=12, pady=8)
        online_box.pack(fill="x", padx=10, pady=(0, 8))
        tk.Label(online_box, text="● En ligne", font=("Segoe UI", 9, "bold"), fg="#22c55e", bg="#0f2d4a").pack(
            anchor="w"
        )
        self.lbl_horloge = tk.Label(
            online_box,
            text=datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            font=("Segoe UI", 8),
            fg="#cbd5e1",
            bg="#0f2d4a",
        )
        self.lbl_horloge.pack(anchor="w")

        tk.Button(
            sidebar,
            text="⏻  Se déconnecter",
            command=self.quitter_app,
            bg="#16324f",
            fg="#f1f5f9",
            activebackground="#dc2626",
            activeforeground="#ffffff",
            bd=0,
            font=("Segoe UI", 9),
            pady=8,
            cursor="hand2",
        ).pack(fill="x", padx=10, pady=(0, 12))

        main_area = tk.Frame(self.root, bg="#e8eef5")
        main_area.pack(side="right", fill="both", expand=True)

        topbar = tk.Frame(main_area, bg="#ffffff", height=48, padx=16)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        self.lbl_titre_page = tk.Label(
            topbar,
            text="P  Monitoring / Gestion du Parking",
            font=("Segoe UI", 12, "bold"),
            bg="#ffffff",
            fg="#0f172a",
        )
        self.lbl_titre_page.pack(side="left", pady=10)

        tk.Label(topbar, text="👤 Admin ▾", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#334155").pack(
            side="right", pady=10
        )
        tk.Label(
            topbar,
            text="Genio",
            font=("Segoe UI", 9, "bold"),
            bg="#e0f2fe",
            fg="#0369a1",
            padx=8,
            pady=2,
        ).pack(side="right", padx=12, pady=12)

        top_grid = tk.Frame(main_area, bg="#e8eef5", padx=12, pady=8)
        top_grid.pack(fill="x")

        cams_row = tk.Frame(top_grid, bg="#e8eef5")
        cams_row.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # --- بطاقة Caméra Entrée ---
        card_e = tk.Frame(cams_row, bg="#ffffff", padx=10, pady=8, highlightbackground="#cbd5e1", highlightthickness=1)
        card_e.pack(side="left", fill="both", expand=True, padx=(0, 8))

        hdr_e = tk.Frame(card_e, bg="#ffffff")
        hdr_e.pack(fill="x")
        tk.Label(hdr_e, text="📹 Caméra Entrée", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0f172a").pack(
            side="left"
        )
        self.lbl_statut_entree = tk.Label(
            hdr_e, text="● En direct", font=("Segoe UI", 8, "bold"), bg="#dcfce7", fg="#15803d", padx=6, pady=1
        )
        self.lbl_statut_entree.pack(side="right")

        cam_box_e = tk.Frame(card_e, bg="#0f172a", width=420, height=215)
        cam_box_e.pack(pady=(6, 4))
        cam_box_e.pack_propagate(False)
        self.lbl_img_entree = tk.Label(cam_box_e, bg="#0f172a")
        self.lbl_img_entree.pack(fill="both", expand=True)

        self.lbl_plaque_badge = tk.Label(
            card_e,
            text=f"✔ Plaque détectée : {self.plaque_courante}",
            font=("Segoe UI", 9, "bold"),
            bg="#16a34a",
            fg="#ffffff",
            pady=4,
        )
        self.lbl_plaque_badge.pack(fill="x", pady=(0, 6))

        bar_e = tk.Frame(card_e, bg="#ffffff")
        bar_e.pack(fill="x")
        tk.Button(
            bar_e,
            text="▶ Caméra Live",
            command=self.demarrer_camera,
            bg="#1d4ed8",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=7,
            pady=5,
            cursor="hand2",
        ).pack(side="left", padx=(0, 3))
        tk.Button(
            bar_e,
            text="🔄 Simuler",
            command=self.simuler_entree,
            bg="#475569",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=7,
            pady=5,
            cursor="hand2",
        ).pack(side="left", padx=(0, 3))
        tk.Button(
            bar_e,
            text="📷 Image",
            command=self.charger_image,
            bg="#0284c7",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=7,
            pady=5,
            cursor="hand2",
        ).pack(side="left")
        tk.Button(
            bar_e,
            text="➜ Pointer Entrée",
            command=self.action_entree,
            bg="#16a34a",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=9,
            pady=5,
            cursor="hand2",
        ).pack(side="right")

        # --- بطاقة Caméra Sortie ---
        card_s = tk.Frame(cams_row, bg="#ffffff", padx=10, pady=8, highlightbackground="#cbd5e1", highlightthickness=1)
        card_s.pack(side="left", fill="both", expand=True)

        hdr_s = tk.Frame(card_s, bg="#ffffff")
        hdr_s.pack(fill="x")
        tk.Label(hdr_s, text="📹 Caméra Sortie", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#0f172a").pack(
            side="left"
        )
        self.lbl_statut_sortie = tk.Label(
            hdr_s, text="● En direct", font=("Segoe UI", 8, "bold"), bg="#dcfce7", fg="#15803d", padx=6, pady=1
        )
        self.lbl_statut_sortie.pack(side="right")

        cam_box_s = tk.Frame(card_s, bg="#0f172a", width=420, height=215)
        cam_box_s.pack(pady=(6, 4))
        cam_box_s.pack_propagate(False)
        self.lbl_img_sortie = tk.Label(cam_box_s, bg="#0f172a")
        self.lbl_img_sortie.pack(fill="both", expand=True)

        plaque_row = tk.Frame(card_s, bg="#ffffff")
        plaque_row.pack(fill="x", pady=(0, 6))
        tk.Label(plaque_row, text="Plaque :", font=("Segoe UI", 8, "bold"), bg="#ffffff", fg="#334155").pack(
            side="left", padx=(0, 6)
        )
        self.entry_plaque = tk.Entry(plaque_row, font=("Segoe UI", 9, "bold"), bg="#f8fafc")
        self.entry_plaque.insert(0, self.plaque_courante)
        self.entry_plaque.pack(side="left", fill="x", expand=True)

        bar_s = tk.Frame(card_s, bg="#ffffff")
        bar_s.pack(fill="x")
        tk.Button(
            bar_s,
            text="⏹ Stop Cam",
            command=self.arreter_camera,
            bg="#64748b",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=7,
            pady=5,
            cursor="hand2",
        ).pack(side="left", padx=(0, 3))
        tk.Button(
            bar_s,
            text="🔄 Simuler",
            command=self.simuler_sortie,
            bg="#475569",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=7,
            pady=5,
            cursor="hand2",
        ).pack(side="left", padx=(0, 3))
        tk.Button(
            bar_s,
            text="📷 Image",
            command=self.charger_image_sortie,
            bg="#0284c7",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=7,
            pady=5,
            cursor="hand2",
        ).pack(side="left")
        tk.Button(
            bar_s,
            text="➜ Pointer Sortie",
            command=self.action_sortie,
            bg="#dc2626",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=9,
            pady=5,
            cursor="hand2",
        ).pack(side="right")

        # --- بطاقة Résumé du Parking + نسبة الإشغال ---
        card_r = tk.Frame(
            top_grid,
            bg="#ffffff",
            padx=12,
            pady=10,
            width=250,
            highlightbackground="#cbd5e1",
            highlightthickness=1,
        )
        card_r.pack(side="right", fill="y")
        card_r.pack_propagate(False)

        tk.Label(card_r, text="Résumé du Parking", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(
            anchor="w", pady=(0, 6)
        )

        self.lbl_val_entrees = self._carte_resume(card_r, "🚗 Véhicules en Entrée", "0", "#16a34a", "#f0fdf4")
        self.lbl_val_sorties = self._carte_resume(card_r, "🚙 Véhicules en Sortie", "0", "#d97706", "#fffbeb")
        self.lbl_val_dispos = self._carte_resume(
            card_r, "🅿 Places Disponibles", f"{self.capacite_parking}/{self.capacite_parking}", "#2563eb", "#eff6ff"
        )

        occ_box = tk.Frame(card_r, bg="#f8fafc", padx=8, pady=6, highlightbackground="#e2e8f0", highlightthickness=1)
        occ_box.pack(fill="x", pady=(6, 0))
        occ_top = tk.Frame(occ_box, bg="#f8fafc")
        occ_top.pack(fill="x")
        tk.Label(occ_top, text="Occupation", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#475569").pack(
            side="left"
        )
        self.lbl_taux_occ = tk.Label(occ_top, text="0%", font=("Segoe UI", 8, "bold"), bg="#f8fafc", fg="#0f172a")
        self.lbl_taux_occ.pack(side="right")

        self.occ_canvas = tk.Canvas(occ_box, height=10, bg="#e2e8f0", highlightthickness=0)
        self.occ_canvas.pack(fill="x", pady=(4, 0))

        # --- جدول Historique des Pointages ---
        card_h = tk.Frame(main_area, bg="#ffffff", padx=12, pady=8, highlightbackground="#cbd5e1", highlightthickness=1)
        card_h.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        top_h = tk.Frame(card_h, bg="#ffffff")
        top_h.pack(fill="x", pady=(0, 6))

        tk.Label(top_h, text="☰ Historique des Pointages", font=("Segoe UI", 10, "bold"), bg="#ffffff", fg="#0f172a").pack(
            side="left"
        )

        tk.Button(
            top_h,
            text="Réinitialiser",
            command=self.reinitialiser_filtres,
            bg="#e2e8f0",
            fg="#1e293b",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
        ).pack(side="right")

        tk.Button(
            top_h,
            text="Filtrer par date",
            command=self.rafraichir_tableau,
            bg="#1d4ed8",
            fg="#ffffff",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            padx=8,
            pady=4,
            cursor="hand2",
        ).pack(side="right", padx=(0, 6))

        self.search_date = tk.Entry(top_h, width=12, font=("Segoe UI", 9))
        self.search_date.pack(side="right", padx=(0, 6))
        self.search_date.bind("<Return>", lambda _e: self.rafraichir_tableau())

        self.search_plaque = tk.Entry(top_h, width=22, font=("Segoe UI", 9))
        self.search_plaque.pack(side="right", padx=(0, 8))
        self.search_plaque.bind("<KeyRelease>", lambda _e: self.rafraichir_tableau())
        tk.Label(top_h, text="🔍", bg="#ffffff", fg="#475569", font=("Segoe UI", 9)).pack(side="right")

        colonnes = ("num", "date", "immatriculation", "entree", "sortie", "duree", "statut", "actions")
        self.tree = ttk.Treeview(card_h, columns=colonnes, show="headings", style="Parking.Treeview", height=6)

        config_cols = {
            "num": ("#", 45),
            "date": ("Date", 105),
            "immatriculation": ("Immatriculations", 180),
            "entree": ("Entrée", 95),
            "sortie": ("Sortie", 95),
            "duree": ("Durée", 95),
            "statut": ("Statut", 105),
            "actions": ("Actions", 95),
        }
        for col, (titre, largeur) in config_cols.items():
            self.tree.heading(col, text=titre)
            self.tree.column(col, width=largeur, anchor="center")

        self.tree.tag_configure("termine", background="#ecfdf5", foreground="#15803d")
        self.tree.tag_configure("en_cours", background="#fefce8", foreground="#b45309")
        self.tree.bind("<<TreeviewSelect>>", self.sur_selection_ligne)
        self.tree.bind("<Double-1>", self.sur_double_clic_ligne)
        self.tree.pack(fill="both", expand=True)

    def _maj_barre_occupation(self, presents: int):
        pct = 0 if self.capacite_parking <= 0 else min(100, max(0, int(round((presents / self.capacite_parking) * 100))))
        self.lbl_taux_occ.configure(text=f"{pct}%")
        self.occ_canvas.update_idletasks()
        w = max(1, self.occ_canvas.winfo_width())
        fill_w = int((w * pct) / 100)
        couleur = "#16a34a" if pct < 60 else ("#d97706" if pct < 85 else "#dc2626")
        self.occ_canvas.delete("all")
        if fill_w > 0:
            self.occ_canvas.create_rectangle(0, 0, fill_w, 10, fill=couleur, width=0)

    def exporter_csv(self):
        chemin = filedialog.asksaveasfilename(
            title="Exporter le rapport CSV",
            defaultextension=".csv",
            initialfile="rapport_parking.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not chemin:
            return
        with open(chemin, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(["#", "Plaque", "Entrée", "Sortie", "Statut"])
            for idx, rec in enumerate(self._records_cache, start=1):
                statut = "En cours" if not rec.get("sortie") else "Terminé"
                writer.writerow([idx, rec.get("plaque", ""), rec.get("entree", ""), rec.get("sortie") or "-", statut])
        messagebox.showinfo("Export CSV", f"Rapport enregistré :\n{chemin}")

    def menu_tableau_de_bord(self):
        self._activer_bouton_menu("Tableau de bord")
        self.lbl_titre_page.configure(text="P  Monitoring / Gestion du Parking")
        self.rafraichir_tout()

    def menu_cameras(self):
        self._activer_bouton_menu("Caméras")
        self.lbl_titre_page.configure(text="P  Caméras Entrée / Sortie")
        self.demarrer_camera()

    def menu_historique(self):
        self._activer_bouton_menu("Historique")
        self.lbl_titre_page.configure(text="P  Historique des Pointages")
        self.rafraichir_tableau()
        self.search_plaque.focus_set()

    def menu_pointages(self):
        self._activer_bouton_menu("Pointages")
        self.lbl_titre_page.configure(text="P  Pointage Entrée / Sortie")
        self.entry_plaque.focus_set()

    def menu_rapports(self):
        self._activer_bouton_menu("Rapports")
        rep = messagebox.askyesno(
            "Rapports du Parking",
            f"Véhicules en Entrée : {self.lbl_val_entrees.cget('text')}\n"
            f"Véhicules en Sortie : {self.lbl_val_sorties.cget('text')}\n"
            f"Places Disponibles : {self.lbl_val_dispos.cget('text')}\n"
            f"Occupation : {self.lbl_taux_occ.cget('text')}\n\n"
            "Voulez-vous exporter ce rapport en CSV ?",
        )
        if rep:
            self.exporter_csv()

    def menu_parametres(self):
        self._activer_bouton_menu("Paramètres")
        nouvelle_cap = simpledialog.askinteger(
            "Paramètres du Parking",
            "Entrez la capacité maximale de places :",
            initialvalue=self.capacite_parking,
            minvalue=1,
            maxvalue=1000,
            parent=self.root,
        )
        if nouvelle_cap:
            self.capacite_parking = nouvelle_cap
            self.rafraichir_tout()
            messagebox.showinfo("Paramètres", f"Capacité mise à jour : {self.capacite_parking} places.")

    def menu_a_propos(self):
        self._activer_bouton_menu("À propos")
        messagebox.showinfo(
            "À propos — Parking Intelligent",
            "Application Smart Parking Tunisie\n"
            "Interface : Tkinter\n"
            "Vision : OpenCV\n"
            "Stockage local : JSON (pointages.json)",
        )

    def _carte_resume(self, parent, titre, valeur, couleur_val, bg_box):
        box = tk.Frame(parent, bg=bg_box, padx=10, pady=6, highlightbackground="#e2e8f0", highlightthickness=1)
        box.pack(fill="x", pady=3)
        tk.Label(box, text=titre, font=("Segoe UI", 8, "bold"), bg=bg_box, fg="#475569").pack(anchor="w")
        lbl = tk.Label(box, text=valeur, font=("Segoe UI", 13, "bold"), bg=bg_box, fg=couleur_val)
        lbl.pack(anchor="w")
        return lbl

    def _to_photo(self, img_cv, max_w, max_h):
        if img_cv is None or img_cv.size == 0:
            return None
        if len(img_cv.shape) == 2:
            rgb = cv2.cvtColor(img_cv, cv2.COLOR_GRAY2RGB)
        else:
            rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        pil_img.thumbnail((max_w, max_h))
        return ImageTk.PhotoImage(pil_img)

    def afficher_scene_entree(self, frame, plaque_texte: str = ""):
        annotated, _, texte_det = detecter_voiture_et_plaque(frame)
        photo = self._to_photo(annotated, 415, 210)
        if photo:
            self.photo_entree = photo
            self.lbl_img_entree.configure(image=photo)

        plaque = formater_plaque_tunisienne(texte_det) or plaque_texte or self.plaque_courante
        if plaque:
            self.plaque_courante = plaque
            self.lbl_plaque_badge.configure(text=f"✔ Plaque détectée : {plaque}")
            self.entry_plaque.delete(0, tk.END)
            self.entry_plaque.insert(0, plaque)

    def afficher_scene_sortie(self, frame, plaque_texte: str = ""):
        annotated, _, texte_det = detecter_voiture_et_plaque(frame)
        photo = self._to_photo(annotated, 415, 210)
        if photo:
            self.photo_sortie = photo
            self.lbl_img_sortie.configure(image=photo)

        plaque = formater_plaque_tunisienne(texte_det) or plaque_texte
        if plaque:
            self.entry_plaque.delete(0, tk.END)
            self.entry_plaque.insert(0, plaque)

    def demarrer_camera(self):
        if self.camera_active:
            return

        self.arreter_camera()
        for idx in (0, 1):
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    self.cap = cap
                    self.camera_active = True
                    self.lbl_statut_entree.configure(text="● Cam Live", bg="#dcfce7", fg="#15803d")
                    self.lbl_statut_sortie.configure(text="● Cam Live", bg="#dcfce7", fg="#15803d")
                    self._boucle_camera()
                    return
            cap.release()

        self.cap = None
        self.simuler_entree()
        self.simuler_sortie()

    def _boucle_camera(self):
        if not self.camera_active or self.cap is None:
            return
        ret, frame = self.cap.read()
        if ret:
            self.afficher_scene_entree(frame)
            self.afficher_scene_sortie(frame)
        self.root.after(50, self._boucle_camera)

    def arreter_camera(self):
        self.camera_active = False
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.lbl_statut_entree.configure(text="● En direct", bg="#e0f2fe", fg="#0369a1")
        self.lbl_statut_sortie.configure(text="● En direct", bg="#e0f2fe", fg="#0369a1")

    def simuler_entree(self):
        self.arreter_camera()
        nouvelle = "789 تونس 0123" if self.plaque_courante != "789 تونس 0123" else "321 تونس 6543"
        self.afficher_scene_entree(generer_scene_entree(nouvelle), nouvelle)

    def simuler_sortie(self):
        self.arreter_camera()
        plaque = formater_plaque_tunisienne(self.entry_plaque.get() or self.plaque_courante)
        self.afficher_scene_sortie(generer_scene_sortie(plaque), plaque)

    def charger_image(self):
        self.arreter_camera()
        chemin = filedialog.askopenfilename(
            title="Choisir une image d'entrée",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")],
        )
        if not chemin:
            return
        frame = cv2.imread(chemin)
        if frame is None:
            messagebox.showerror("Erreur", "Impossible de lire l'image.")
            return
        saisie = simpledialog.askstring(
            "Matricule Entrée",
            "Entrez le matricule (ex: 456 تونس 7890) :",
            initialvalue=self.entry_plaque.get() or "456 تونس 7890",
            parent=self.root,
        )
        self.afficher_scene_entree(frame, saisie or self.plaque_courante)

    def charger_image_sortie(self):
        self.arreter_camera()
        chemin = filedialog.askopenfilename(
            title="Choisir une image de sortie",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")],
        )
        if not chemin:
            return
        frame = cv2.imread(chemin)
        if frame is None:
            messagebox.showerror("Erreur", "Impossible de lire l'image.")
            return
        saisie = simpledialog.askstring(
            "Matricule Sortie",
            "Entrez le matricule à la sortie :",
            initialvalue=self.entry_plaque.get() or self.plaque_courante,
            parent=self.root,
        )
        plaque = formater_plaque_tunisienne(saisie or self.plaque_courante)
        self.afficher_scene_sortie(frame, plaque)

    def sur_selection_ligne(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if len(vals) >= 3 and vals[2]:
            self.entry_plaque.delete(0, tk.END)
            self.entry_plaque.insert(0, vals[2])

    def sur_double_clic_ligne(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if len(vals) < 7:
            return
        _, date_aff, plaque, h_entree, h_sortie, duree, statut, _ = vals
        if statut == "En cours":
            conf = messagebox.askyesno(
                "Sortie véhicule",
                f"Véhicule : {plaque}\nEntrée : {date_aff} à {h_entree}\n\nEnregistrer la sortie maintenant ?",
            )
            if conf:
                self.entry_plaque.delete(0, tk.END)
                self.entry_plaque.insert(0, plaque)
                self.action_sortie()
        else:
            messagebox.showinfo(
                "Détails du Pointage",
                f"Matricule : {plaque}\nDate : {date_aff}\nEntrée : {h_entree}\nSortie : {h_sortie}\nDurée : {duree}\nStatut : {statut}",
            )

    def action_entree(self):
        plaque = formater_plaque_tunisienne(self.entry_plaque.get())
        if not plaque:
            messagebox.showwarning("Attention", "Veuillez saisir un matricule.")
            return
        ok, msg = enregistrer_entree(plaque)
        if ok:
            self.afficher_scene_entree(generer_scene_entree(plaque), plaque)
            messagebox.showinfo("Entrée enregistrée", msg)
            self.rafraichir_tout()
        else:
            messagebox.showerror("Erreur", msg)

    def action_sortie(self):
        plaque = formater_plaque_tunisienne(self.entry_plaque.get())
        if not plaque:
            messagebox.showwarning("Attention", "Veuillez saisir un matricule.")
            return
        ok, msg = enregistrer_sortie(plaque)
        if ok:
            self.afficher_scene_sortie(generer_scene_sortie(plaque), plaque)
            messagebox.showinfo("Sortie enregistrée", msg)
            self.rafraichir_tout()
        else:
            messagebox.showerror("Erreur", msg)

    def reinitialiser_filtres(self):
        self.search_plaque.delete(0, tk.END)
        self.search_date.delete(0, tk.END)
        self.rafraichir_tableau()

    def rafraichir_tableau(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        filtre_plaque = self.search_plaque.get().strip() or None
        filtre_date = self.search_date.get().strip() or None
        records = lister_pointages(plaque=filtre_plaque, date_str=filtre_date)
        self._records_cache = list(records)

        for idx, rec in enumerate(records, start=1):
            plaque = rec.get("plaque", "")
            entree_raw = rec.get("entree", "")
            sortie_raw = rec.get("sortie") or ""

            date_aff = "-"
            if len(entree_raw) >= 10:
                try:
                    d_obj = datetime.date.fromisoformat(entree_raw[:10])
                    date_aff = d_obj.strftime("%d/%m/%Y")
                except ValueError:
                    date_aff = entree_raw[:10]

            heure_entree = entree_raw[11:19] if len(entree_raw) >= 19 else entree_raw or "-"
            heure_sortie = sortie_raw[11:19] if len(sortie_raw) >= 19 else "-"
            est_en_cours = not bool(sortie_raw)
            statut = "En cours" if est_en_cours else "Terminé"

            duree = "-"
            if entree_raw and sortie_raw:
                try:
                    t1 = datetime.datetime.fromisoformat(entree_raw)
                    t2 = datetime.datetime.fromisoformat(sortie_raw)
                    minutes = max(0, int((t2 - t1).total_seconds() // 60))
                    heures, mins = divmod(minutes, 60)
                    duree = f"{heures}h {mins:02d}min" if heures else f"{mins} min"
                except ValueError:
                    duree = "-"

            tag = "en_cours" if est_en_cours else "termine"
            self.tree.insert(
                "",
                "end",
                values=(idx, date_aff, plaque, heure_entree, heure_sortie, duree, statut, "👁  ✎"),
                tags=(tag,),
            )

    def rafraichir_tout(self):
        resume = get_resume_parking()
        if isinstance(resume, (tuple, list)) and len(resume) >= 3:
            total_entrees, total_sorties = resume[0], resume[1]
        elif isinstance(resume, dict):
            total_entrees = resume.get("entrees", 0)
            total_sorties = resume.get("sorties", 0)
        else:
            total_entrees, total_sorties = 0, 0

        presents = max(0, total_entrees - total_sorties)
        dispos = max(0, self.capacite_parking - presents)

        self.lbl_val_entrees.configure(text=str(total_entrees))
        self.lbl_val_sorties.configure(text=str(total_sorties))
        self.lbl_val_dispos.configure(text=f"{dispos}/{self.capacite_parking}")
        self._maj_barre_occupation(presents)
        self.rafraichir_tableau()

    def quitter_app(self):
        self.arreter_camera()
        self.root.destroy()


if __name__ == "__main__":
    app_root = tk.Tk()
    app = SmartParkingApp(app_root)
    app_root.mainloop()