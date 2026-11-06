/* Interactive furnace synoptic (SCADA cross-section) — JS port of synoptic.py.
   Returns a self-contained SVG string reflecting the reactor state at an instant. */
(function (root) {
  "use strict";
  const lerp = (a, b, t) => a + (b - a) * Math.max(0, Math.min(1, t));
  const hx = (r, g, b) => "#" +
    [r, g, b].map(v => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");

  function tempColor(T, lo = 1450, hi = 1700) {
    let t = Math.max(0, Math.min(1, (T - lo) / (hi - lo)));
    if (t < 0.5) { const u = t / 0.5; return hx(lerp(120, 255, u), lerp(20, 120, u), lerp(10, 20, u)); }
    const u = (t - 0.5) / 0.5; return hx(255, lerp(120, 210, u), lerp(20, 150, u));
  }

  function buildSynoptic(state, width) {
    width = width || 900;
    const g = (k, d) => (state[k] === undefined || state[k] === null) ? (d || 0) : +state[k];
    const S = (k, d) => (state[k] === undefined || state[k] === null) ? (d || "") : state[k];

    const Tm = g("T_metal", 1550), Tsl = g("T_slag", 1560), Tsc = g("T_scrap", 500);
    const Tg = g("T_gas", 1200), Troof = g("T_roof", 700);
    const mm = g("m_metal"), msc = g("m_scrap_solid"), msl = g("m_slag");
    const Cpct = g("C_pct"), Sipct = g("Si_pct"), Mnpct = g("Mn_pct"), Ppct = g("P_pct");
    const FeO = g("FeO_pct"), B2 = g("basicity_B2"), foam = g("foam_coverage");
    const Parc = g("P_arc_MW"), Pchem = g("P_chem_MW");
    const o2 = g("O2_Nm3"), fed = g("scrap_fed"), tmin = g("t_min"), phase = S("phase", "—");

    const metal_col = tempColor(Tm), slag_col = tempColor(Tsl, 1400, 1700);
    const scrap_col = tempColor(Tsc, 300, 1500), roof_glow = tempColor(Troof, 400, 1000);
    const arc_on = Parc > 1.0;

    const sx = 250, sy = 150, sw = 400, sh = 250, bmax = 150;
    const mh = 40 + bmax * Math.min(1, mm / 150);
    const metal_top = sy + sh - mh;
    const slag_h = 14 + 26 * Math.min(1, msl / 18);
    const slag_top = metal_top - slag_h;
    const ex = [0.34, 0.5, 0.66].map(f => sx + sw * f);

    const F = "Inter,'Segoe UI',system-ui,sans-serif";
    const MONO = "ui-monospace,'SF Mono',Menlo,Consolas,monospace";
    const txt = (x, y, s, size, col, anchor, weight, mono, op) =>
      `<text x="${x}" y="${y}" font-size="${size || 12}" fill="${col || "#d7e2ec"}" ` +
      `text-anchor="${anchor || "start"}" font-weight="${weight || "400"}" ` +
      `font-family="${mono ? MONO : F}" opacity="${op === undefined ? 1 : op}">${s}</text>`;
    const tag = (x, y, label, value, col, w) => {
      w = w || 132; col = col || metal_col;
      return `<g><rect x="${x}" y="${y}" width="${w}" height="34" rx="6" fill="#16212e" ` +
        `stroke="#26333f" stroke-width="1"/><rect x="${x}" y="${y}" width="4" height="34" ` +
        `rx="2" fill="${col}"/>${txt(x + 12, y + 14, label, 9.5, "#8aa0b2", "start", "600")}` +
        `${txt(x + 12, y + 28, value, 13, "#eef4fa", "start", "700", true)}</g>`;
    };

    let arc = "";
    if (arc_on) ex.forEach(x => {
      arc += `<line x1="${x}" y1="${sy - 40}" x2="${x}" y2="${slag_top + 2}" stroke="#ffd27f" ` +
        `stroke-width="10" stroke-linecap="round" opacity="0.9"/>` +
        `<line x1="${x}" y1="${slag_top - 24}" x2="${x}" y2="${slag_top + 2}" stroke="#fff" ` +
        `stroke-width="4" opacity="0.95"><animate attributeName="opacity" values="0.4;1;0.4" ` +
        `dur="0.5s" repeatCount="indefinite"/></line>` +
        `<circle cx="${x}" cy="${slag_top + 2}" r="16" fill="#ffcf87" opacity="0.35">` +
        `<animate attributeName="r" values="12;20;12" dur="0.7s" repeatCount="indefinite"/></circle>`;
    });

    let foam_b = "";
    if (foam > 0.05) {
      const n = Math.floor(6 + foam * 10);
      for (let i = 0; i < n; i++) {
        const bx = sx + 30 + (sw - 60) * ((i * 37) % 100) / 100;
        const by = slag_top + 4 + (slag_h - 6) * ((i * 53) % 100) / 100;
        const r = 2 + 3 * (((i * 17) % 10) / 10);
        foam_b += `<circle cx="${bx.toFixed(0)}" cy="${by.toFixed(0)}" r="${r.toFixed(1)}" fill="#ffe0a3" opacity="0.5"/>`;
      }
    }

    const conv_y = slag_top - 8, conv_x0 = 158;
    let conveyor = `<rect x="${conv_x0}" y="${conv_y - 18}" width="${sx - conv_x0}" height="26" rx="4" ` +
      `fill="#1b2735" stroke="#2f4055" stroke-width="1.5"/>` +
      `<line x1="${conv_x0 + 10}" y1="${conv_y + 2}" x2="${sx - 8}" y2="${conv_y + 2}" ` +
      `stroke="#3a4d63" stroke-width="1" stroke-dasharray="6 5"/>`;
    for (let i = 0; i < 5; i++) conveyor += `<rect x="${conv_x0 + 8 + i * 17}" y="${conv_y - 14}" ` +
      `width="11" height="11" rx="2" fill="${scrap_col}" opacity="0.9"/>`;
    let drop = `<polygon points="${sx - 2},${conv_y - 6} ${sx + 12},${conv_y - 6} ${sx + 22},${slag_top - 2} ` +
      `${sx - 12},${slag_top - 2}" fill="#2a3a4d" opacity="0.6"/>`;
    for (let i = 0; i < 3; i++) drop += `<rect x="${sx + i * 6}" y="${conv_y + 6 + i * 18}" width="8" height="8" ` +
      `rx="1" fill="${scrap_col}"><animate attributeName="y" values="${conv_y + 2};${slag_top - 6}" ` +
      `dur="${0.9 + i * 0.2}s" repeatCount="indefinite"/></rect>`;

    const duct = `<path d="M ${sx + sw - 40} ${sy - 30} q 0 -40 60 -40 l 60 0" fill="none" ` +
      `stroke="#33475c" stroke-width="16" stroke-linecap="round"/>`;
    let gas = "";
    for (let i = 0; i < 3; i++) gas += `<circle cx="${sx + sw - 40 + i * 4}" cy="${sy - 34}" r="4" ` +
      `fill="#8aa0b2" opacity="0.35"><animate attributeName="cy" values="${sy - 34};${sy - 70}" ` +
      `dur="1.6s" repeatCount="indefinite"/><animate attributeName="opacity" values="0.4;0" ` +
      `dur="1.6s" repeatCount="indefinite"/></circle>`;

    let lance = `<line x1="${sx - 6}" y1="${metal_top - 30}" x2="${sx + 70}" y2="${metal_top + 8}" ` +
      `stroke="#5b9bd5" stroke-width="5" stroke-linecap="round"/>` +
      txt(sx - 40, metal_top - 30, "O₂", 11, "#5b9bd5", "start", "700");
    if (o2 > 0) for (let i = 0; i < 3; i++) lance += `<circle cx="${sx + 62 + i * 5}" cy="${metal_top + 10 + i * 4}" ` +
      `r="2.5" fill="#8fc1f0"><animate attributeName="opacity" values="1;0" dur="0.6s" repeatCount="indefinite"/></circle>`;

    const layers =
      `<rect x="${sx - 14}" y="${sy - 14}" width="${sw + 28}" height="${sh + 28}" rx="16" fill="#0c1219" stroke="#3a4d63" stroke-width="2"/>` +
      `<rect x="${sx - 9}" y="${sy - 9}" width="${sw + 18}" height="${sh + 18}" rx="13" fill="none" stroke="#5a3d2a" stroke-width="4" opacity="0.8"/>` +
      `<rect x="${sx - 3}" y="${sy - 3}" width="${sw + 6}" height="${sh + 6}" rx="11" fill="none" stroke="#7a4a2a" stroke-width="5" opacity="0.9"/>`;

    let scrapChunks = "";
    const nch = Math.floor(Math.min(6, 1 + msc));
    for (let i = 0; i < nch; i++) scrapChunks += `<rect x="${sx + 40 + i * 70}" y="${metal_top + 20 + ((i * 29) % 40)}" ` +
      `width="14" height="14" rx="2" fill="${scrap_col}" opacity="0.8" transform="rotate(${i * 20} ${sx + 47 + i * 70} ${metal_top + 27})"/>`;

    let electrodes = "";
    ex.forEach(x => electrodes += `<rect x="${x - 9}" y="${sy - 70}" width="18" height="${slag_top - sy + 68}" rx="3" fill="#2b2b2b" stroke="#444" stroke-width="1"/>`);

    const hhmm = String(Math.floor(tmin / 60)).padStart(2, "0") + ":" + String(Math.floor((tmin * 60) % 60)).padStart(2, "0");

    return `<svg viewBox="0 0 ${width} 560" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:auto;background:radial-gradient(1200px 500px at 60% 20%, #16212e 0%, #0f1720 70%);border:1px solid #26333f;border-radius:12px;">
<defs>
<linearGradient id="mg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="${metal_col}"/><stop offset="100%" stop-color="#7a1e0a"/></linearGradient>
<linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#ffd27f"/><stop offset="100%" stop-color="${slag_col}"/></linearGradient>
<filter id="sf"><feGaussianBlur stdDeviation="2"/></filter></defs>
${txt(30, 34, "CONTINUOUS-CHARGE EAF · FURNACE SYNOPTIC", 15, "#eef4fa", "start", "800")}
${txt(30, 52, "Industry-X   ·   flat-bath immersion melting", 11, "#8aa0b2")}
<rect x="${width - 232}" y="18" width="200" height="40" rx="8" fill="#16212e" stroke="#26333f"/>
${txt(width - 220, 36, "HEAT TIME", 9.5, "#8aa0b2", "start", "700")}
${txt(width - 220, 52, hhmm + "  ·  " + phase, 13, "#39d0d8", "start", "800", true)}
${layers}
<ellipse cx="${sx + sw / 2}" cy="${sy - 2}" rx="${sw / 2 - 10}" ry="16" fill="${roof_glow}" opacity="0.25" filter="url(#sf)"/>
<rect x="${sx}" y="${metal_top}" width="${sw}" height="${mh}" fill="url(#mg)"/>
<ellipse cx="${sx + sw / 2}" cy="${metal_top}" rx="${sw / 2}" ry="9" fill="${metal_col}" opacity="0.85"/>
<rect x="${sx}" y="${slag_top}" width="${sw}" height="${slag_h}" fill="url(#sg)" opacity="0.92"/>
${foam_b}${scrapChunks}${electrodes}${arc}${conveyor}${drop}${duct}${gas}
${txt(sx + sw + 70, sy - 84, "OFF-GAS", 10, "#8aa0b2", "start", "700")}
${lance}
${txt(sx + sw / 2, metal_top + mh / 2, "LIQUID STEEL", 12, "#1a0f0a", "middle", "800")}
${txt(sx + sw - 8, slag_top + slag_h - 4, "FOAMY SLAG", 9, "#4a2f10", "end", "700")}
${txt(conv_x0 - 2, conv_y - 24, "SCRAP CONVEYOR (preheated)", 9, "#8aa0b2", "start", "700")}
${tag(20, 90, "BATH TEMP", Tm.toLocaleString(undefined, {maximumFractionDigits: 0}) + " °C", metal_col)}
${tag(20, 130, "SLAG TEMP", Tsl.toLocaleString(undefined, {maximumFractionDigits: 0}) + " °C", slag_col)}
${tag(20, 170, "SCRAP TEMP", Tsc.toLocaleString(undefined, {maximumFractionDigits: 0}) + " °C", scrap_col)}
${tag(20, 210, "GAS TEMP", Tg.toLocaleString(undefined, {maximumFractionDigits: 0}) + " °C", "#b48ead")}
${tag(20, 250, "SHELL TEMP", g("T_shell", 300).toLocaleString(undefined, {maximumFractionDigits: 0}) + " °C", "#5b9bd5")}
${tag(width - 152, 90, "LIQUID MASS", mm.toFixed(1) + " t", "#ff8c42")}
${tag(width - 152, 130, "SOLID SCRAP", msc.toFixed(1) + " t", "#39d0d8")}
${tag(width - 152, 170, "SLAG MASS", msl.toFixed(1) + " t", "#ffc857")}
${tag(width - 152, 210, "ARC POWER", Parc.toFixed(1) + " MW", "#ff8c42")}
${tag(width - 152, 250, "CHEM POWER", Pchem.toFixed(1) + " MW", "#5fd08a")}
${tag(20, 470, "CARBON", Cpct.toFixed(3) + " %", "#ff8c42", 120)}
${tag(148, 470, "SILICON", Sipct.toFixed(3) + " %", "#39d0d8", 120)}
${tag(276, 470, "MANGANESE", Mnpct.toFixed(3) + " %", "#5fd08a", 120)}
${tag(404, 470, "PHOSPHORUS", Ppct.toFixed(4) + " %", "#ef6f6c", 120)}
${tag(532, 470, "SLAG FeO", FeO.toFixed(1) + " %", "#ffc857", 120)}
${tag(660, 470, "BASICITY B2", B2.toFixed(2), "#b48ead", 120)}
${width > 820 ? tag(width - 90, 470, "O₂ USED", o2.toLocaleString(undefined, {maximumFractionDigits: 0}), "#5b9bd5", 70) : ""}
${txt(20, 526, "SCRAP CHARGED", 9.5, "#8aa0b2", "start", "700")}
<rect x="140" y="516" width="${width - 320}" height="12" rx="6" fill="#16212e" stroke="#26333f"/>
<rect x="140" y="516" width="${((width - 320) * Math.min(1, fed / 110)).toFixed(0)}" height="12" rx="6" fill="#ff8c42"/>
${txt(width - 160, 526, fed.toFixed(1) + " t fed", 11, "#eef4fa", "end", "700", true)}
</svg>`;
  }

  root.buildSynoptic = buildSynoptic;
  root.tempColor = tempColor;
})(typeof window !== "undefined" ? window : globalThis);
