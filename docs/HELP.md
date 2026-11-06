# Help & FAQ — Continuous-Charge EAF Digital Twin

**Extractmet Private Limited**

---

**Q. What does this tool model?**
A continuously-charged (Consteel-type) electric-arc furnace: scrap is fed
continuously onto a conveyor into a retained hot heel, the furnace holds a flat
liquid bath, and scrap melts by immersion. The model integrates coupled mass and
energy balances every timestep with oxidation thermochemistry, kinetics, foamy-slag
physics and multilayer heat loss. See `MATHEMATICAL_MODEL.md` for the equations.

**Q. Is it validated?**
Yes — every headline KPI sits inside the peer-reviewed literature window and the model
conserves mass and energy to within ±1 %. See `VALIDATION.md`.

**Q. Which interface should I use?**
- Just want to try it or share a single file → **web console** (`web/index.html`).
- Want a hosted dashboard for a team → **Streamlit** (`streamlit/`).
- Want a native desktop tool with save dialogs → **desktop app** (`gui/eaf_desktop.py`).
All three give identical results.

**Q. The web console shows a blank page.**
Make sure `eaf_engine.js`, `synoptic.js` and `charts.js` are in the same folder as
`index.html`. If you opened it from inside a zip, extract the `web/` folder first.

**Q. The desktop app says `No module named tkinter`.**
Install the Tk bindings for your Python (`sudo apt install python3-tk` on Debian/
Ubuntu; Tk ships with the python.org installers on Windows/macOS).

**Q. Streamlit deploy fails to find the engine.**
The `streamlit/` folder is self-contained: `streamlit_app.py`, `synoptic.py` and
`eaf_model.py` must be pushed together. Point Streamlit Cloud at `streamlit_app.py`.

**Q. Why is my electrical SEC below 300 kWh/t?**
A high scrap preheat and/or a large hot heel supply "free" enthalpy that lowers the
*purchased* electrical energy. The **total** energy demand (electrical + chemical +
preheat/heel credit) is what should be compared with the ~570 kWh/t benchmark — see
the note on the Overview tab and in `VALIDATION.md`.

**Q. Why did my yield exceed 93 %?**
The default scrap is a clean, prepared grade. Raise the gangue/rust/moisture content
(scrap chemistry controls) to model a dirtier mix; yield will fall into the 88–92 %
band and slag FeO/lime will rise.

**Q. The heat didn't tap.**
Tapping requires solid scrap essentially consumed, the bath at tap temperature,
[C] ≤ 1.5× target and ≥ 98 % of scrap charged, all within the 60-minute horizon. If a
configuration can't reach those (e.g. far too little power for the charge), increase
power or reduce the scrap mass. The event log will show an END marker instead of TAP.

**Q. Can I change the scrap composition / gangue in the Streamlit app?**
The Streamlit sidebar exposes the main scrap elements; the web console and desktop app
expose them directly as sliders. Gangue/rust/moisture fractions are engine parameters
(`scrap_gangue_*`, `scrap_rust_FeO`, `scrap_moisture`) and can be set in code or via a
future settings panel.

**Q. How do I export the data?**
Use the *Data* tab: CSV for the full trajectory, JSON for a KPI + balance report.

**Q. Are plant identities anonymised?**
Yes. All configurations default to *Industry-X*; the tool never embeds a real client
name.

**Q. Who do I contact?**
Extractmet Private Limited, for evaluation licences and sponsored pilot engagements.

---
*© Extractmet Private Limited.*
