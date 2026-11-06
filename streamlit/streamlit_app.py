#!/usr/bin/env python3
# =============================================================================
#  Continuous-Charge (Consteel-type) EAF  —  Process Digital Twin
#  Extractmet Private Limited   ·   deployable HMI (Streamlit Community Cloud)
# =============================================================================
import io
import json
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from eaf_model import EAFModel, EAFConfig, Composition, RefractoryLayer, M
from synoptic import build_synoptic

# -----------------------------------------------------------------------------
st.set_page_config(page_title="Continuous-Charge EAF · Digital Twin",
                   page_icon="🔥", layout="wide",
                   initial_sidebar_state="expanded")

# ---- SCADA / control-room theme --------------------------------------------
BG, PANEL, GRID = "#0f1720", "#16212e", "#26333f"
FG, MUTED = "#d7e2ec", "#8aa0b2"
ORANGE, AMBER, CYAN = "#ff8c42", "#ffc857", "#39d0d8"
GREEN, RED, BLUE, VIOLET = "#5fd08a", "#ef6f6c", "#5b9bd5", "#b48ead"

st.markdown(f"""
<style>
  .stApp {{ background:
    radial-gradient(1400px 700px at 70% -10%, #17222f 0%, {BG} 60%); color:{FG}; }}
  section[data-testid="stSidebar"] {{ background:{PANEL}; border-right:1px solid {GRID}; }}
  h1,h2,h3,h4 {{ color:{FG}; font-family:Inter,'Segoe UI',system-ui,sans-serif;
    letter-spacing:.2px; }}
  .stApp, p, label, span, div {{ font-family:Inter,'Segoe UI',system-ui,sans-serif; }}
  code, .mono {{ font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace; }}
  .stTabs [data-baseweb="tab-list"] {{ gap:2px; border-bottom:1px solid {GRID}; }}
  .stTabs [data-baseweb="tab"] {{ background:{PANEL}; color:{MUTED};
    border:1px solid {GRID}; border-bottom:none; border-radius:8px 8px 0 0;
    padding:8px 16px; font-weight:600; font-size:13px; }}
  .stTabs [aria-selected="true"] {{ background:{BG}; color:{ORANGE};
    border-top:2px solid {ORANGE}; }}
  .kpi {{ background:{PANEL}; border:1px solid {GRID}; border-radius:12px;
    padding:14px 16px; position:relative; overflow:hidden; }}
  .kpi::before {{ content:''; position:absolute; left:0; top:0; bottom:0;
    width:4px; background:var(--ac,{ORANGE}); }}
  .kpi .lab {{ color:{MUTED}; font-size:11px; font-weight:700; letter-spacing:.4px;
    text-transform:uppercase; }}
  .kpi .val {{ color:{FG}; font-size:26px; font-weight:800;
    font-family:ui-monospace,Menlo,monospace; margin-top:3px; }}
  .kpi .sub {{ color:{MUTED}; font-size:11px; margin-top:2px; }}
  .badge {{ display:inline-block; padding:2px 9px; border-radius:20px;
    font-size:11px; font-weight:700; }}
  .ok {{ background:rgba(95,208,138,.15); color:{GREEN};
    border:1px solid rgba(95,208,138,.4); }}
  .warn {{ background:rgba(255,200,87,.15); color:{AMBER};
    border:1px solid rgba(255,200,87,.4); }}
  .stButton>button {{ background:linear-gradient(180deg,{ORANGE},#e06a1f);
    color:#160c05; font-weight:800; border:none; border-radius:10px;
    padding:12px; width:100%; font-size:15px; letter-spacing:.3px; }}
  .stButton>button:hover {{ filter:brightness(1.08); }}
  .evt {{ background:{PANEL}; border:1px solid {GRID}; border-left:3px solid {CYAN};
    border-radius:8px; padding:9px 13px; margin-bottom:7px; }}
  .stDownloadButton>button {{ background:{PANEL}; color:{CYAN};
    border:1px solid {GRID}; border-radius:8px; font-weight:700; }}
  hr {{ border-color:{GRID}; }}
  .small {{ color:{MUTED}; font-size:12px; }}
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
#  Plot helpers (Plotly, themed)
# -----------------------------------------------------------------------------
def base_layout(fig, h=340, title=None, ylab=None, y2lab=None):
    fig.update_layout(
        height=h, template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=PANEL,
        margin=dict(l=60, r=20, t=40 if title else 16, b=40),
        font=dict(color=FG, size=11, family="Inter"),
        title=dict(text=title, font=dict(size=13, color=FG)) if title else None,
        legend=dict(bgcolor="rgba(22,33,46,.7)", bordercolor=GRID, borderwidth=1,
                    font=dict(size=10), orientation="h", yanchor="bottom",
                    y=1.0, xanchor="right", x=1.0),
        xaxis=dict(gridcolor=GRID, zeroline=False, title="Time  [min]"),
        yaxis=dict(gridcolor=GRID, zeroline=False, title=ylab),
    )
    if y2lab:
        fig.update_layout(yaxis2=dict(gridcolor="rgba(0,0,0,0)", overlaying="y",
                                      side="right", title=y2lab))
    return fig


def line(fig, x, y, name, color, width=2, dash=None, y2=False):
    fig.add_trace(go.Scatter(x=x, y=y, name=name, mode="lines",
                             line=dict(color=color, width=width, dash=dash),
                             yaxis="y2" if y2 else "y"))


def band(fig, lo, hi, color=GREEN):
    fig.add_hrect(y0=lo, y1=hi, fillcolor=color, opacity=0.10, line_width=0)


# -----------------------------------------------------------------------------
#  Cached engine run
# -----------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def run_engine(cfg_dict: dict):
    cfg = EAFConfig()
    for k, v in cfg_dict.items():
        if k == "scrap_comp":
            cfg.scrap_comp = Composition(**v)
        elif hasattr(cfg, k):
            setattr(cfg, k, v)
    model = EAFModel(cfg)
    res = model.run()
    df = pd.DataFrame(res.history)
    return {
        "df": df,
        "kpis": res.kpis(),
        "energy": res.energy_balance(),
        "mass": res.mass_balance(),
        "events": res.events,
        "static": model.static_balance(),
        "final_slag": dict(model.state.sl),
    }


def phase_at(df, i):
    row = df.iloc[i]
    if row["scrap_fed"] < 1.0:
        return "start-up"
    if row["m_scrap_solid"] > 0.02 * row.get("scrap_fed", 1):
        if row["T_metal"] < 1600:
            return "melt-in"
    if row["C_pct"] > 0.12:
        return "flat-bath melt"
    if row["T_metal"] >= 1600:
        return "refining"
    return "melt-in"


# =============================================================================
#  SIDEBAR  —  configuration
# =============================================================================
st.sidebar.markdown(f"""
<div style="text-align:center;padding:6px 0 10px">
  <div style="font-size:22px;font-weight:900;color:{ORANGE};letter-spacing:.5px">
    EXTRACTMET</div>
  <div style="font-size:11px;color:{MUTED};letter-spacing:2px;margin-top:-2px">
    PYROMETALLURGY · DIGITAL TWINS</div>
</div>""", unsafe_allow_html=True)
st.sidebar.markdown("### ⚙️ Furnace configuration")

with st.sidebar.expander("🏷️  Identity", expanded=False):
    plant_name = st.text_input("Plant", "Industry-X")
    heat_id = st.text_input("Heat ID", "H-000001")
    furnace_type = st.selectbox("Furnace type", ["AC", "DC"], 0)

with st.sidebar.expander("📐  Geometry & refractory", expanded=False):
    shell_inner_diameter = st.slider("Shell inner Ø [m]", 4.0, 8.0, 6.0, 0.1)
    bath_depth_full = st.slider("Bath depth [m]", 0.3, 1.0, 0.60, 0.05)
    freeboard_height = st.slider("Freeboard height [m]", 1.5, 4.0, 2.60, 0.1)
    st.caption("Multilayer wall lining (hot face → shell)")
    l1 = st.slider("MgO-C working lining [mm]", 200, 700, 450, 10)
    l1k = st.slider("… k [W/m·K]", 5.0, 25.0, 14.0, 0.5)
    l2 = st.slider("Magnesia safety lining [mm]", 80, 300, 180, 10)
    l3 = st.slider("Insulating board [mm]", 10, 60, 30, 5)

with st.sidebar.expander("🚚  Charge (continuous)", expanded=True):
    hot_heel_mass = st.slider("Hot heel [t]", 20.0, 70.0, 40.0, 1.0) * 1e3
    hot_heel_c = st.slider("Hot heel temp [°C]", 1450, 1650, 1550, 10)
    total_scrap_mass = st.slider("Scrap charged [t]", 70.0, 160.0, 110.0, 1.0) * 1e3
    scrap_feed_rate = st.slider("Conveyor feed [kg/s]", 20.0, 70.0, 45.0, 1.0)
    scrap_preheat = st.slider("Scrap preheat [°C]", 200, 600, 420, 10)
    st.caption("Scrap chemistry [wt%]")
    sc_C = st.number_input("C", 0.0, 2.0, 0.25, 0.05) / 100
    sc_Si = st.number_input("Si", 0.0, 1.0, 0.30, 0.05) / 100
    sc_Mn = st.number_input("Mn", 0.0, 2.0, 0.40, 0.05) / 100
    sc_P = st.number_input("P", 0.0, 0.2, 0.04, 0.01) / 100
    sc_Cr = st.number_input("Cr", 0.0, 2.0, 0.20, 0.05) / 100

with st.sidebar.expander("🧱  Fluxes", expanded=False):
    lime_total = st.slider("Lime (CaO) [t]", 1.0, 8.0, 4.3, 0.1) * 1e3
    dololime_total = st.slider("Dololime [t]", 0.5, 5.0, 2.0, 0.1) * 1e3
    flux_feed_rate = st.slider("Flux dosing [kg/s]", 1.0, 10.0, 4.0, 0.5)

with st.sidebar.expander("⚡  Electrical", expanded=True):
    transformer_mva = st.slider("Transformer [MVA]", 50.0, 150.0, 90.0, 5.0)
    active_power_max = st.slider("Max active power [MW]", 40.0, 120.0, 72.0, 1.0) * 1e6
    power_factor = st.slider("Power factor", 0.60, 0.95, 0.78, 0.01)
    arc_efficiency = st.slider("Arc efficiency", 0.75, 0.98, 0.90, 0.01)

with st.sidebar.expander("💨  Chemical inputs", expanded=False):
    o2_lance_rate = st.slider("O₂ lance [Nm³/s]", 0.3, 2.5, 1.05, 0.05)
    o2_postcomb_rate = st.slider("O₂ post-comb [Nm³/s]", 0.0, 1.0, 0.32, 0.02)
    carbon_inject_rate = st.slider("Carbon inject [kg/s]", 0.0, 1.5, 0.50, 0.05)
    ng_burner_rate = st.slider("Natural gas [Nm³/s]", 0.0, 1.0, 0.0, 0.05)

with st.sidebar.expander("🎯  Targets & integration", expanded=False):
    tap_temperature = st.slider("Tap temp [°C]", 1580, 1680, 1620, 5)
    tap_carbon = st.slider("Tap carbon [wt%]", 0.03, 0.20, 0.06, 0.01) / 100
    tap_mass_target = st.slider("Tap-mass trigger [t]", 100.0, 160.0, 150.0, 1.0) * 1e3
    dt = st.select_slider("Time step [s]", [0.25, 0.5, 1.0], 0.5)

run_btn = st.sidebar.button("▶  RUN SIMULATION", use_container_width=True)
st.sidebar.markdown(
    f"<div class='small' style='margin-top:8px'>First-principles dynamic model — "
    f"mass &amp; heat balances every {dt:g}s, coupled thermochemistry, kinetics, "
    f"multilayer heat loss. © Extractmet Private Limited.</div>",
    unsafe_allow_html=True)

cfg_dict = dict(
    plant_name=plant_name, heat_id=heat_id, furnace_type=furnace_type,
    shell_inner_diameter=shell_inner_diameter, bath_depth_full=bath_depth_full,
    freeboard_height=freeboard_height,
    refractory=[RefractoryLayer("MgO-C working lining", l1/1000, l1k),
                RefractoryLayer("Magnesia safety lining", l2/1000, 4.5),
                RefractoryLayer("Insulating board", l3/1000, 0.25),
                RefractoryLayer("Carbon-steel shell", 0.050, 45.0)],
    hot_heel_mass=hot_heel_mass, hot_heel_temp=hot_heel_c + 273.15,
    total_scrap_mass=total_scrap_mass, scrap_feed_rate=scrap_feed_rate,
    scrap_preheat_temp=scrap_preheat + 273.15,
    scrap_comp=dict(C=sc_C, Si=sc_Si, Mn=sc_Mn, P=sc_P, Cr=sc_Cr),
    lime_total=lime_total, dololime_total=dololime_total, flux_feed_rate=flux_feed_rate,
    transformer_mva=transformer_mva, active_power_max=active_power_max,
    power_factor=power_factor, arc_efficiency=arc_efficiency,
    o2_lance_rate=o2_lance_rate, o2_postcomb_rate=o2_postcomb_rate,
    carbon_inject_rate=carbon_inject_rate, ng_burner_rate=ng_burner_rate,
    tap_temperature=tap_temperature + 273.15, tap_carbon=tap_carbon,
    tap_mass_target=tap_mass_target, dt=dt,
)

# run on first load or on button
if run_btn or "result" not in st.session_state:
    with st.spinner("Integrating heat …"):
        st.session_state.result = run_engine(cfg_dict)
R = st.session_state.result
df, K = R["df"], R["kpis"]
EB, MB, EV = R["energy"], R["mass"], R["events"]

# =============================================================================
#  HEADER
# =============================================================================
st.markdown(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-end;
     border-bottom:1px solid {GRID};padding-bottom:12px;margin-bottom:4px">
  <div>
    <div style="font-size:26px;font-weight:900;color:{FG}">
      Continuous-Charge EAF — Process Digital Twin</div>
    <div style="color:{MUTED};font-size:13px">
      {plant_name} · Heat {heat_id} · {furnace_type} · flat-bath immersion melting
      · first-principles dynamic model</div>
  </div>
  <div style="text-align:right;color:{MUTED};font-size:12px">
    <span class="mono" style="color:{ORANGE};font-size:15px;font-weight:800">
    Extractmet</span><br>Private Limited</div>
</div>""", unsafe_allow_html=True)


