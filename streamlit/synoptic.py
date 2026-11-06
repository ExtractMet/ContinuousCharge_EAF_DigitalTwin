"""
Interactive furnace synoptic (SCADA-style cross-section) for the continuous-charge
EAF.  Produces a self-contained SVG string that reflects the reactor state at a
chosen instant: zone temperatures drive the metal/slag/scrap fills, the conveyor
feeds glowing scrap into the flat bath, electrodes strike an arc under a foamy
slag, lances inject O2/C, and every live parameter is annotated on the diagram.

Pure-Python, no dependencies -- returned SVG is embedded directly in Streamlit
(st.markdown / components.html) and mirrors the JS synoptic in the web GUI.
"""
from __future__ import annotations


def _lerp(a, b, t):
    return a + (b - a) * max(0.0, min(1.0, t))


def _hex(r, g, b):
    return f"#{int(max(0,min(255,r))):02x}{int(max(0,min(255,g))):02x}{int(max(0,min(255,b))):02x}"


def temp_to_color(T, lo=1450, hi=1700):
    """Map a temperature [C] to an incandescent colour (dark-red -> orange -> white)."""
    t = (T - lo) / (hi - lo)
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        u = t / 0.5
        return _hex(_lerp(120, 255, u), _lerp(20, 120, u), _lerp(10, 20, u))
    u = (t - 0.5) / 0.5
    return _hex(255, _lerp(120, 210, u), _lerp(20, 150, u))


