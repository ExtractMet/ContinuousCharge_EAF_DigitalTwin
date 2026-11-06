# Mathematical Model — Continuous-Charge (Consteel-type) EAF

**Extractmet Private Limited · Process Digital Twin**
First-principles dynamic simulator for a continuously-charged electric-arc furnace
operating in flat-bath immersion-melting mode.

---

## 1. Scope and modelling philosophy

The simulator integrates the transient mass and energy balances of a
continuously-charged EAF from power-on to tap. Unlike a conventional batch EAF,
scrap is fed **continuously** onto a conveyor into a retained **hot heel**, so the
furnace holds a **flat liquid bath** throughout the heat and scrap melts by
**immersion** at the bath/scrap interface rather than by bore-down arc melting.

The reactor is discretised into four interacting zones, each with its own mass
inventory and temperature:

| Zone | Symbol | Contents |
|------|--------|----------|
| Liquid metal (bath + heel) | mt | Fe, C, Si, Mn, P, Cr |
| Liquid slag | sl | CaO, SiO₂, MgO, Al₂O₃, FeO, MnO, P₂O₅, Cr₂O₃ |
| Solid scrap (in bath) | sc | Fe, C, Si, Mn, P, Cr |
| Solid slag formers | sf | CaO, MgO, SiO₂, Al₂O₃ (undissolved lime/dololime) |
| Freeboard gas | g | CO, CO₂, O₂, N₂, H₂O |

All balances are advanced with an explicit forward-Euler step of size Δt
(default 0.5 s). Every quantity is tracked in SI (kg, K, J, s) and converted to
engineering units only for reporting.

---

## 2. Governing balances

### 2.1 Species mass balance

For each element *i* in the metal zone:

```
d(m_i^mt)/dt = ṁ_i^melt  −  ṁ_i^ox  (+ ṁ_i^reduction)
```

where `ṁ_i^melt` is the rate at which element *i* enters the liquid from melting
solid scrap, `ṁ_i^ox` is its oxidation rate to slag/gas, and the reduction term
applies to Fe returned from FeO by carbon.

For each oxide *j* in the liquid slag:

```
d(m_j^sl)/dt = ṁ_j^ox  +  ṁ_j^dissolve  −  ṁ_j^reduction
```

The system also enforces a **global mass conservation** check by tracking the
cumulative mass added after t = 0 (scrap metallics, gangue, rust, moisture, fluxes,
lanced O₂, leak air, natural gas, injected carbon) against the total zone
inventories plus cumulative off-gas mass:

```
closure = (m_initial + Σ ṁ_in·Δt) − (m^mt + m^sc + m^sf + m^sl + m^offgas)
```

Reported mass closure is `100·closure / m_in`, typically well within ±1 %.

### 2.2 Zone energy balance

Each zone temperature is advanced from a lumped first-law balance
`C_zone · dT/dt = ΣQ̇`:

**Metal bath**
```
m^mt·c_p,liq · dT_mt/dt = P_bath + 0.85·Q̇_rxn,bath
                          − Q̇_mt→sl − Q̇_bath→sc − Q̇_endo
```
- `P_bath` — arc power delivered to the bath (§4)
- `Q̇_rxn,bath` — net exothermic heat of oxidation released in the bath
- `Q̇_mt→sl` — convective transfer to slag, `h_ms·A·(T_mt − T_sl)`
- `Q̇_bath→sc` — heat drawn to melt/warm immersed scrap
- `Q̇_endo` — endothermic FeO reduction + Boudouard

**Liquid slag**
```
m^sl·c_p,sl · dT_sl/dt = P_slag + 0.15·Q̇_rxn,bath + Q̇_mt→sl
                         − Q̇_sl→wall − Q̇_surf,roof − Q̇_diss
```

**Refractory hot face** (lumped capacity `C_wall`)
```
C_wall · dT_wall/dt = Q̇_sl→wall − Q̇_refractory,loss
```

