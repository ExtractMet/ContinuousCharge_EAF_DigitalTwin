"""
================================================================================
 CC-EAF-SIM  |  Continuously-Charged Electric Arc Furnace Steelmaking Simulator
 Extractmet Private Limited  --  first-principles pyrometallurgical process model
================================================================================

A dependency-light (NumPy-only) mechanistic dynamic + static model of a
continuously-charged (Consteel(R)-type, flat-bath immersion-melting) AC/DC
electric-arc-furnace steelmaking reactor.

The formulation follows the multi-zone control-volume approach established for
EAF process models (Bekker et al. 1999; MacRosty & Swartz 2005; Logar, Dovzan &
Skrjanc, ISIJ Int. 52 (2012) 402 / 413 / 1225; Meier 2016; Hay, Reimann &
Echterhof, Metall. Mater. Trans. B 50 (2019) 2377), adapted here for *continuous*
metallic charging under constant flat-bath conditions rather than discrete
bucket charging.

Eight thermally-distinct zones (control volumes), each internally homogeneous in
temperature and composition, exchange mass and energy every time step:

    1  Solid scrap            (sc)   -- fed continuously, melts by immersion
    2  Liquid metal bath      (mt)   -- Fe, C, Si, Mn, P, Cr  (+ dissolved O)
    3  Solid slag formers     (sf)   -- lime / dololime, dissolve into slag
    4  Liquid slag            (sl)   -- CaO SiO2 MgO Al2O3 FeO MnO P2O5 Cr2O3
    5  Gas / freeboard        (g )   -- CO CO2 O2 N2 H2O  (flow-through)
    6  Water-cooled roof+upper wall panels (roof)
    7  Refractory lower wall + hearth  (wall)   -- multilayer conduction to shell
    8  Electrode(s)           (el)

Heat source : electric arc.   Heat sinks : cooling water, refractory shell loss,
off-gas enthalpy.  Coupled conduction-convection-radiation is solved explicitly
for the multilayer refractory (working + safety + insulation + steel shell) and
for the water-cooled panels.

Author  : Extractmet Private Limited
Contact  : www.extractmet.com
License : Commercial (evaluation build).  (c) Extractmet Private Limited.
"""

from __future__ import annotations
import math
import copy
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable

import numpy as np

# =============================================================================
# 0.  PHYSICAL CONSTANTS AND THERMODYNAMIC DATA
# =============================================================================

SIGMA = 5.670374419e-8       # Stefan-Boltzmann constant  [W/m2/K4]
R_GAS = 8.314462618          # universal gas constant      [J/mol/K]
T_REF = 298.15               # reference temperature       [K]
G_ACC = 9.80665              # gravity                     [m/s2]

# ---- molar masses [kg/mol] --------------------------------------------------
M = {
    "Fe": 0.055845, "C": 0.012011, "Si": 0.028085, "Mn": 0.054938,
    "P": 0.030974, "Cr": 0.051996, "O": 0.015999, "O2": 0.031998,
    "Ca": 0.040078, "Mg": 0.024305, "Al": 0.026982,
    "CaO": 0.056077, "MgO": 0.040304, "SiO2": 0.060083, "Al2O3": 0.101961,
    "FeO": 0.071844, "Fe2O3": 0.159687, "MnO": 0.070937, "P2O5": 0.141943,
    "Cr2O3": 0.151990,
    "CO": 0.028010, "CO2": 0.044009, "N2": 0.028014, "H2O": 0.018015,
    "CH4": 0.016043, "H2": 0.002016,
}

# ---- specific heats [J/kg/K] (effective, high-temperature averages) ---------
CP = {
    "steel_solid": 700.0,     # solid scrap (avg 298-1809 K incl. transformations)
    "steel_liquid": 820.0,    # liquid iron/steel
    "slag_solid": 1000.0,     # lime / dololime charge
    "slag_liquid": 1250.0,    # molten oxide slag
    "electrode": 1700.0,      # graphite (very high cp)
    "shell": 490.0,           # carbon-steel shell
    "water": 4186.0,
}

# ---- molar heat capacities of gas species [J/mol/K] (avg ~300-1600 K) -------
CP_GAS = {"CO": 33.0, "CO2": 51.0, "O2": 34.0, "N2": 31.5, "H2O": 41.0,
          "CH4": 55.0, "H2": 30.0}

# ---- phase-change enthalpies [J/kg] -----------------------------------------
L_FUS_STEEL = 272.0e3         # latent heat of fusion of steel
H_DISS_LIME = 210.0e3         # effective dissolution enthalpy of lime into slag

# ---- reaction enthalpies [J per mol of the FIRST listed reactant] -----------
# (negative = exothermic).  Referenced to dissolved species at steelmaking T
# where relevant; values are literature-consistent effective heats.
DH = {
    "C_O2_CO":   -130.0e3,    # [C] + 1/2 O2(g) -> CO(g)          per mol C
    "Si_O2":     -800.0e3,    # [Si] + O2(g) -> (SiO2)            per mol Si
    "Mn_O2":     -362.0e3,    # [Mn] + 1/2 O2(g) -> (MnO)         per mol Mn
    "Fe_O2":     -240.0e3,    # Fe + 1/2 O2(g) -> (FeO)           per mol Fe
    "P_O2":      -600.0e3,    # [P] + 5/4 O2 -> 1/2(P2O5)         per mol P
    "Cr_O2":     -560.0e3,    # [Cr] + 3/4 O2 -> 1/2(Cr2O3)       per mol Cr
    "CO_O2_CO2": -283.0e3,    # CO(g) + 1/2 O2(g) -> CO2(g)       per mol CO
    "CH4_comb":  -802.0e3,    # CH4 + 2 O2 -> CO2 + 2 H2O(g)      per mol CH4  (LHV)
    "FeO_C":     +110.0e3,    # (FeO) + [C] -> Fe + CO(g)         per mol C  (endo)
    "C_boud":    +172.0e3,    # C(s) + CO2 -> 2 CO(g)             per mol C  (endo)
}

# ---- oxide -> element mass factors ------------------------------------------
def _oxfac(el, ox, n_el, n_ox):
    """kg element per kg oxide."""
    return n_el * M[el] / M[ox]

# =============================================================================
# 1.  CONFIGURATION
# =============================================================================

@dataclass
class Composition:
    """Elemental mass fractions of a metallic stream (balance = Fe)."""
    C: float = 0.0020
    Si: float = 0.0025
    Mn: float = 0.0035
    P: float = 0.0006
    Cr: float = 0.0015

    def fe(self) -> float:
        return max(0.0, 1.0 - (self.C + self.Si + self.Mn + self.P + self.Cr))


@dataclass
class RefractoryLayer:
    name: str
    thickness: float     # [m]
    k: float             # thermal conductivity [W/m/K]


