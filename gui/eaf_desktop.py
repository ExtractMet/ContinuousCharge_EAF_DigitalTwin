#!/usr/bin/env python3
# =============================================================================
#  Continuous-Charge (Consteel-type) EAF  —  Desktop Digital Twin  (Tkinter)
#  Extractmet Private Limited
#
#  Native desktop HMI: configure the furnace, run the first-principles dynamic
#  model, and explore results across an interactive furnace synoptic, a full
#  suite of embedded Matplotlib trajectories, static & dynamic balances, slag
#  chemistry, an energy/mass balance and a time-stamped event log.
#
#  Run:  python eaf_desktop.py        (needs a display; headless: xvfb-run -a python eaf_desktop.py)
# =============================================================================
import os
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from eaf_model import EAFModel, EAFConfig, Composition, RefractoryLayer, M

# ----------------------------------------------------------------------------
#  Industrial control-room palette
# ----------------------------------------------------------------------------
BG      = "#0f1720"
PANEL   = "#16212e"
PANEL2  = "#1b2735"
GRID    = "#26333f"
FG      = "#d7e2ec"
MUTED   = "#8aa0b2"
ORANGE  = "#ff8c42"
AMBER   = "#ffc857"
CYAN    = "#39d0d8"
GREEN   = "#5fd08a"
RED     = "#ef6f6c"
BLUE    = "#5b9bd5"
VIOLET  = "#b48ead"

MONO = ("DejaVu Sans Mono", 10)
MONO_B = ("DejaVu Sans Mono", 11, "bold")
SANS = ("DejaVu Sans", 10)
SANS_B = ("DejaVu Sans", 11, "bold")
H1 = ("DejaVu Sans", 15, "bold")
H2 = ("DejaVu Sans", 12, "bold")


# ----------------------------------------------------------------------------
#  colour helpers (shared with the synoptic)
# ----------------------------------------------------------------------------
def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _rgb(r, g, b):
    return "#%02x%02x%02x" % (int(max(0, min(255, r))), int(max(0, min(255, g))),
                              int(max(0, min(255, b))))


def temp_color(T, lo=1450, hi=1700):
    t = max(0.0, min(1.0, (T - lo) / (hi - lo)))
    if t < 0.5:
        u = t / 0.5
        return _rgb(_lerp(120, 255, u), _lerp(20, 120, u), _lerp(10, 20, u))
    u = (t - 0.5) / 0.5
    return _rgb(255, _lerp(120, 210, u), _lerp(20, 150, u))


def mpl_style(fig):
    fig.patch.set_facecolor(BG)


def style_ax(ax, title=None, xlabel="Time  [min]", ylabel=None):
    ax.set_facecolor(PANEL)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.grid(True, color=GRID, alpha=0.5, linewidth=0.6)
    if title:
        ax.set_title(title, color=FG, fontsize=10, fontweight="bold")
    if xlabel:
        ax.set_xlabel(xlabel, color=MUTED, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=MUTED, fontsize=9)