Latent heat of fusion of the newly-molten scrap is charged to the bath through the
melting term; the freshly-molten mass enters at the liquidus and mixes with the
hotter bath by enthalpy-conserving mixing (§5.2), which is essential for closure.

### 2.3 Energy inventory (reporting)

Cumulative energy ledgers are integrated every step for the input/output balance:

```
E_elec   += (P_arc / η_arc)·Δt        electrical draw
E_chem   += (Q̇_chem + Q̇_CO,unburned)·Δt
E_offgas += (q̇_offgas + Q̇_CO,unburned)·Δt
E_water  += q̇_panel·Δt
E_shell  += q̇_refractory·Δt
```

The unburned-CO calorific term is booked simultaneously to **both** the chemical
input and the off-gas output (full-calorific-value convention). It therefore
cancels in the bath thermal balance while correctly placing the chemical potential
of exported CO on the input/off-gas split, which is how plant energy audits report
it.

---

## 3. Thermochemistry and kinetics

### 3.1 Oxidation reactions

The lanced oxygen is partitioned across the oxidisable elements; the model uses
effective reaction enthalpies (per mole of the first reactant, negative =
exothermic):

| Reaction | ΔH [kJ/mol] |
|----------|-------------|
| [C] + ½O₂(g) → CO(g) | −130 |
| [Si] + O₂(g) → (SiO₂) | −800 |
| [Mn] + ½O₂(g) → (MnO) | −362 |
| Fe + ½O₂(g) → (FeO) | −240 |
| [P] + 5/4 O₂ → ½(P₂O₅) | −600 |
| [Cr] + 3/4 O₂ → ½(Cr₂O₃) | −560 |
| CO(g) + ½O₂(g) → CO₂(g) | −283 |
| CH₄ + 2O₂ → CO₂ + 2H₂O(g) | −802 (LHV) |
| (FeO) + [C] → Fe + CO(g) | +110 (endothermic) |
| C(s) + CO₂ → 2CO(g) (Boudouard) | +172 (endothermic) |

**Oxygen partition.** Si and Mn are oxidised preferentially (they capture up to
35 % of the lanced O₂ at their kinetic rates), the majority of the remainder goes
to carbon (`o2_to_carbon_pref ≈ 0.62·` remaining O₂), and any O₂ still unreacted
oxidises Fe to FeO — the dominant yield-loss channel.

### 3.2 Decarburisation

Two parallel routes remove carbon:

**(a) Direct oxygen decarburisation** — kinetically limited by the lower of the
oxygen-supply rate and a mass-transfer expression as [C] falls below ~3·c_crit:

```
ṙ_C,O2 = min( 2·ṅ_O2,C ,  A_bath·ρ_mt·k_dec·(w_C − w_C,eq) / M_C )
```

so that at low carbon the rate becomes **mass-transfer-limited**, reproducing the
characteristic tail as [C] → 0.04–0.09 %.

**(b) Slag FeO reduction** — carbon reacts with dissolved FeO:

```
ṙ_FeO,C ∝ a_FeO·(w_C − w_C,eq)·m_mt
```

bounded by available FeO and dissolved carbon. This is the endothermic route that
sustains a foamy slag.

Total CO generation `ṅ_CO = ṙ_C,total (+ 2·ṙ_Boudouard)` drives the gas balance and
foam.

### 3.3 Dephosphorisation

Phosphorus partition is gated by slag basicity, FeO activity and temperature
(favoured by high basicity, high FeO, lower temperature):

```
η_P = clip((B₃−1.5)/2, 0, 1) · clip(a_FeO/0.20, 0, 1.5) · clip((1900−T_mt)/250, 0, 1)
ṙ_P = k_P·η_P·[P]/M_P
```

### 3.4 Post-combustion and burners

A fraction of CO is post-combusted above the bath by the post-combustion O₂ jet up
to a target post-combustion ratio (PCR ≈ 0.35); a portion of that heat
(`postcomb_heat_recovery ≈ 0.55`) is returned to the bath/slag, the remainder
raises the freeboard gas enthalpy. Optional natural-gas burners add
`−ΔH_CH4·ṅ_CH4`.