@dataclass
class EAFConfig:
    """Complete furnace + operating configuration for one heat."""

    # ---- identity -----------------------------------------------------------
    plant_name: str = "Industry-X"
    heat_id: str = "H-000001"
    furnace_type: str = "AC"                # "AC" or "DC"

    # ---- geometry -----------------------------------------------------------
    shell_inner_diameter: float = 6.0       # [m]
    bath_depth_full: float = 0.60           # [m] liquid depth at nominal bath
    freeboard_height: float = 2.60          # [m] slag line to roof
    roof_area_factor: float = 1.12          # domed roof area / bath area

    # ---- charge programme (continuous) --------------------------------------
    hot_heel_mass: float = 40.0e3           # [kg] liquid heel retained at start
    hot_heel_temp: float = 1550.0 + 273.15  # [K]
    total_scrap_mass: float = 110.0e3       # [kg] scrap fed over the heat
    scrap_feed_rate: float = 45.0           # [kg/s] nominal conveyor feed rate
    scrap_preheat_temp: float = 420.0 + 273.15   # [K] Consteel preheat (400-600 C)
    scrap_comp: Composition = field(default_factory=lambda: Composition(
        C=0.0025, Si=0.0030, Mn=0.0040, P=0.0004, Cr=0.0020))
    scrap_bulk_density: float = 1100.0      # [kg/m3] loose scrap in bath region
    # Non-metallic burden riding in with the "as-weighed" scrap (mass frac of
    # charge).  This is the DOMINANT metallic-yield loss channel: real scrap is
    # weighed wet & dirty, so dirt (silica/alumina), adhering rust (FeO) and
    # moisture do not become liquid steel.  Total burden ~6-7 wt% here gives a
    # metallic yield of ~90-93 % (literature 88-93 %).  The silica seed also sets
    # binary basicity B2 = CaO/SiO2 to 1.8-2.5.  (Gangue in metallics is reported
    # at 3.9-8.4 wt%, IIMA DRI factsheet.)
    scrap_gangue_SiO2: float = 0.0180       # [-] SiO2 dirt per kg scrap
    scrap_gangue_Al2O3: float = 0.0070      # [-] Al2O3 dirt per kg scrap
    scrap_gangue_CaO: float = 0.0050        # [-] CaO dirt per kg scrap
    scrap_gangue_MgO: float = 0.0025        # [-] MgO dirt per kg scrap
    scrap_rust_FeO: float = 0.0120          # [-] adhering rust (FeO) -> slag
    scrap_moisture: float = 0.0190          # [-] moisture -> H2O vapour off-gas

    # ---- fluxes / additions -------------------------------------------------
    lime_total: float = 4.3e3               # [kg] CaO-rich lime over heat (~30 kg/t)
    dololime_total: float = 2.0e3           # [kg] MgO-CaO dololime over heat
    lime_purity_CaO: float = 0.92
    dololime_CaO: float = 0.58
    dololime_MgO: float = 0.38
    flux_feed_rate: float = 4.0             # [kg/s] flux dosing while active

    # ---- electrical ---------------------------------------------------------
    transformer_mva: float = 90.0           # [MVA] rated apparent power
    active_power_max: float = 72.0e6        # [W] max active (real) power to arc
    power_factor: float = 0.78
    arc_efficiency: float = 0.90            # electrical->thermal delivered to furnace

    # ---- chemical inputs ----------------------------------------------------
    o2_lance_rate: float = 1.05             # [Nm3/s] O2 through supersonic lances
    o2_postcomb_rate: float = 0.32          # [Nm3/s] O2 for CO post-combustion
    carbon_inject_rate: float = 0.50        # [kg/s] injected carbon (foaming/recarb)
    carbon_charge_total: float = 0.7e3      # [kg] charge carbon with scrap
    ng_burner_rate: float = 0.0             # [Nm3/s] natural gas (Consteel often 0)
    postcomb_ratio_target: float = 0.35     # target CO2/(CO+CO2) in freeboard
    postcomb_heat_recovery: float = 0.55    # fraction of PC heat returned to charge

    # ---- refractory (hot face -> shell), lower wall + hearth ----------------
    refractory: List[RefractoryLayer] = field(default_factory=lambda: [
        RefractoryLayer("MgO-C working lining", 0.450, 14.0),
        RefractoryLayer("Magnesia safety lining", 0.180, 4.5),
        RefractoryLayer("Insulating board", 0.030, 0.25),
        RefractoryLayer("Carbon-steel shell", 0.050, 45.0),
    ])
    shell_emissivity: float = 0.80
    ambient_temp: float = 30.0 + 273.15     # [K]
    h_shell_ambient: float = 12.0           # [W/m2/K] natural+forced convection

    # ---- water-cooled panels (roof + upper wall) ----------------------------
    panel_area: float = 55.0                # [m2] water-cooled surface
    panel_water_flow: float = 260.0         # [kg/s] cooling-water mass flow
    panel_water_inlet: float = 35.0 + 273.15
    panel_hotface_emissivity: float = 0.85
    panel_wall_resistance: float = 0.0016   # [m2K/W] copper+scale to water

    # ---- heat-transfer coefficients [W/m2/K] --------------------------------
    h_metal_slag: float = 6000.0
    h_slag_wall: float = 1200.0
    h_bath_scrap: float = 3500.0            # immersion melting (flat bath)
    h_gas_surface: float = 45.0
    emissivity_bath: float = 0.40
    emissivity_slag: float = 0.60

    # ---- arc power distribution (flat-bath / foamed-slag operation) ---------
    arc_to_bath_frac: float = 0.72          # to liquid metal (immersed/foamed arc)
    arc_to_scrap_frac: float = 0.10         # to solid scrap in feed region
    arc_to_slag_frac: float = 0.08          # to slag
    # remainder radiates to panels/roof; reduced by foam coverage
    foam_shielding: float = 0.75            # 0..1 fraction of wall radiation shielded

    # ---- freeboard / off-gas ------------------------------------------------
    leak_air_rate: float = 2.8              # [Nm3/s] infiltrated air (N2+O2)
    gas_holdup_mol: float = 1200.0          # [mol] effective freeboard inventory
    offgas_ref_temp: float = T_REF

    # ---- kinetics -----------------------------------------------------------
    k_scrap_melt: float = 1.0               # melting-rate multiplier
    k_decarb_mt: float = 6.5e-4             # [m/s] carbon liquid mass-transfer coeff
    c_crit: float = 0.30 / 100.0            # transition [C] frac (mass-frac units)
    k_si: float = 0.020                     # Si oxidation rate constant [1/s-ish]
    k_mn: float = 0.010
    k_p: float = 0.0060
    k_cr: float = 0.0040
    o2_to_carbon_pref: float = 0.62         # O2 fraction preferentially to C at high C
    feo_build_frac: float = 0.30            # O2 fraction to Fe (-> FeO) baseline

    # ---- targets / tapping --------------------------------------------------
    tap_temperature: float = 1620.0 + 273.15    # [K]
    tap_carbon: float = 0.06 / 100.0            # target [C] at tap (mass frac)
    tap_mass_target: float = 150.0e3            # [kg] bath mass to trigger tap window

    # ---- integration --------------------------------------------------------
    dt: float = 0.5                         # [s] time step
    t_end: float = 3600.0                   # [s] max simulated time
    seed: int = 7

    def clone(self) -> "EAFConfig":
        return copy.deepcopy(self)


# convenience: Nm3 -> mol (ideal gas at 0 C, 101.325 kPa)
NM3_TO_MOL = 101325.0 / (R_GAS * 273.15)     # ~ 44.615 mol / Nm3


# =============================================================================
# 2.  STATE
# =============================================================================

class EAFState:
    """
    Mutable state of the reactor.  Masses are in kg; temperatures in K.
    Species are held in flat dictionaries keyed by zone.
    """
    # element / species lists per zone
    MT_EL = ["Fe", "C", "Si", "Mn", "P", "Cr"]
    SC_EL = ["Fe", "C", "Si", "Mn", "P", "Cr"]
    SF_OX = ["CaO", "MgO", "SiO2", "Al2O3"]
    SL_OX = ["CaO", "SiO2", "MgO", "Al2O3", "FeO", "MnO", "P2O5", "Cr2O3"]
    GAS   = ["CO", "CO2", "O2", "N2", "H2O"]

    def __init__(self, cfg: EAFConfig):
        self.cfg = cfg
        # --- masses ---
        self.mt = {e: 0.0 for e in self.MT_EL}
        self.sc = {e: 0.0 for e in self.SC_EL}
        self.sf = {o: 0.0 for o in self.SF_OX}
        self.sl = {o: 0.0 for o in self.SL_OX}
        # --- temperatures ---
        self.T_mt = cfg.hot_heel_temp
        self.T_sc = cfg.scrap_preheat_temp
        self.T_sf = cfg.ambient_temp
        self.T_sl = cfg.hot_heel_temp - 20.0
        self.T_g = 1400.0 + 273.15
        self.T_roof = 350.0 + 273.15
        self.T_wall = 1200.0 + 273.15       # refractory hot-face
        self.T_el = 2500.0 + 273.15
        # --- book-keeping / cumulative ---
        self.t = 0.0
        self.E_elec = 0.0        # [J] cumulative electrical energy to arc
        self.E_chem = 0.0        # [J] cumulative chemical (oxidation+PC+burner) energy
        self.E_offgas = 0.0      # [J] cumulative off-gas enthalpy loss
        self.E_water = 0.0       # [J] cumulative water-cooled panel loss
        self.E_shell = 0.0       # [J] cumulative refractory/shell conduction loss
        self.E_slag = 0.0        # [J] enthalpy tapped in slag (reporting)
        self.scrap_fed = 0.0     # [kg] cumulative scrap charged
        self.lime_fed = 0.0
        self.dololime_fed = 0.0
        self.carbon_fed = 0.0    # injected carbon cumulative
        self.o2_used = 0.0       # [Nm3] cumulative oxygen (lance+PC)
        self.ng_used = 0.0       # [Nm3] cumulative natural gas
        # off-gas cumulative composition (mol)
        self.offgas_mol = {g: 0.0 for g in self.GAS}
        # panel water outlet temperature (reporting)
        self.T_water_out = cfg.panel_water_inlet
        self.shell_temp = 150.0 + 273.15
        self.tapped = False
        # rigorous total-mass conservation trackers
        self.mass_in_cum = 0.0       # [kg] cumulative mass added after t=0
        self.m_initial = 0.0         # [kg] total inventory at t=0

        self._init_charge()
        # snapshot the starting inventory for the conservation check
        self.m_initial = (self.mass_mt() + self.mass_sc()
                          + self.mass_sf() + self.mass_sl())

    # ------------------------------------------------------------------
    def _init_charge(self):
        """Set the initial hot heel (liquid metal + a little starting slag)."""
        c = self.cfg
        comp = Composition(C=0.10/100, Si=0.0, Mn=0.08/100, P=0.010/100, Cr=0.05/100)
        m = c.hot_heel_mass
        self.mt["C"] = m * comp.C
        self.mt["Si"] = m * comp.Si
        self.mt["Mn"] = m * comp.Mn
        self.mt["P"] = m * comp.P
        self.mt["Cr"] = m * comp.Cr
        self.mt["Fe"] = m - sum(self.mt[e] for e in ["C", "Si", "Mn", "P", "Cr"])
        # small residual foamy slag on the heel
        self.sl["CaO"] = 900.0
        self.sl["SiO2"] = 380.0
        self.sl["MgO"] = 260.0
        self.sl["FeO"] = 520.0
        self.sl["MnO"] = 120.0
        self.sl["Al2O3"] = 60.0

    # ---- aggregate helpers -------------------------------------------
    def mass_mt(self) -> float:
        return sum(self.mt.values())

    def mass_sc(self) -> float:
        return sum(self.sc.values())

    def mass_sf(self) -> float:
        return sum(self.sf.values())

    def mass_sl(self) -> float:
        return sum(self.sl.values())

    def wt_mt(self) -> Dict[str, float]:
        m = self.mass_mt()
        if m <= 0:
            return {e: 0.0 for e in self.MT_EL}
        return {e: self.mt[e] / m for e in self.MT_EL}

    def wt_sl(self) -> Dict[str, float]:
        m = self.mass_sl()
        if m <= 0:
            return {o: 0.0 for o in self.SL_OX}
        return {o: self.sl[o] / m for o in self.SL_OX}

    def basicity(self) -> float:
        s = self.sl["SiO2"]
        return (self.sl["CaO"] / s) if s > 1e-6 else 0.0

    def basicity_b3(self) -> float:
        denom = self.sl["SiO2"] + self.sl["Al2O3"]
        return ((self.sl["CaO"] + self.sl["MgO"]) / denom) if denom > 1e-6 else 0.0

    def feo_pct(self) -> float:
        m = self.mass_sl()
        return 100.0 * self.sl["FeO"] / m if m > 1e-6 else 0.0