def kpi(col, label, value, sub, ac, ok=None):
    badge = ""
    if ok is True:
        badge = "<span class='badge ok'>in-window</span>"
    elif ok is False:
        badge = "<span class='badge warn'>edge</span>"
    col.markdown(
        f"<div class='kpi' style='--ac:{ac}'><div class='lab'>{label}</div>"
        f"<div class='val'>{value}</div><div class='sub'>{sub} {badge}</div></div>",
        unsafe_allow_html=True)


c = st.columns(6)
kpi(c[0], "Tap mass", f"{K['tap_mass_t']:.1f} t", "liquid steel", ORANGE)
kpi(c[1], "Tap temp", f"{K['tap_temp_C']:.0f} °C", "target 1600–1650",
    AMBER, 1600 <= K['tap_temp_C'] <= 1650)
kpi(c[2], "Final C", f"{K['final_C_pct']:.3f} %", "target 0.05–0.10",
    CYAN, 0.05 <= K['final_C_pct'] <= 0.10)
kpi(c[3], "Elec SEC", f"{K['SEC_elec_kWh_t']:.0f}", "kWh/t · 300–360",
    GREEN, 295 <= K['SEC_elec_kWh_t'] <= 360)
kpi(c[4], "Productivity", f"{K['productivity_t_per_h_per_MW']:.2f}", "t/h/MW · 2.1–2.7",
    VIOLET, 2.1 <= K['productivity_t_per_h_per_MW'] <= 2.7)
