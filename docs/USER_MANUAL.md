# User Manual — Continuous-Charge EAF Digital Twin

**Extractmet Private Limited**

The product ships as one validated physics engine with three interchangeable
front-ends. Pick whichever suits the context:

| Interface | Best for | Runs on |
|-----------|----------|---------|
| **Web console** (`web/index.html`) | Quick demos, sharing a single file, offline use | Any modern browser, no install |
| **Streamlit HMI** (`streamlit/`) | Hosted dashboards, team access via a URL | Streamlit Community Cloud / any server |
| **Desktop app** (`gui/eaf_desktop.py`) | Engineers who want a native tool with export dialogs | Windows / macOS / Linux + Python |

All three share the same look, the same tabs and the same first-principles engine,
so results are identical across them (to arc-flicker noise).

---

## 1. Quick start

### 1.1 Web console (zero install)

Open `web/index.html` in any browser (double-click, or serve the `web/` folder).
The model runs immediately with the default configuration. Everything executes
locally in the browser — no server, no data leaves the machine.

### 1.2 Streamlit HMI

```bash
cd streamlit
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`). To deploy publicly,
push the `streamlit/` folder to GitHub and point Streamlit Community Cloud at
`streamlit_app.py` (see `streamlit/README.md`).

### 1.3 Desktop app

```bash
cd gui
pip install numpy pandas matplotlib
python eaf_desktop.py
```

Requires a Tk-enabled Python (`python3-tk` on Linux). On a headless server you can
still run it under `xvfb-run -a python eaf_desktop.py`.

---

## 2. Configuring a heat

Every interface exposes the same configuration groups in the sidebar. Set them, then
press **Run simulation**.

- **Identity** — plant name (anonymised as *Industry-X* by default), heat ID,
  AC/DC furnace type.
- **Geometry & refractory** — shell inner diameter, bath depth, and the multilayer
  wall lining thicknesses/conductivity (MgO-C working lining, magnesia safety lining,
  insulating board, steel shell).
- **Charge (continuous)** — hot-heel mass and temperature, total scrap charged,
  conveyor feed rate, scrap preheat temperature, and scrap chemistry (C, Si, Mn, P).
- **Fluxes** — lime and dololime totals and the flux dosing rate.
- **Electrical** — transformer rating, maximum active power, power factor, arc
  efficiency.
- **Chemical inputs** — O₂ lance rate, post-combustion O₂, carbon injection, optional
  natural-gas burner.
- **Targets & integration** — tap temperature, tap carbon, and the integration time
  step (0.25–1 s).

All ranges are physically reasonable; extreme combinations may push a KPI outside the
literature band (which the scorecard will flag honestly).

---

## 3. Reading the results

The results are organised into eight tabs, identical across the three GUIs.

### 3.1 Overview
- **Validation scorecard** — each KPI shown as a marker on its literature band.
  Green = inside the window, amber = at the edge.
- **Heat summary** — tap mass/temperature, final chemistry, yield, slag, energies,
  productivity, consumables, and the mass/energy closures.
- **Energy sinks** — where the input energy goes (steel, off-gas, water, slag, shell).

### 3.2 Furnace synoptic
An interactive SCADA cross-section of the furnace. Drag the **Heat time** slider to
scrub through the heat; every zone temperature, mass and chemistry value updates live
on the diagram. You can watch the arc strike under the foamy slag on a flat bath while
preheated scrap feeds continuously from the conveyor.

### 3.3 Static balance
A closed-form, steady-state first-law balance for the target tap condition, shown
alongside a static-vs-dynamic cross-check. Agreement confirms the transient
integrator conserves energy.

### 3.4 Trajectories
Eight time-series panels: zone temperatures, mass inventory, metal composition,
power input, heat losses, cumulative specific energy, foam/decarburisation, and
refractory/cooling temperatures. In the web console, hover any chart for a crosshair
read-out.

### 3.5 Slag & chemistry
Slag oxide evolution, basicity (B₂, B₃) and FeO against their target bands, and the
final slag composition compared with the Pretorius & Marr reference slag.

### 3.6 Energy & mass
The full first-law input/output bar charts, energy and mass closures, and a detailed
mass-balance breakdown (metallic in→out, elements to slag, carbon to gas).

### 3.7 Event log
A time-stamped record of every process milestone: heat start, 25/50/75/100 % charge
points, flat-bath establishment, foamy-slag onset, low-carbon transition, tap
temperature reached, and tap.

### 3.8 Data
The full timestep-resolved trajectory table. Export the complete heat log as **CSV**
or a KPI + balance **report as JSON** for downstream analysis.

---

## 4. Exporting results

- **Web console / Streamlit:** use the download buttons on the *Data* tab
  (`eaf_heat_trajectory.csv`, `eaf_heat_report.json`).
- **Desktop app:** use *Export CSV* / *Export report (JSON)* on the *Data* tab, which
  open native save dialogs.

---

## 5. Tips

- Start from the defaults, change one group at a time, and watch the scorecard to
  build intuition for each lever.
- To explore the Consteel preheat benefit, vary the **scrap preheat** temperature and
  watch the electrical SEC on the Overview tab move while the total energy stays near
  570 kWh/t.
- For a dirtier scrap mix, raise the gangue/rust content (web/desktop expose scrap
  chemistry directly) and observe yield fall into the 88–92 % band and FeO/lime rise.
- Reduce the time step to 0.25 s for a smoother trajectory at the cost of a longer
  run.

---
*© Extractmet Private Limited. Model estimates are for engineering guidance and do
not constitute a guarantee of plant performance.*