# =============================================================================
# 3.  MODEL  (dynamic integrator + static balances)
# =============================================================================

class EAFModel:
    """Mechanistic dynamic model of the continuously-charged EAF."""

    def __init__(self, cfg: Optional[EAFConfig] = None):
        self.cfg = cfg or EAFConfig()
        self.state = EAFState(self.cfg)
        self.rng = np.random.default_rng(self.cfg.seed)
        self.history: List[dict] = []      # per-step snapshots (time series)
        self.events: List[dict] = []       # timestamped operational events
        self._last_event_flags = {}
        self._log_event(0.0, "HEAT START",
                        f"Hot heel {self.cfg.hot_heel_mass/1e3:.0f} t at "
                        f"{self.cfg.hot_heel_temp-273.15:.0f} C charged; power on.",
                        category="milestone")

    # ------------------------------------------------------------------
    # geometry helpers
    # ------------------------------------------------------------------
    def _bath_area(self) -> float:
        return math.pi * (self.cfg.shell_inner_diameter ** 2) / 4.0

    def _wall_area(self) -> float:
        return math.pi * self.cfg.shell_inner_diameter * self.cfg.bath_depth_full

    def _foam_coverage(self) -> float:
        """Foamy-slag coverage 0..1 from slag mass & FeO (drives arc shielding)."""
        s = self.state
        m_sl = s.mass_sl()
        cov = 1.0 - math.exp(-m_sl / 4500.0)           # more slag -> more foam
        cov *= (0.6 + 0.4 * math.tanh(s.feo_pct() / 20.0))
        return float(np.clip(cov, 0.0, 1.0))

    # ------------------------------------------------------------------
    # multilayer refractory conduction  (coupled cond-conv-radiation)
    # ------------------------------------------------------------------
    def _refractory_loss(self, T_hotface: float, area: float) -> (float, float):
        """
        1-D quasi-steady heat loss through the multilayer refractory to ambient.
        Series conduction (working + safety + insulation + shell) then outer-surface
        convection + radiation.  Returns (q_loss [W], shell_temp [K]).
        """
        c = self.cfg
        R_cond = sum(L.thickness / (L.k * area) for L in c.refractory)   # [K/W]
        Ta = c.ambient_temp
        # solve shell temperature: conduction flux = surface (conv+rad) flux
        Ts = 0.5 * (T_hotface + Ta)
        for _ in range(40):
            q_cond = (T_hotface - Ts) / R_cond
            q_surf = (c.h_shell_ambient * area * (Ts - Ta)
                      + c.shell_emissivity * SIGMA * area * (Ts ** 4 - Ta ** 4))
            f = q_cond - q_surf
            # derivative wrt Ts
            df = (-1.0 / R_cond) - (c.h_shell_ambient * area
                                    + 4.0 * c.shell_emissivity * SIGMA * area * Ts ** 3)
            Ts_new = Ts - f / df
            if not math.isfinite(Ts_new):
                break
            Ts_new = min(max(Ts_new, Ta), T_hotface)
            if abs(Ts_new - Ts) < 1e-4:
                Ts = Ts_new
                break
            Ts = Ts_new
        q_loss = max(0.0, (T_hotface - Ts) / R_cond)
        return q_loss, Ts

    # ------------------------------------------------------------------
    # water-cooled panel loss (roof + upper wall)
    # ------------------------------------------------------------------
    def _panel_loss(self, P_arc_incident: float, T_gas: float) -> (float, float, float):
        """
        Water-cooled panel (roof + upper wall) heat load, removed by cooling water.
        Physically the panels are loaded by (i) the fraction of arc radiation that
        is *not* shielded by foamy slag and reaches the upper shell, plus (ii)
        radiative + convective exchange with the hot freeboard gas.  This ties the
        panel loss to the arc power (so it scales correctly) rather than letting the
        panels "see" the full bath at bath temperature (which is unphysical).
        Returns (q_panel [W], T_water_out [K], T_panel_hotface [K]).
        """
        c = self.cfg
        A = c.panel_area
        Twi = c.panel_water_inlet
        Tw = Twi + 8.0                      # approx water film temperature
        # (i) intercepted arc radiation
        q_arc = max(0.0, P_arc_incident)
        # (ii) freeboard gas radiation + convection to a view-factor-limited panel
        F_gas = 0.35                        # effective gas->panel view factor
        q_gas = (F_gas * c.panel_hotface_emissivity * SIGMA * A
                 * (max(T_gas, 300.0) ** 4 - Tw ** 4)
                 + c.h_gas_surface * A * max(0.0, T_gas - Tw))
        q_panel = max(0.0, q_arc + max(0.0, q_gas))
        Two = Twi + q_panel / (c.panel_water_flow * CP["water"])
        Tp = Twi + q_panel * c.panel_wall_resistance / A     # hot-face temp
        return q_panel, Two, Tp

    # ------------------------------------------------------------------
    # main derivative + step
    # ------------------------------------------------------------------
    def _inputs_active(self):
        """
        Return current continuous input rates.  The scrap feed rate is *controlled*
        to hold the bath at a melting-phase set-point at (near-)constant power --
        the defining control philosophy of continuous (Consteel-type) charging.
        Once all scrap is charged the furnace enters a short refining phase.
        """
        c, s = self.cfg, self.state
        remaining = max(0.0, c.total_scrap_mass - s.scrap_fed)

        # ---- continuous feed at (near-)constant conveyor rate ----
        # Arc power is modulated (see _arc_power) to hold the bath temperature,
        # matching power to the feed rate -- the Consteel control philosophy of a
        # constant specific energy (kWh/ton/min) at constant flat-bath temperature.
        if remaining > 1.0:
            feed = min(c.scrap_feed_rate, remaining / self.cfg.dt)
            self._T_set = 1560.0 + 273.15        # melting-phase bath set-point
            self._refining = False
        else:
            feed = 0.0
            self._T_set = c.tap_temperature       # refine to tap temperature
            self._refining = True

        # ---- fluxes track scrap feed (charged with the metallics) ----
        flux = c.flux_feed_rate if (s.lime_fed < c.lime_total or
                                    s.dololime_fed < c.dololime_total) else 0.0

        # ---- injected carbon (foaming) : tapers tightly near the [C] target ----
        wC0 = s.wt_mt()["C"]
        c_taper = float(np.clip((wC0 - c.tap_carbon) / 0.0010, 0.0, 1.0))
        cinj = c.carbon_inject_rate * c_taper if s.mass_mt() > 1.0 else 0.0

        # ---- oxygen held high through refining, ramping down only near target ----
        wC = s.wt_mt()["C"]
        o2_scale = float(np.clip((wC - c.tap_carbon) / 0.0015, 0.35, 1.0))
        o2_lance = c.o2_lance_rate * o2_scale
        o2_pc = c.o2_postcomb_rate
        ng = c.ng_burner_rate if s.mass_sc() > 0.05 * c.total_scrap_mass else 0.0
        return feed, flux, cinj, o2_lance, o2_pc, ng

    def step(self):
        c = self.cfg
        s = self.state
        dt = c.dt
        A_bath = self._bath_area()
        foam = self._foam_coverage()

        feed, flux, cinj, o2_lance, o2_pc, ng = self._inputs_active()

        flux_dict = {}   # store fluxes for logging

        # -------------------------------------------------------------
        # (a) CONTINUOUS CHARGING  (mass into solid zones)
        # -------------------------------------------------------------
        if feed > 0:
            comp = c.scrap_comp
            add = feed * dt                          # as-weighed scrap increment
            s.scrap_fed += add
            s.mass_in_cum += add
            # --- split the as-weighed scrap into metallic + non-metallic burden ---
            g_SiO2 = c.scrap_gangue_SiO2 * add
            g_Al2O3 = c.scrap_gangue_Al2O3 * add
            g_CaO = c.scrap_gangue_CaO * add
            g_MgO = c.scrap_gangue_MgO * add
            m_rust = c.scrap_rust_FeO * add           # adhering rust -> slag FeO
            m_h2o = c.scrap_moisture * add            # moisture -> vapour
            burden = g_SiO2 + g_Al2O3 + g_CaO + g_MgO + m_rust + m_h2o
            m_metal = max(0.0, add - burden)          # recoverable metallic mass
            self._add_scrap(m_metal, comp)
            # charge carbon proportional to metallic scrap fed
            cc = c.carbon_charge_total * (add / c.total_scrap_mass)
            s.sc["C"] += cc
            s.mass_in_cum += cc
            # dirt -> solid slag formers
            s.sf["SiO2"] += g_SiO2
            s.sf["Al2O3"] += g_Al2O3
            s.sf["CaO"] += g_CaO
            s.sf["MgO"] += g_MgO
            # adhering rust reports straight to the liquid slag as FeO
            s.sl["FeO"] += m_rust
            # scrap moisture flashes to steam and leaves with the off-gas
            s.offgas_mol["H2O"] += m_h2o / M["H2O"]
        if flux > 0:
            self._add_flux(flux * dt)
            s.mass_in_cum += flux * dt

        # injected carbon (into bath region for foaming / recarburisation)
        c_inj_add = cinj * dt
        s.carbon_fed += c_inj_add
        s.mass_in_cum += c_inj_add
        # a portion dissolves into metal, remainder reacts with slag/gas (foaming)
        s.mt["C"] += 0.06 * c_inj_add
        c_for_boud = 0.94 * c_inj_add     # available for Boudouard / FeO reduction

        # -------------------------------------------------------------
        # (b) ARC POWER distribution (computed before melting)
        # -------------------------------------------------------------
        m_sc = s.mass_sc()
        P_arc = self._arc_power()
        # foam shields wall radiation, returning heat to bath
        rem = max(0.0, 1.0 - c.arc_to_bath_frac - c.arc_to_scrap_frac - c.arc_to_slag_frac)
        shield = c.foam_shielding * foam
        P_wall_rad = P_arc * rem * (1.0 - shield)
        P_bath = P_arc * (c.arc_to_bath_frac + rem * shield)
        P_scrap = P_arc * c.arc_to_scrap_frac if m_sc > 1e-3 else 0.0
        P_slag = P_arc * c.arc_to_slag_frac
        s.E_elec += P_arc / max(c.arc_efficiency, 1e-6) * dt   # electrical input
        flux_dict["P_arc"] = P_arc
        flux_dict["P_bath"] = P_bath
        flux_dict["P_wall_rad"] = P_wall_rad

        # -------------------------------------------------------------
        # (c) SCRAP MELTING (heat-supply-limited immersion melting)
        # -------------------------------------------------------------
        # In flat-bath immersion melting the scrap melts at the metal/scrap
        # interface while the cold core lags.  The melting rate is therefore set by
        # the heat delivered to the scrap divided by the enthalpy required to raise
        # interface material from the bulk scrap temperature to the liquidus and
        # melt it: mdot = Q_to_scrap / (cp*(T_liq - T_scrap) + L).  A small fraction
        # of the heat soaks (warms) the remaining solid.  This self-balances the
        # melting rate against the feed rate (energy-conserving).
        melt_rate = 0.0
        Q_bath_sc = 0.0
        T_liq = 1809.0
        cp_sc = CP["steel_solid"]
        if m_sc > 1e-3:
            A_sc = min(A_bath, m_sc / (c.scrap_bulk_density * 0.5))
            Q_bath_sc = c.h_bath_scrap * A_sc * max(0.0, s.T_mt - s.T_sc)
            # do not drain the bath faster than it can plausibly supply
            Q_bath_sc = min(Q_bath_sc, 1.15 * (P_bath + max(0.0, chem_reserve := 0.0)))
            Q_sc_in = Q_bath_sc + P_scrap
            f_warm = 0.12
            L_eff = cp_sc * max(50.0, T_liq - s.T_sc) + L_FUS_STEEL
            melt_rate = c.k_scrap_melt * (1.0 - f_warm) * Q_sc_in / L_eff
            melt_rate = min(melt_rate, m_sc / dt)
            dT_sc = f_warm * Q_sc_in / max(1.0, m_sc * cp_sc)
            s.T_sc += dT_sc * dt
            s.T_sc = min(s.T_sc, T_liq)              # cannot exceed liquidus as solid
            flux_dict["Q_bath_sc"] = Q_bath_sc
        if melt_rate > 0:
            self._melt_transfer(melt_rate * dt)
        flux_dict["melt_rate"] = melt_rate

        # -------------------------------------------------------------
        # (d) CHEMISTRY  -- oxidation kinetics + thermodynamics
        # -------------------------------------------------------------
        chem = self._chemistry(o2_lance, o2_pc, ng, c_for_boud, A_bath, dt)
        flux_dict.update(chem["flux"])

        # -------------------------------------------------------------
        # (e) SLAG FORMATION -- dissolve solid slag formers into liquid slag
        # -------------------------------------------------------------
        Q_slag_diss = self._dissolve_flux(dt)

        # -------------------------------------------------------------
        # (f) HEAT TRANSFER between zones
        # -------------------------------------------------------------
        A_ms = A_bath
        A_sw = self._wall_area()
        Q_mt_sl = c.h_metal_slag * A_ms * (s.T_mt - s.T_sl)
        Q_sl_wall = c.h_slag_wall * A_sw * (s.T_sl - s.T_wall)
        Q_surf_roof = (c.emissivity_slag * SIGMA * A_bath *
                       (max(s.T_sl, 300.0) ** 4 - s.T_roof ** 4))

        # refractory conduction loss (hot face = wall zone temp)
        q_wall_loss, shell_T = self._refractory_loss(s.T_wall, A_sw + A_bath)
        s.shell_temp = shell_T
        # water-cooled panel loss (roof + upper wall): 70% of un-shielded arc
        # radiation is intercepted by the upper panels, remainder loads refractory
        P_arc_to_panel = 0.70 * P_wall_rad
        q_panel, Two, Tp = self._panel_loss(P_arc_to_panel, s.T_g)
        s.T_water_out = Two
        s.T_roof = Tp

        # -------------------------------------------------------------
        # (g) GAS / OFF-GAS energy balance -> T_g and off-gas loss
        # -------------------------------------------------------------
        q_offgas, T_g_new, pc_return = self._gas_energy(chem, P_wall_rad, q_panel, dt)
        s.T_g += float(np.clip(T_g_new - s.T_g, -60.0, 60.0)) * 1.0

        # -------------------------------------------------------------
        # (h) ASSEMBLE ENERGY BALANCES  (dT/dt for each zone)
        # -------------------------------------------------------------
        # heat of reaction to bath (exothermic oxidation, minus endothermic paths)
        Q_rxn_bath = chem["Q_bath"] + pc_return         # PC/burner recovery to bath
        # metal zone: gains arc + reaction heat; loses heat conducted to scrap
        # (immersion melting), heat to slag, and endothermic reaction heat.  The
        # molten mass has already been mixed in at the liquidus (dilution cooling),
        # so melting is fully accounted without a separate 'melt draw' term.
        m_mt = max(1.0, s.mass_mt())
        C_mt = m_mt * CP["steel_liquid"]
        Q_mt = (P_bath + 0.85 * Q_rxn_bath - Q_mt_sl
                - Q_bath_sc - chem["Q_endo_bath"])
        dT_mt = Q_mt / C_mt

        # slag zone
        m_sl = max(1.0, s.mass_sl())
        C_sl = m_sl * CP["slag_liquid"]
        Q_sl = (P_slag + 0.15 * Q_rxn_bath + Q_mt_sl - Q_sl_wall
                - Q_surf_roof - Q_slag_diss)
        dT_sl = Q_sl / C_sl

        # wall (refractory hot face) zone -- lumped thermal mass
        C_wall = 9.0e7        # [J/K] effective heat capacity of lining hot region
        Q_wall = Q_sl_wall - q_wall_loss
        dT_wall = Q_wall / C_wall

        # electrode -- quasi-steady, weak coupling (report only)
        # gas temperature handled above

        # -------------------------------------------------------------
        # (i) INTEGRATE temperatures (physical; absolute safety bounds only)
        # -------------------------------------------------------------
        s.T_mt += dT_mt * dt
        s.T_sl += dT_sl * dt
        s.T_wall += dT_wall * dt
        s.T_mt = float(np.clip(s.T_mt, 1450.0, 2100.0))
        s.T_sl = float(np.clip(s.T_sl, 1350.0, 2100.0))
        s.T_wall = float(np.clip(s.T_wall, 800.0, 2000.0))

        # -------------------------------------------------------------
        # (j) ACCUMULATE energy ledger
        # -------------------------------------------------------------
        # Chemical input booked at full calorific value: heat liberated in-furnace
        # plus the calorific value of the CO that leaves unburned.  The latter is
        # simultaneously booked as an off-gas loss, so it cancels in the bath
        # balance but appears correctly in the input/off-gas split.
        s.E_chem += (chem["E_chem_rate"] + chem["Q_CO_chem_out"]) * dt
        s.E_offgas += (q_offgas + chem["Q_CO_chem_out"]) * dt
        s.E_water += q_panel * dt
        s.E_shell += q_wall_loss * dt
        s.o2_used += (o2_lance + o2_pc) * dt
        s.ng_used += ng * dt
        # gas-phase mass inputs (for total-mass conservation)
        s.mass_in_cum += (o2_lance + o2_pc) * NM3_TO_MOL * M["O2"] * dt
        s.mass_in_cum += c.leak_air_rate * NM3_TO_MOL * (
            0.21 * M["O2"] + 0.79 * M["N2"]) * dt
        s.mass_in_cum += ng * NM3_TO_MOL * M["CH4"] * dt

        # -------------------------------------------------------------
        # (k) EVENTS + snapshot
        # -------------------------------------------------------------
        s.t += dt
        self._detect_events()
        self._snapshot(flux_dict, chem, q_wall_loss, q_panel, q_offgas, P_arc, foam)

        # -------------------------------------------------------------
        # (l) TAP logic
        # -------------------------------------------------------------
        if (not s.tapped and s.mass_sc() < 0.01 * c.total_scrap_mass
                and s.T_mt >= c.tap_temperature
                and s.wt_mt()["C"] <= c.tap_carbon * 1.5
                and s.scrap_fed >= 0.98 * c.total_scrap_mass):
            self._tap()
        return not s.tapped and s.t < c.t_end

    # ==================================================================
    #  CHARGING / MELTING HELPERS
    # ==================================================================
    def _add_scrap(self, mass: float, comp: Composition):
        """
        Charge a mass increment of (preheated) scrap.  The incoming cold scrap is
        mixed into the scrap zone with enthalpy conservation: fresh preheated scrap
        pulls the bulk scrap temperature down toward the preheat temperature, which
        sustains the bath->scrap driving force for continuous immersion melting.
        """
        s = self.state
        m_old = s.mass_sc()
        s.sc["C"] += mass * comp.C
        s.sc["Si"] += mass * comp.Si
        s.sc["Mn"] += mass * comp.Mn
        s.sc["P"] += mass * comp.P
        s.sc["Cr"] += mass * comp.Cr
        s.sc["Fe"] += mass * comp.fe()
        if m_old + mass > 1e-9:
            s.T_sc = (m_old * s.T_sc + mass * self.cfg.scrap_preheat_temp) \
                / (m_old + mass)

    def _add_flux(self, mass: float):
        """Distribute a mass increment of lime + dololime per their remaining split."""
        c, s = self.cfg, self.state
        rem_lime = max(0.0, c.lime_total - s.lime_fed)
        rem_dolo = max(0.0, c.dololime_total - s.dololime_fed)
        tot = rem_lime + rem_dolo
        if tot <= 1e-9:
            return
        lime = mass * rem_lime / tot
        dolo = mass * rem_dolo / tot
        # lime -> mostly CaO (+ minor SiO2/Al2O3 gangue)
        s.sf["CaO"] += lime * c.lime_purity_CaO
        s.sf["SiO2"] += lime * (1.0 - c.lime_purity_CaO) * 0.6
        s.sf["Al2O3"] += lime * (1.0 - c.lime_purity_CaO) * 0.4
        s.lime_fed += lime
        # dololime -> CaO + MgO
        s.sf["CaO"] += dolo * c.dololime_CaO
        s.sf["MgO"] += dolo * c.dololime_MgO
        s.sf["SiO2"] += dolo * max(0.0, 1 - c.dololime_CaO - c.dololime_MgO) * 0.6
        s.sf["Al2O3"] += dolo * max(0.0, 1 - c.dololime_CaO - c.dololime_MgO) * 0.4
        s.dololime_fed += dolo

    def _melt_transfer(self, dm: float):
        """
        Move dm kg of solid scrap (element-wise) into the liquid metal zone with
        enthalpy-conserving mixing: the newly-molten mass enters at the liquidus
        temperature and mixes with the (hotter) bath, diluting its temperature.
        Latent heat of fusion is charged to the bath separately in the energy
        balance (immersion melting).  This mixing is essential for closure.
        """
        s = self.state
        m_sc = s.mass_sc()
        if m_sc <= 1e-9 or dm <= 0:
            return
        T_enter = 1809.0                    # liquidus [K]
        m_old = s.mass_mt()
        frac = min(1.0, dm / m_sc)
        moved = 0.0
        for e in EAFState.SC_EL:
            trans = s.sc[e] * frac
            s.sc[e] -= trans
            s.mt[e] += trans
            moved += trans
        if m_old + moved > 1e-9:
            # enthalpy mixing (equal cp): T_new = (m_old*T + dm*T_enter)/(m_old+dm)
            s.T_mt = (m_old * s.T_mt + moved * T_enter) / (m_old + moved)

    def _dissolve_flux(self, dt: float) -> float:
        """
        Dissolve solid slag formers into liquid slag (first-order, temperature
        gated).  Returns endothermic dissolution heat drawn from the slag [W].
        """
        s = self.state
        m_sf = s.mass_sf()
        if m_sf <= 1e-6:
            return 0.0
        # dissolution accelerates with slag superheat above ~1450 C
        drive = float(np.clip((s.T_sl - (1450.0 + 273.15)) / 120.0, 0.05, 1.0))
        k_diss = 0.010 * drive          # [1/s]
        dm = min(m_sf, k_diss * m_sf * dt)
        frac = dm / m_sf
        for o in EAFState.SF_OX:
            trans = s.sf[o] * frac
            s.sf[o] -= trans
            s.sl[o] = s.sl.get(o, 0.0) + trans
        Q_diss = dm / dt * H_DISS_LIME       # [W] endothermic
        return Q_diss

    # ==================================================================
    #  ARC POWER
    # ==================================================================
    def _arc_power(self) -> float:
        """
        Delivered arc thermal power [W].  Power is modulated: reduced during heavy
        scrap presence at feed point and slightly stochastic (arc flicker).
        """
        c, s = self.cfg, self.state
        base = c.active_power_max
        # small realistic flicker
        flick = 1.0 + 0.02 * self.rng.standard_normal()
        # ---- closed-loop power controller: hold bath at the active set-point ----
        # full power while the bath is below set-point; sharply reduced once it is
        # reached (excess power would otherwise overheat the flat bath).
        T_set = getattr(self, "_T_set", c.tap_temperature)
        err = T_set - s.T_mt                      # >0 : bath below set-point
        factor = float(np.clip(1.0 + 0.030 * err, 0.12, 1.0))
        base *= factor
        # protect water-cooled panels if they approach critical temperature
        if s.T_roof > (750.0 + 273.15):
            base *= 0.85
        P_delivered = base * flick * c.arc_efficiency
        return max(0.0, P_delivered)

    # ==================================================================
    #  CHEMISTRY  (kinetics + thermodynamics + heat of reaction)
    # ==================================================================
    def _chemistry(self, o2_lance, o2_pc, ng, c_boud_avail, A_bath, dt) -> dict:
        """
        Oxidation of C, Si, Mn, Fe, P, Cr by lanced O2 and slag FeO; post-combustion
        of CO; natural-gas burner combustion; Boudouard reduction.  All rates in
        mol/s unless noted.  Returns heat splits and gas generation.
        """
        c, s = self.cfg, self.state
        wt = s.wt_mt()
        m_mt = max(1.0, s.mass_mt())
        rho_mt = 7000.0                      # liquid steel density [kg/m3]

        # ---- available O2 (mol/s) from lances ----
        nO2 = o2_lance * NM3_TO_MOL          # [mol O2/s]

        # ---- Si oxidation (fast, preferred): [Si]+O2->SiO2 (1 O2 per Si) ----
        rSi = c.k_si * s.mt["Si"] / M["Si"]              # [mol Si/s] kinetic demand
        rSi = max(0.0, rSi)
        o2_Si = rSi * 1.0
        # ---- Mn oxidation: [Mn]+1/2 O2 -> MnO (0.5 O2 per Mn) ----
        rMn = c.k_mn * s.mt["Mn"] / M["Mn"]
        rMn = max(0.0, rMn)
        o2_Mn = rMn * 0.5

        # limit Si+Mn to a share of O2 (they get priority but capped)
        o2_SiMn = o2_Si + o2_Mn
        share_SiMn = min(o2_SiMn, 0.35 * nO2)
        if o2_SiMn > 1e-12:
            sc_ = share_SiMn / o2_SiMn
            rSi *= sc_; rMn *= sc_; o2_Si *= sc_; o2_Mn *= sc_
        nO2_rem = nO2 - (o2_Si + o2_Mn)

        # ---- Carbon oxidation ----
        # O2 offered to carbon = preference fraction of remaining O2
        o2_C = c.o2_to_carbon_pref * nO2_rem
        # mass-transfer capacity (low-C tail): dmC/dt = A*rho*k*(wC-wCeq)
        wC_eq = 0.0
        r_C_mt_kg = A_bath * rho_mt * c.k_decarb_mt * max(0.0, wt["C"] - wC_eq)  # kg/s
        r_C_mt = r_C_mt_kg / M["C"]                    # mol/s
        # carbon burnable by offered O2 (C+1/2 O2 -> CO : 2 mol C per mol O2)
        r_C_by_O2_supply = 2.0 * o2_C
        rC_O2 = min(r_C_by_O2_supply, r_C_mt) if wt["C"] < 3.0 * c.c_crit else r_C_by_O2_supply
        rC_O2 = max(0.0, rC_O2)
        o2_C_used = rC_O2 / 2.0
        nO2_rem2 = nO2_rem - o2_C_used

        # ---- FeO-driven decarburisation: (FeO)+[C]->Fe+CO ----
        # Rate multiplier calibrated so steady-state slag FeO sits in the
        # literature foamy-slag window (12-25 wt%, Pretorius/Marr) rather than
        # being over-reduced.  Lowered 1.6 -> 0.5 per research fine-tuning.
        a_FeO = s.feo_pct() / 100.0
        r_FeOC = 0.40 * a_FeO * max(0.0, wt["C"] - wC_eq) * m_mt / M["C"] * 0.02
        r_FeOC = max(0.0, min(r_FeOC, s.sl["FeO"] / M["FeO"] / dt,
                              s.mt["C"] / M["C"] / dt))
        rC_total = rC_O2 + r_FeOC

        # clamp to available carbon
        c_avail_mol = s.mt["C"] / M["C"] / dt
        if rC_total > c_avail_mol:
            scale = c_avail_mol / max(rC_total, 1e-12)
            rC_O2 *= scale; r_FeOC *= scale; rC_total = c_avail_mol
            o2_C_used = rC_O2 / 2.0

        # ---- remaining O2 -> Fe oxidation (FeO build) + baseline direct ----
        o2_Fe = max(0.0, nO2_rem2) + c.feo_build_frac * 0.0
        rFe = 2.0 * o2_Fe                               # Fe+1/2O2->FeO: 2 Fe per O2
        rFe = max(0.0, min(rFe, s.mt["Fe"] / M["Fe"] / dt))

        # ---- P and Cr : partition-driven relaxation toward slag ----
        B = s.basicity_b3()
        # dephos favoured by high B, high FeO, lower T -> effective rate
        deP_drive = float(np.clip((B - 1.5) / 2.0, 0.0, 1.0)) * \
                    float(np.clip(a_FeO / 0.20, 0.0, 1.5)) * \
                    float(np.clip((1900.0 - s.T_mt) / 250.0, 0.0, 1.0))
        rP = c.k_p * deP_drive * s.mt["P"] / M["P"]
        rP = max(0.0, min(rP, s.mt["P"] / M["P"] / dt))
        rCr = c.k_cr * float(np.clip(a_FeO / 0.15, 0.0, 1.2)) * s.mt["Cr"] / M["Cr"]
        rCr = max(0.0, min(rCr, s.mt["Cr"] / M["Cr"] / dt))

        # ==============================================================
        #  APPLY MASS CHANGES
        # ==============================================================
        # metal losses
        s.mt["Si"] -= rSi * M["Si"] * dt
        s.mt["Mn"] -= rMn * M["Mn"] * dt
        s.mt["C"] -= rC_total * M["C"] * dt
        s.mt["Fe"] -= rFe * M["Fe"] * dt
        s.mt["P"] -= rP * M["P"] * dt
        s.mt["Cr"] -= rCr * M["Cr"] * dt
        # FeO consumed by FeO-C decarb, Fe returned to metal
        s.sl["FeO"] -= r_FeOC * M["FeO"] * dt
        s.mt["Fe"] += r_FeOC * M["Fe"] * dt
        for k in EAFState.MT_EL:
            s.mt[k] = max(0.0, s.mt[k])
        # slag gains oxides
        s.sl["SiO2"] += rSi * M["SiO2"] * dt
        s.sl["MnO"] += rMn * M["MnO"] * dt
        s.sl["FeO"] += rFe * M["FeO"] * dt
        s.sl["P2O5"] += rP * 0.5 * M["P2O5"] * dt        # 2P -> 1 P2O5
        s.sl["Cr2O3"] += rCr * 0.5 * M["Cr2O3"] * dt
        for k in EAFState.SL_OX:
            s.sl[k] = max(0.0, s.sl[k])

        # ---- CO generation (mol/s) from all decarburisation ----
        nCO_gen = rC_total                               # 1 CO per C oxidised
        # ---- Boudouard: injected C + CO2 -> 2CO (endothermic, foaming) ----
        r_boud = min(c_boud_avail / dt / M["C"], 0.4 * nCO_gen)    # mol C/s
        r_boud = max(0.0, r_boud)
        nCO_gen += 2.0 * r_boud

        # ==============================================================
        #  HEAT OF REACTION
        # ==============================================================
        Q_Si = -DH["Si_O2"] * rSi
        Q_Mn = -DH["Mn_O2"] * rMn
        Q_C = -DH["C_O2_CO"] * rC_O2
        Q_Fe = -DH["Fe_O2"] * rFe
        Q_P = -DH["P_O2"] * rP
        Q_Cr = -DH["Cr_O2"] * rCr
        Q_FeOC = DH["FeO_C"] * r_FeOC                    # endothermic (+)
        Q_boud = DH["C_boud"] * r_boud                   # endothermic (+)
        Q_exo_bath = Q_Si + Q_Mn + Q_C + Q_Fe + Q_P + Q_Cr   # [W]
        Q_endo_bath = Q_FeOC + Q_boud                        # [W] (drawn from bath)

        # ---- POST-COMBUSTION : CO + 1/2 O2 -> CO2 (freeboard) ----
        nO2_pc = o2_pc * NM3_TO_MOL
        # CO available in freeboard = generated CO this step (flow basis)
        nCO_avail = nCO_gen
        nCO2_pc = min(nCO_avail, 2.0 * nO2_pc)           # 1 CO per 1/2 O2 -> 2 CO per O2
        nCO2_pc = max(0.0, min(nCO2_pc, c.postcomb_ratio_target * nCO_avail + 1e-9))
        Q_pc = -DH["CO_O2_CO2"] * nCO2_pc                # [W]

        # ---- BURNER : CH4 + 2 O2 -> CO2 + 2 H2O ----
        nCH4 = ng * NM3_TO_MOL
        Q_burn = -DH["CH4_comb"] * nCH4

        # heat returned to charge/bath from freeboard reactions
        pc_return = c.postcomb_heat_recovery * (Q_pc + Q_burn)

        # ---- chemical energy input rate (heat actually liberated in-furnace) ----
        E_chem_rate = Q_exo_bath + Q_pc + Q_burn

        # ---- gas products (mol/s) leaving freeboard ----
        nCO_out = max(0.0, nCO_gen - nCO2_pc)
        nCO2_out = nCO2_pc + nCH4
        nH2O_out = 2.0 * nCH4
        nO2_out = max(0.0, nO2_pc - 0.5 * nCO2_pc)       # unreacted PC O2
        # leak air
        n_leak = c.leak_air_rate * NM3_TO_MOL
        nN2_out = 0.79 * n_leak
        nO2_leak = 0.21 * n_leak
        # leak O2 can also post-combust a little CO
        nCO2_leak = min(nCO_out, 2.0 * nO2_leak * 0.5)
        nCO_out -= nCO2_leak
        nCO2_out += nCO2_leak
        nO2_out += max(0.0, nO2_leak - 0.5 * nCO2_leak)

        # ---- chemical energy leaving as UNBURNED CO (mol/s * 283 kJ/mol) ----
        # The CO that exits the furnace carries its unrealised CO->CO2 combustion
        # enthalpy up the off-take.  Under the full-calorific-value convention this
        # is counted as part of the chemical energy made available by the carbon
        # AND as an off-gas loss (it never heats the bath), so the bath energy
        # balance is unchanged while the input/off-gas split matches plant data
        # (off-gas ~15-25 % of purchased energy; total ~570 kWh/t).
        Q_CO_chem_out = abs(DH["CO_O2_CO2"]) * nCO_out          # [W]

        # accumulate off-gas composition
        s.offgas_mol["CO"] += nCO_out * dt
        s.offgas_mol["CO2"] += nCO2_out * dt
        s.offgas_mol["O2"] += nO2_out * dt
        s.offgas_mol["N2"] += nN2_out * dt
        s.offgas_mol["H2O"] += nH2O_out * dt

        flux = {
            "rC_total_kgps": rC_total * M["C"],
            "rSi_kgps": rSi * M["Si"],
            "rMn_kgps": rMn * M["Mn"],
            "rFe_kgps": rFe * M["Fe"],
            "decarb_pct_per_min": (rC_total * M["C"] / m_mt) * 100.0 * 60.0,
            "nCO_out": nCO_out, "nCO2_out": nCO2_out,
            "PCR": (nCO2_out) / max(1e-9, nCO_out + nCO2_out),
        }
        return {
            "Q_bath": Q_exo_bath,          # exothermic to bath (before endo)
            "Q_endo_bath": Q_endo_bath,    # endothermic drawn from bath
            "E_chem_rate": E_chem_rate,    # heat liberated in-furnace
            "Q_CO_chem_out": Q_CO_chem_out,  # unburned-CO calorific value leaving
            "pc_return": pc_return,
            "gas_out_mol": {
                "CO": nCO_out, "CO2": nCO2_out, "O2": nO2_out,
                "N2": nN2_out, "H2O": nH2O_out},
            "gas_sensible_src": nCO_gen,   # generated at bath T
            "flux": flux,
        }

    # ==================================================================
    #  GAS / OFF-GAS ENERGY BALANCE
    # ==================================================================
    def _gas_energy(self, chem, P_wall_rad, q_panel, dt):
        """
        Lumped freeboard gas energy balance -> gas temperature & off-gas enthalpy
        loss.  Off-gas carries sensible enthalpy above reference temperature.
        """
        c, s = self.cfg, self.state
        gas = chem["gas_out_mol"]
        n_tot = sum(gas.values())
        cp_mol = sum(gas[g] * CP_GAS[g] for g in gas) / max(1e-9, n_tot)  # J/mol/K
        Ccp = n_tot * cp_mol                                             # [W/K]
        # Heat available to heat the off-gas stream from reference to T_g:
        #  - sensible heat carried by gases evolving at bath temperature
        #  - the non-recovered fraction of post-combustion + burner heat
        Q_evolve = n_tot * cp_mol * (s.T_mt - c.offgas_ref_temp) * 0.55
        Q_pc_to_gas = (1.0 - c.postcomb_heat_recovery) * chem["pc_return"] \
            / max(c.postcomb_heat_recovery, 1e-6) * c.postcomb_heat_recovery
        # (pc_return already = recovery*(Q_pc+Q_burn); the complementary part heats gas)
        Q_pc_complement = (1.0 / max(c.postcomb_heat_recovery, 1e-6) - 1.0) \
            * chem["pc_return"]
        Q_gas_src = Q_evolve + Q_pc_complement
        T_g_eq = (c.offgas_ref_temp + Q_gas_src / Ccp) if Ccp > 1e-6 else s.T_g
        T_g_eq = float(np.clip(T_g_eq, 900.0 + 273.15, 1650.0 + 273.15))
        # off-gas enthalpy leaving the furnace at current gas temperature
        q_offgas = Ccp * max(0.0, s.T_g - c.offgas_ref_temp)
        return q_offgas, T_g_eq, chem["pc_return"]

    # ==================================================================
    #  EVENTS
    # ==================================================================
    def _log_event(self, t, label, detail, category="info"):
        self.events.append({
            "t": t, "time_str": _fmt_time(t), "label": label,
            "detail": detail, "category": category,
        })

    def _detect_events(self):
        s, c = self.state, self.cfg
        flags = self._last_event_flags
        wt = s.wt_mt()
        # 25/50/75/100 % scrap fed
        for pct in (25, 50, 75, 100):
            key = f"fed{pct}"
            if key not in flags and s.scrap_fed >= pct / 100.0 * c.total_scrap_mass - 1:
                flags[key] = True
                self._log_event(s.t, f"CHARGE {pct}%",
                                f"{s.scrap_fed/1e3:.1f} t scrap fed "
                                f"({s.mass_sc()/1e3:.1f} t solid in bath).",
                                category="charge")
        # first flat bath (scrap essentially melted mid-heat)
        if "flatbath" not in flags and s.mass_sc() < 0.06 * c.total_scrap_mass \
                and s.scrap_fed > 0.4 * c.total_scrap_mass:
            flags["flatbath"] = True
            self._log_event(s.t, "FLAT BATH",
                            f"Solid scrap < 6%; T={s.T_mt-273.15:.0f} C, "
                            f"C={wt['C']*100:.3f}%.", category="milestone")
        # foamy slag established
        if "foam" not in flags and self._foam_coverage() > 0.6:
            flags["foam"] = True
            self._log_event(s.t, "FOAMY SLAG",
                            f"Foam coverage > 60% (FeO {s.feo_pct():.1f}%, "
                            f"B3 {s.basicity_b3():.2f}).", category="slag")
        # carbon below 0.10 %
        if "clow" not in flags and wt["C"] < 0.10 / 100.0 and s.scrap_fed > 0.5*c.total_scrap_mass:
            flags["clow"] = True
            self._log_event(s.t, "LOW CARBON",
                            f"[C] below 0.10% -> mass-transfer-limited decarburisation.",
                            category="chem")
        # tap temperature reached
        if "taptemp" not in flags and s.T_mt >= c.tap_temperature:
            flags["taptemp"] = True
            self._log_event(s.t, "TAP TEMP",
                            f"Bath reached tap temperature {c.tap_temperature-273.15:.0f} C.",
                            category="milestone")

    def _tap(self):
        s, c = self.state, self.cfg
        s.tapped = True
        # slag enthalpy tapped (reporting)
        s.E_slag = s.mass_sl() * CP["slag_liquid"] * (s.T_sl - c.offgas_ref_temp)
        self._log_event(s.t, "TAP",
                        f"Tapped {s.mass_mt()/1e3:.1f} t at {s.T_mt-273.15:.0f} C, "
                        f"[C]={s.wt_mt()['C']*100:.3f}%, "
                        f"[P]={s.wt_mt()['P']*100:.4f}%.",
                        category="milestone")

    # ==================================================================
    #  SNAPSHOT (time-series record)
    # ==================================================================
    def _snapshot(self, flux, chem, q_wall, q_panel, q_offgas, P_arc, foam):
        s = self.state
        wt = s.wt_mt()
        wsl = s.wt_sl()
        m_liq = s.mass_mt()
        rec = {
            "t": s.t,
            "t_min": s.t / 60.0,
            # temperatures [C]
            "T_metal": s.T_mt - 273.15,
            "T_slag": s.T_sl - 273.15,
            "T_scrap": s.T_sc - 273.15,
            "T_gas": s.T_g - 273.15,
            "T_roof": s.T_roof - 273.15,
            "T_wall_hotface": s.T_wall - 273.15,
            "T_shell": s.shell_temp - 273.15,
            "T_water_out": s.T_water_out - 273.15,
            # masses [t]
            "m_metal": m_liq / 1e3,
            "m_scrap_solid": s.mass_sc() / 1e3,
            "m_slag": s.mass_sl() / 1e3,
            "m_slag_formers_solid": s.mass_sf() / 1e3,
            "scrap_fed": s.scrap_fed / 1e3,
            # metal composition [wt%]
            "C_pct": wt["C"] * 100.0,
            "Si_pct": wt["Si"] * 100.0,
            "Mn_pct": wt["Mn"] * 100.0,
            "P_pct": wt["P"] * 100.0,
            "Cr_pct": wt["Cr"] * 100.0,
            # slag composition [wt%]
            "slag_CaO": wsl["CaO"] * 100.0,
            "slag_SiO2": wsl["SiO2"] * 100.0,
            "slag_MgO": wsl["MgO"] * 100.0,
            "slag_FeO": wsl["FeO"] * 100.0,
            "slag_MnO": wsl["MnO"] * 100.0,
            "slag_Al2O3": wsl["Al2O3"] * 100.0,
            "slag_P2O5": wsl["P2O5"] * 100.0,
            "basicity_B2": s.basicity(),
            "basicity_B3": s.basicity_b3(),
            "FeO_pct": s.feo_pct(),
            "foam_coverage": foam,
            # energy [MW] instantaneous & [kWh cumulative]
            "P_arc_MW": P_arc / 1e6,
            "P_chem_MW": chem["E_chem_rate"] / 1e6,
            "Q_offgas_MW": q_offgas / 1e6,
            "Q_water_MW": q_panel / 1e6,
            "Q_shell_MW": q_wall / 1e6,
            "E_elec_kWh": s.E_elec / 3.6e6,
            "E_chem_kWh": s.E_chem / 3.6e6,
            "E_offgas_kWh": s.E_offgas / 3.6e6,
            "E_water_kWh": s.E_water / 3.6e6,
            "E_shell_kWh": s.E_shell / 3.6e6,
            # specific (per tonne liquid) energy
            "SEC_elec_kWh_t": (s.E_elec / 3.6e6) / max(0.1, m_liq / 1e3),
            "SEC_total_kWh_t": ((s.E_elec + s.E_chem) / 3.6e6) / max(0.1, m_liq / 1e3),
            # rates
            "decarb_rate": flux.get("decarb_pct_per_min", 0.0),
            "PCR": flux.get("PCR", 0.0),
            # consumption
            "O2_Nm3": s.o2_used,
            "carbon_inj_kg": s.carbon_fed,
            "lime_fed_t": s.lime_fed / 1e3,
        }
        self.history.append(rec)

    # ==================================================================
    #  RUN
    # ==================================================================
    def run(self, progress: Optional[Callable[[float], None]] = None) -> "EAFResult":
        """Integrate the full heat until tap or t_end."""
        cont = True
        n = 0
        while cont:
            cont = self.step()
            n += 1
            if progress and n % 40 == 0:
                progress(min(1.0, self.state.t / self.cfg.t_end))
        if not self.state.tapped:
            self._log_event(self.state.t, "END",
                            "Simulation horizon reached before tap conditions met.",
                            category="warn")
        return EAFResult(self)

    # ==================================================================
    #  STATIC (0-D) OVERALL BALANCE
    # ==================================================================
    def static_balance(self) -> dict:
        """
        Time-independent overall mass & energy balance for the whole heat, using
        charge inventory and target tap chemistry.  Complements the dynamic run
        with a lumped design-basis check.
        """
        c = self.cfg
        # ---- overall metallic input ----
        heel = c.hot_heel_mass
        scrap = c.total_scrap_mass
        comp = c.scrap_comp
        # elements in (kg): heel(approx) + scrap
        el_in = {}
        for e, x in [("C", comp.C), ("Si", comp.Si), ("Mn", comp.Mn),
                     ("P", comp.P), ("Cr", comp.Cr)]:
            el_in[e] = scrap * x + heel * (0.001 if e == "C" else 0.0005)
        el_in["Fe"] = (scrap * comp.fe() + heel * 0.995
                       + c.carbon_charge_total * 0.0)
        m_in_metal = heel + scrap
        # ---- target tap ----
        tap_mass = m_in_metal * 0.90            # ~90% yield (oxidation + dust)
        tap_C = c.tap_carbon
        # ---- oxidation losses (approx, kg) ----
        ox = {
            "Si": el_in["Si"] * 0.98,
            "Mn": el_in["Mn"] * 0.70,
            "P": el_in["P"] * 0.85,
            "Cr": el_in["Cr"] * 0.30,
            "C": max(0.0, el_in["C"] + c.carbon_charge_total * 1.0 - tap_mass * tap_C),
            "Fe": m_in_metal * 0.02,
        }
        # ---- slag mass ----
        slag = (c.lime_total * c.lime_purity_CaO + c.dololime_total *
                (c.dololime_CaO + c.dololime_MgO)
                + ox["Si"] * M["SiO2"] / M["Si"]
                + ox["Mn"] * M["MnO"] / M["Mn"]
                + ox["Fe"] * M["FeO"] / M["Fe"]
                + ox["P"] * 0.5 * M["P2O5"] / M["P"]
                + ox["Cr"] * 0.5 * M["Cr2O3"] / M["Cr"])
        # ---- energy demand (design basis) ----
        # sensible + latent to bring charge from preheat to tap T
        dT_heat = (c.tap_temperature - c.scrap_preheat_temp)
        E_steel = scrap * (CP["steel_solid"] * (1809.0 - c.scrap_preheat_temp)
                           + L_FUS_STEEL
                           + CP["steel_liquid"] * (c.tap_temperature - 1809.0))
        E_slag = slag * (CP["slag_liquid"] * (c.tap_temperature - c.ambient_temp)
                         + H_DISS_LIME)
        # chemical energy credit
        E_chem = (ox["C"] * (-DH["C_O2_CO"]) / M["C"]
                  + ox["Si"] * (-DH["Si_O2"]) / M["Si"]
                  + ox["Mn"] * (-DH["Mn_O2"]) / M["Mn"]
                  + ox["Fe"] * (-DH["Fe_O2"]) / M["Fe"])
        # losses estimate
        E_offgas = 0.22 * (E_steel + E_slag)      # ~22% off-gas
        E_cool = 0.10 * (E_steel + E_slag)
        E_demand = E_steel + E_slag + E_offgas + E_cool
        E_elec = max(0.0, E_demand - E_chem * 0.85)
        return {
            "elements_in_kg": el_in,
            "oxidised_kg": ox,
            "steel_t": tap_mass / 1e3,
            "charge_t": m_in_metal / 1e3,
            "tap_temp_C": c.tap_temperature - 273.15,
            "tap_mass_t": tap_mass / 1e3,
            "yield_pct": 100.0 * tap_mass / m_in_metal,
            "slag_mass_t": slag / 1e3,
            "E_steel_kWh": E_steel / 3.6e6,
            "E_slag_kWh": E_slag / 3.6e6,
            "E_chem_kWh": E_chem / 3.6e6,
            "E_offgas_kWh": E_offgas / 3.6e6,
            "E_cool_kWh": E_cool / 3.6e6,
            "E_preheat_kWh": scrap * CP["steel_solid"]
                             * (c.scrap_preheat_temp - c.ambient_temp) / 3.6e6,
            "E_elec_demand_kWh": E_elec / 3.6e6,
            "SEC_elec_kWh_t": (E_elec / 3.6e6) / (tap_mass / 1e3),
            "SEC_total_kWh_t": ((E_elec + E_chem) / 3.6e6) / (tap_mass / 1e3),
        }


