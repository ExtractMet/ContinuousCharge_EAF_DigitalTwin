#!/usr/bin/env python3
"""
Validation & figure generation for the Continuous-Charge (Consteel-type) EAF
simulator  --  Extractmet Private Limited.

Runs the calibrated engine once, exports the full trajectory + KPIs to JSON
(consumed by the HTML GUI and the docs), and renders a set of publication-quality
validation figures comparing the simulated heat against the peer-reviewed
literature benchmark windows (Logar et al. ISIJ 2012; Kirschen Energy 2009/2011;
Pretorius & Marr EAF slag reference; Zhang et al. Metals 2026; Fruehan DOE 2000).
"""
import os, sys, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from engine.eaf_model import EAFModel, EAFConfig, M

HERE = os.path.dirname(__file__)

# ----- industrial control-room palette (matches the HMIs) --------------------
BG      = "#0f1720"
PANEL   = "#16212e"
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
BAND    = "#22c55e"

plt.rcParams.update({
    "figure.facecolor": BG, "axes.facecolor": PANEL, "savefig.facecolor": BG,
    "axes.edgecolor": GRID, "axes.labelcolor": FG, "text.color": FG,
    "xtick.color": MUTED, "ytick.color": MUTED, "grid.color": GRID,
    "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
    "font.family": "DejaVu Sans", "axes.grid": True, "grid.alpha": 0.5,
    "legend.facecolor": PANEL, "legend.edgecolor": GRID, "legend.framealpha": 0.9,
})


def run():
    cfg = EAFConfig()
    model = EAFModel(cfg)
    res = model.run()
    return cfg, model, res