kpi(c[5], "Tap-to-tap", f"{K['tap_to_tap_min']:.0f} min", "target 40–60",
    BLUE, 40 <= K['tap_to_tap_min'] <= 60)

# =============================================================================
#  TABS
# =============================================================================
T = st.tabs(["📊 Overview", "🏭 Furnace synoptic", "🧮 Static balance",
             "📈 Dynamic trajectories", "⚗️ Slag & chemistry",
             "🔥 Energy & mass", "📋 Event log", "🗄️ Data"])

# ---------------------------------------------------------------- OVERVIEW ----
with T[0]:
    st.markdown("#### Validation scorecard — simulated vs peer-reviewed windows")
    bench = [
        ("Tap temperature", K['tap_temp_C'], 1600, 1650, "°C"),
        ("Tap-to-tap time", K['tap_to_tap_min'], 40, 60, "min"),
        ("Final carbon", K['final_C_pct'], 0.05, 0.10, "wt%"),
        ("Electrical SEC", K['SEC_elec_kWh_t'], 300, 360, "kWh/t"),
        ("Productivity", K['productivity_t_per_h_per_MW'], 2.1, 2.7, "t/h/MW"),
        ("Metallic yield", K['yield_pct'], 88, 93, "%"),
        ("Slag basicity B2", float(df['basicity_B2'].iloc[-1]), 1.8, 2.5, "-"),
        ("Slag FeO", K['slag_FeO_pct'], 12, 25, "wt%"),
        ("Oxygen use", K['O2_Nm3_t'], 18, 40, "Nm³/t"),
        ("Lime addition", K['lime_kg_t'], 35, 55, "kg/t"),
    ]
    fig = go.Figure()
    labels = [b[0] for b in bench]
    for i, (lab, val, lo, hi, unit) in enumerate(bench):
        y = len(bench) - i
        fig.add_trace(go.Scatter(x=[lo, hi], y=[y, y], mode="lines",
                      line=dict(color=GREEN, width=14), opacity=0.22,
                      showlegend=False, hoverinfo="skip"))
        inside = lo <= val <= hi
        fig.add_trace(go.Scatter(x=[val], y=[y], mode="markers+text",
                      marker=dict(size=15, color=GREEN if inside else AMBER,
                                  line=dict(color="white", width=1.5)),
                      text=[f"{val:.3g}"], textposition="top center",
                      textfont=dict(size=11, color=FG), showlegend=False,
                      hovertext=[f"{lab}: {val:.3g} {unit}  (window {lo}–{hi})"],
                      hoverinfo="text"))
        fig.add_annotation(x=lo, y=y, text=f"{lo:g}", showarrow=False,
                           xshift=-16, font=dict(size=9, color=MUTED))
        fig.add_annotation(x=hi, y=y, text=f"{hi:g} {unit}", showarrow=False,
                           xshift=24, font=dict(size=9, color=MUTED))
    fig.update_layout(height=440, template="plotly_dark", paper_bgcolor=BG,
                      plot_bgcolor=PANEL, margin=dict(l=140, r=40, t=10, b=20),
                      font=dict(color=FG), showlegend=False,
                      yaxis=dict(tickmode="array",
                                 tickvals=list(range(1, len(bench)+1)),
                                 ticktext=labels[::-1], gridcolor="rgba(0,0,0,0)"),
                      xaxis=dict(gridcolor=GRID, zeroline=False))
    st.plotly_chart(fig, use_container_width=True)

    cc = st.columns(2)
    with cc[0]:
        st.markdown("##### Heat summary")
        rows = {
            "Plant / heat": f"{plant_name} · {heat_id}",
            "Tapped": "✅ yes" if K["tapped"] else "❌ no",
            "Liquid tapped": f"{K['tap_mass_t']:.1f} t @ {K['tap_temp_C']:.0f} °C",
            "Final chemistry": (f"C {K['final_C_pct']:.3f} · Si {K['final_Si_pct']:.3f} "
                                f"· Mn {K['final_Mn_pct']:.3f} · P {K['final_P_pct']:.4f} %"),
            "Metallic yield": f"{K['yield_pct']:.1f} %",
            "Slag": (f"{K['slag_mass_t']:.1f} t · B2 "
                     f"{df['basicity_B2'].iloc[-1]:.2f} · FeO {K['slag_FeO_pct']:.1f} %"),
            "Electrical energy": f"{K['E_elec_kWh']:,.0f} kWh · {K['SEC_elec_kWh_t']:.0f} kWh/t",
            "Chemical energy": f"{K['E_chem_kWh']:,.0f} kWh",
            "Total (purchased)": f"{K['SEC_total_kWh_t']:.0f} kWh/t",
            "Productivity": f"{K['productivity_t_per_h_per_h' if False else 'productivity_t_per_h']:.0f} t/h · {K['productivity_t_per_h_per_MW']:.2f} t/h/MW",
            "Oxygen / lime / C": (f"{K['O2_Nm3_t']:.1f} Nm³/t · {K['lime_kg_t']:.0f} kg/t "
                                  f"· {K['carbon_kg_t']:.1f} kg/t"),
            "Mass closure": f"{MB['closure_pct']:.2f} %",
            "Energy closure": f"{EB['closure_pct']:.2f} %",
        }
        st.markdown("<div class='kpi' style='--ac:%s'>" % CYAN +
                    "".join(f"<div style='display:flex;justify-content:space-between;"
                            f"padding:5px 0;border-bottom:1px solid {GRID}'>"
                            f"<span class='small'>{k}</span>"
                            f"<span class='mono' style='color:{FG};font-size:13px'>{v}</span></div>"
                            for k, v in rows.items()) + "</div>",
                    unsafe_allow_html=True)
    with cc[1]:
        st.markdown("##### Energy sources & sinks")
        fig = make_subplots(rows=1, cols=2, specs=[[{"type": "domain"},
                                                    {"type": "domain"}]],
                            subplot_titles=["Inputs", "Outputs"])
        ins = EB["inputs"]; outs = EB["outputs"]
        fig.add_trace(go.Pie(labels=list(ins), values=list(ins.values()), hole=0.5,
                             marker=dict(colors=[ORANGE, CYAN, AMBER, GREEN]),
                             textinfo="percent", textfont=dict(size=10)), 1, 1)
        fig.add_trace(go.Pie(labels=list(outs), values=list(outs.values()), hole=0.5,
                             marker=dict(colors=[ORANGE, AMBER, VIOLET, BLUE, RED, MUTED]),
                             textinfo="percent", textfont=dict(size=10)), 1, 2)
        fig.update_layout(height=360, template="plotly_dark", paper_bgcolor=BG,
                          font=dict(color=FG, size=10), margin=dict(t=40, b=10),
                          legend=dict(font=dict(size=9), orientation="h", y=-0.1))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Total-energy demand = purchased (electrical+chemical) + the "
                   "scrap-preheat & hot-heel enthalpy credit — the Consteel saving "
                   "that pulls purchased SEC below the ~570 kWh/t total.")