# =============================================================================
# 4.  RESULT WRAPPER  (KPIs, series extraction, balances)
# =============================================================================

class EAFResult:
    def __init__(self, model: EAFModel):
        self.cfg = model.cfg
        self.state = model.state
        self.history = model.history
        self.events = model.events
        self._final = self.history[-1] if self.history else {}

    def series(self, key: str) -> np.ndarray:
        return np.array([h.get(key, np.nan) for h in self.history], dtype=float)

    def time_min(self) -> np.ndarray:
        return self.series("t_min")

    @property
    def final(self) -> dict:
        return self._final

    def kpis(self) -> dict:
        s = self.state
        m_liq = s.mass_mt()
        m_liq_t = m_liq / 1e3
        wt = s.wt_mt()
        tap_time = s.t
        E_in = s.E_elec + s.E_chem
        return {
            "heat_id": self.cfg.heat_id,
            "plant": self.cfg.plant_name,
            "furnace_type": self.cfg.furnace_type,
            "tapped": s.tapped,
            "tap_to_tap_min": tap_time / 60.0,
            "tap_mass_t": m_liq_t,
            "tap_temp_C": s.T_mt - 273.15,
            "final_C_pct": wt["C"] * 100.0,
            "final_Si_pct": wt["Si"] * 100.0,
            "final_Mn_pct": wt["Mn"] * 100.0,
            "final_P_pct": wt["P"] * 100.0,
            "final_Cr_pct": wt["Cr"] * 100.0,
            "yield_pct": 100.0 * m_liq / (self.cfg.hot_heel_mass + s.scrap_fed),
            "slag_mass_t": s.mass_sl() / 1e3,
            "slag_basicity_B3": s.basicity_b3(),
            "slag_FeO_pct": s.feo_pct(),
            "E_elec_kWh": s.E_elec / 3.6e6,
            "E_chem_kWh": s.E_chem / 3.6e6,
            "E_total_kWh": E_in / 3.6e6,
            "SEC_elec_kWh_t": (s.E_elec / 3.6e6) / max(0.1, m_liq_t),
            "SEC_total_kWh_t": (E_in / 3.6e6) / max(0.1, m_liq_t),
            "productivity_t_per_h": m_liq_t / max(1e-6, tap_time / 3600.0),
            "productivity_t_per_h_per_MW": (m_liq_t / max(1e-6, tap_time / 3600.0))
                                           / max(1e-6, self.cfg.active_power_max / 1e6),
            "O2_Nm3_t": s.o2_used / max(0.1, m_liq_t),
            "carbon_kg_t": (s.carbon_fed + self.cfg.carbon_charge_total)
                           / max(0.1, m_liq_t),
            "lime_kg_t": (s.lime_fed + s.dololime_fed) / max(0.1, m_liq_t),
            "offgas_loss_kWh": s.E_offgas / 3.6e6,
            "water_loss_kWh": s.E_water / 3.6e6,
            "shell_loss_kWh": s.E_shell / 3.6e6,
        }

    def energy_balance(self) -> dict:
        """
        Reference-consistent input/output energy split [kWh] (datum = ambient T).
        Inputs: electrical + chemical + sensible enthalpy carried in by the
        preheated scrap and by the initial liquid hot heel.  Outputs: tapped steel
        and slag enthalpy, off-gas, cooling water and refractory/shell losses.
        """
        c, s = self.cfg, self.state
        Tamb = c.ambient_temp

        def steel_enthalpy(mass, T):
            if T <= 1809.0:
                return mass * CP["steel_solid"] * (T - Tamb)
            return mass * (CP["steel_solid"] * (1809.0 - Tamb) + L_FUS_STEEL
                           + CP["steel_liquid"] * (T - 1809.0))

        m_liq = s.mass_mt()
        E_steel = steel_enthalpy(m_liq, s.T_mt) / 3.6e6
        E_slag = (s.mass_sl() * (CP["slag_liquid"] * (s.T_sl - Tamb) + H_DISS_LIME)
                  ) / 3.6e6
        # inputs
        H_scrap_in = c.total_scrap_mass * CP["steel_solid"] * \
            (c.scrap_preheat_temp - Tamb) / 3.6e6
        H_heel_in = steel_enthalpy(c.hot_heel_mass, c.hot_heel_temp) / 3.6e6
        inputs = {
            "Electrical": s.E_elec / 3.6e6,
            "Chemical": s.E_chem / 3.6e6,
            "Scrap preheat": H_scrap_in,
            "Hot heel": H_heel_in,
        }
        outputs = {
            "Steel enthalpy": E_steel,
            "Slag enthalpy": E_slag,
            "Off-gas": s.E_offgas / 3.6e6,
            "Cooling water": s.E_water / 3.6e6,
            "Shell/refractory": s.E_shell / 3.6e6,
        }
        tot_in = sum(inputs.values())
        tot_out = sum(outputs.values())
        outputs["Other/unaccounted"] = tot_in - tot_out
        return {"inputs": inputs, "outputs": outputs,
                "total_in": tot_in, "total_out": tot_out,
                "closure_pct": 100.0 * (tot_in - tot_out) / max(1.0, tot_in)}

    def mass_balance(self) -> dict:
        """
        Rigorous total-system mass closure [kg]:
        (initial inventory + all inputs)  vs  (final inventory in every zone
        + cumulative off-gas mass).  A well-conserved model closes to << 0.1 %.
        Also reports the metallic split (metal / slag / gas) for reference.
        """
        s = self.state
        # total mass in = initial + everything added
        m_in = s.m_initial + s.mass_in_cum
        # total mass out (present) = all condensed zones + off-gas leaving
        offgas_mass = sum(s.offgas_mol[g] * M[g] for g in s.offgas_mol)
        m_out = (s.mass_mt() + s.mass_sc() + s.mass_sf()
                 + s.mass_sl() + offgas_mass)
        closure = m_in - m_out
        # metallic reference split
        metal_in = self.cfg.hot_heel_mass + s.scrap_fed
        to_slag = (s.sl["SiO2"] * M["Si"] / M["SiO2"]
                   + s.sl["MnO"] * M["Mn"] / M["MnO"]
                   + s.sl["FeO"] * M["Fe"] / M["FeO"]
                   + s.sl["P2O5"] * 2 * M["P"] / M["P2O5"]
                   + s.sl["Cr2O3"] * 2 * M["Cr"] / M["Cr2O3"])
        c_to_gas = (s.offgas_mol["CO"] + s.offgas_mol["CO2"]) * M["C"]
        return {
            "total_in_kg": m_in,
            "total_out_kg": m_out,
            "offgas_mass_kg": offgas_mass,
            "closure_kg": closure,
            "closure_pct": 100.0 * closure / max(1.0, m_in),
            "metal_in_kg": metal_in,
            "metal_out_kg": s.mass_mt(),
            "elements_to_slag_kg": to_slag,
            "carbon_to_gas_kg": c_to_gas,
        }

    def to_table(self) -> List[dict]:
        return self.history


