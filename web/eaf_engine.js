/* =============================================================================
 * Continuous-Charge (Consteel-type) EAF  —  first-principles dynamic engine
 * Faithful JavaScript port of eaf_model.py   ·   Extractmet Private Limited
 *
 * Pure JS, no dependencies.  Runs in the browser (window.EAF) and in Node
 * (module.exports).  Reproduces the Python engine's mass + heat balances,
 * thermochemistry, kinetics and multilayer heat loss to within noise.
 * ========================================================================== */
(function (root) {
  "use strict";

  // ---- physical constants ---------------------------------------------------
  const SIGMA = 5.670374419e-8;      // Stefan-Boltzmann [W/m2/K4]
  const R_GAS = 8.314462618;         // gas constant [J/mol/K]
  const T_REF = 298.15;              // reference temperature [K]

  const M = {                        // molar masses [kg/mol]
    Fe:0.055845, C:0.012011, Si:0.028085, Mn:0.054938, P:0.030974, Cr:0.051996,
    O:0.015999, O2:0.031998, Ca:0.040078, Mg:0.024305, Al:0.026982,
    CaO:0.056077, MgO:0.040304, SiO2:0.060083, Al2O3:0.101961,
    FeO:0.071844, Fe2O3:0.159687, MnO:0.070937, P2O5:0.141943, Cr2O3:0.151990,
    CO:0.028010, CO2:0.044009, N2:0.028014, H2O:0.018015, CH4:0.016043, H2:0.002016
  };
  const CP = {                       // specific heats [J/kg/K]
    steel_solid:700.0, steel_liquid:820.0, slag_solid:1000.0, slag_liquid:1250.0,
    electrode:1700.0, shell:490.0, water:4186.0
  };
  const CP_GAS = {CO:33.0, CO2:51.0, O2:34.0, N2:31.5, H2O:41.0, CH4:55.0, H2:30.0};
  const L_FUS_STEEL = 272.0e3;
  const H_DISS_LIME = 210.0e3;
  const DH = {
    C_O2_CO:-130.0e3, Si_O2:-800.0e3, Mn_O2:-362.0e3, Fe_O2:-240.0e3,
    P_O2:-600.0e3, Cr_O2:-560.0e3, CO_O2_CO2:-283.0e3, CH4_comb:-802.0e3,
    FeO_C:+110.0e3, C_boud:+172.0e3
  };
  const NM3_TO_MOL = 101325.0 / (R_GAS * 273.15);   // ~44.615

  // ---- helpers --------------------------------------------------------------
  const clip = (x, lo, hi) => Math.max(lo, Math.min(hi, x));
  const K = (c) => c + 273.15;

  // seeded PRNG (mulberry32) + Box-Muller gaussian — small arc flicker only
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function gauss(rng) {
    let u = 0, v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
  }

  // ---- default configuration (mirrors EAFConfig) ----------------------------
  function defaultConfig() {
    return {
      plant_name:"Industry-X", heat_id:"H-000001", furnace_type:"AC",
      // geometry
      shell_inner_diameter:6.0, bath_depth_full:0.60, freeboard_height:2.60,
      roof_area_factor:1.12,
      // charge (continuous)
      hot_heel_mass:40.0e3, hot_heel_temp:K(1550),
      total_scrap_mass:110.0e3, scrap_feed_rate:45.0, scrap_preheat_temp:K(420),
      scrap_comp:{C:0.0025, Si:0.0030, Mn:0.0040, P:0.0004, Cr:0.0020},
      scrap_bulk_density:1100.0,
      scrap_gangue_SiO2:0.0180, scrap_gangue_Al2O3:0.0070, scrap_gangue_CaO:0.0050,
      scrap_gangue_MgO:0.0025, scrap_rust_FeO:0.0120, scrap_moisture:0.0190,
      // fluxes
      lime_total:4.3e3, dololime_total:2.0e3, lime_purity_CaO:0.92,
      dololime_CaO:0.58, dololime_MgO:0.38, flux_feed_rate:4.0,
      // electrical
      transformer_mva:90.0, active_power_max:72.0e6, power_factor:0.78,
      arc_efficiency:0.90,
      // chemical
      o2_lance_rate:1.05, o2_postcomb_rate:0.32, carbon_inject_rate:0.50,
      carbon_charge_total:0.7e3, ng_burner_rate:0.0, postcomb_ratio_target:0.35,
      postcomb_heat_recovery:0.55,
      // refractory (hotface -> shell) [name, thickness m, k W/mK]
      refractory:[["MgO-C working lining",0.450,14.0],
                  ["Magnesia safety lining",0.180,4.5],
                  ["Insulating board",0.030,0.25],
                  ["Carbon-steel shell",0.050,45.0]],
      shell_emissivity:0.80, ambient_temp:K(30), h_shell_ambient:12.0,
      // water-cooled panels
      panel_area:55.0, panel_water_flow:260.0, panel_water_inlet:K(35),
      panel_hotface_emissivity:0.85, panel_wall_resistance:0.0016,
      // heat-transfer coeffs
      h_metal_slag:6000.0, h_slag_wall:1200.0, h_bath_scrap:3500.0,
      h_gas_surface:45.0, emissivity_bath:0.40, emissivity_slag:0.60,
      // arc power distribution
      arc_to_bath_frac:0.72, arc_to_scrap_frac:0.10, arc_to_slag_frac:0.08,
      foam_shielding:0.75,
      // freeboard / off-gas
      leak_air_rate:2.8, gas_holdup_mol:1200.0, offgas_ref_temp:T_REF,
      // kinetics
      k_scrap_melt:1.0, k_decarb_mt:6.5e-4, c_crit:0.30/100.0, k_si:0.020,
      k_mn:0.010, k_p:0.0060, k_cr:0.0040, o2_to_carbon_pref:0.62,
      feo_build_frac:0.30,
      // targets / tapping
      tap_temperature:K(1620), tap_carbon:0.06/100.0, tap_mass_target:150.0e3,
      // integration
      dt:0.5, t_end:3600.0, seed:7
    };
  }

  const MT_EL = ["Fe","C","Si","Mn","P","Cr"];
  const SC_EL = ["Fe","C","Si","Mn","P","Cr"];
  const SF_OX = ["CaO","MgO","SiO2","Al2O3"];
  const SL_OX = ["CaO","SiO2","MgO","Al2O3","FeO","MnO","P2O5","Cr2O3"];
  const GAS   = ["CO","CO2","O2","N2","H2O"];

  const sumVals = (o) => Object.values(o).reduce((a, b) => a + b, 0);
  const zero = (keys) => { const o = {}; keys.forEach(k => o[k] = 0.0); return o; };

  function fmtTime(t) {
    const m = Math.floor(t / 60), s = Math.floor(t % 60);
    return String(m).padStart(2, "0") + ":" + String(s).padStart(2, "0");
  }

  // ===========================================================================
  //  STATE
  // ===========================================================================
  class State {
    constructor(cfg) {
      this.cfg = cfg;
      this.mt = zero(MT_EL); this.sc = zero(SC_EL);
      this.sf = zero(SF_OX); this.sl = zero(SL_OX);
      this.T_mt = cfg.hot_heel_temp; this.T_sc = cfg.scrap_preheat_temp;
      this.T_sf = cfg.ambient_temp; this.T_sl = cfg.hot_heel_temp - 20.0;
      this.T_g = K(1400); this.T_roof = K(350); this.T_wall = K(1200);
      this.T_el = K(2500);
      this.t = 0.0;
      this.E_elec = 0; this.E_chem = 0; this.E_offgas = 0; this.E_water = 0;
      this.E_shell = 0; this.E_slag = 0;
      this.scrap_fed = 0; this.lime_fed = 0; this.dololime_fed = 0;
      this.carbon_fed = 0; this.o2_used = 0; this.ng_used = 0;
      this.offgas_mol = zero(GAS);
      this.T_water_out = cfg.panel_water_inlet; this.shell_temp = K(150);
      this.tapped = false; this.mass_in_cum = 0; this.m_initial = 0;
      this._initCharge();
      this.m_initial = this.massMt() + this.massSc() + this.massSf() + this.massSl();
    }
    _initCharge() {
      const c = this.cfg, comp = {C:0.10/100, Si:0.0, Mn:0.08/100, P:0.010/100, Cr:0.05/100};
      const m = c.hot_heel_mass;
      this.mt.C = m*comp.C; this.mt.Si = m*comp.Si; this.mt.Mn = m*comp.Mn;
      this.mt.P = m*comp.P; this.mt.Cr = m*comp.Cr;
      this.mt.Fe = m - (this.mt.C+this.mt.Si+this.mt.Mn+this.mt.P+this.mt.Cr);
      this.sl.CaO=900; this.sl.SiO2=380; this.sl.MgO=260; this.sl.FeO=520;
      this.sl.MnO=120; this.sl.Al2O3=60;
    }
    massMt() { return sumVals(this.mt); }
    massSc() { return sumVals(this.sc); }
    massSf() { return sumVals(this.sf); }
    massSl() { return sumVals(this.sl); }
    wtMt() {
      const m = this.massMt(), o = {};
      MT_EL.forEach(e => o[e] = m > 0 ? this.mt[e]/m : 0.0); return o;
    }
    wtSl() {
      const m = this.massSl(), o = {};
      SL_OX.forEach(x => o[x] = m > 0 ? this.sl[x]/m : 0.0); return o;
    }
    basicity() { return this.sl.SiO2 > 1e-6 ? this.sl.CaO/this.sl.SiO2 : 0.0; }
    basicityB3() {
      const d = this.sl.SiO2 + this.sl.Al2O3;
      return d > 1e-6 ? (this.sl.CaO + this.sl.MgO)/d : 0.0;
    }
    feoPct() { const m = this.massSl(); return m > 1e-6 ? 100.0*this.sl.FeO/m : 0.0; }
  }

  // ===========================================================================
  //  MODEL
  // ===========================================================================
  class Model {
    constructor(cfg) {
      this.cfg = Object.assign(defaultConfig(), cfg || {});
      this.state = new State(this.cfg);
      this.rng = mulberry32(this.cfg.seed >>> 0);
      this.history = []; this.events = []; this._flags = {};
      this._T_set = this.cfg.tap_temperature; this._refining = false;
      this._log(0.0, "HEAT START",
        `Hot heel ${(this.cfg.hot_heel_mass/1e3).toFixed(0)} t at ` +
        `${(this.cfg.hot_heel_temp-273.15).toFixed(0)} C charged; power on.`, "milestone");
    }
    _log(t, label, detail, category="info") {
      this.events.push({t, time_str:fmtTime(t), label, detail, category});
    }
    // ---- geometry ----
    bathArea() { return Math.PI*Math.pow(this.cfg.shell_inner_diameter,2)/4.0; }
    wallArea() { return Math.PI*this.cfg.shell_inner_diameter*this.cfg.bath_depth_full; }
    foamCoverage() {
      const s = this.state, m = s.massSl();
      let cov = 1.0 - Math.exp(-m/4500.0);
      cov *= (0.6 + 0.4*Math.tanh(s.feoPct()/20.0));
      return clip(cov, 0.0, 1.0);
    }
    // ---- multilayer refractory conduction (coupled cond-conv-rad) ----
    refractoryLoss(T_hot, area) {
      const c = this.cfg, Ta = c.ambient_temp;
      let R = 0; c.refractory.forEach(L => R += L[1]/(L[2]*area));
      let Ts = 0.5*(T_hot + Ta);
      for (let i = 0; i < 40; i++) {
        const q_cond = (T_hot - Ts)/R;
        const q_surf = c.h_shell_ambient*area*(Ts-Ta)
                     + c.shell_emissivity*SIGMA*area*(Math.pow(Ts,4)-Math.pow(Ta,4));
        const f = q_cond - q_surf;
        const df = (-1.0/R) - (c.h_shell_ambient*area
                   + 4.0*c.shell_emissivity*SIGMA*area*Math.pow(Ts,3));
        let Tn = Ts - f/df;
        if (!isFinite(Tn)) break;
        Tn = Math.min(Math.max(Tn, Ta), T_hot);
        if (Math.abs(Tn - Ts) < 1e-4) { Ts = Tn; break; }
        Ts = Tn;
      }
      return [Math.max(0.0, (T_hot - Ts)/R), Ts];
    }
    // ---- water-cooled panel loss ----
    panelLoss(P_arc_incident, T_gas) {
      const c = this.cfg, A = c.panel_area, Twi = c.panel_water_inlet, Tw = Twi + 8.0;
      const q_arc = Math.max(0.0, P_arc_incident);
      const F_gas = 0.35;
      const q_gas = F_gas*c.panel_hotface_emissivity*SIGMA*A
                    *(Math.pow(Math.max(T_gas,300.0),4)-Math.pow(Tw,4))
                    + c.h_gas_surface*A*Math.max(0.0, T_gas-Tw);
      const q_panel = Math.max(0.0, q_arc + Math.max(0.0, q_gas));
      const Two = Twi + q_panel/(c.panel_water_flow*CP.water);
      const Tp = Twi + q_panel*c.panel_wall_resistance/A;
      return [q_panel, Two, Tp];
    }
    // ---- controller (continuous inputs) ----
    inputsActive() {
      const c = this.cfg, s = this.state;
      const remaining = Math.max(0.0, c.total_scrap_mass - s.scrap_fed);
      let feed;
      if (remaining > 1.0) {
        feed = Math.min(c.scrap_feed_rate, remaining/c.dt);
        this._T_set = K(1560); this._refining = false;
      } else {
        feed = 0.0; this._T_set = c.tap_temperature; this._refining = true;
      }
      const flux = (s.lime_fed < c.lime_total || s.dololime_fed < c.dololime_total)
                   ? c.flux_feed_rate : 0.0;
      const wC0 = s.wtMt().C;
      const c_taper = clip((wC0 - c.tap_carbon)/0.0010, 0.0, 1.0);
      const cinj = s.massMt() > 1.0 ? c.carbon_inject_rate*c_taper : 0.0;
      const wC = s.wtMt().C;
      const o2_scale = clip((wC - c.tap_carbon)/0.0015, 0.35, 1.0);
      const o2_lance = c.o2_lance_rate*o2_scale;
      const o2_pc = c.o2_postcomb_rate;
      const ng = s.massSc() > 0.05*c.total_scrap_mass ? c.ng_burner_rate : 0.0;
      return {feed, flux, cinj, o2_lance, o2_pc, ng};
    }
    // ---- arc power ----
    arcPower() {
      const c = this.cfg, s = this.state;
      let base = c.active_power_max;
      const flick = 1.0 + 0.02*gauss(this.rng);
      const T_set = this._T_set;
      const err = T_set - s.T_mt;
      const factor = clip(1.0 + 0.030*err, 0.12, 1.0);
      base *= factor;
      if (s.T_roof > K(750)) base *= 0.85;
      return Math.max(0.0, base*flick*c.arc_efficiency);
    }
    // ---- charging helpers ----
    addScrap(mass, comp) {
      const s = this.state, mOld = s.massSc();
      s.sc.C += mass*comp.C; s.sc.Si += mass*comp.Si; s.sc.Mn += mass*comp.Mn;
      s.sc.P += mass*comp.P; s.sc.Cr += mass*comp.Cr;
      const fe = 1.0 - (comp.C+comp.Si+comp.Mn+comp.P+comp.Cr);
      s.sc.Fe += mass*fe;
      if (mOld + mass > 1e-9)
        s.T_sc = (mOld*s.T_sc + mass*this.cfg.scrap_preheat_temp)/(mOld + mass);
    }
    addFlux(mass) {
      const c = this.cfg, s = this.state;
      const remL = Math.max(0.0, c.lime_total - s.lime_fed);
      const remD = Math.max(0.0, c.dololime_total - s.dololime_fed);
      const tot = remL + remD; if (tot <= 1e-9) return;
      const lime = mass*remL/tot, dolo = mass*remD/tot;
      s.sf.CaO += lime*c.lime_purity_CaO;
      s.sf.SiO2 += lime*(1.0-c.lime_purity_CaO)*0.6;
      s.sf.Al2O3 += lime*(1.0-c.lime_purity_CaO)*0.4;
      s.lime_fed += lime;
      s.sf.CaO += dolo*c.dololime_CaO; s.sf.MgO += dolo*c.dololime_MgO;
      const r = Math.max(0.0, 1 - c.dololime_CaO - c.dololime_MgO);
      s.sf.SiO2 += dolo*r*0.6; s.sf.Al2O3 += dolo*r*0.4;
      s.dololime_fed += dolo;
    }
    meltTransfer(dm) {
      const s = this.state, mSc = s.massSc();
      if (mSc <= 1e-9 || dm <= 0) return;
      const Tenter = 1809.0, mOld = s.massMt(), frac = Math.min(1.0, dm/mSc);
      let moved = 0.0;
      SC_EL.forEach(e => { const tr = s.sc[e]*frac; s.sc[e] -= tr; s.mt[e] += tr; moved += tr; });
      if (mOld + moved > 1e-9)
        s.T_mt = (mOld*s.T_mt + moved*Tenter)/(mOld + moved);
    }
    dissolveFlux(dt) {
      const s = this.state, mSf = s.massSf(); if (mSf <= 1e-6) return 0.0;
      const drive = clip((s.T_sl - K(1450))/120.0, 0.05, 1.0);
      const kd = 0.010*drive, dm = Math.min(mSf, kd*mSf*dt), frac = dm/mSf;
      SF_OX.forEach(o => { const tr = s.sf[o]*frac; s.sf[o] -= tr; s.sl[o] = (s.sl[o]||0) + tr; });
      return dm/dt*H_DISS_LIME;
    }
    // ---- chemistry ----
    chemistry(o2_lance, o2_pc, ng, c_boud_avail, A_bath, dt) {
      const c = this.cfg, s = this.state, wt = s.wtMt();
      const m_mt = Math.max(1.0, s.massMt()), rho_mt = 7000.0;
      const nO2 = o2_lance*NM3_TO_MOL;
      // Si oxidation
      let rSi = Math.max(0.0, c.k_si*s.mt.Si/M.Si), o2_Si = rSi*1.0;
      // Mn oxidation
      let rMn = Math.max(0.0, c.k_mn*s.mt.Mn/M.Mn), o2_Mn = rMn*0.5;
      let o2_SiMn = o2_Si + o2_Mn, share = Math.min(o2_SiMn, 0.35*nO2);
      if (o2_SiMn > 1e-12) { const sc = share/o2_SiMn; rSi*=sc; rMn*=sc; o2_Si*=sc; o2_Mn*=sc; }
      const nO2_rem = nO2 - (o2_Si + o2_Mn);
      // carbon oxidation
      const o2_C = c.o2_to_carbon_pref*nO2_rem;
      const wC_eq = 0.0;
      const r_C_mt_kg = A_bath*rho_mt*c.k_decarb_mt*Math.max(0.0, wt.C - wC_eq);
      const r_C_mt = r_C_mt_kg/M.C;
      const r_C_by_O2 = 2.0*o2_C;
      let rC_O2 = (wt.C < 3.0*c.c_crit) ? Math.min(r_C_by_O2, r_C_mt) : r_C_by_O2;
      rC_O2 = Math.max(0.0, rC_O2);
      let o2_C_used = rC_O2/2.0;
      let nO2_rem2 = nO2_rem - o2_C_used;
      // FeO-driven decarburisation
      const a_FeO = s.feoPct()/100.0;
      let r_FeOC = 0.40*a_FeO*Math.max(0.0, wt.C - wC_eq)*m_mt/M.C*0.02;
      r_FeOC = Math.max(0.0, Math.min(r_FeOC, s.sl.FeO/M.FeO/dt, s.mt.C/M.C/dt));
      let rC_total = rC_O2 + r_FeOC;
      const c_avail = s.mt.C/M.C/dt;
      if (rC_total > c_avail) {
        const sc = c_avail/Math.max(rC_total, 1e-12);
        rC_O2*=sc; r_FeOC*=sc; rC_total = c_avail; o2_C_used = rC_O2/2.0;
      }
      // remaining O2 -> Fe oxidation (FeO build)
      let o2_Fe = Math.max(0.0, nO2_rem2);
      let rFe = 2.0*o2_Fe;
      rFe = Math.max(0.0, Math.min(rFe, s.mt.Fe/M.Fe/dt));
      // P and Cr
      const B = s.basicityB3();
      const deP = clip((B-1.5)/2.0,0.0,1.0)*clip(a_FeO/0.20,0.0,1.5)*clip((1900.0-s.T_mt)/250.0,0.0,1.0);
      let rP = c.k_p*deP*s.mt.P/M.P; rP = Math.max(0.0, Math.min(rP, s.mt.P/M.P/dt));
      let rCr = c.k_cr*clip(a_FeO/0.15,0.0,1.2)*s.mt.Cr/M.Cr;
      rCr = Math.max(0.0, Math.min(rCr, s.mt.Cr/M.Cr/dt));
      // apply mass changes
      s.mt.Si -= rSi*M.Si*dt; s.mt.Mn -= rMn*M.Mn*dt; s.mt.C -= rC_total*M.C*dt;
      s.mt.Fe -= rFe*M.Fe*dt; s.mt.P -= rP*M.P*dt; s.mt.Cr -= rCr*M.Cr*dt;
      s.sl.FeO -= r_FeOC*M.FeO*dt; s.mt.Fe += r_FeOC*M.Fe*dt;
      MT_EL.forEach(k => s.mt[k] = Math.max(0.0, s.mt[k]));
      s.sl.SiO2 += rSi*M.SiO2*dt; s.sl.MnO += rMn*M.MnO*dt; s.sl.FeO += rFe*M.FeO*dt;
      s.sl.P2O5 += rP*0.5*M.P2O5*dt; s.sl.Cr2O3 += rCr*0.5*M.Cr2O3*dt;
      SL_OX.forEach(k => s.sl[k] = Math.max(0.0, s.sl[k]));
      // CO generation + Boudouard
      let nCO_gen = rC_total;
      let r_boud = Math.min(c_boud_avail/dt/M.C, 0.4*nCO_gen);
      r_boud = Math.max(0.0, r_boud); nCO_gen += 2.0*r_boud;
      // heat of reaction
      const Q_Si=-DH.Si_O2*rSi, Q_Mn=-DH.Mn_O2*rMn, Q_C=-DH.C_O2_CO*rC_O2;
      const Q_Fe=-DH.Fe_O2*rFe, Q_P=-DH.P_O2*rP, Q_Cr=-DH.Cr_O2*rCr;
      const Q_FeOC=DH.FeO_C*r_FeOC, Q_boud=DH.C_boud*r_boud;
      const Q_exo_bath = Q_Si+Q_Mn+Q_C+Q_Fe+Q_P+Q_Cr;
      const Q_endo_bath = Q_FeOC+Q_boud;
      // post-combustion
      const nO2_pc = o2_pc*NM3_TO_MOL, nCO_avail = nCO_gen;
      let nCO2_pc = Math.min(nCO_avail, 2.0*nO2_pc);
      nCO2_pc = Math.max(0.0, Math.min(nCO2_pc, c.postcomb_ratio_target*nCO_avail + 1e-9));
      const Q_pc = -DH.CO_O2_CO2*nCO2_pc;
      // burner
      const nCH4 = ng*NM3_TO_MOL, Q_burn = -DH.CH4_comb*nCH4;
      const pc_return = c.postcomb_heat_recovery*(Q_pc + Q_burn);
      const E_chem_rate = Q_exo_bath + Q_pc + Q_burn;
      // gas products leaving
      let nCO_out = Math.max(0.0, nCO_gen - nCO2_pc);
      let nCO2_out = nCO2_pc + nCH4;
      const nH2O_out = 2.0*nCH4;
      let nO2_out = Math.max(0.0, nO2_pc - 0.5*nCO2_pc);
      const n_leak = c.leak_air_rate*NM3_TO_MOL;
      const nN2_out = 0.79*n_leak, nO2_leak = 0.21*n_leak;
      const nCO2_leak = Math.min(nCO_out, 2.0*nO2_leak*0.5);
      nCO_out -= nCO2_leak; nCO2_out += nCO2_leak;
      nO2_out += Math.max(0.0, nO2_leak - 0.5*nCO2_leak);
      const Q_CO_chem_out = Math.abs(DH.CO_O2_CO2)*nCO_out;
      // accumulate off-gas
      s.offgas_mol.CO += nCO_out*dt; s.offgas_mol.CO2 += nCO2_out*dt;
      s.offgas_mol.O2 += nO2_out*dt; s.offgas_mol.N2 += nN2_out*dt;
      s.offgas_mol.H2O += nH2O_out*dt;
      const flux = {
        rC_total_kgps:rC_total*M.C, rSi_kgps:rSi*M.Si, rMn_kgps:rMn*M.Mn,
        rFe_kgps:rFe*M.Fe, decarb_pct_per_min:(rC_total*M.C/m_mt)*100.0*60.0,
        nCO_out, nCO2_out, PCR:nCO2_out/Math.max(1e-9, nCO_out+nCO2_out)
      };
      return {
        Q_bath:Q_exo_bath, Q_endo_bath, E_chem_rate, Q_CO_chem_out, pc_return,
        gas_out_mol:{CO:nCO_out, CO2:nCO2_out, O2:nO2_out, N2:nN2_out, H2O:nH2O_out},
        gas_sensible_src:nCO_gen, flux
      };
    }
    // ---- gas energy ----
    gasEnergy(chem, P_wall_rad, q_panel, dt) {
      const c = this.cfg, s = this.state, gas = chem.gas_out_mol;
      let n_tot = 0, cpsum = 0;
      Object.keys(gas).forEach(g => { n_tot += gas[g]; cpsum += gas[g]*CP_GAS[g]; });
      const cp_mol = cpsum/Math.max(1e-9, n_tot), Ccp = n_tot*cp_mol;
      const Q_evolve = n_tot*cp_mol*(s.T_mt - c.offgas_ref_temp)*0.55;
      const Q_pc_complement = (1.0/Math.max(c.postcomb_heat_recovery,1e-6) - 1.0)*chem.pc_return;
      const Q_gas_src = Q_evolve + Q_pc_complement;
      let T_g_eq = Ccp > 1e-6 ? (c.offgas_ref_temp + Q_gas_src/Ccp) : s.T_g;
      T_g_eq = clip(T_g_eq, K(900), K(1650));
      const q_offgas = Ccp*Math.max(0.0, s.T_g - c.offgas_ref_temp);
      return [q_offgas, T_g_eq, chem.pc_return];
    }
    // ---- master timestep ----
    step() {
      const c = this.cfg, s = this.state, dt = c.dt;
      const A_bath = this.bathArea(), foam = this.foamCoverage();
      const inp = this.inputsActive();
      const flux_dict = {};
      // (a) charging
      if (inp.feed > 0) {
        const comp = c.scrap_comp, add = inp.feed*dt;
        s.scrap_fed += add; s.mass_in_cum += add;
        const g_SiO2 = c.scrap_gangue_SiO2*add, g_Al2O3 = c.scrap_gangue_Al2O3*add;
        const g_CaO = c.scrap_gangue_CaO*add, g_MgO = c.scrap_gangue_MgO*add;
        const m_rust = c.scrap_rust_FeO*add, m_h2o = c.scrap_moisture*add;
        const burden = g_SiO2+g_Al2O3+g_CaO+g_MgO+m_rust+m_h2o;
        const m_metal = Math.max(0.0, add - burden);
        this.addScrap(m_metal, comp);
        const cc = c.carbon_charge_total*(add/c.total_scrap_mass);
        s.sc.C += cc; s.mass_in_cum += cc;
        s.sf.SiO2 += g_SiO2; s.sf.Al2O3 += g_Al2O3; s.sf.CaO += g_CaO; s.sf.MgO += g_MgO;
        s.sl.FeO += m_rust; s.offgas_mol.H2O += m_h2o/M.H2O;
      }
      if (inp.flux > 0) { this.addFlux(inp.flux*dt); s.mass_in_cum += inp.flux*dt; }
      // injected carbon
      const c_inj_add = inp.cinj*dt;
      s.carbon_fed += c_inj_add; s.mass_in_cum += c_inj_add;
      s.mt.C += 0.06*c_inj_add;
      const c_for_boud = 0.94*c_inj_add;
      // (b) arc power
      const m_sc = s.massSc(), P_arc = this.arcPower();
      const rem = Math.max(0.0, 1.0 - c.arc_to_bath_frac - c.arc_to_scrap_frac - c.arc_to_slag_frac);
      const shield = c.foam_shielding*foam;
      const P_wall_rad = P_arc*rem*(1.0 - shield);
      const P_bath = P_arc*(c.arc_to_bath_frac + rem*shield);
      const P_scrap = m_sc > 1e-3 ? P_arc*c.arc_to_scrap_frac : 0.0;
      const P_slag = P_arc*c.arc_to_slag_frac;
      s.E_elec += P_arc/Math.max(c.arc_efficiency,1e-6)*dt;
      // (c) melting
      let melt_rate = 0.0, Q_bath_sc = 0.0;
      const T_liq = 1809.0, cp_sc = CP.steel_solid;
      if (m_sc > 1e-3) {
        const A_sc = Math.min(A_bath, m_sc/(c.scrap_bulk_density*0.5));
        Q_bath_sc = c.h_bath_scrap*A_sc*Math.max(0.0, s.T_mt - s.T_sc);
        Q_bath_sc = Math.min(Q_bath_sc, 1.15*P_bath);
        const Q_sc_in = Q_bath_sc + P_scrap, f_warm = 0.12;
        const L_eff = cp_sc*Math.max(50.0, T_liq - s.T_sc) + L_FUS_STEEL;
        melt_rate = c.k_scrap_melt*(1.0 - f_warm)*Q_sc_in/L_eff;
        melt_rate = Math.min(melt_rate, m_sc/dt);
        const dT_sc = f_warm*Q_sc_in/Math.max(1.0, m_sc*cp_sc);
        s.T_sc += dT_sc*dt; s.T_sc = Math.min(s.T_sc, T_liq);
      }
      if (melt_rate > 0) this.meltTransfer(melt_rate*dt);
      // (d) chemistry
      const chem = this.chemistry(inp.o2_lance, inp.o2_pc, inp.ng, c_for_boud, A_bath, dt);
      Object.assign(flux_dict, chem.flux);
      // (e) slag formation
      const Q_slag_diss = this.dissolveFlux(dt);
      // (f) heat transfer
      const A_ms = A_bath, A_sw = this.wallArea();
      const Q_mt_sl = c.h_metal_slag*A_ms*(s.T_mt - s.T_sl);
      const Q_sl_wall = c.h_slag_wall*A_sw*(s.T_sl - s.T_wall);
      const Q_surf_roof = c.emissivity_slag*SIGMA*A_bath*(Math.pow(Math.max(s.T_sl,300.0),4)-Math.pow(s.T_roof,4));
      const [q_wall_loss, shell_T] = this.refractoryLoss(s.T_wall, A_sw + A_bath);
      s.shell_temp = shell_T;
      const P_arc_to_panel = 0.70*P_wall_rad;
      const [q_panel, Two, Tp] = this.panelLoss(P_arc_to_panel, s.T_g);
      s.T_water_out = Two; s.T_roof = Tp;
      // (g) gas energy
      const [q_offgas, T_g_new, pc_return] = this.gasEnergy(chem, P_wall_rad, q_panel, dt);
      s.T_g += clip(T_g_new - s.T_g, -60.0, 60.0);
      // (h) assemble energy balances
      const Q_rxn_bath = chem.Q_bath + pc_return;
      const m_mt = Math.max(1.0, s.massMt()), C_mt = m_mt*CP.steel_liquid;
      const Q_mt = P_bath + 0.85*Q_rxn_bath - Q_mt_sl - Q_bath_sc - chem.Q_endo_bath;
      const dT_mt = Q_mt/C_mt;
      const m_sl = Math.max(1.0, s.massSl()), C_sl = m_sl*CP.slag_liquid;
      const Q_sl = P_slag + 0.15*Q_rxn_bath + Q_mt_sl - Q_sl_wall - Q_surf_roof - Q_slag_diss;
      const dT_sl = Q_sl/C_sl;
      const C_wall = 9.0e7, Q_wall = Q_sl_wall - q_wall_loss, dT_wall = Q_wall/C_wall;
      // (i) integrate
      s.T_mt += dT_mt*dt; s.T_sl += dT_sl*dt; s.T_wall += dT_wall*dt;
      s.T_mt = clip(s.T_mt, 1450.0, 2100.0);
      s.T_sl = clip(s.T_sl, 1350.0, 2100.0);
      s.T_wall = clip(s.T_wall, 800.0, 2000.0);
      // (j) ledger
      s.E_chem += (chem.E_chem_rate + chem.Q_CO_chem_out)*dt;
      s.E_offgas += (q_offgas + chem.Q_CO_chem_out)*dt;
      s.E_water += q_panel*dt; s.E_shell += q_wall_loss*dt;
      s.o2_used += (inp.o2_lance + inp.o2_pc)*dt; s.ng_used += inp.ng*dt;
      s.mass_in_cum += (inp.o2_lance + inp.o2_pc)*NM3_TO_MOL*M.O2*dt;
      s.mass_in_cum += c.leak_air_rate*NM3_TO_MOL*(0.21*M.O2 + 0.79*M.N2)*dt;
      s.mass_in_cum += inp.ng*NM3_TO_MOL*M.CH4*dt;
      // (k) events + snapshot
      s.t += dt; this.detectEvents();
      this.snapshot(flux_dict, chem, q_wall_loss, q_panel, q_offgas, P_arc, foam);
      // (l) tap
      if (!s.tapped && s.massSc() < 0.01*c.total_scrap_mass && s.T_mt >= c.tap_temperature
          && s.wtMt().C <= c.tap_carbon*1.5 && s.scrap_fed >= 0.98*c.total_scrap_mass) {
        this.tap();
      }
      return !s.tapped && s.t < c.t_end;
    }
    detectEvents() {
      const s = this.state, c = this.cfg, f = this._flags, wt = s.wtMt();
      [25,50,75,100].forEach(pct => {
        const key = "fed"+pct;
        if (!f[key] && s.scrap_fed >= pct/100.0*c.total_scrap_mass - 1) {
          f[key] = true;
          this._log(s.t, `CHARGE ${pct}%`,
            `${(s.scrap_fed/1e3).toFixed(1)} t scrap fed ` +
            `(${(s.massSc()/1e3).toFixed(1)} t solid in bath).`, "charge");
        }
      });
      if (!f.flatbath && s.massSc() < 0.06*c.total_scrap_mass && s.scrap_fed > 0.4*c.total_scrap_mass) {
        f.flatbath = true;
        this._log(s.t, "FLAT BATH",
          `Solid scrap < 6%; T=${(s.T_mt-273.15).toFixed(0)} C, C=${(wt.C*100).toFixed(3)}%.`, "milestone");
      }
      if (!f.foam && this.foamCoverage() > 0.6) {
        f.foam = true;
        this._log(s.t, "FOAMY SLAG",
          `Foam coverage > 60% (FeO ${s.feoPct().toFixed(1)}%, B3 ${s.basicityB3().toFixed(2)}).`, "slag");
      }
      if (!f.clow && wt.C < 0.10/100.0 && s.scrap_fed > 0.5*c.total_scrap_mass) {
        f.clow = true;
        this._log(s.t, "LOW CARBON",
          `[C] below 0.10% -> mass-transfer-limited decarburisation.`, "chem");
      }
      if (!f.taptemp && s.T_mt >= c.tap_temperature) {
        f.taptemp = true;
        this._log(s.t, "TAP TEMP",
          `Bath reached tap temperature ${(c.tap_temperature-273.15).toFixed(0)} C.`, "milestone");
      }
    }
    tap() {
      const s = this.state, c = this.cfg;
      s.tapped = true;
      s.E_slag = s.massSl()*CP.slag_liquid*(s.T_sl - c.offgas_ref_temp);
      this._log(s.t, "TAP",
        `Tapped ${(s.massMt()/1e3).toFixed(1)} t at ${(s.T_mt-273.15).toFixed(0)} C, ` +
        `[C]=${(s.wtMt().C*100).toFixed(3)}%, [P]=${(s.wtMt().P*100).toFixed(4)}%.`, "milestone");
    }
    snapshot(flux, chem, q_wall, q_panel, q_offgas, P_arc, foam) {
      const s = this.state, wt = s.wtMt(), wsl = s.wtSl(), m_liq = s.massMt();
      this.history.push({
        t:s.t, t_min:s.t/60.0,
        T_metal:s.T_mt-273.15, T_slag:s.T_sl-273.15, T_scrap:s.T_sc-273.15,
        T_gas:s.T_g-273.15, T_roof:s.T_roof-273.15, T_wall_hotface:s.T_wall-273.15,
        T_shell:s.shell_temp-273.15, T_water_out:s.T_water_out-273.15,
        m_metal:m_liq/1e3, m_scrap_solid:s.massSc()/1e3, m_slag:s.massSl()/1e3,
        m_slag_formers_solid:s.massSf()/1e3, scrap_fed:s.scrap_fed/1e3,
        C_pct:wt.C*100.0, Si_pct:wt.Si*100.0, Mn_pct:wt.Mn*100.0,
        P_pct:wt.P*100.0, Cr_pct:wt.Cr*100.0,
        slag_CaO:wsl.CaO*100.0, slag_SiO2:wsl.SiO2*100.0, slag_MgO:wsl.MgO*100.0,
        slag_FeO:wsl.FeO*100.0, slag_MnO:wsl.MnO*100.0, slag_Al2O3:wsl.Al2O3*100.0,
        slag_P2O5:wsl.P2O5*100.0,
        basicity_B2:s.basicity(), basicity_B3:s.basicityB3(), FeO_pct:s.feoPct(),
        foam_coverage:foam,
        P_arc_MW:P_arc/1e6, P_chem_MW:chem.E_chem_rate/1e6,
        Q_offgas_MW:q_offgas/1e6, Q_water_MW:q_panel/1e6, Q_shell_MW:q_wall/1e6,
        E_elec_kWh:s.E_elec/3.6e6, E_chem_kWh:s.E_chem/3.6e6,
        E_offgas_kWh:s.E_offgas/3.6e6, E_water_kWh:s.E_water/3.6e6,
        E_shell_kWh:s.E_shell/3.6e6,
        SEC_elec_kWh_t:(s.E_elec/3.6e6)/Math.max(0.1, m_liq/1e3),
        SEC_total_kWh_t:((s.E_elec+s.E_chem)/3.6e6)/Math.max(0.1, m_liq/1e3),
        decarb_rate:flux.decarb_pct_per_min||0.0, PCR:flux.PCR||0.0,
        O2_Nm3:s.o2_used, carbon_inj_kg:s.carbon_fed, lime_fed_t:s.lime_fed/1e3
      });
    }
    run(progress) {
      let cont = true, n = 0;
      while (cont) {
        cont = this.step(); n++;
        if (progress && n % 40 === 0) progress(Math.min(1.0, this.state.t/this.cfg.t_end));
      }
      if (!this.state.tapped)
        this._log(this.state.t, "END", "Simulation horizon reached before tap.", "warn");
      return new Result(this);
    }
    // ---- static balance ----
    staticBalance() {
      const c = this.cfg, heel = c.hot_heel_mass, scrap = c.total_scrap_mass, comp = c.scrap_comp;
      const el_in = {};
      [["C",comp.C],["Si",comp.Si],["Mn",comp.Mn],["P",comp.P],["Cr",comp.Cr]].forEach(([e,x]) => {
        el_in[e] = scrap*x + heel*(e==="C"?0.001:0.0005);
      });
      const fe = 1.0-(comp.C+comp.Si+comp.Mn+comp.P+comp.Cr);
      el_in.Fe = scrap*fe + heel*0.995;
      const m_in_metal = heel + scrap, tap_mass = m_in_metal*0.90, tap_C = c.tap_carbon;
      const ox = {
        Si:el_in.Si*0.98, Mn:el_in.Mn*0.70, P:el_in.P*0.85, Cr:el_in.Cr*0.30,
        C:Math.max(0.0, el_in.C + c.carbon_charge_total - tap_mass*tap_C), Fe:m_in_metal*0.02
      };
      const slag = c.lime_total*c.lime_purity_CaO + c.dololime_total*(c.dololime_CaO+c.dololime_MgO)
        + ox.Si*M.SiO2/M.Si + ox.Mn*M.MnO/M.Mn + ox.Fe*M.FeO/M.Fe
        + ox.P*0.5*M.P2O5/M.P + ox.Cr*0.5*M.Cr2O3/M.Cr;
      const E_steel = scrap*(CP.steel_solid*(1809.0-c.scrap_preheat_temp) + L_FUS_STEEL
        + CP.steel_liquid*(c.tap_temperature-1809.0));
      const E_slag = slag*(CP.slag_liquid*(c.tap_temperature-c.ambient_temp) + H_DISS_LIME);
      const E_chem = ox.C*(-DH.C_O2_CO)/M.C + ox.Si*(-DH.Si_O2)/M.Si
        + ox.Mn*(-DH.Mn_O2)/M.Mn + ox.Fe*(-DH.Fe_O2)/M.Fe;
      const E_offgas = 0.22*(E_steel+E_slag), E_cool = 0.10*(E_steel+E_slag);
      const E_demand = E_steel+E_slag+E_offgas+E_cool, E_elec = Math.max(0.0, E_demand - E_chem*0.85);
      return {
        steel_t:tap_mass/1e3, charge_t:m_in_metal/1e3, tap_temp_C:c.tap_temperature-273.15,
        tap_mass_t:tap_mass/1e3, yield_pct:100.0*tap_mass/m_in_metal, slag_mass_t:slag/1e3,
        E_steel_kWh:E_steel/3.6e6, E_slag_kWh:E_slag/3.6e6, E_chem_kWh:E_chem/3.6e6,
        E_offgas_kWh:E_offgas/3.6e6, E_cool_kWh:E_cool/3.6e6,
        E_preheat_kWh:scrap*CP.steel_solid*(c.scrap_preheat_temp-c.ambient_temp)/3.6e6,
        E_elec_demand_kWh:E_elec/3.6e6, SEC_elec_kWh_t:(E_elec/3.6e6)/(tap_mass/1e3),
        SEC_total_kWh_t:((E_elec+E_chem)/3.6e6)/(tap_mass/1e3)
      };
    }
  }

  // ===========================================================================
  //  RESULT
  // ===========================================================================
  class Result {
    constructor(model) {
      this.cfg = model.cfg; this.state = model.state;
      this.history = model.history; this.events = model.events; this.model = model;
    }
    series(key) { return this.history.map(h => h[key]); }
    kpis() {
      const s = this.state, m_liq = s.massMt(), m_liq_t = m_liq/1e3, wt = s.wtMt();
      const tap_time = s.t, E_in = s.E_elec + s.E_chem;
      return {
        heat_id:this.cfg.heat_id, plant:this.cfg.plant_name, furnace_type:this.cfg.furnace_type,
        tapped:s.tapped, tap_to_tap_min:tap_time/60.0, tap_mass_t:m_liq_t,
        tap_temp_C:s.T_mt-273.15, final_C_pct:wt.C*100.0, final_Si_pct:wt.Si*100.0,
        final_Mn_pct:wt.Mn*100.0, final_P_pct:wt.P*100.0, final_Cr_pct:wt.Cr*100.0,
        yield_pct:100.0*m_liq/(this.cfg.hot_heel_mass + s.scrap_fed),
        slag_mass_t:s.massSl()/1e3, slag_basicity_B3:s.basicityB3(), slag_FeO_pct:s.feoPct(),
        E_elec_kWh:s.E_elec/3.6e6, E_chem_kWh:s.E_chem/3.6e6, E_total_kWh:E_in/3.6e6,
        SEC_elec_kWh_t:(s.E_elec/3.6e6)/Math.max(0.1,m_liq_t),
        SEC_total_kWh_t:(E_in/3.6e6)/Math.max(0.1,m_liq_t),
        productivity_t_per_h:m_liq_t/Math.max(1e-6, tap_time/3600.0),
        productivity_t_per_h_per_MW:(m_liq_t/Math.max(1e-6,tap_time/3600.0))/Math.max(1e-6,this.cfg.active_power_max/1e6),
        O2_Nm3_t:s.o2_used/Math.max(0.1,m_liq_t),
        carbon_kg_t:(s.carbon_fed+this.cfg.carbon_charge_total)/Math.max(0.1,m_liq_t),
        lime_kg_t:(s.lime_fed+s.dololime_fed)/Math.max(0.1,m_liq_t),
        offgas_loss_kWh:s.E_offgas/3.6e6, water_loss_kWh:s.E_water/3.6e6, shell_loss_kWh:s.E_shell/3.6e6
      };
    }
    energyBalance() {
      const c = this.cfg, s = this.state, Tamb = c.ambient_temp;
      const steelEnth = (mass, T) => T <= 1809.0
        ? mass*CP.steel_solid*(T-Tamb)
        : mass*(CP.steel_solid*(1809.0-Tamb) + L_FUS_STEEL + CP.steel_liquid*(T-1809.0));
      const m_liq = s.massMt();
      const E_steel = steelEnth(m_liq, s.T_mt)/3.6e6;
      const E_slag = (s.massSl()*(CP.slag_liquid*(s.T_sl-Tamb)+H_DISS_LIME))/3.6e6;
      const H_scrap_in = c.total_scrap_mass*CP.steel_solid*(c.scrap_preheat_temp-Tamb)/3.6e6;
      const H_heel_in = steelEnth(c.hot_heel_mass, c.hot_heel_temp)/3.6e6;
      const inputs = {"Electrical":s.E_elec/3.6e6, "Chemical":s.E_chem/3.6e6,
                      "Scrap preheat":H_scrap_in, "Hot heel":H_heel_in};
      const outputs = {"Steel enthalpy":E_steel, "Slag enthalpy":E_slag,
                       "Off-gas":s.E_offgas/3.6e6, "Cooling water":s.E_water/3.6e6,
                       "Shell/refractory":s.E_shell/3.6e6};
      const tot_in = sumVals(inputs), tot_out = sumVals(outputs);
      outputs["Other/unaccounted"] = tot_in - tot_out;
      return {inputs, outputs, total_in:tot_in, total_out:tot_out,
              closure_pct:100.0*(tot_in-tot_out)/Math.max(1.0,tot_in)};
    }
    massBalance() {
      const s = this.state, m_in = s.m_initial + s.mass_in_cum;
      let offgas_mass = 0; Object.keys(s.offgas_mol).forEach(g => offgas_mass += s.offgas_mol[g]*M[g]);
      const m_out = s.massMt()+s.massSc()+s.massSf()+s.massSl()+offgas_mass;
      const closure = m_in - m_out;
      const metal_in = this.cfg.hot_heel_mass + s.scrap_fed;
      const to_slag = s.sl.SiO2*M.Si/M.SiO2 + s.sl.MnO*M.Mn/M.MnO + s.sl.FeO*M.Fe/M.FeO
        + s.sl.P2O5*2*M.P/M.P2O5 + s.sl.Cr2O3*2*M.Cr/M.Cr2O3;
      const c_to_gas = (s.offgas_mol.CO + s.offgas_mol.CO2)*M.C;
      return {total_in_kg:m_in, total_out_kg:m_out, offgas_mass_kg:offgas_mass,
              closure_kg:closure, closure_pct:100.0*closure/Math.max(1.0,m_in),
              metal_in_kg:metal_in, metal_out_kg:s.massMt(),
              elements_to_slag_kg:to_slag, carbon_to_gas_kg:c_to_gas};
    }
    finalSlag() { return Object.assign({}, this.state.sl); }
  }

  const EAF = {defaultConfig, Model, Result, M, CP, DH, constants:{SIGMA,R_GAS,T_REF,NM3_TO_MOL,L_FUS_STEEL,H_DISS_LIME}};
  if (typeof module !== "undefined" && module.exports) module.exports = EAF;
  root.EAF = EAF;
})(typeof window !== "undefined" ? window : globalThis);