# --------------------------------------------------------------- SYNOPTIC ----
with T[1]:
    st.markdown("#### Live furnace synoptic")
    st.caption("Scrub through the heat — every zone temperature, mass and chemistry "
               "value updates on the cross-section. The arc strikes under foamy slag "
               "on a flat bath while preheated scrap feeds continuously from the conveyor.")
    idx = st.slider("Heat time", 0, len(df) - 1, len(df) - 1,
                    format="step %d")
    row = df.iloc[idx]
    state = {k: row[k] for k in df.columns}
    state["phase"] = phase_at(df, idx)
    st.components.v1.html(
        f"<div style='background:{BG};padding:6px'>{build_synoptic(state)}</div>",
        height=580, scrolling=False)
    tcur = row["t_min"]
    st.markdown(
        f"<div class='small'>t = <b class='mono' style='color:{CYAN}'>"
        f"{int(tcur//60):02d}:{int((tcur*60)%60):02d}</b> · phase "
        f"<b style='color:{ORANGE}'>{state['phase']}</b> · arc "
        f"<b class='mono'>{row['P_arc_MW']:.1f} MW</b> · foam "
        f"<b class='mono'>{row['foam_coverage']*100:.0f}%</b></div>",
        unsafe_allow_html=True)

# ---------------------------------------------------------------- STATIC ----
with T[2]:
    st.markdown("#### Static (steady-state) energy & mass balance")
    st.caption("A closed-form first-law balance for the target tap condition — "
               "independent of the dynamic integration. Use it as a quick design "
               "check and a sanity bound on the transient result.")
    S = R["static"]
    cc = st.columns([1.1, 1])
    with cc[0]:
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
        st.markdown("<div class='kpi' style='--ac:%s'>" % AMBER +
                    "".join(f"<div style='display:flex;justify-content:space-between;"
                            f"padding:6px 0;border-bottom:1px solid {GRID}'>"
                            f"<span class='small'>{k}</span>"
                            f"<span class='mono' style='color:{FG}'>{v}</span></div>"
                            for k, v in rows.items()) + "</div>",
                    unsafe_allow_html=True)
    with cc[1]:
        fig = go.Figure(go.Waterfall(
            orientation="v",
            measure=["relative", "relative", "relative", "relative",
                     "relative", "relative", "total"],
            x=["Steel", "Slag", "Off-gas", "Cool+shell", "− Chemical",
               "− Preheat", "Electrical"],
            y=[S['E_steel_kWh'], S['E_slag_kWh'], S['E_offgas_kWh'],
               S['E_cool_kWh'], -S['E_chem_kWh'], -S['E_preheat_kWh'], 0],
            connector=dict(line=dict(color=GRID)),
            increasing=dict(marker=dict(color=ORANGE)),
            decreasing=dict(marker=dict(color=GREEN)),
            totals=dict(marker=dict(color=CYAN))))
        base_layout(fig, 380, "Static energy waterfall  [kWh]", "kWh")
        fig.update_layout(xaxis=dict(title=None))
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("##### Static vs dynamic cross-check")
    comp = pd.DataFrame({
        "Metric": ["Steel enthalpy [kWh]", "Electrical demand [kWh]",
                   "Specific electrical [kWh/t]"],
        "Static": [f"{S['E_steel_kWh']:,.0f}", f"{S['E_elec_demand_kWh']:,.0f}",
                   f"{S['SEC_elec_kWh_t']:.0f}"],
        "Dynamic": [f"{EB['outputs']['Steel enthalpy']:,.0f}",
                    f"{K['E_elec_kWh']:,.0f}", f"{K['SEC_elec_kWh_t']:.0f}"],
    })
    st.dataframe(comp, use_container_width=True, hide_index=True)