# =============================================================================
# 5.  UTILITIES
# =============================================================================

def _fmt_time(t: float) -> str:
    m = int(t // 60)
    sec = int(t % 60)
    return f"{m:02d}:{sec:02d}"


# convenience alias exposed on config for chemistry (active power getter)
def _active_power_now(cfg, model):
    return model._arc_power()


if __name__ == "__main__":
    cfg = EAFConfig()
    model = EAFModel(cfg)
    res = model.run()
    k = res.kpis()
    print(f"Tapped: {k['tapped']}  tap-to-tap {k['tap_to_tap_min']:.1f} min")
    print(f"Tap mass {k['tap_mass_t']:.1f} t at {k['tap_temp_C']:.0f} C, "
          f"C={k['final_C_pct']:.3f}%")
    print(f"SEC elec {k['SEC_elec_kWh_t']:.0f} kWh/t | total {k['SEC_total_kWh_t']:.0f} kWh/t")
    print(f"Productivity {k['productivity_t_per_h']:.1f} t/h "
          f"({k['productivity_t_per_h_per_MW']:.2f} t/h/MW)")
    mb = res.mass_balance()
    print(f"Mass closure {mb['closure_pct']:.2f}%")
    eb = res.energy_balance()
    print("Energy in:", {k2: round(v) for k2, v in eb['inputs'].items()})
    print("Energy out:", {k2: round(v) for k2, v in eb['outputs'].items()})