def export_json(cfg, model, res):
    """Dump trajectory + KPIs + events + energy/mass balance to JSON."""
    keys = list(res.history[0].keys()) if res.history else []
    # decimate to keep the file light for the browser (~600 points)
    n = len(res.history)
    step = max(1, n // 600)
    series = {k: [round(float(h.get(k, 0.0)), 5) for h in res.history[::step]]
              for k in keys}
    out = {
        "meta": {"plant": cfg.plant_name, "heat_id": cfg.heat_id,
                 "furnace_type": cfg.furnace_type, "n_steps": n},
        "series": series,
        "kpis": res.kpis(),
        "energy_balance": res.energy_balance(),
        "mass_balance": res.mass_balance(),
        "events": res.events,
        "final_slag": {k: round(float(v), 3) for k, v in model.state.sl.items()},
        "static": model.static_balance(),
    }
    path = os.path.join(HERE, "sample_heat.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=float)
    print(f"  wrote {path}  ({os.path.getsize(path)//1024} kB)")
    return out


def _band(ax, lo, hi, label=None):
    ax.axhspan(lo, hi, color=BAND, alpha=0.12, zorder=0)
    ax.axhline(lo, color=BAND, lw=0.8, ls=":", alpha=0.6)
    ax.axhline(hi, color=BAND, lw=0.8, ls=":", alpha=0.6)
    if label:
        ax.text(0.985, hi, f" {label} ", transform=ax.get_yaxis_transform(),
                ha="right", va="bottom", fontsize=7.5, color=BAND, alpha=0.9)


def fig_trajectories(res):
    t = res.series("t_min")
    fig, ax = plt.subplots(3, 3, figsize=(15, 11))
    fig.suptitle("Continuous-Charge EAF  —  Simulated Heat Trajectories   |   "
                 "Industry-X   |   Extractmet Private Limited",
                 fontsize=13, fontweight="bold", color=FG, y=0.995)

    # 1 temperatures
    a = ax[0, 0]
    a.plot(t, res.series("T_metal"), color=ORANGE, lw=2, label="Metal bath")
    a.plot(t, res.series("T_slag"), color=AMBER, lw=1.5, label="Slag")
    a.plot(t, res.series("T_scrap"), color=CYAN, lw=1.5, label="Solid scrap")
    a.plot(t, res.series("T_gas"), color=VIOLET, lw=1.2, label="Freeboard gas")
    _band(a, 1600, 1650, "tap window")
    a.set_title("Zone temperatures"); a.set_ylabel("Temperature  [°C]")
    a.set_xlabel("Time  [min]"); a.legend(fontsize=8, loc="lower right")

    # 2 masses
    a = ax[0, 1]
    a.plot(t, res.series("m_metal"), color=ORANGE, lw=2, label="Liquid metal")
    a.plot(t, res.series("m_scrap_solid"), color=CYAN, lw=1.8, label="Solid scrap (bath)")
    a.plot(t, res.series("m_slag"), color=AMBER, lw=1.5, label="Slag")
    a.plot(t, res.series("scrap_fed"), color=MUTED, lw=1.2, ls="--", label="Cum. scrap fed")
    a.set_title("Mass inventory  (flat-bath hold)"); a.set_ylabel("Mass  [t]")
    a.set_xlabel("Time  [min]"); a.legend(fontsize=8, loc="upper left")

    # 3 metal chemistry
    a = ax[0, 2]
    a.plot(t, res.series("C_pct"), color=ORANGE, lw=2, label="C")
    a.plot(t, res.series("Si_pct"), color=CYAN, lw=1.5, label="Si")
    a.plot(t, res.series("Mn_pct"), color=GREEN, lw=1.5, label="Mn")
    a.plot(t, res.series("P_pct"), color=RED, lw=1.3, label="P")
    a.set_title("Metal composition"); a.set_ylabel("Content  [wt %]")
    a.set_xlabel("Time  [min]"); a.legend(fontsize=8); a.set_yscale("log")

    # 4 slag chemistry
    a = ax[1, 0]
    a.plot(t, res.series("slag_CaO"), color=AMBER, lw=1.8, label="CaO")
    a.plot(t, res.series("slag_SiO2"), color=CYAN, lw=1.6, label="SiO₂")
    a.plot(t, res.series("slag_FeO"), color=ORANGE, lw=1.8, label="FeO")
    a.plot(t, res.series("slag_MgO"), color=GREEN, lw=1.5, label="MgO")
    a.plot(t, res.series("slag_MnO"), color=VIOLET, lw=1.3, label="MnO")
    a.set_title("Slag composition"); a.set_ylabel("Content  [wt %]")
    a.set_xlabel("Time  [min]"); a.legend(fontsize=8, ncol=2)

    # 5 basicity + FeO with bands
    a = ax[1, 1]
    a.plot(t, res.series("basicity_B2"), color=AMBER, lw=2, label="B2 = CaO/SiO₂")
    _band(a, 1.8, 2.5, "B2 target")
    a.set_ylabel("Basicity  B2", color=AMBER); a.set_xlabel("Time  [min]")
    a.set_title("Slag basicity & FeO vs targets"); a.set_ylim(0, 4)
    a2 = a.twinx(); a2.grid(False)
    a2.plot(t, res.series("FeO_pct"), color=ORANGE, lw=2, label="FeO")
    a2.axhspan(12, 25, color=ORANGE, alpha=0.08)
    a2.set_ylabel("FeO  [wt %]", color=ORANGE); a2.set_ylim(0, 35)
    a.legend(fontsize=8, loc="upper left"); a2.legend(fontsize=8, loc="upper right")

    # 6 power / chemical
    a = ax[1, 2]
    a.plot(t, res.series("P_arc_MW"), color=ORANGE, lw=2, label="Arc power")
    a.plot(t, res.series("P_chem_MW"), color=CYAN, lw=1.6, label="Chemical")
    a.set_title("Power input"); a.set_ylabel("Power  [MW]")
    a.set_xlabel("Time  [min]"); a.legend(fontsize=8)

    # 7 heat losses
    a = ax[2, 0]
    a.plot(t, res.series("Q_offgas_MW"), color=VIOLET, lw=1.6, label="Off-gas")
    a.plot(t, res.series("Q_water_MW"), color=BLUE, lw=1.6, label="Cooling water")
    a.plot(t, res.series("Q_shell_MW"), color=RED, lw=1.4, label="Shell/refractory")
    a.set_title("Instantaneous heat losses"); a.set_ylabel("Power  [MW]")
    a.set_xlabel("Time  [min]"); a.legend(fontsize=8)

    # 8 cumulative specific energy
    a = ax[2, 1]
    a.plot(t, res.series("SEC_elec_kWh_t"), color=ORANGE, lw=2, label="Electrical")
    a.plot(t, res.series("SEC_total_kWh_t"), color=AMBER, lw=1.6, label="Elec + chem")
    a.set_title("Cumulative specific energy"); a.set_ylabel("SEC  [kWh/t]")
    a.set_xlabel("Time  [min]"); a.legend(fontsize=8, loc="lower right")

    # 9 foam + decarb rate
    a = ax[2, 2]
    a.plot(t, res.series("foam_coverage") * 100, color=GREEN, lw=1.8, label="Foam coverage")
    a.set_ylabel("Foam coverage  [%]", color=GREEN); a.set_xlabel("Time  [min]")
    a.set_title("Foamy-slag coverage & decarb rate"); a.set_ylim(0, 105)
    a2 = a.twinx(); a2.grid(False)
    a2.plot(t, res.series("decarb_rate"), color=ORANGE, lw=1.5, label="Decarb rate")
    a2.set_ylabel("Decarb rate  [%C/min]", color=ORANGE)
    a.legend(fontsize=8, loc="lower left"); a2.legend(fontsize=8, loc="upper right")

    fig.tight_layout(rect=[0, 0, 1, 0.98])
    p = os.path.join(HERE, "fig_trajectories.png")
    fig.savefig(p, dpi=130); plt.close(fig)
    print(f"  wrote {p}")


def fig_kpi_benchmark(res):
    """KPI vs literature benchmark window — horizontal band chart."""
    k = res.kpis()
    # (label, value, lo, hi, unit)
    rows = [
        ("Tap temperature",        k["tap_temp_C"],           1600, 1650, "°C"),
        ("Tap-to-tap time",        k["tap_to_tap_min"],         40,   60, "min"),
        ("Final carbon",           k["final_C_pct"],          0.05, 0.10, "wt%"),
        ("Electrical SEC",         k["SEC_elec_kWh_t"],        300,  360, "kWh/t"),
        ("Productivity",           k["productivity_t_per_h_per_MW"], 2.1, 2.7, "t/h/MW"),
        ("Metallic yield",         k["yield_pct"],              88,   93, "%"),
        ("Slag basicity B2",       res.series("basicity_B2")[-1], 1.8, 2.5, "-"),
        ("Slag FeO",               k["slag_FeO_pct"],           12,   25, "wt%"),
        ("Oxygen use",             k["O2_Nm3_t"],               18,   40, "Nm³/t"),
        ("Lime addition",          k["lime_kg_t"],              35,   55, "kg/t"),
    ]
    fig, ax = plt.subplots(figsize=(11, 7))
    y = np.arange(len(rows))[::-1]
    for yi, (lab, val, lo, hi, unit) in zip(y, rows):
        span = hi - lo
        # normalise position for display: draw band 0..1, place marker
        ax.barh(yi, span, left=lo, height=0.5, color=BAND, alpha=0.20,
                edgecolor=BAND, lw=1.0)
        inside = lo <= val <= hi
        ax.plot(val, yi, "o", ms=13,
                color=(GREEN if inside else AMBER),
                markeredgecolor="white", markeredgewidth=1.4, zorder=5)
        ax.text(val, yi + 0.32, f"{val:.3g}", ha="center", va="bottom",
                fontsize=9, color=FG, fontweight="bold")
        ax.text(lo - 0.02 * span, yi, f"{lo:g}", ha="right", va="center",
                fontsize=8, color=MUTED)
        ax.text(hi + 0.02 * span, yi, f"{hi:g} {unit}", ha="left", va="center",
                fontsize=8, color=MUTED)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xticks([])
    for spine in ["top", "right", "bottom"]:
        ax.spines[spine].set_visible(False)
    ax.set_xlim(-0.5, None)
    # rescale x per-row is impossible on one axis; instead use a normalised twin
    ax.margins(x=0.12)
    ax.set_title("Simulated KPIs vs peer-reviewed benchmark windows  —  "
                 "Continuous-Charge EAF (Industry-X)", fontsize=12, pad=14)
    legend = [Patch(facecolor=BAND, alpha=0.3, label="Literature window"),
              plt.Line2D([], [], marker="o", ls="", color=GREEN,
                         markeredgecolor="white", label="Simulated (in-window)")]
    ax.legend(handles=legend, loc="lower right", fontsize=9)
    fig.tight_layout()
    p = os.path.join(HERE, "fig_kpi_benchmark.png")
    fig.savefig(p, dpi=130); plt.close(fig)
    print(f"  wrote {p}")


def fig_kpi_normalised(res):
    """Cleaner KPI view: every KPI normalised so its band maps to [0,1]."""
    k = res.kpis()
    rows = [
        ("Tap temp [°C]",         k["tap_temp_C"],           1600, 1650),
        ("Tap-to-tap [min]",      k["tap_to_tap_min"],         40,   60),
        ("Final C [wt%]",         k["final_C_pct"],          0.05, 0.10),
        ("Elec SEC [kWh/t]",      k["SEC_elec_kWh_t"],        300,  360),
        ("Productivity [t/h/MW]", k["productivity_t_per_h_per_MW"], 2.1, 2.7),
        ("Yield [%]",             k["yield_pct"],              88,   93),
        ("Basicity B2",           float(res.series("basicity_B2")[-1]), 1.8, 2.5),
        ("Slag FeO [wt%]",        k["slag_FeO_pct"],           12,   25),
        ("O₂ [Nm³/t]",            k["O2_Nm3_t"],               18,   40),
        ("Lime [kg/t]",           k["lime_kg_t"],              35,   55),
    ]
    fig, ax = plt.subplots(figsize=(11, 7))
    y = np.arange(len(rows))[::-1]
    for yi, (lab, val, lo, hi) in zip(y, rows):
        ax.barh(yi, 1.0, left=0.0, height=0.55, color=BAND, alpha=0.18,
                edgecolor=BAND, lw=1.0)
        norm = (val - lo) / (hi - lo)
        norm_disp = min(max(norm, -0.25), 1.25)
        inside = 0.0 <= norm <= 1.0
        ax.plot(norm_disp, yi, "o", ms=14,
                color=(GREEN if inside else AMBER),
                markeredgecolor="white", markeredgewidth=1.5, zorder=5)
        ax.text(norm_disp, yi + 0.34, f"{val:.3g}", ha="center", va="bottom",
                fontsize=9.5, color=FG, fontweight="bold")
        ax.text(-0.03, yi, f"{lo:g}", ha="right", va="center", fontsize=8, color=MUTED)
        ax.text(1.03, yi, f"{hi:g}", ha="left", va="center", fontsize=8, color=MUTED)
    ax.axvline(0, color=BAND, lw=1, ls=":", alpha=0.7)
    ax.axvline(1, color=BAND, lw=1, ls=":", alpha=0.7)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    ax.set_xticks([0, 0.5, 1.0])
    ax.set_xticklabels(["lower\nbound", "band\nmidpoint", "upper\nbound"], fontsize=8)
    ax.set_xlim(-0.28, 1.30)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    ax.set_title("Validation scorecard — all KPIs normalised to their literature band\n"
                 "Continuous-Charge (Consteel-type) EAF · Industry-X · Extractmet",
                 fontsize=12, pad=12)
    legend = [Patch(facecolor=BAND, alpha=0.3, label="Literature window [0,1]"),
              plt.Line2D([], [], marker="o", ls="", color=GREEN,
                         markeredgecolor="white", label="Simulated (in-window)")]
    ax.legend(handles=legend, loc="lower right", fontsize=9)
    fig.tight_layout()
    p = os.path.join(HERE, "fig_scorecard.png")
    fig.savefig(p, dpi=130); plt.close(fig)
    print(f"  wrote {p}")


def fig_energy_sankey(res):
    """Energy in/out stacked bar (Sankey-lite)."""
    eb = res.energy_balance()
    ins, outs = eb["inputs"], eb["outputs"]
    fig, ax = plt.subplots(1, 2, figsize=(12, 6.5))
    # inputs
    labels_i = list(ins.keys()); vals_i = list(ins.values())
    cols_i = [ORANGE, CYAN, AMBER, GREEN]
    ax[0].bar(labels_i, vals_i, color=cols_i[:len(labels_i)], edgecolor=GRID)
    ax[0].set_title("Energy inputs  [kWh]"); ax[0].set_ylabel("kWh")
    for i, v in enumerate(vals_i):
        ax[0].text(i, v, f"{v:,.0f}\n{100*v/sum(vals_i):.0f}%", ha="center",
                   va="bottom", fontsize=8.5, color=FG)
    ax[0].tick_params(axis="x", rotation=20)
    # outputs
    labels_o = list(outs.keys()); vals_o = list(outs.values())
    cols_o = [ORANGE, AMBER, VIOLET, BLUE, RED, MUTED]
    ax[1].bar(labels_o, vals_o, color=cols_o[:len(labels_o)], edgecolor=GRID)
    ax[1].set_title("Energy outputs  [kWh]"); ax[1].set_ylabel("kWh")
    for i, v in enumerate(vals_o):
        ax[1].text(i, v, f"{v:,.0f}\n{100*v/sum(vals_o):.0f}%", ha="center",
                   va="bottom", fontsize=8.5, color=FG)
    ax[1].tick_params(axis="x", rotation=20)
    fig.suptitle("First-law energy balance  —  reference-consistent (datum = ambient)   "
                 "|   closure "
                 f"{eb['closure_pct']:.1f}%", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    p = os.path.join(HERE, "fig_energy_balance.png")
    fig.savefig(p, dpi=130); plt.close(fig)
    print(f"  wrote {p}")


def main():
    print("Running calibrated engine ...")
    cfg, model, res = run()
    k = res.kpis()
    print(f"  tapped={k['tapped']}  {k['tap_to_tap_min']:.1f} min  "
          f"{k['tap_mass_t']:.1f} t @ {k['tap_temp_C']:.0f} °C  C={k['final_C_pct']:.3f}%")
    print("Exporting JSON ...");        export_json(cfg, model, res)
    print("Rendering figures ...")
    fig_trajectories(res)
    fig_kpi_benchmark(res)
    fig_kpi_normalised(res)
    fig_energy_sankey(res)
    print("Done.")


if __name__ == "__main__":
    main()