# ------------------------------------------------------ DYNAMIC TRAJECTORIES --
with T[3]:
    st.markdown("#### Dynamic process trajectories")
    x = df["t_min"]
    r1 = st.columns(2)
    with r1[0]:
        fig = go.Figure()
        line(fig, x, df.T_metal, "Metal bath", ORANGE)
        line(fig, x, df.T_slag, "Slag", AMBER)
        line(fig, x, df.T_scrap, "Solid scrap", CYAN)
        line(fig, x, df.T_gas, "Freeboard gas", VIOLET, 1.4)
        band(fig, 1600, 1650)
        base_layout(fig, 340, "Zone temperatures", "Temperature  [°C]")
        st.plotly_chart(fig, use_container_width=True)
    with r1[1]:
        fig = go.Figure()
        line(fig, x, df.m_metal, "Liquid metal", ORANGE)
        line(fig, x, df.m_scrap_solid, "Solid scrap (bath)", CYAN)
        line(fig, x, df.m_slag, "Slag", AMBER)
        line(fig, x, df.scrap_fed, "Cum. scrap fed", MUTED, 1.4, "dash")
        base_layout(fig, 340, "Mass inventory (flat-bath hold)", "Mass  [t]")
        st.plotly_chart(fig, use_container_width=True)
    r2 = st.columns(2)
    with r2[0]:
        fig = go.Figure()
        line(fig, x, df.C_pct, "C", ORANGE)
        line(fig, x, df.Si_pct, "Si", CYAN)
        line(fig, x, df.Mn_pct, "Mn", GREEN)
        line(fig, x, df.P_pct, "P", RED, 1.4)
        base_layout(fig, 340, "Metal composition (log)", "Content  [wt %]")
        fig.update_yaxes(type="log")
        st.plotly_chart(fig, use_container_width=True)
    with r2[1]:
        fig = go.Figure()
        line(fig, x, df.P_arc_MW, "Arc power", ORANGE)
        line(fig, x, df.P_chem_MW, "Chemical", CYAN)
        base_layout(fig, 340, "Power input", "Power  [MW]")
        st.plotly_chart(fig, use_container_width=True)
    r3 = st.columns(2)
    with r3[0]:
        fig = go.Figure()
        line(fig, x, df.Q_offgas_MW, "Off-gas", VIOLET)
        line(fig, x, df.Q_water_MW, "Cooling water", BLUE)
        line(fig, x, df.Q_shell_MW, "Shell/refractory", RED, 1.4)
        base_layout(fig, 340, "Instantaneous heat losses", "Power  [MW]")
        st.plotly_chart(fig, use_container_width=True)
    with r3[1]:
        fig = go.Figure()
        line(fig, x, df.SEC_elec_kWh_t, "Electrical", ORANGE)
        line(fig, x, df.SEC_total_kWh_t, "Elec + chem", AMBER)
        base_layout(fig, 340, "Cumulative specific energy", "SEC  [kWh/t]")
        st.plotly_chart(fig, use_container_width=True)
    r4 = st.columns(2)
    with r4[0]:
        fig = go.Figure()
        line(fig, x, df.foam_coverage*100, "Foam coverage", GREEN)
        line(fig, x, df.decarb_rate, "Decarb rate", ORANGE, y2=True)
        base_layout(fig, 340, "Foamy-slag coverage & decarburisation",
                    "Foam coverage [%]", "Decarb rate [%C/min]")
        st.plotly_chart(fig, use_container_width=True)
    with r4[1]:
        fig = go.Figure()
        line(fig, x, df.T_shell, "Shell", BLUE)
        line(fig, x, df.T_wall_hotface, "Lining hot face", ORANGE)
        line(fig, x, df.T_water_out, "Cooling-water out", CYAN)
        base_layout(fig, 340, "Refractory & cooling temperatures", "Temperature  [°C]")
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------- SLAG & CHEMISTRY ----
with T[4]:
    st.markdown("#### Slag evolution & chemistry")
    x = df["t_min"]
    cc = st.columns(2)
    with cc[0]:
        fig = go.Figure()
        for name, col in [("slag_CaO", AMBER), ("slag_SiO2", CYAN),
                          ("slag_FeO", ORANGE), ("slag_MgO", GREEN),
                          ("slag_MnO", VIOLET), ("slag_Al2O3", BLUE)]:
            line(fig, x, df[name], name.replace("slag_", ""), col,
                 2 if name in ("slag_CaO", "slag_FeO") else 1.4)
        base_layout(fig, 360, "Slag oxide composition", "Content  [wt %]")
        st.plotly_chart(fig, use_container_width=True)
    with cc[1]:
        fig = go.Figure()
        line(fig, x, df.basicity_B2, "B2 = CaO/SiO₂", AMBER)
        line(fig, x, df.basicity_B3, "B3 = CaO/(SiO₂+Al₂O₃)", VIOLET, 1.4)
        band(fig, 1.8, 2.5)
        line(fig, x, df.FeO_pct, "FeO", ORANGE, 2, y2=True)
        base_layout(fig, 360, "Basicity & FeO vs targets", "Basicity", "FeO  [wt %]")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("##### Final slag composition")
    fs = R["final_slag"]; tot = sum(fs.values())
    cc = st.columns([1, 1])
    with cc[0]:
        fig = go.Figure(go.Bar(
            x=[f"{100*v/tot:.1f}" for v in fs.values()], y=list(fs.keys()),
            orientation="h", marker=dict(color=[AMBER, GREEN, CYAN, BLUE, ORANGE,
                                                VIOLET, RED, "#c98a5a"]),
            text=[f"{100*v/tot:.1f}%" for v in fs.values()], textposition="auto"))
        base_layout(fig, 320, "Final slag [wt %]", None)
        fig.update_layout(xaxis=dict(title="wt %"), yaxis=dict(title=None))
        st.plotly_chart(fig, use_container_width=True)
    with cc[1]:
        pretorius = {"CaO": 34, "MgO": 9, "SiO2": 15, "Al2O3": 5, "FeO": 32, "MnO": 5}
        sim = {k: 100*fs[k]/tot for k in pretorius}
        comp = pd.DataFrame({"Oxide": list(pretorius),
                             "Simulated wt%": [f"{sim[k]:.1f}" for k in pretorius],
                             "Pretorius ref": [f"{pretorius[k]}" for k in pretorius]})
        st.dataframe(comp, use_container_width=True, hide_index=True, height=300)
        st.caption("Reference: Pretorius & Marr, *Fundamentals of EAF & Ladle "
                   "Slags* (Baker Refractories). Lower FeO here reflects a "
                   "well-foamed, well-decarburised low-carbon tap.")