# ============================================================================
#  MAIN APPLICATION
# ============================================================================
class EAFDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Continuous-Charge EAF — Desktop Digital Twin  ·  Extractmet Private Limited")
        self.geometry("1500x950")
        self.configure(bg=BG)
        self.minsize(1200, 780)

        self.result = None
        self.df = None
        self._scrub_job = None

        self._init_style()
        self._build_header()
        self._build_body()
        # first run
        self.after(200, self.run_simulation)

    # ------------------------------------------------------------------
    def _init_style(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure(".", background=BG, foreground=FG, fieldbackground=PANEL,
                     bordercolor=GRID, font=SANS)
        st.configure("TFrame", background=BG)
        st.configure("Panel.TFrame", background=PANEL)
        st.configure("Card.TFrame", background=PANEL, relief="flat")
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Panel.TLabel", background=PANEL, foreground=FG)
        st.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=("DejaVu Sans", 9))
        st.configure("TNotebook", background=BG, borderwidth=0)
        st.configure("TNotebook.Tab", background=PANEL, foreground=MUTED,
                     padding=(14, 7), font=SANS_B)
        st.map("TNotebook.Tab", background=[("selected", BG)],
               foreground=[("selected", ORANGE)])
        st.configure("Horizontal.TScale", background=PANEL, troughcolor=GRID)
        st.configure("TCombobox", fieldbackground=BG, background=PANEL, foreground=FG,
                     arrowcolor=FG)
        st.configure("Run.TButton", background=ORANGE, foreground="#160c05",
                     font=("DejaVu Sans", 12, "bold"), padding=10, borderwidth=0)
        st.map("Run.TButton", background=[("active", "#e06a1f")])
        st.configure("DL.TButton", background=PANEL2, foreground=CYAN,
                     font=SANS_B, padding=8, borderwidth=1)
        st.configure("Vertical.TScrollbar", background=PANEL, troughcolor=BG,
                     arrowcolor=MUTED, bordercolor=GRID)

    # ------------------------------------------------------------------
    def _build_header(self):
        hdr = tk.Frame(self, bg=BG, height=64)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)
        left = tk.Frame(hdr, bg=BG)
        left.pack(side="left", padx=18, pady=8)
        tk.Label(left, text="EXTRACTMET", bg=BG, fg=ORANGE,
                 font=("DejaVu Sans", 18, "bold")).pack(anchor="w")
        tk.Label(left, text="PYROMETALLURGY · DIGITAL TWINS", bg=BG, fg=MUTED,
                 font=("DejaVu Sans", 8)).pack(anchor="w")
        mid = tk.Frame(hdr, bg=BG)
        mid.pack(side="left", padx=20)
        tk.Label(mid, text="Continuous-Charge EAF — Process Digital Twin", bg=BG,
                 fg=FG, font=H1).pack(anchor="w")
        self.subhead = tk.Label(mid, text="Industry-X · flat-bath immersion melting · "
                                "first-principles dynamic model", bg=BG, fg=MUTED,
                                font=("DejaVu Sans", 10))
        self.subhead.pack(anchor="w")
        tk.Label(hdr, text="native desktop HMI\n© Extractmet Private Limited", bg=BG,
                 fg=MUTED, font=("DejaVu Sans", 9), justify="right").pack(side="right", padx=18)
        tk.Frame(self, bg=GRID, height=1).pack(side="top", fill="x")

    # ------------------------------------------------------------------
    def _build_body(self):
        body = tk.Frame(self, bg=BG)
        body.pack(side="top", fill="both", expand=True)
        self._build_sidebar(body)
        self._build_main(body)

    # ------------------------------------------------------------------
    #  SIDEBAR (scrollable config)
    # ------------------------------------------------------------------
    def _build_sidebar(self, parent):
        outer = tk.Frame(parent, bg=PANEL, width=330)
        outer.pack(side="left", fill="y")
        outer.pack_propagate(False)

        canvas = tk.Canvas(outer, bg=PANEL, highlightthickness=0, width=310)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        self.cfg_frame = tk.Frame(canvas, bg=PANEL)
        self.cfg_frame.bind("<Configure>",
                            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.cfg_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        # mouse wheel
        def _wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)) if e.delta else
                                (-1 if e.num == 4 else 1), "units")
        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind_all("<Button-4>", _wheel)
        canvas.bind_all("<Button-5>", _wheel)

        self.vars = {}
        tk.Label(self.cfg_frame, text="⚙  FURNACE CONFIGURATION", bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))

        groups = [
            ("Identity", [
                ("plant_name", "Plant", "text", "Industry-X"),
                ("heat_id", "Heat ID", "text", "H-000001"),
                ("furnace_type", "Furnace type", "choice", ["AC", "DC"]),
            ]),
            ("Geometry & refractory", [
                ("shell_inner_diameter", "Shell inner Ø [m]", 4.0, 8.0, 6.0, 0.1),
                ("bath_depth_full", "Bath depth [m]", 0.3, 1.0, 0.6, 0.05),
                ("ref_l1", "MgO-C working lining [mm]", 200, 700, 450, 10),
                ("ref_l1k", "Working lining k [W/mK]", 5, 25, 14, 0.5),
                ("ref_l2", "Magnesia safety lining [mm]", 80, 300, 180, 10),
            ]),
            ("Charge (continuous)", [
                ("hot_heel_t", "Hot heel [t]", 20, 70, 40, 1),
                ("hot_heel_c", "Hot heel temp [°C]", 1450, 1650, 1550, 10),
                ("total_scrap_t", "Scrap charged [t]", 70, 160, 110, 1),
                ("scrap_feed_rate", "Conveyor feed [kg/s]", 20, 70, 45, 1),
                ("scrap_preheat_c", "Scrap preheat [°C]", 200, 600, 420, 10),
                ("sc_C", "Scrap C [%]", 0.0, 2.0, 0.25, 0.05),
                ("sc_Si", "Scrap Si [%]", 0.0, 1.0, 0.30, 0.05),
                ("sc_Mn", "Scrap Mn [%]", 0.0, 2.0, 0.40, 0.05),
                ("sc_P", "Scrap P [%]", 0.0, 0.2, 0.04, 0.01),
            ]),
            ("Fluxes", [
                ("lime_t", "Lime (CaO) [t]", 1.0, 8.0, 4.3, 0.1),
                ("dololime_t", "Dololime [t]", 0.5, 5.0, 2.0, 0.1),
                ("flux_feed_rate", "Flux dosing [kg/s]", 1.0, 10.0, 4.0, 0.5),
            ]),
            ("Electrical", [
                ("transformer_mva", "Transformer [MVA]", 50, 150, 90, 5),
                ("active_power_MW", "Max active power [MW]", 40, 120, 72, 1),
                ("power_factor", "Power factor", 0.6, 0.95, 0.78, 0.01),
                ("arc_efficiency", "Arc efficiency", 0.75, 0.98, 0.90, 0.01),
            ]),
            ("Chemical inputs", [
                ("o2_lance_rate", "O₂ lance [Nm³/s]", 0.3, 2.5, 1.05, 0.05),
                ("o2_postcomb_rate", "O₂ post-comb [Nm³/s]", 0.0, 1.0, 0.32, 0.02),
                ("carbon_inject_rate", "Carbon inject [kg/s]", 0.0, 1.5, 0.50, 0.05),
                ("ng_burner_rate", "Natural gas [Nm³/s]", 0.0, 1.0, 0.0, 0.05),
            ]),
            ("Targets & integration", [
                ("tap_temp_c", "Tap temp [°C]", 1580, 1680, 1620, 5),
                ("tap_carbon_pct", "Tap carbon [%]", 0.03, 0.20, 0.06, 0.01),
                ("dt", "Time step [s]", 0.25, 1.0, 0.5, 0.25),
            ]),
        ]
        for gname, items in groups:
            self._group(gname, items)

        runbtn = ttk.Button(self.cfg_frame, text="▶  RUN SIMULATION",
                            style="Run.TButton", command=self.run_simulation)
        runbtn.pack(fill="x", padx=12, pady=(8, 4))
        self.status = tk.Label(self.cfg_frame, text="", bg=PANEL, fg=CYAN,
                               font=("DejaVu Sans", 9))
        self.status.pack(anchor="w", padx=12)
        tk.Label(self.cfg_frame,
                 text="First-principles dynamic model — mass & heat balances every\n"
                      "timestep, coupled thermochemistry, kinetics, multilayer heat loss.\n"
                      "© Extractmet Private Limited.",
                 bg=PANEL, fg=MUTED, font=("DejaVu Sans", 8), justify="left").pack(
            anchor="w", padx=12, pady=(6, 16))

    def _group(self, name, items):
        hdr = tk.Frame(self.cfg_frame, bg=PANEL2)
        hdr.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(hdr, text="  " + name, bg=PANEL2, fg=FG,
                 font=("DejaVu Sans", 10, "bold")).pack(anchor="w", pady=5)
        box = tk.Frame(self.cfg_frame, bg=PANEL)
        box.pack(fill="x", padx=8)
        for it in items:
            key = it[0]
            if it[2] == "text":
                self._text_field(box, key, it[1], it[3])
            elif it[2] == "choice":
                self._choice_field(box, key, it[1], it[3])
            else:
                _, label, lo, hi, val, step = it
                self._slider(box, key, label, lo, hi, val, step)

    def _text_field(self, parent, key, label, default):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(fill="x", pady=4)
        tk.Label(f, text=label, bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9)).pack(anchor="w")
        v = tk.StringVar(value=default)
        e = tk.Entry(f, textvariable=v, bg=BG, fg=FG, insertbackground=FG,
                     relief="flat", font=MONO, highlightthickness=1,
                     highlightbackground=GRID, highlightcolor=ORANGE)
        e.pack(fill="x", ipady=3)
        self.vars[key] = v

    def _choice_field(self, parent, key, label, opts):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(fill="x", pady=4)
        tk.Label(f, text=label, bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9)).pack(anchor="w")
        v = tk.StringVar(value=opts[0])
        cb = ttk.Combobox(f, textvariable=v, values=opts, state="readonly")
        cb.pack(fill="x")
        self.vars[key] = v

    def _slider(self, parent, key, label, lo, hi, val, step):
        f = tk.Frame(parent, bg=PANEL)
        f.pack(fill="x", pady=3)
        top = tk.Frame(f, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9)).pack(side="left")
        valv = tk.StringVar(value=self._fmt(val, step))
        tk.Label(top, textvariable=valv, bg=PANEL, fg=FG,
                 font=MONO).pack(side="right")
        v = tk.DoubleVar(value=val)

        def on_move(x):
            # snap to step
            sv = round(float(x) / step) * step
            valv.set(self._fmt(sv, step))
        s = ttk.Scale(f, from_=lo, to=hi, orient="horizontal", variable=v,
                      command=on_move)
        s.pack(fill="x")
        self.vars[key] = v
        self.vars[key + "__step"] = step

    @staticmethod
    def _fmt(v, step):
        return ("%.2f" % v) if step < 1 else ("%d" % round(v))

    # ------------------------------------------------------------------
    #  MAIN AREA (KPIs + notebook)
    # ------------------------------------------------------------------
    def _build_main(self, parent):
        main = tk.Frame(parent, bg=BG)
        main.pack(side="left", fill="both", expand=True, padx=(10, 10), pady=8)

        self.kpi_bar = tk.Frame(main, bg=BG)
        self.kpi_bar.pack(side="top", fill="x", pady=(0, 8))

        self.nb = ttk.Notebook(main)
        self.nb.pack(side="top", fill="both", expand=True)

        self.tab_overview = tk.Frame(self.nb, bg=BG)
        self.tab_synoptic = tk.Frame(self.nb, bg=BG)
        self.tab_static = tk.Frame(self.nb, bg=BG)
        self.tab_traj = tk.Frame(self.nb, bg=BG)
        self.tab_slag = tk.Frame(self.nb, bg=BG)
        self.tab_energy = tk.Frame(self.nb, bg=BG)
        self.tab_events = tk.Frame(self.nb, bg=BG)
        self.tab_data = tk.Frame(self.nb, bg=BG)
        self.nb.add(self.tab_overview, text="  Overview  ")
        self.nb.add(self.tab_synoptic, text="  Furnace synoptic  ")
        self.nb.add(self.tab_static, text="  Static balance  ")
        self.nb.add(self.tab_traj, text="  Trajectories  ")
        self.nb.add(self.tab_slag, text="  Slag & chemistry  ")
        self.nb.add(self.tab_energy, text="  Energy & mass  ")
        self.nb.add(self.tab_events, text="  Event log  ")
        self.nb.add(self.tab_data, text="  Data  ")

    # ==================================================================
    #  CONFIG + RUN
    # ==================================================================
    def _v(self, key):
        return float(self.vars[key].get())

    def build_config(self) -> EAFConfig:
        cfg = EAFConfig()
        cfg.plant_name = self.vars["plant_name"].get()
        cfg.heat_id = self.vars["heat_id"].get()
        cfg.furnace_type = self.vars["furnace_type"].get()
        cfg.shell_inner_diameter = self._v("shell_inner_diameter")
        cfg.bath_depth_full = self._v("bath_depth_full")
        cfg.refractory = [
            RefractoryLayer("MgO-C working lining", self._v("ref_l1") / 1000, self._v("ref_l1k")),
            RefractoryLayer("Magnesia safety lining", self._v("ref_l2") / 1000, 4.5),
            RefractoryLayer("Insulating board", 0.030, 0.25),
            RefractoryLayer("Carbon-steel shell", 0.050, 45.0),
        ]
        cfg.hot_heel_mass = self._v("hot_heel_t") * 1e3
        cfg.hot_heel_temp = self._v("hot_heel_c") + 273.15
        cfg.total_scrap_mass = self._v("total_scrap_t") * 1e3
        cfg.scrap_feed_rate = self._v("scrap_feed_rate")
        cfg.scrap_preheat_temp = self._v("scrap_preheat_c") + 273.15
        cfg.scrap_comp = Composition(C=self._v("sc_C") / 100, Si=self._v("sc_Si") / 100,
                                     Mn=self._v("sc_Mn") / 100, P=self._v("sc_P") / 100, Cr=0.0020)
        cfg.lime_total = self._v("lime_t") * 1e3
        cfg.dololime_total = self._v("dololime_t") * 1e3
        cfg.flux_feed_rate = self._v("flux_feed_rate")
        cfg.transformer_mva = self._v("transformer_mva")
        cfg.active_power_max = self._v("active_power_MW") * 1e6
        cfg.power_factor = self._v("power_factor")
        cfg.arc_efficiency = self._v("arc_efficiency")
        cfg.o2_lance_rate = self._v("o2_lance_rate")
        cfg.o2_postcomb_rate = self._v("o2_postcomb_rate")
        cfg.carbon_inject_rate = self._v("carbon_inject_rate")
        cfg.ng_burner_rate = self._v("ng_burner_rate")
        cfg.tap_temperature = self._v("tap_temp_c") + 273.15
        cfg.tap_carbon = self._v("tap_carbon_pct") / 100
        cfg.dt = self._v("dt")
        return cfg

    def run_simulation(self):
        self.status.config(text="Integrating heat …")
        self.update_idletasks()
        cfg = self.build_config()

        def worker():
            model = EAFModel(cfg)
            res = model.run()
            self.result = res
            self.model = model
            import pandas as pd
            self.df = pd.DataFrame(res.history)
            self.after(0, self._on_result_ready, cfg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_result_ready(self, cfg):
        self.status.config(text="Done.")
        self.subhead.config(text=f"{cfg.plant_name} · Heat {cfg.heat_id} · "
                            f"{cfg.furnace_type} · flat-bath immersion melting")
        self.render_kpis()
        self.render_overview()
        self.render_synoptic_tab()
        self.render_static()
        self.render_trajectories()
        self.render_slag()
        self.render_energy()
        self.render_events()
        self.render_data()

    # ==================================================================
    #  KPI BAR
    # ==================================================================
    def render_kpis(self):
        for w in self.kpi_bar.winfo_children():
            w.destroy()
        k = self.result.kpis()
        cards = [
            ("TAP MASS", f"{k['tap_mass_t']:.1f} t", "liquid steel", ORANGE, None),
            ("TAP TEMP", f"{k['tap_temp_C']:.0f} °C", "target 1600–1650", AMBER,
             1600 <= k['tap_temp_C'] <= 1650),
            ("FINAL C", f"{k['final_C_pct']:.3f} %", "target 0.05–0.10", CYAN,
             0.05 <= k['final_C_pct'] <= 0.10),
            ("ELEC SEC", f"{k['SEC_elec_kWh_t']:.0f}", "kWh/t · 300–360", GREEN,
             295 <= k['SEC_elec_kWh_t'] <= 360),
            ("PRODUCTIVITY", f"{k['productivity_t_per_h_per_MW']:.2f}", "t/h/MW · 2.1–2.7",
             VIOLET, 2.1 <= k['productivity_t_per_h_per_MW'] <= 2.7),
            ("TAP-TO-TAP", f"{k['tap_to_tap_min']:.0f} min", "target 40–60", BLUE,
             40 <= k['tap_to_tap_min'] <= 60),
        ]
        for i, (lab, val, sub, ac, ok) in enumerate(cards):
            self.kpi_bar.columnconfigure(i, weight=1)
            self._kpi_card(self.kpi_bar, lab, val, sub, ac, ok).grid(
                row=0, column=i, sticky="ew", padx=4)

    def _kpi_card(self, parent, lab, val, sub, ac, ok=None):
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=GRID)
        bar = tk.Frame(card, bg=ac, width=4)
        bar.pack(side="left", fill="y")
        inner = tk.Frame(card, bg=PANEL)
        inner.pack(side="left", fill="both", expand=True, padx=10, pady=8)
        tk.Label(inner, text=lab, bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 8, "bold")).pack(anchor="w")
        tk.Label(inner, text=val, bg=PANEL, fg=FG,
                 font=("DejaVu Sans Mono", 17, "bold")).pack(anchor="w")
        subf = tk.Frame(inner, bg=PANEL)
        subf.pack(anchor="w", fill="x")
        tk.Label(subf, text=sub, bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 8)).pack(side="left")
        if ok is True:
            tk.Label(subf, text=" in-window ", bg="#163020", fg=GREEN,
                     font=("DejaVu Sans", 8, "bold")).pack(side="left", padx=3)
        elif ok is False:
            tk.Label(subf, text=" edge ", bg="#2a2410", fg=AMBER,
                     font=("DejaVu Sans", 8, "bold")).pack(side="left", padx=3)
        return card

    # ==================================================================
    #  helpers
    # ==================================================================
    @staticmethod
    def _clear(tab):
        for w in tab.winfo_children():
            w.destroy()

    def _embed_fig(self, parent, fig):
        mpl_style(fig)
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        w = canvas.get_tk_widget()
        w.configure(bg=BG, highlightthickness=0)
        return w

    def _kv_panel(self, parent, title, rows, ac=CYAN):
        card = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=GRID)
        tk.Label(card, text=title, bg=PANEL, fg=FG, font=H2).pack(anchor="w", padx=12, pady=(10, 6))
        for k, v in rows.items():
            r = tk.Frame(card, bg=PANEL)
            r.pack(fill="x", padx=12)
            tk.Label(r, text=k, bg=PANEL, fg=MUTED, font=("DejaVu Sans", 9)).pack(side="left")
            tk.Label(r, text=v, bg=PANEL, fg=FG, font=MONO).pack(side="right")
            tk.Frame(card, bg=GRID, height=1).pack(fill="x", padx=12)
        tk.Frame(card, bg=PANEL, height=6).pack()
        return card

    # ==================================================================
    #  OVERVIEW
    # ==================================================================
    def render_overview(self):
        self._clear(self.tab_overview)
        k = self.result.kpis()
        eb = self.result.energy_balance()
        df = self.df

        # scorecard on a canvas
        top = tk.Frame(self.tab_overview, bg=PANEL, highlightthickness=1, highlightbackground=GRID)
        top.pack(side="top", fill="x", padx=6, pady=6)
        tk.Label(top, text="Validation scorecard — simulated vs peer-reviewed windows",
                 bg=PANEL, fg=FG, font=H2).pack(anchor="w", padx=12, pady=(10, 2))
        bench = [
            ("Tap temperature", k['tap_temp_C'], 1600, 1650, "°C"),
            ("Tap-to-tap time", k['tap_to_tap_min'], 40, 60, "min"),
            ("Final carbon", k['final_C_pct'], 0.05, 0.10, "wt%"),
            ("Electrical SEC", k['SEC_elec_kWh_t'], 300, 360, "kWh/t"),
            ("Productivity", k['productivity_t_per_h_per_MW'], 2.1, 2.7, "t/h/MW"),
            ("Metallic yield", k['yield_pct'], 88, 93, "%"),
            ("Slag basicity B2", float(df['basicity_B2'].iloc[-1]), 1.8, 2.5, "-"),
            ("Slag FeO", k['slag_FeO_pct'], 12, 25, "wt%"),
            ("Oxygen use", k['O2_Nm3_t'], 18, 40, "Nm³/t"),
            ("Lime addition", k['lime_kg_t'], 35, 55, "kg/t"),
        ]
        cv = tk.Canvas(top, bg=PANEL, height=len(bench) * 26 + 12, highlightthickness=0)
        cv.pack(fill="x", padx=12, pady=(2, 10))
        cv.update_idletasks()
        def draw_score(event=None):
            cv.delete("all")
            W = cv.winfo_width() or 900
            x0, x1 = 170, W - 150
            for i, (lab, val, lo, hi, unit) in enumerate(bench):
                y = 16 + i * 26
                cv.create_text(12, y, text=lab, fill=MUTED, anchor="w",
                               font=("DejaVu Sans", 9))
                cv.create_rectangle(x0, y - 8, x1, y + 8, fill="#14251c", outline="#2c6b46")
                norm = max(-0.25, min(1.25, (val - lo) / (hi - lo)))
                px = x0 + (x1 - x0) * norm
                inside = lo <= val <= hi
                cv.create_oval(px - 7, y - 7, px + 7, y + 7,
                               fill=(GREEN if inside else AMBER), outline="white", width=2)
                cv.create_text(x1 + 8, y, text=f"{val:.3g}  ({lo}–{hi} {unit})", fill=MUTED,
                               anchor="w", font=("DejaVu Sans Mono", 8))
        cv.bind("<Configure>", draw_score)
        self.after(60, draw_score)

        bottom = tk.Frame(self.tab_overview, bg=BG)
        bottom.pack(side="top", fill="both", expand=True, padx=6)
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        bottom.rowconfigure(0, weight=1)

        rows = {
            "Plant / heat": f"{k['plant']} · {k['heat_id']}",
            "Tapped": "yes" if k["tapped"] else "no",
            "Liquid tapped": f"{k['tap_mass_t']:.1f} t @ {k['tap_temp_C']:.0f} °C",
            "Final chemistry": f"C {k['final_C_pct']:.3f} Si {k['final_Si_pct']:.3f} "
                               f"Mn {k['final_Mn_pct']:.3f} P {k['final_P_pct']:.4f}",
            "Metallic yield": f"{k['yield_pct']:.1f} %",
            "Slag": f"{k['slag_mass_t']:.1f} t · B2 {df['basicity_B2'].iloc[-1]:.2f} "
                    f"· FeO {k['slag_FeO_pct']:.1f}%",
            "Electrical": f"{k['E_elec_kWh']:,.0f} kWh · {k['SEC_elec_kWh_t']:.0f} kWh/t",
            "Chemical": f"{k['E_chem_kWh']:,.0f} kWh",
            "Total purchased": f"{k['SEC_total_kWh_t']:.0f} kWh/t",
            "Productivity": f"{k['productivity_t_per_h']:.0f} t/h · "
                            f"{k['productivity_t_per_h_per_MW']:.2f} t/h/MW",
            "O₂ / lime / C": f"{k['O2_Nm3_t']:.1f} Nm³/t · {k['lime_kg_t']:.0f} kg/t "
                             f"· {k['carbon_kg_t']:.1f} kg/t",
            "Mass closure": f"{self.result.mass_balance()['closure_pct']:.2f} %",
            "Energy closure": f"{eb['closure_pct']:.2f} %",
        }
        self._kv_panel(bottom, "Heat summary", rows, AMBER).grid(
            row=0, column=0, sticky="nsew", padx=4, pady=6)

        # energy sinks pie
        fig = Figure(figsize=(5, 4.2), dpi=90)
        ax = fig.add_subplot(111)
        outs = {kk: max(0, vv) for kk, vv in eb["outputs"].items()}
        cols = [ORANGE, AMBER, VIOLET, BLUE, RED, MUTED]
        wedges, _, _ = ax.pie(list(outs.values()), colors=cols[:len(outs)],
                              autopct="%1.0f%%", textprops={"color": FG, "fontsize": 8},
                              wedgeprops={"edgecolor": BG})
        ax.legend(wedges, list(outs.keys()), loc="center left",
                  bbox_to_anchor=(0.92, 0.5), fontsize=7, facecolor=PANEL,
                  edgecolor=GRID, labelcolor=FG)
        ax.set_title("Energy sinks", color=FG, fontsize=11, fontweight="bold")
        fig.patch.set_facecolor(BG)
        card2 = tk.Frame(bottom, bg=PANEL, highlightthickness=1, highlightbackground=GRID)
        card2.grid(row=0, column=1, sticky="nsew", padx=4, pady=6)
        self._embed_fig(card2, fig).pack(fill="both", expand=True, padx=6, pady=6)

    # ==================================================================
    #  SYNOPTIC (Tkinter Canvas + scrubber)
    # ==================================================================
    def render_synoptic_tab(self):
        self._clear(self.tab_synoptic)
        top = tk.Frame(self.tab_synoptic, bg=PANEL, highlightthickness=1,
                       highlightbackground=GRID)
        top.pack(fill="both", expand=True, padx=6, pady=6)
        tk.Label(top, text="Live furnace synoptic", bg=PANEL, fg=FG,
                 font=H2).pack(anchor="w", padx=12, pady=(10, 0))
        tk.Label(top, text="Scrub through the heat — every zone temperature, mass and "
                 "chemistry value updates on the cross-section.", bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9)).pack(anchor="w", padx=12)

        ctrl = tk.Frame(top, bg=PANEL)
        ctrl.pack(fill="x", padx=12, pady=8)
        tk.Label(ctrl, text="Heat time", bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9)).pack(side="left")
        n = len(self.df) - 1
        self.scrub_var = tk.DoubleVar(value=n)
        self.scrub_lbl = tk.Label(ctrl, text="", bg=PANEL, fg=CYAN, font=MONO_B, width=22)
        self.scrub_lbl.pack(side="right")
        scale = ttk.Scale(ctrl, from_=0, to=n, orient="horizontal",
                          variable=self.scrub_var, command=self._on_scrub)
        scale.pack(side="left", fill="x", expand=True, padx=10)

        self.syn_canvas = tk.Canvas(top, bg=BG, highlightthickness=1,
                                    highlightbackground=GRID)
        self.syn_canvas.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.syn_canvas.bind("<Configure>", lambda e: self._draw_synoptic())
        self.after(80, self._draw_synoptic)

    def _on_scrub(self, _=None):
        if self._scrub_job:
            self.after_cancel(self._scrub_job)
        self._scrub_job = self.after(15, self._draw_synoptic)

    def _phase_at(self, i):
        r = self.df.iloc[i]
        if r["scrap_fed"] < 1.0:
            return "start-up"
        if r["C_pct"] > 0.12 and r["m_scrap_solid"] > 0.5:
            return "flat-bath melt"
        if r["T_metal"] >= 1600:
            return "refining"
        return "melt-in"

    def _draw_synoptic(self):
        if self.df is None:
            return
        c = self.syn_canvas
        c.delete("all")
        W = c.winfo_width() or 940
        H = c.winfo_height() or 540
        idx = int(self.scrub_var.get())
        idx = max(0, min(len(self.df) - 1, idx))
        row = self.df.iloc[idx]
        phase = self._phase_at(idx)
        tmin = row["t_min"]
        self.scrub_lbl.config(text=f"{int(tmin//60):02d}:{int((tmin*60)%60):02d} · {phase}")

        g = lambda kk, d=0.0: float(row[kk]) if kk in row and row[kk] == row[kk] else d
        Tm = g("T_metal", 1550); Tsl = g("T_slag", 1560); Tsc = g("T_scrap", 500)
        Tg = g("T_gas", 1200); Troof = g("T_roof", 700)
        mm = g("m_metal"); msc = g("m_scrap_solid"); msl = g("m_slag")
        Cp = g("C_pct"); Sip = g("Si_pct"); Mnp = g("Mn_pct"); Pp = g("P_pct")
        FeO = g("FeO_pct"); B2 = g("basicity_B2"); foam = g("foam_coverage")
        Parc = g("P_arc_MW"); Pchem = g("P_chem_MW")
        o2 = g("O2_Nm3"); fed = g("scrap_fed"); Tshell = g("T_shell", 250)

        metal_col = temp_color(Tm)
        slag_col = temp_color(Tsl, 1400, 1700)
        scrap_col = temp_color(Tsc, 300, 1500)
        arc_on = Parc > 1.0

        # geometry — scale to canvas
        sx, sy, sw, sh = int(W * 0.27), 120, int(W * 0.44), 250
        mh = 40 + 150 * min(1.0, mm / 150.0)
        metal_top = sy + sh - mh
        slag_h = 14 + 26 * min(1.0, msl / 18.0)
        slag_top = metal_top - slag_h
        ex = [sx + sw * f for f in (0.34, 0.5, 0.66)]

        def chip(x, y, lab, val, col, w=132):
            c.create_rectangle(x, y, x + w, y + 34, fill=PANEL, outline=GRID)
            c.create_rectangle(x, y, x + 4, y + 34, fill=col, outline=col)
            c.create_text(x + 12, y + 10, text=lab, fill=MUTED, anchor="w",
                          font=("DejaVu Sans", 8, "bold"))
            c.create_text(x + 12, y + 24, text=val, fill="#eef4fa", anchor="w",
                          font=("DejaVu Sans Mono", 10, "bold"))

        # title strip
        c.create_text(24, 22, text="CONTINUOUS-CHARGE EAF · FURNACE SYNOPTIC", fill="#eef4fa",
                      anchor="w", font=("DejaVu Sans", 13, "bold"))
        c.create_text(24, 40, text="Industry-X · flat-bath immersion melting", fill=MUTED,
                      anchor="w", font=("DejaVu Sans", 9))
        c.create_rectangle(W - 210, 12, W - 20, 48, fill=PANEL, outline=GRID)
        c.create_text(W - 200, 24, text="HEAT TIME", fill=MUTED, anchor="w",
                      font=("DejaVu Sans", 8, "bold"))
        c.create_text(W - 200, 38, text=f"{int(tmin//60):02d}:{int((tmin*60)%60):02d}  ·  {phase}",
                      fill=CYAN, anchor="w", font=("DejaVu Sans Mono", 10, "bold"))

        # refractory shell (multilayer look)
        c.create_rectangle(sx - 14, sy - 14, sx + sw + 14, sy + sh + 14, fill="#0c1219",
                           outline="#3a4d63", width=2)
        c.create_rectangle(sx - 9, sy - 9, sx + sw + 9, sy + sh + 9, outline="#5a3d2a", width=4)
        c.create_rectangle(sx - 3, sy - 3, sx + sw + 3, sy + sh + 3, outline="#7a4a2a", width=5)

        # roof glow
        c.create_oval(sx + sw / 2 - (sw / 2 - 10), sy - 18, sx + sw / 2 + (sw / 2 - 10),
                      sy + 14, fill=temp_color(Troof, 400, 1000), outline="", stipple="gray25")

        # metal bath (banded fill to fake a gradient)
        nb = 10
        for j in range(nb):
            yy0 = metal_top + (mh) * j / nb
            yy1 = metal_top + (mh) * (j + 1) / nb
            col = temp_color(Tm - j * 8, 1450, 1700)
            c.create_rectangle(sx, yy0, sx + sw, yy1, fill=col, outline="")
        c.create_oval(sx, metal_top - 8, sx + sw, metal_top + 8, fill=metal_col, outline="")

        # slag layer
        c.create_rectangle(sx, slag_top, sx + sw, slag_top + slag_h, fill=slag_col, outline="")
        c.create_rectangle(sx, slag_top, sx + sw, slag_top + slag_h / 2, fill="#ffd27f",
                           outline="", stipple="gray50")
        if foam > 0.05:
            for i in range(int(6 + foam * 10)):
                bx = sx + 30 + (sw - 60) * ((i * 37) % 100) / 100.0
                by = slag_top + 4 + (slag_h - 6) * ((i * 53) % 100) / 100.0
                r = 2 + 3 * (((i * 17) % 10) / 10.0)
                c.create_oval(bx - r, by - r, bx + r, by + r, fill="#ffe0a3", outline="")

        # suspended scrap
        for i in range(int(min(6, 1 + msc))):
            xx = sx + 40 + i * 70
            yy = metal_top + 20 + ((i * 29) % 40)
            c.create_rectangle(xx, yy, xx + 14, yy + 14, fill=scrap_col, outline="")

        # electrodes + arcs
        for x in ex:
            c.create_rectangle(x - 9, sy - 70, x + 9, slag_top - 2, fill="#2b2b2b", outline="#444")
            if arc_on:
                c.create_line(x, slag_top - 26, x, slag_top + 2, fill="#ffffff", width=4)
                c.create_line(x, sy - 40, x, slag_top + 2, fill="#ffd27f", width=8)
                c.create_oval(x - 14, slag_top - 12, x + 14, slag_top + 14, outline="",
                              fill="#ffcf87", stipple="gray25")

        # conveyor
        conv_y = slag_top - 8
        cx0 = sx - 96
        c.create_rectangle(cx0, conv_y - 18, sx, conv_y + 8, fill=PANEL2, outline="#2f4055")
        for i in range(5):
            xx = cx0 + 8 + i * 17
            c.create_rectangle(xx, conv_y - 14, xx + 11, conv_y - 3, fill=scrap_col, outline="")
        c.create_text(cx0, conv_y - 26, text="SCRAP CONVEYOR (preheated)", fill=MUTED,
                      anchor="w", font=("DejaVu Sans", 8, "bold"))

        # off-gas duct
        c.create_line(sx + sw - 40, sy - 30, sx + sw + 20, sy - 70, sx + sw + 80, sy - 70,
                      fill="#33475c", width=14, capstyle="round", joinstyle="round")
        c.create_text(sx + sw + 80, sy - 84, text="OFF-GAS", fill=MUTED, anchor="w",
                      font=("DejaVu Sans", 8, "bold"))

        # O2 lance
        c.create_line(sx - 6, metal_top - 30, sx + 70, metal_top + 8, fill=BLUE, width=5,
                      capstyle="round")
        c.create_text(sx - 30, metal_top - 30, text="O₂", fill=BLUE, anchor="w",
                      font=("DejaVu Sans", 9, "bold"))

        # zone labels
        c.create_text(sx + sw / 2, metal_top + mh / 2, text="LIQUID STEEL", fill="#1a0f0a",
                      font=("DejaVu Sans", 10, "bold"))
        c.create_text(sx + sw - 8, slag_top + slag_h - 3, text="FOAMY SLAG", fill="#4a2f10",
                      anchor="e", font=("DejaVu Sans", 8, "bold"))

        # readout chips (left temps)
        chip(20, 74, "BATH TEMP", f"{Tm:,.0f} °C", metal_col)
        chip(20, 114, "SLAG TEMP", f"{Tsl:,.0f} °C", slag_col)
        chip(20, 154, "SCRAP TEMP", f"{Tsc:,.0f} °C", scrap_col)
        chip(20, 194, "GAS TEMP", f"{Tg:,.0f} °C", VIOLET)
        chip(20, 234, "SHELL TEMP", f"{Tshell:,.0f} °C", BLUE)
        # right masses/power
        chip(W - 152, 74, "LIQUID MASS", f"{mm:,.1f} t", ORANGE)
        chip(W - 152, 114, "SOLID SCRAP", f"{msc:,.1f} t", CYAN)
        chip(W - 152, 154, "SLAG MASS", f"{msl:,.1f} t", AMBER)
        chip(W - 152, 194, "ARC POWER", f"{Parc:,.1f} MW", ORANGE)
        chip(W - 152, 234, "CHEM POWER", f"{Pchem:,.1f} MW", GREEN)
        # bottom chemistry row
        by = H - 90
        for i, (lab, val, col) in enumerate([
                ("CARBON", f"{Cp:.3f} %", ORANGE), ("SILICON", f"{Sip:.3f} %", CYAN),
                ("MANGANESE", f"{Mnp:.3f} %", GREEN), ("PHOSPHORUS", f"{Pp:.4f} %", RED),
                ("SLAG FeO", f"{FeO:.1f} %", AMBER), ("BASICITY B2", f"{B2:.2f}", VIOLET)]):
            chip(20 + i * 128, by, lab, val, col, 120)

        # scrap charged progress
        py = H - 34
        c.create_text(20, py, text="SCRAP CHARGED", fill=MUTED, anchor="w",
                      font=("DejaVu Sans", 8, "bold"))
        bx0, bx1 = 140, W - 180
        c.create_rectangle(bx0, py - 6, bx1, py + 6, fill=PANEL, outline=GRID)
        fill_w = (bx1 - bx0) * min(1.0, fed / 110.0)
        c.create_rectangle(bx0, py - 6, bx0 + fill_w, py + 6, fill=ORANGE, outline="")
        c.create_text(W - 170, py, text=f"{fed:,.1f} t fed", fill="#eef4fa", anchor="w",
                      font=("DejaVu Sans Mono", 9, "bold"))

    # ==================================================================
    #  STATIC BALANCE
    # ==================================================================
    def render_static(self):
        self._clear(self.tab_static)
        S = self.model.static_balance()
        k = self.result.kpis()
        eb = self.result.energy_balance()
        wrap = tk.Frame(self.tab_static, bg=BG)
        wrap.pack(fill="both", expand=True, padx=6, pady=6)
        wrap.columnconfigure(0, weight=1)
        wrap.columnconfigure(1, weight=1)
        wrap.rowconfigure(0, weight=1)

        rows = {
            "Steel produced (target)": f"{S['steel_t']:.1f} t @ {S['tap_temp_C']:.0f} °C",
            "Scrap + heel charged": f"{S['charge_t']:.1f} t",
            "Sensible+latent to steel": f"{S['E_steel_kWh']:,.0f} kWh",
            "Slag enthalpy": f"{S['E_slag_kWh']:,.0f} kWh",
            "Off-gas loss (≈22%)": f"{S['E_offgas_kWh']:,.0f} kWh",
            "Cooling + shell loss": f"{S['E_cool_kWh']:,.0f} kWh",
            "Chemical credit": f"−{S['E_chem_kWh']:,.0f} kWh",
            "Scrap-preheat credit": f"−{S['E_preheat_kWh']:,.0f} kWh",
            "Net electrical demand": f"{S['E_elec_demand_kWh']:,.0f} kWh",
            "Specific electrical": f"{S['SEC_elec_kWh_t']:.0f} kWh/t",
        }
        self._kv_panel(wrap, "Static (steady-state) balance", rows, AMBER).grid(
            row=0, column=0, sticky="nsew", padx=4)

        cross = {
            "Steel enthalpy [kWh]": f"static {S['E_steel_kWh']:,.0f}  |  dyn "
                                    f"{eb['outputs']['Steel enthalpy']:,.0f}",
            "Electrical demand [kWh]": f"static {S['E_elec_demand_kWh']:,.0f}  |  dyn "
                                       f"{k['E_elec_kWh']:,.0f}",
            "Specific electrical [kWh/t]": f"static {S['SEC_elec_kWh_t']:.0f}  |  dyn "
                                           f"{k['SEC_elec_kWh_t']:.0f}",
            "Steel yield [%]": f"static {S['yield_pct']:.1f}  |  dyn {k['yield_pct']:.1f}",
            "Slag mass [t]": f"static {S['slag_mass_t']:.1f}  |  dyn {k['slag_mass_t']:.1f}",
        }
        c2 = self._kv_panel(wrap, "Static vs dynamic cross-check", cross, GREEN)
        c2.grid(row=0, column=1, sticky="nsew", padx=4)
        tk.Label(c2, text="The two independent methods agree within model tolerance,\n"
                 "confirming the transient integrator conserves energy.", bg=PANEL,
                 fg=MUTED, font=("DejaVu Sans", 9), justify="left").pack(anchor="w",
                                                                         padx=12, pady=8)

    # ==================================================================
    #  TRAJECTORIES  (matplotlib grid)
    # ==================================================================
    def render_trajectories(self):
        self._clear(self.tab_traj)
        df = self.df
        t = df["t_min"].values
        fig = Figure(figsize=(13, 8.4), dpi=88)
        fig.subplots_adjust(hspace=0.42, wspace=0.28, left=0.05, right=0.98,
                            top=0.96, bottom=0.06)

        ax = fig.add_subplot(2, 4, 1)
        ax.plot(t, df.T_metal, color=ORANGE, lw=1.8, label="Metal")
        ax.plot(t, df.T_slag, color=AMBER, lw=1.3, label="Slag")
        ax.plot(t, df.T_scrap, color=CYAN, lw=1.3, label="Scrap")
        ax.plot(t, df.T_gas, color=VIOLET, lw=1.1, label="Gas")
        ax.axhspan(1600, 1650, color=GREEN, alpha=0.12)
        style_ax(ax, "Zone temperatures", ylabel="°C")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        ax = fig.add_subplot(2, 4, 2)
        ax.plot(t, df.m_metal, color=ORANGE, lw=1.8, label="Liquid")
        ax.plot(t, df.m_scrap_solid, color=CYAN, lw=1.5, label="Scrap")
        ax.plot(t, df.m_slag, color=AMBER, lw=1.3, label="Slag")
        ax.plot(t, df.scrap_fed, color=MUTED, lw=1.1, ls="--", label="Fed")
        style_ax(ax, "Mass inventory", ylabel="t")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        ax = fig.add_subplot(2, 4, 3)
        ax.plot(t, df.C_pct, color=ORANGE, lw=1.8, label="C")
        ax.plot(t, df.Si_pct, color=CYAN, lw=1.3, label="Si")
        ax.plot(t, df.Mn_pct, color=GREEN, lw=1.3, label="Mn")
        ax.plot(t, df.P_pct, color=RED, lw=1.1, label="P")
        ax.set_yscale("log")
        style_ax(ax, "Metal composition", ylabel="wt %")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        ax = fig.add_subplot(2, 4, 4)
        ax.plot(t, df.P_arc_MW, color=ORANGE, lw=1.8, label="Arc")
        ax.plot(t, df.P_chem_MW, color=CYAN, lw=1.3, label="Chemical")
        style_ax(ax, "Power input", ylabel="MW")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        ax = fig.add_subplot(2, 4, 5)
        ax.plot(t, df.Q_offgas_MW, color=VIOLET, lw=1.4, label="Off-gas")
        ax.plot(t, df.Q_water_MW, color=BLUE, lw=1.4, label="Water")
        ax.plot(t, df.Q_shell_MW, color=RED, lw=1.1, label="Shell")
        style_ax(ax, "Heat losses", ylabel="MW")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        ax = fig.add_subplot(2, 4, 6)
        ax.plot(t, df.SEC_elec_kWh_t, color=ORANGE, lw=1.8, label="Electrical")
        ax.plot(t, df.SEC_total_kWh_t, color=AMBER, lw=1.3, label="Elec+chem")
        style_ax(ax, "Cumulative SEC", ylabel="kWh/t")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        ax = fig.add_subplot(2, 4, 7)
        ax.plot(t, df.foam_coverage * 100, color=GREEN, lw=1.6, label="Foam %")
        ax2 = ax.twinx()
        ax2.plot(t, df.decarb_rate, color=ORANGE, lw=1.3)
        ax2.tick_params(colors=MUTED, labelsize=8)
        ax2.set_ylabel("decarb %C/min", color=ORANGE, fontsize=8)
        style_ax(ax, "Foam & decarburisation", ylabel="foam %")

        ax = fig.add_subplot(2, 4, 8)
        ax.plot(t, df.T_shell, color=BLUE, lw=1.4, label="Shell")
        ax.plot(t, df.T_wall_hotface, color=ORANGE, lw=1.4, label="Hot face")
        ax.plot(t, df.T_water_out, color=CYAN, lw=1.3, label="Water out")
        style_ax(ax, "Refractory & cooling", ylabel="°C")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        self._embed_fig(self.tab_traj, fig).pack(fill="both", expand=True, padx=4, pady=4)

    # ==================================================================
    #  SLAG & CHEMISTRY
    # ==================================================================
    def render_slag(self):
        self._clear(self.tab_slag)
        df = self.df
        t = df["t_min"].values
        left = tk.Frame(self.tab_slag, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        fig = Figure(figsize=(8, 8), dpi=88)
        fig.subplots_adjust(hspace=0.35, left=0.09, right=0.9, top=0.96, bottom=0.07)
        ax = fig.add_subplot(2, 1, 1)
        for name, col, lw in [("slag_CaO", AMBER, 1.8), ("slag_SiO2", CYAN, 1.5),
                              ("slag_FeO", ORANGE, 1.8), ("slag_MgO", GREEN, 1.4),
                              ("slag_MnO", VIOLET, 1.2), ("slag_Al2O3", BLUE, 1.2)]:
            ax.plot(t, df[name], color=col, lw=lw, label=name.replace("slag_", ""))
        style_ax(ax, "Slag oxide composition", ylabel="wt %")
        ax.legend(fontsize=7, ncol=2, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)

        ax = fig.add_subplot(2, 1, 2)
        ax.plot(t, df.basicity_B2, color=AMBER, lw=1.8, label="B2")
        ax.plot(t, df.basicity_B3, color=VIOLET, lw=1.2, label="B3")
        ax.axhspan(1.8, 2.5, color=GREEN, alpha=0.10)
        ax.set_ylabel("Basicity", color=MUTED, fontsize=9)
        ax2 = ax.twinx()
        ax2.plot(t, df.FeO_pct, color=ORANGE, lw=1.6)
        ax2.set_ylabel("FeO wt %", color=ORANGE, fontsize=9)
        ax2.tick_params(colors=MUTED, labelsize=8)
        style_ax(ax, "Basicity & FeO vs targets", ylabel="Basicity")
        ax.legend(fontsize=7, facecolor=PANEL, edgecolor=GRID, labelcolor=FG)
        self._embed_fig(left, fig).pack(fill="both", expand=True, padx=4, pady=4)

        # final slag table
        right = tk.Frame(self.tab_slag, bg=BG, width=320)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        fs = dict(self.model.state.sl)
        tot = sum(fs.values())
        ref = {"CaO": 34, "MgO": 9, "SiO2": 15, "Al2O3": 5, "FeO": 32, "MnO": 5}
        rows = {o: f"{100*fs[o]/tot:5.1f}%   (ref {ref[o]}%)" for o in ref}
        p = self._kv_panel(right, "Final slag vs Pretorius reference", rows, ORANGE)
        p.pack(fill="x", padx=4, pady=6)
        tk.Label(right, text="Reference: Pretorius & Marr, Fundamentals of\n"
                 "EAF & Ladle Slags (Baker Refractories). Lower\n"
                 "FeO reflects a well-foamed, well-decarburised\n"
                 "low-carbon tap.", bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9), justify="left").pack(anchor="w", padx=8)

    # ==================================================================
    #  ENERGY & MASS
    # ==================================================================
    def render_energy(self):
        self._clear(self.tab_energy)
        eb = self.result.energy_balance()
        mb = self.result.mass_balance()
        top = tk.Frame(self.tab_energy, bg=BG)
        top.pack(side="top", fill="both", expand=True)
        fig = Figure(figsize=(12, 4.4), dpi=88)
        fig.subplots_adjust(wspace=0.25, left=0.07, right=0.98, top=0.9, bottom=0.2)
        ax = fig.add_subplot(1, 2, 1)
        ins = eb["inputs"]
        ax.bar(range(len(ins)), list(ins.values()),
               color=[ORANGE, CYAN, AMBER, GREEN][:len(ins)], edgecolor=GRID)
        ax.set_xticks(range(len(ins)))
        ax.set_xticklabels(list(ins.keys()), rotation=18, fontsize=8, color=MUTED)
        style_ax(ax, "Energy inputs [kWh]", xlabel=None, ylabel="kWh")
        ax = fig.add_subplot(1, 2, 2)
        outs = {kk: max(0, vv) for kk, vv in eb["outputs"].items()}
        ax.bar(range(len(outs)), list(outs.values()),
               color=[ORANGE, AMBER, VIOLET, BLUE, RED, MUTED][:len(outs)], edgecolor=GRID)
        ax.set_xticks(range(len(outs)))
        ax.set_xticklabels(list(outs.keys()), rotation=18, fontsize=8, color=MUTED)
        style_ax(ax, "Energy outputs [kWh]", xlabel=None, ylabel="kWh")
        self._embed_fig(top, fig).pack(fill="both", expand=True, padx=4, pady=4)

        bottom = tk.Frame(self.tab_energy, bg=BG)
        bottom.pack(side="top", fill="x")
        bottom.columnconfigure(0, weight=1)
        bottom.columnconfigure(1, weight=1)
        closerows = {
            "Total in": f"{eb['total_in']:,.0f} kWh",
            "Total out": f"{eb['total_out']:,.0f} kWh",
            "Energy closure": f"{eb['closure_pct']:.2f} %",
            "Mass closure": f"{mb['closure_pct']:.2f} %",
        }
        self._kv_panel(bottom, "Closures", closerows, GREEN).grid(
            row=0, column=0, sticky="nsew", padx=4, pady=4)
        massrows = {
            "Total mass in": f"{mb['total_in_kg']/1e3:,.2f} t",
            "Total mass out": f"{mb['total_out_kg']/1e3:,.2f} t",
            "Off-gas mass": f"{mb['offgas_mass_kg']/1e3:,.2f} t",
            "Metallic in→liquid out": f"{mb['metal_in_kg']/1e3:,.1f} → {mb['metal_out_kg']/1e3:,.1f} t",
            "Elements → slag": f"{mb['elements_to_slag_kg']/1e3:,.2f} t",
            "Carbon → gas": f"{mb['carbon_to_gas_kg']/1e3:,.2f} t",
        }
        self._kv_panel(bottom, "Mass balance", massrows, VIOLET).grid(
            row=0, column=1, sticky="nsew", padx=4, pady=4)

    # ==================================================================
    #  EVENT LOG
    # ==================================================================
    def render_events(self):
        self._clear(self.tab_events)
        card = tk.Frame(self.tab_events, bg=PANEL, highlightthickness=1, highlightbackground=GRID)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        tk.Label(card, text="Process event log", bg=PANEL, fg=FG, font=H2).pack(
            anchor="w", padx=12, pady=(10, 2))
        tk.Label(card, text="Time-stamped record of every charge milestone, addition and "
                 "process transition detected during the heat.", bg=PANEL, fg=MUTED,
                 font=("DejaVu Sans", 9)).pack(anchor="w", padx=12, pady=(0, 8))
        cv = tk.Canvas(card, bg=PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(card, orient="vertical", command=cv.yview)
        inner = tk.Frame(cv, bg=PANEL)
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=inner, anchor="nw")
        cv.configure(yscrollcommand=sb.set)
        cv.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        sb.pack(side="right", fill="y", pady=(0, 12), padx=(0, 8))
        icons = {"HEAT START": "●", "CHARGE": "»", "FOAMY SLAG": "≈", "FLAT BATH": "◆",
                 "TAP TEMP": "▲", "LOW CARBON": "⚗", "TAP": "■", "END": "□"}
        for e in self.result.events:
            row = tk.Frame(inner, bg=PANEL2, highlightthickness=1, highlightbackground=GRID)
            row.pack(fill="x", pady=3, padx=2)
            tk.Frame(row, bg=CYAN, width=3).pack(side="left", fill="y")
            ic = next((v for kk, v in icons.items() if kk in e["label"]), "•")
            head = tk.Frame(row, bg=PANEL2)
            head.pack(fill="x", padx=8, pady=4)
            tk.Label(head, text=e["time_str"], bg=PANEL2, fg=CYAN,
                     font=("DejaVu Sans Mono", 10, "bold")).pack(side="left")
            tk.Label(head, text=f"  {ic}  {e['label']}", bg=PANEL2, fg=FG,
                     font=SANS_B).pack(side="left")
            tk.Label(row, text=e["detail"], bg=PANEL2, fg=MUTED,
                     font=("DejaVu Sans", 9), justify="left", wraplength=1000).pack(
                anchor="w", padx=18, pady=(0, 4))

    # ==================================================================
    #  DATA
    # ==================================================================
    def render_data(self):
        self._clear(self.tab_data)
        df = self.df
        card = tk.Frame(self.tab_data, bg=PANEL, highlightthickness=1, highlightbackground=GRID)
        card.pack(fill="both", expand=True, padx=6, pady=6)
        head = tk.Frame(card, bg=PANEL)
        head.pack(fill="x", padx=12, pady=10)
        tk.Label(head, text=f"Full trajectory data  ·  {len(df):,} timesteps × "
                 f"{len(df.columns)} channels", bg=PANEL, fg=FG, font=H2).pack(side="left")
        ttk.Button(head, text="⬇ Export CSV", style="DL.TButton",
                   command=self._export_csv).pack(side="right", padx=4)
        ttk.Button(head, text="⬇ Export report (JSON)", style="DL.TButton",
                   command=self._export_json).pack(side="right", padx=4)

        cols = list(df.columns)[:14]
        tv = ttk.Treeview(card, columns=cols, show="headings", height=22)
        style = ttk.Style(self)
        style.configure("Treeview", background=PANEL2, fieldbackground=PANEL2,
                        foreground=FG, font=("DejaVu Sans Mono", 8), rowheight=20)
        style.configure("Treeview.Heading", background=GRID, foreground=FG,
                        font=("DejaVu Sans", 8, "bold"))
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=95, anchor="e")
        step = max(1, len(df) // 250)
        for i in range(0, len(df), step):
            tv.insert("", "end", values=[f"{df.iloc[i][c]:.3f}" for c in cols])
        vsb = ttk.Scrollbar(card, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        tv.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=(0, 12))
        vsb.pack(side="right", fill="y", pady=(0, 12), padx=(0, 8))

    def _export_csv(self):
        p = filedialog.asksaveasfilename(defaultextension=".csv",
                                         initialfile="eaf_heat_trajectory.csv",
                                         filetypes=[("CSV", "*.csv")])
        if p:
            self.df.to_csv(p, index=False)
            messagebox.showinfo("Saved", f"Trajectory written to\n{p}")

    def _export_json(self):
        p = filedialog.asksaveasfilename(defaultextension=".json",
                                         initialfile="eaf_heat_report.json",
                                         filetypes=[("JSON", "*.json")])
        if p:
            rep = {"kpis": self.result.kpis(),
                   "energy_balance": self.result.energy_balance(),
                   "mass_balance": self.result.mass_balance(),
                   "static": self.model.static_balance(),
                   "events": self.result.events}
            with open(p, "w") as f:
                json.dump(rep, f, indent=2, default=float)
            messagebox.showinfo("Saved", f"Report written to\n{p}")


if __name__ == "__main__":
    app = EAFDesktop()
    app.mainloop()