---

## 4. Arc power and its distribution

Delivered arc thermal power is modulated by a closed-loop controller that holds the
bath at the active set-point — the defining feature of continuous charging (constant
specific power at constant flat-bath temperature):

```
P_arc = P_max · clip(1 + 0.030·(T_set − T_mt), 0.12, 1) · (1 + ε_flicker) · η_arc
```

where `T_set` = 1560 °C during melting and the tap temperature during refining, and
`ε_flicker ~ N(0, 0.02)` is a small arc-flicker perturbation. Panel-protection
trims power if the roof approaches its critical temperature.

The delivered power is split between the bath, the solid scrap, the slag and the
upper shell:

```
P_bath  = P_arc·(f_bath + f_rem·s_foam)
P_scrap = P_arc·f_scrap
P_slag  = P_arc·f_slag
P_wall  = P_arc·f_rem·(1 − s_foam)
```

with `f_rem = 1 − f_bath − f_scrap − f_slag` the radiant fraction to the wall, and
`s_foam = foam_shielding·φ_foam` the fraction of that radiation intercepted and
returned to the bath by the foamy slag (the energy benefit of foam). Base split
values (`f_bath ≈ 0.72`, `f_scrap ≈ 0.10`, `f_slag ≈ 0.08`) follow the arc-heat
distribution reported by Logar et al. (ISIJ Int. 52 (2012)).

---

## 5. Melting, mixing and slag formation

### 5.1 Immersion melting rate

Scrap melts at the metal/scrap interface at a rate set by the heat delivered to the
scrap divided by the enthalpy needed to raise interface material from the bulk
scrap temperature to the liquidus and melt it:

```
ṁ_melt = k_melt·(1 − f_warm)·Q̇_sc,in / [ c_p,s·(T_liq − T_sc) + L_fus ]
```

where `Q̇_sc,in = Q̇_bath→sc + P_scrap` and a small fraction `f_warm` warms the
remaining solid. Because `Q̇_bath→sc = h_bs·A_sc·(T_mt − T_sc)`, the melting rate is
self-balancing against the feed rate: feeding cold scrap depresses `T_sc`, which
sustains the bath→scrap driving force — the physical mechanism of continuous
melting.

### 5.2 Enthalpy-conserving mixing

Newly-molten mass `dm` enters the liquid at the liquidus `T_liq` and mixes with the
bath (equal specific heats):

```
T_mt ← (m_old·T_mt + dm·T_liq) / (m_old + dm)
```

### 5.3 Flux dissolution

Solid lime/dololime dissolve into the liquid slag by a first-order, temperature-
gated law with an endothermic dissolution enthalpy `H_diss`:

```
drive = clip((T_sl − 1450°C)/120, 0.05, 1);   ṁ_diss = k_d·drive·m^sf
Q̇_diss = ṁ_diss·H_diss
```

Slag basicity is reported as `B₂ = CaO/SiO₂` and `B₃ = (CaO+MgO)/(SiO₂+Al₂O₃)`.

### 5.4 Foamy-slag coverage

```
φ_foam = clip( [1 − exp(−m^sl/4500)] · (0.6 + 0.4·tanh(FeO%/20)), 0, 1 )
```

Coverage rises with slag mass and FeO, shielding the arc and returning radiation to
the bath (§4).

---

## 6. Heat losses

### 6.1 Multilayer refractory conduction

The wall is a series of conduction resistances (working lining → safety lining →
insulating board → steel shell) closed by an outer surface that loses heat by
convection **and** radiation to ambient. The shell temperature `T_s` is found by a
Newton iteration equating conducted and surface-rejected flux:

```
R_cond = Σ_k  L_k / (k_k · A)
(T_hot − T_s)/R_cond = h_amb·A·(T_s − T_amb) + ε·σ·A·(T_s⁴ − T_amb⁴)
q̇_refractory = (T_hot − T_s)/R_cond
```