# ---------------------------------------------------------- ENERGY & MASS ----
with T[5]:
    st.markdown("#### First-law energy balance")
    cc = st.columns(2)
    with cc[0]:
        ins = EB["inputs"]
        fig = go.Figure(go.Bar(x=list(ins), y=list(ins.values()),
                        marker=dict(color=[ORANGE, CYAN, AMBER, GREEN]),
                        text=[f"{v:,.0f}<br>{100*v/sum(ins.values()):.0f}%"
                              for v in ins.values()], textposition="auto"))
        base_layout(fig, 340, "Energy inputs  [kWh]", "kWh")
        fig.update_layout(xaxis=dict(title=None))
        st.plotly_chart(fig, use_container_width=True)
    with cc[1]:
        outs = EB["outputs"]
        fig = go.Figure(go.Bar(x=list(outs), y=list(outs.values()),
                        marker=dict(color=[ORANGE, AMBER, VIOLET, BLUE, RED, MUTED]),
                        text=[f"{v:,.0f}<br>{100*v/sum(outs.values()):.0f}%"
                              for v in outs.values()], textposition="auto"))
        base_layout(fig, 340, "Energy outputs  [kWh]", "kWh")
        fig.update_layout(xaxis=dict(title=None))
        st.plotly_chart(fig, use_container_width=True)
    m1, m2, m3, m4 = st.columns(4)
    kpi(m1, "Total in", f"{EB['total_in']:,.0f}", "kWh", ORANGE)
    kpi(m2, "Total out", f"{EB['total_out']:,.0f}", "kWh", AMBER)
    kpi(m3, "Energy closure", f"{EB['closure_pct']:.2f} %", "|in−out|/in", GREEN,
        abs(EB['closure_pct']) < 3)
    kpi(m4, "Mass closure", f"{MB['closure_pct']:.2f} %", "system", CYAN,
        abs(MB['closure_pct']) < 3)
    st.markdown("#### Mass balance")
    mrows = {
        "Total mass in": f"{MB['total_in_kg']/1e3:,.2f} t",
        "Total mass out": f"{MB['total_out_kg']/1e3:,.2f} t",
        "Off-gas mass": f"{MB['offgas_mass_kg']/1e3:,.2f} t",
        "Closure": f"{MB['closure_kg']:,.0f} kg ({MB['closure_pct']:.2f} %)",
        "Metallic in → liquid out": f"{MB['metal_in_kg']/1e3:,.1f} → {MB['metal_out_kg']/1e3:,.1f} t",
        "Elements oxidised to slag": f"{MB['elements_to_slag_kg']/1e3:,.2f} t",
        "Carbon to gas (CO/CO₂)": f"{MB['carbon_to_gas_kg']/1e3:,.2f} t",
    }
    st.markdown("<div class='kpi' style='--ac:%s'>" % VIOLET +
                "".join(f"<div style='display:flex;justify-content:space-between;"
                        f"padding:6px 0;border-bottom:1px solid {GRID}'>"
                        f"<span class='small'>{k}</span>"
                        f"<span class='mono' style='color:{FG}'>{v}</span></div>"
                        for k, v in mrows.items()) + "</div>", unsafe_allow_html=True)

