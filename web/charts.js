/* Minimal dependency-free canvas charts (line + bar) with a SCADA theme,
   hover crosshair + tooltip, target bands and dual y-axis. */
(function (root) {
  "use strict";
  const CLR = {
    bg: "#16212e", grid: "#26333f", fg: "#d7e2ec", muted: "#8aa0b2",
    band: "#22c55e"
  };
  const DPR = Math.max(1, (root.devicePixelRatio) || 1);

  function fit(canvas) {
    const r = canvas.getBoundingClientRect();
    canvas.width = Math.max(10, r.width * DPR);
    canvas.height = Math.max(10, r.height * DPR);
    const ctx = canvas.getContext("2d");
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    return { ctx, w: r.width, h: r.height };
  }

  function niceTicks(min, max, n) {
    if (min === max) { max = min + 1; }
    const span = max - min, step0 = span / n;
    const mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const norm = step0 / mag;
    let step = mag;
    if (norm >= 5) step = 5 * mag; else if (norm >= 2) step = 2 * mag; else step = mag;
    const start = Math.ceil(min / step) * step, ticks = [];
    for (let v = start; v <= max + step * 0.5; v += step) ticks.push(+v.toFixed(10));
    return ticks;
  }

  /* spec = {x:[...], series:[{y,name,color,width,dash,axis:'y'|'y2'}],
            xlabel, ylabel, y2label, band:[lo,hi], title } */
  function lineChart(canvas, spec) {
    const { ctx, w, h } = fit(canvas);
    ctx.clearRect(0, 0, w, h);
    const hasY2 = spec.series.some(s => s.axis === "y2");
    const mL = 52, mR = hasY2 ? 52 : 16, mT = spec.title ? 26 : 10, mB = 34;
    const pw = w - mL - mR, ph = h - mT - mB;
    const x = spec.x;
    const xmin = x[0], xmax = x[x.length - 1];
    const sY = spec.series.filter(s => (s.axis || "y") === "y");
    const sY2 = spec.series.filter(s => s.axis === "y2");
    const yvals = [].concat(...sY.map(s => s.y)).filter(v => isFinite(v));
    let ymin = Math.min(...yvals), ymax = Math.max(...yvals);
    if (spec.band) { ymin = Math.min(ymin, spec.band[0]); ymax = Math.max(ymax, spec.band[1]); }
    const pad = (ymax - ymin) * 0.08 || 1; ymin -= pad; ymax += pad;
    if (spec.ylog) { ymin = Math.max(1e-4, Math.min(...yvals.filter(v => v > 0))); }
    let y2min = 0, y2max = 1;
    if (sY2.length) {
      const v2 = [].concat(...sY2.map(s => s.y)).filter(v => isFinite(v));
      y2min = Math.min(...v2); y2max = Math.max(...v2);
      const p2 = (y2max - y2min) * 0.08 || 1; y2min -= p2; y2max += p2;
    }
    const px = v => mL + (v - xmin) / (xmax - xmin || 1) * pw;
    const logmap = v => (Math.log10(Math.max(v, ymin)) - Math.log10(ymin)) / (Math.log10(ymax) - Math.log10(ymin) || 1);
    const py = v => spec.ylog ? mT + ph - logmap(v) * ph : mT + ph - (v - ymin) / (ymax - ymin || 1) * ph;
    const py2 = v => mT + ph - (v - y2min) / (y2max - y2min || 1) * ph;

    if (spec.title) { ctx.fillStyle = CLR.fg; ctx.font = "700 12px Inter,sans-serif"; ctx.textAlign = "left"; ctx.fillText(spec.title, mL, 16); }

    // band
    if (spec.band) {
      ctx.fillStyle = "rgba(34,197,94,0.10)";
      const y0 = py(spec.band[1]), y1 = py(spec.band[0]);
      ctx.fillRect(mL, y0, pw, y1 - y0);
      ctx.strokeStyle = "rgba(34,197,94,0.5)"; ctx.setLineDash([3, 3]); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(mL, y0); ctx.lineTo(mL + pw, y0);
      ctx.moveTo(mL, y1); ctx.lineTo(mL + pw, y1); ctx.stroke(); ctx.setLineDash([]);
    }

    // grid + y ticks
    ctx.strokeStyle = CLR.grid; ctx.fillStyle = CLR.muted;
    ctx.font = "10px ui-monospace,Menlo,monospace"; ctx.lineWidth = 1;
    const yticks = spec.ylog
      ? [ymin, ymin * 10, ymin * 100, ymin * 1000].filter(v => v <= ymax)
      : niceTicks(ymin, ymax, 5);
    yticks.forEach(v => {
      const Y = py(v); ctx.beginPath(); ctx.moveTo(mL, Y); ctx.lineTo(mL + pw, Y); ctx.stroke();
      ctx.textAlign = "right";
      ctx.fillText(Math.abs(v) >= 1000 ? v.toFixed(0) : (Math.abs(v) < 1 ? v.toFixed(3) : v.toFixed(1)), mL - 6, Y + 3);
    });
    // x ticks
    const xticks = niceTicks(xmin, xmax, 6);
    ctx.textAlign = "center";
    xticks.forEach(v => {
      const X = px(v); if (X < mL - 1 || X > mL + pw + 1) return;
      ctx.strokeStyle = CLR.grid; ctx.beginPath(); ctx.moveTo(X, mT); ctx.lineTo(X, mT + ph); ctx.stroke();
      ctx.fillStyle = CLR.muted; ctx.fillText(v.toFixed(0), X, mT + ph + 16);
    });
    // y2 ticks
    if (sY2.length) {
      ctx.textAlign = "left"; ctx.fillStyle = CLR.muted;
      niceTicks(y2min, y2max, 5).forEach(v => {
        const Y = py2(v); ctx.fillText(Math.abs(v) < 1 ? v.toFixed(2) : v.toFixed(1), mL + pw + 6, Y + 3);
      });
    }
    // axis labels
    ctx.fillStyle = CLR.muted; ctx.font = "10px Inter,sans-serif";
    ctx.textAlign = "center"; ctx.fillText(spec.xlabel || "Time  [min]", mL + pw / 2, h - 4);
    if (spec.ylabel) { ctx.save(); ctx.translate(11, mT + ph / 2); ctx.rotate(-Math.PI / 2); ctx.fillText(spec.ylabel, 0, 0); ctx.restore(); }
    if (spec.y2label) { ctx.save(); ctx.translate(w - 6, mT + ph / 2); ctx.rotate(Math.PI / 2); ctx.fillText(spec.y2label, 0, 0); ctx.restore(); }

    // series
    ctx.lineWidth = 2;
    spec.series.forEach(s => {
      const Y = s.axis === "y2" ? py2 : py;
      ctx.strokeStyle = s.color; ctx.lineWidth = s.width || 2;
      if (s.dash) ctx.setLineDash(s.dash); else ctx.setLineDash([]);
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < x.length; i++) {
        const v = s.y[i]; if (!isFinite(v)) continue;
        const X = px(x[i]), Yv = Y(v);
        if (!started) { ctx.moveTo(X, Yv); started = true; } else ctx.lineTo(X, Yv);
      }
      ctx.stroke(); ctx.setLineDash([]);
    });

    // legend
    ctx.font = "10px Inter,sans-serif"; ctx.textAlign = "left";
    let lx = mL + 6, ly = mT + 12;
    spec.series.forEach(s => {
      const tw = ctx.measureText(s.name).width + 20;
      if (lx + tw > mL + pw - 4) { lx = mL + 6; ly += 15; }
      ctx.strokeStyle = s.color; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(lx, ly - 3); ctx.lineTo(lx + 12, ly - 3); ctx.stroke();
      ctx.fillStyle = CLR.fg; ctx.fillText(s.name, lx + 16, ly);
      lx += tw + 8;
    });

    // hover
    canvas._spec = spec; canvas._geom = { mL, mT, pw, ph, xmin, xmax, px, py, py2 };
    if (!canvas._hoverBound) {
      canvas._hoverBound = true;
      const tip = document.createElement("div");
      tip.className = "chart-tip";
      tip.style.cssText = "position:fixed;pointer-events:none;background:#0c1219;border:1px solid #26333f;" +
        "border-radius:6px;padding:6px 9px;font:11px ui-monospace,Menlo,monospace;color:#d7e2ec;" +
        "z-index:9999;display:none;white-space:nowrap;box-shadow:0 4px 14px rgba(0,0,0,.5)";
      document.body.appendChild(tip);
      canvas._tip = tip;
      canvas.addEventListener("mousemove", ev => {
        const sp = canvas._spec, gm = canvas._geom; if (!sp) return;
        const r = canvas.getBoundingClientRect(), mx = ev.clientX - r.left;
        if (mx < gm.mL || mx > gm.mL + gm.pw) { tip.style.display = "none"; redraw(); return; }
        const xv = gm.xmin + (mx - gm.mL) / gm.pw * (gm.xmax - gm.xmin);
        let idx = 0, best = 1e18;
        for (let i = 0; i < sp.x.length; i++) { const d = Math.abs(sp.x[i] - xv); if (d < best) { best = d; idx = i; } }
        redraw();
        const { ctx } = fit(canvas); // note: redraw already refit; draw crosshair on top
        const X = gm.px(sp.x[idx]);
        ctx.strokeStyle = "rgba(215,226,236,.35)"; ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(X, gm.mT); ctx.lineTo(X, gm.mT + gm.ph); ctx.stroke(); ctx.setLineDash([]);
        sp.series.forEach(s => {
          const v = s.y[idx]; if (!isFinite(v)) return;
          const Y = (s.axis === "y2" ? gm.py2 : gm.py)(v);
          ctx.fillStyle = s.color; ctx.beginPath(); ctx.arc(X, Y, 3.2, 0, 7); ctx.fill();
        });
        let html = `<b style="color:#39d0d8">${sp.x[idx].toFixed(1)} min</b>`;
        sp.series.forEach(s => {
          const v = s.y[idx]; if (!isFinite(v)) return;
          html += `<br><span style="color:${s.color}">■</span> ${s.name}: <b>${v.toFixed(v < 1 ? 3 : 1)}</b>`;
        });
        tip.innerHTML = html; tip.style.display = "block";
        tip.style.left = (ev.clientX + 14) + "px"; tip.style.top = (ev.clientY + 10) + "px";
      });
      canvas.addEventListener("mouseleave", () => { canvas._tip.style.display = "none"; redraw(); });
      function redraw() { lineChart(canvas, canvas._spec); }
    }
  }

  /* barChart(canvas, {labels, values, colors, horizontal, valueFmt, title}) */
  function barChart(canvas, spec) {
    const { ctx, w, h } = fit(canvas);
    ctx.clearRect(0, 0, w, h);
    const horiz = spec.horizontal;
    const mT = spec.title ? 26 : 10, mB = 26, mL = horiz ? 96 : 40, mR = 12;
    const pw = w - mL - mR, ph = h - mT - mB;
    const vmax = Math.max(...spec.values) * 1.15 || 1;
    if (spec.title) { ctx.fillStyle = CLR.fg; ctx.font = "700 12px Inter,sans-serif"; ctx.textAlign = "left"; ctx.fillText(spec.title, mL, 16); }
    const n = spec.values.length;
    if (horiz) {
      const bh = ph / n * 0.62;
      spec.values.forEach((v, i) => {
        const Y = mT + (i + 0.5) * ph / n, L = v / vmax * pw;
        ctx.fillStyle = spec.colors[i % spec.colors.length];
        ctx.fillRect(mL, Y - bh / 2, L, bh);
        ctx.fillStyle = CLR.muted; ctx.font = "10px Inter,sans-serif"; ctx.textAlign = "right";
        ctx.fillText(spec.labels[i], mL - 6, Y + 3);
        ctx.fillStyle = CLR.fg; ctx.textAlign = "left"; ctx.font = "700 10px ui-monospace,monospace";
        ctx.fillText(spec.valueFmt ? spec.valueFmt(v) : v.toFixed(1), mL + L + 5, Y + 3);
      });
    } else {
      const bw = pw / n * 0.62;
      spec.values.forEach((v, i) => {
        const X = mL + (i + 0.5) * pw / n, H = v / vmax * ph;
        ctx.fillStyle = spec.colors[i % spec.colors.length];
        ctx.fillRect(X - bw / 2, mT + ph - H, bw, H);
        ctx.fillStyle = CLR.muted; ctx.font = "9px Inter,sans-serif"; ctx.textAlign = "center";
        ctx.fillText(spec.labels[i], X, mT + ph + 14);
        ctx.fillStyle = CLR.fg; ctx.font = "700 10px ui-monospace,monospace";
        ctx.fillText(spec.valueFmt ? spec.valueFmt(v) : v.toFixed(0), X, mT + ph - H - 4);
      });
    }
  }

  root.Charts = { lineChart, barChart };
})(typeof window !== "undefined" ? window : globalThis);