def build_synoptic(state: dict, width: int = 900) -> str:
    """
    `state` is a dict of the current-instant values.  Expected keys (all optional,
    safe defaults applied):
        t_min, T_metal, T_slag, T_scrap, T_gas, T_roof, T_shell,
        m_metal, m_scrap_solid, m_slag, C_pct, Si_pct, Mn_pct, P_pct,
        FeO_pct, basicity_B2, foam_coverage, P_arc_MW, P_chem_MW,
        O2_Nm3, carbon_inj_kg, scrap_fed, phase
    """
    g = lambda k, d=0.0: float(state.get(k, d)) if state.get(k) is not None else d
    s_ = lambda k, d="": state.get(k, d)

    Tm = g("T_metal", 1550); Tsl = g("T_slag", 1560); Tsc = g("T_scrap", 500)
    Tg = g("T_gas", 1200); Troof = g("T_roof", 700)
    mm = g("m_metal"); msc = g("m_scrap_solid"); msl = g("m_slag")
    Cpct = g("C_pct"); Sipct = g("Si_pct"); Mnpct = g("Mn_pct"); Ppct = g("P_pct")
    FeO = g("FeO_pct"); B2 = g("basicity_B2"); foam = g("foam_coverage")
    Parc = g("P_arc_MW"); Pchem = g("P_chem_MW")
    o2 = g("O2_Nm3"); cinj = g("carbon_inj_kg"); fed = g("scrap_fed")
    tmin = g("t_min"); phase = s_("phase", "—")

    metal_col = temp_to_color(Tm)
    slag_col = temp_to_color(Tsl, 1400, 1700)
    scrap_col = temp_to_color(Tsc, 300, 1500)
    roof_glow = temp_to_color(Troof, 400, 1000)
    arc_on = Parc > 1.0

    # bath geometry inside the shell
    shell_x, shell_y, shell_w, shell_h = 250, 150, 400, 250
    bath_max_h = 150
    # metal fill height scales with liquid mass (0..~150 t)
    mh = 40 + bath_max_h * min(1.0, mm / 150.0)
    metal_top = shell_y + shell_h - mh
    slag_h = 14 + 26 * min(1.0, msl / 18.0)
    slag_top = metal_top - slag_h

    # electrode positions
    ex = [shell_x + shell_w * f for f in (0.34, 0.5, 0.66)]

    def txt(x, y, s, size=12, col="#d7e2ec", anchor="start", weight="400",
            mono=False, opacity=1.0):
        fam = ("ui-monospace,'SF Mono',Menlo,Consolas,monospace" if mono
               else "Inter,'Segoe UI',system-ui,sans-serif")
        return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{col}" '
                f'text-anchor="{anchor}" font-weight="{weight}" '
                f'font-family="{fam}" opacity="{opacity}">{s}</text>')

    def tag(x, y, label, value, col=metal_col, w=132):
        """A small readout chip."""
        return (
            f'<g>'
            f'<rect x="{x}" y="{y}" width="{w}" height="34" rx="6" '
            f'fill="#16212e" stroke="#26333f" stroke-width="1"/>'
            f'<rect x="{x}" y="{y}" width="4" height="34" rx="2" fill="{col}"/>'
            f'{txt(x+12, y+14, label, 9.5, "#8aa0b2", weight="600")}'
            f'{txt(x+12, y+28, value, 13, "#eef4fa", weight="700", mono=True)}'
            f'</g>')

    arc = ""
    if arc_on:
        for x in ex:
            arc += (f'<line x1="{x}" y1="{shell_y-40}" x2="{x}" y2="{slag_top+2}" '
                    f'stroke="#ffd27f" stroke-width="10" stroke-linecap="round" '
                    f'opacity="0.9"/>'
                    f'<line x1="{x}" y1="{slag_top-24}" x2="{x}" y2="{slag_top+2}" '
                    f'stroke="#ffffff" stroke-width="4" opacity="0.95">'
                    f'<animate attributeName="opacity" values="0.4;1;0.4" '
                    f'dur="0.5s" repeatCount="indefinite"/></line>'
                    f'<circle cx="{x}" cy="{slag_top+2}" r="16" fill="#ffcf87" '
                    f'opacity="0.35"><animate attributeName="r" values="12;20;12" '
                    f'dur="0.7s" repeatCount="indefinite"/></circle>')

    # foamy slag bubbles
    foam_bubbles = ""
    if foam > 0.05:
        import math
        n = int(6 + foam * 10)
        for i in range(n):
            bx = shell_x + 30 + (shell_w - 60) * ((i * 37) % 100) / 100.0
            by = slag_top + 4 + (slag_h - 6) * ((i * 53) % 100) / 100.0
            r = 2 + 3 * (((i * 17) % 10) / 10.0)
            foam_bubbles += (f'<circle cx="{bx:.0f}" cy="{by:.0f}" r="{r:.1f}" '
                             f'fill="#ffe0a3" opacity="0.5"/>')

    # conveyor with glowing scrap chunks (sits in the clear gap left of the shell)
    conv_y = slag_top - 8
    conv_x0 = 158
    conveyor = (
        f'<rect x="{conv_x0}" y="{conv_y-18}" width="{shell_x-conv_x0}" height="26" rx="4" '
        f'fill="#1b2735" stroke="#2f4055" stroke-width="1.5"/>'
        f'<line x1="{conv_x0+10}" y1="{conv_y+2}" x2="{shell_x-8}" y2="{conv_y+2}" '
        f'stroke="#3a4d63" stroke-width="1" stroke-dasharray="6 5"/>')
    for i in range(5):
        cx = conv_x0 + 8 + i * 17
        conveyor += (f'<rect x="{cx}" y="{conv_y-14}" width="11" height="11" rx="2" '
                     f'fill="{scrap_col}" opacity="0.9"/>')
    # falling scrap into the bath
    drop = (f'<polygon points="{shell_x-2},{conv_y-6} {shell_x+12},{conv_y-6} '
            f'{shell_x+22},{slag_top-2} {shell_x-12},{slag_top-2}" '
            f'fill="#2a3a4d" opacity="0.6"/>')
    for i in range(3):
        dx = shell_x + i * 6
        drop += (f'<rect x="{dx}" y="{conv_y+6+i*18}" width="8" height="8" rx="1" '
                 f'fill="{scrap_col}"><animate attributeName="y" '
                 f'values="{conv_y+2};{slag_top-6}" dur="{0.9+i*0.2}s" '
                 f'repeatCount="indefinite"/></rect>')

    # off-gas duct + elbow
    duct = (f'<path d="M {shell_x+shell_w-40} {shell_y-30} '
            f'q 0 -40 60 -40 l 60 0" fill="none" stroke="#33475c" '
            f'stroke-width="16" stroke-linecap="round"/>')
    gas_wisp = ""
    for i in range(3):
        gx = shell_x + shell_w - 40 + i * 4
        gas_wisp += (f'<circle cx="{gx}" cy="{shell_y-34}" r="4" fill="#8aa0b2" '
                     f'opacity="0.35"><animate attributeName="cy" '
                     f'values="{shell_y-34};{shell_y-70}" dur="1.6s" '
                     f'repeatCount="indefinite"/><animate attributeName="opacity" '
                     f'values="0.4;0" dur="1.6s" repeatCount="indefinite"/></circle>')

    # lances
    lance = (
        f'<line x1="{shell_x-6}" y1="{metal_top-30}" x2="{shell_x+70}" '
        f'y2="{metal_top+8}" stroke="#5b9bd5" stroke-width="5" stroke-linecap="round"/>'
        f'{txt(shell_x-40, metal_top-30, "O₂", 11, "#5b9bd5", weight="700")}')
    if o2 > 0:
        for i in range(3):
            lx = shell_x + 62 + i * 5
            lance += (f'<circle cx="{lx}" cy="{metal_top+10+i*4}" r="2.5" '
                      f'fill="#8fc1f0"><animate attributeName="opacity" '
                      f'values="1;0" dur="0.6s" repeatCount="indefinite"/></circle>')

    # multilayer refractory shell (drawn as nested rounded rects)
    layers = (
        f'<rect x="{shell_x-14}" y="{shell_y-14}" width="{shell_w+28}" '
        f'height="{shell_h+28}" rx="16" fill="#0c1219" stroke="#3a4d63" '
        f'stroke-width="2"/>'
        f'<rect x="{shell_x-9}" y="{shell_y-9}" width="{shell_w+18}" '
        f'height="{shell_h+18}" rx="13" fill="none" stroke="#5a3d2a" '
        f'stroke-width="4" opacity="0.8"/>'   # safety lining
        f'<rect x="{shell_x-3}" y="{shell_y-3}" width="{shell_w+6}" '
        f'height="{shell_h+6}" rx="11" fill="none" stroke="#7a4a2a" '
        f'stroke-width="5" opacity="0.9"/>')  # working lining (MgO-C)

    svg = f'''
<svg viewBox="0 0 {width} 560" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;height:auto;background:
     radial-gradient(1200px 500px at 60% 20%, #16212e 0%, #0f1720 70%);
     border:1px solid #26333f;border-radius:12px;">
  <defs>
    <linearGradient id="metalGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{metal_col}"/>
      <stop offset="100%" stop-color="#7a1e0a"/>
    </linearGradient>
    <linearGradient id="slagGrad" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#ffd27f"/>
      <stop offset="100%" stop-color="{slag_col}"/>
    </linearGradient>
    <filter id="soft"><feGaussianBlur stdDeviation="2"/></filter>
  </defs>

  <!-- title strip -->
  {txt(30, 34, "CONTINUOUS-CHARGE EAF · FURNACE SYNOPTIC", 15, "#eef4fa", weight="800")}
  {txt(30, 52, "Industry-X   ·   flat-bath immersion melting", 11, "#8aa0b2")}
  <rect x="{width-232}" y="18" width="200" height="40" rx="8" fill="#16212e"
        stroke="#26333f"/>
  {txt(width-220, 36, "HEAT TIME", 9.5, "#8aa0b2", weight="700")}
  {txt(width-220, 52, f"{int(tmin//60):02d}:{int((tmin*60)%60):02d}  ·  {phase}", 13, "#39d0d8", weight="800", mono=True)}

  <!-- refractory shell + layers -->
  {layers}

  <!-- roof glow -->
  <ellipse cx="{shell_x+shell_w/2}" cy="{shell_y-2}" rx="{shell_w/2-10}" ry="16"
           fill="{roof_glow}" opacity="0.25" filter="url(#soft)"/>

  <!-- metal bath -->
  <rect x="{shell_x}" y="{metal_top}" width="{shell_w}" height="{mh}"
        fill="url(#metalGrad)"/>
  <ellipse cx="{shell_x+shell_w/2}" cy="{metal_top}" rx="{shell_w/2}" ry="9"
           fill="{metal_col}" opacity="0.85"/>

  <!-- slag layer -->
  <rect x="{shell_x}" y="{slag_top}" width="{shell_w}" height="{slag_h}"
        fill="url(#slagGrad)" opacity="0.92"/>
  {foam_bubbles}

  <!-- suspended solid scrap in bath -->
  {"".join(f'<rect x="{shell_x+40+i*70}" y="{metal_top+20+((i*29)%40)}" width="14" height="14" rx="2" fill="{scrap_col}" opacity="0.8" transform="rotate({i*20} {shell_x+47+i*70} {metal_top+27})"/>' for i in range(int(min(6, 1+msc))))}

  <!-- electrodes -->
  {"".join(f'<rect x="{x-9}" y="{shell_y-70}" width="18" height="{slag_top-shell_y+68}" rx="3" fill="#2b2b2b" stroke="#444" stroke-width="1"/>' for x in ex)}
  {arc}

  <!-- conveyor feed system -->
  {conveyor}{drop}

  <!-- off-gas duct -->
  {duct}{gas_wisp}
  {txt(shell_x+shell_w+70, shell_y-84, "OFF-GAS", 10, "#8aa0b2", weight="700")}

  <!-- oxygen / carbon lance -->
  {lance}

  <!-- zone labels -->
  {txt(shell_x+shell_w/2, metal_top+mh/2, "LIQUID STEEL", 12, "#1a0f0a", "middle", "800")}
  {txt(shell_x+shell_w-8, slag_top+slag_h-4, "FOAMY SLAG", 9, "#4a2f10", "end", "700")}
  {txt(conv_x0 - 2, conv_y-24, "SCRAP CONVEYOR (preheated)", 9, "#8aa0b2", weight="700")}

  <!-- LEFT readout column: temperatures -->
  {tag(20, 90, "BATH TEMP", f"{Tm:,.0f} °C", metal_col)}
  {tag(20, 130, "SLAG TEMP", f"{Tsl:,.0f} °C", slag_col)}
  {tag(20, 170, "SCRAP TEMP", f"{Tsc:,.0f} °C", scrap_col)}
  {tag(20, 210, "GAS TEMP", f"{Tg:,.0f} °C", "#b48ead")}
  {tag(20, 250, "SHELL TEMP", f"{g('T_shell', 300):,.0f} °C", "#5b9bd5")}

  <!-- RIGHT readout column: masses & power -->
  {tag(width-152, 90, "LIQUID MASS", f"{mm:,.1f} t", "#ff8c42")}
  {tag(width-152, 130, "SOLID SCRAP", f"{msc:,.1f} t", "#39d0d8")}
  {tag(width-152, 170, "SLAG MASS", f"{msl:,.1f} t", "#ffc857")}
  {tag(width-152, 210, "ARC POWER", f"{Parc:,.1f} MW", "#ff8c42")}
  {tag(width-152, 250, "CHEM POWER", f"{Pchem:,.1f} MW", "#5fd08a")}

  <!-- BOTTOM readout row: chemistry -->
  {tag(20, 470, "CARBON", f"{Cpct:.3f} %", "#ff8c42", 120)}
  {tag(148, 470, "SILICON", f"{Sipct:.3f} %", "#39d0d8", 120)}
  {tag(276, 470, "MANGANESE", f"{Mnpct:.3f} %", "#5fd08a", 120)}
  {tag(404, 470, "PHOSPHORUS", f"{Ppct:.4f} %", "#ef6f6c", 120)}
  {tag(532, 470, "SLAG FeO", f"{FeO:.1f} %", "#ffc857", 120)}
  {tag(660, 470, "BASICITY B2", f"{B2:.2f}", "#b48ead", 120)}
  {tag(width-90, 470, "O₂ USED", f"{o2:,.0f}", "#5b9bd5", 70) if width>820 else ""}

  <!-- scrap fed progress bar -->
  {txt(20, 526, "SCRAP CHARGED", 9.5, "#8aa0b2", weight="700")}
  <rect x="140" y="516" width="{width-320}" height="12" rx="6" fill="#16212e"
        stroke="#26333f"/>
  <rect x="140" y="516" width="{max(0,(width-320))*min(1.0, fed/110.0):.0f}" height="12"
        rx="6" fill="#ff8c42"/>
  {txt(width-160, 526, f"{fed:,.1f} t fed", 11, "#eef4fa", "end", "700", mono=True)}
</svg>'''
    return svg