# --------------------------------------------------------------- EVENT LOG ----
with T[6]:
    st.markdown("#### Process event log")
    st.caption("Time-stamped record of every charge milestone, addition and "
               "process transition detected during the heat.")
    icons = {"HEAT START": "🟢", "CHARGE": "🚚", "FOAMY SLAG": "🫧",
             "FLAT BATH": "🔵", "TAP TEMP": "🌡️", "LOW CARBON": "⚗️", "TAP": "🏁"}
    for e in EV:
        t = e.get("t", 0)
        ic = next((v for k, v in icons.items() if k in e.get("label", "")), "•")
        st.markdown(
            f"<div class='evt'><span class='mono' style='color:{CYAN};"
            f"font-weight:800'>{int(t//60):02d}:{int(t%60):02d}</span> "
            f"&nbsp;{ic}&nbsp; <b style='color:{FG}'>{e.get('label','')}</b>"
            f"<br><span class='small'>{e.get('detail','')}</span></div>",
            unsafe_allow_html=True)

# ------------------------------------------------------------------- DATA ----
with T[7]:
    st.markdown("#### Full trajectory data")
    st.caption(f"{len(df):,} timesteps · {len(df.columns)} channels. "
               "Download the complete heat log or the KPI/balance report.")
    csv = df.to_csv(index=False).encode()
    report = json.dumps({"kpis": K, "energy_balance": EB, "mass_balance": MB,
                         "events": EV, "static": R["static"],
                         "config": {k: (v if not isinstance(v, (list,)) else "…")
                                    for k, v in cfg_dict.items()
                                    if k != "refractory" and k != "scrap_comp"}},
                        indent=2, default=float).encode()
    d1, d2 = st.columns(2)
    d1.download_button("⬇  Trajectory CSV", csv, "eaf_heat_trajectory.csv",
                       "text/csv", use_container_width=True)
    d2.download_button("⬇  KPI + balance report (JSON)", report,
                       "eaf_heat_report.json", "application/json",
                       use_container_width=True)
    st.dataframe(df.round(3), use_container_width=True, height=460)

st.markdown(
    f"<div style='text-align:center;color:{MUTED};font-size:11px;margin-top:24px;"
    f"padding-top:12px;border-top:1px solid {GRID}'>"
    f"Continuous-Charge EAF Digital Twin · first-principles dynamic model "
    f"(thermochemistry · kinetics · coupled heat transfer) · validated against "
    f"Logar <i>et&nbsp;al.</i> ISIJ 2012, Kirschen <i>Energy</i> 2009/11, "
    f"Pretorius &amp; Marr, Zhang <i>et&nbsp;al.</i> Metals 2026 · "
    f"© Extractmet Private Limited — all plant references anonymised as "
    f"Industry-X</div>", unsafe_allow_html=True)