### 6.2 Water-cooled panels

The roof and upper-wall panels are loaded by (i) the un-shielded arc radiation that
reaches them and (ii) radiative + convective exchange with the hot freeboard gas
(view-factor limited). The load is removed by cooling water:

```
q̇_panel = q̇_arc,intercepted + F_gas·ε·σ·A·(T_g⁴ − T_w⁴) + h_gs·A·(T_g − T_w)
T_water,out = T_water,in + q̇_panel / (ṁ_w·c_p,w)
```

Tying the panel load to the arc power (rather than letting the panels "see" the full
bath) keeps the loss physically scaled with input.

### 6.3 Off-gas enthalpy

The off-gas carries sensible heat proportional to its molar heat capacity and the
gas–reference temperature difference; the CO leaving unburned additionally carries
its calorific value (§2.3).

---

## 7. Static (0-D) design balance

Independent of the transient run, a closed-form overall balance is provided for the
target tap condition as a design cross-check. It computes the sensible + latent
enthalpy to bring the charge from preheat to tap temperature, the slag enthalpy, the
chemical credit from oxidation, an off-gas allowance (~22 %) and a cooling/shell
allowance (~10 %), and returns the net electrical demand and specific electrical
energy. Agreement between the static demand and the dynamic result confirms the
integrator conserves energy.

---

## 8. Numerical scheme and stability

- **Integration:** explicit forward Euler, Δt = 0.25–1 s. Temperatures are clipped
  to physically admissible ranges as a numerical guard; under the default
  parameters the solution never approaches these guards.
- **Rate limiters:** every reaction rate is capped by the available reactant mass
  per step (`ṙ·Δt ≤ m_available`), guaranteeing non-negative inventories.
- **Tap trigger:** the heat is tapped when solid scrap is essentially consumed
  (< 1 % of charge), the bath reaches tap temperature, [C] ≤ 1.5·target, and
  ≥ 98 % of scrap has been charged.

---

## 9. Key parameters (default configuration)

| Group | Parameter | Default |
|-------|-----------|---------|
| Charge | Hot heel | 40 t @ 1550 °C |
| | Scrap charged | 110 t @ 420 °C preheat |
| | Conveyor feed | 45 kg/s |
| Electrical | Max active power | 72 MW (90 MVA, PF 0.78) |
| | Arc efficiency | 0.90 |
| Chemical | O₂ lance / post-comb | 1.05 / 0.32 Nm³/s |
| | Carbon injection | 0.50 kg/s |
| Fluxes | Lime / dololime | 4.3 / 2.0 t |
| Targets | Tap temperature / carbon | 1620 °C / 0.06 % |
| Refractory | MgO-C / magnesia / board / shell | 450 / 180 / 30 / 50 mm |

All parameters are exposed in each GUI and may be varied within physically
reasonable ranges.

---

## 10. References

1. V. Logar, D. Dovžan, I. Škrjanc, *Modeling and Validation of an EAF, Parts I & II*,
   ISIJ International **52** (2012) 402–423, 1225–1242.
2. M. Kirschen, V. Risonarta, H. Pfeifer, *Energy efficiency and the influence of gas
   burners to the energy related carbon dioxide emissions of EAFs*, Energy **34** (2009).
3. E. B. Pretorius, R. C. Marr, *The Fundamentals of Electric Arc Furnace and Ladle
   Slags*, Baker Refractories.
4. R. J. Fruehan (ed.), *The Making, Shaping and Treating of Steel — Steelmaking and
   Refining Volume*, AIST; and EAF energy-loss study, US DOE (2000).
5. Y. Zhang et al., *Analysis of electrical energy consumption of Consteel EAFs*,
   Metals **16(6)** (2026) 594.

---
*© Extractmet Private Limited. Model estimates are for engineering guidance and do
not constitute a guarantee of plant performance.*
