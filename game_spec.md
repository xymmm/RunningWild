# Survival Knapsack Game — Formal Specification (v0.1)

This document defines the game in a self-contained, computable form. All ambiguities from the v0.0 prototype have been resolved by explicit convention; conventions are flagged with **[CONV]** when they encode a design choice rather than a logical necessity.

## 1. Game state

At each day t ∈ {0, 1, ..., T} with T = 50 by default, a team's state is the tuple:

| Symbol | Domain | Meaning | Initial value |
|---|---|---|---|
| HP_t | ℤ | hit points | 20 |
| W_t | ℝ≥0 | water in litres | 6.0 |
| F_t | ℤ≥0 | food in kcal | 6000 |
| inv | 2^Items | inventory chosen at t=0, fixed | by MILP or intuition |
| loc | Locations | location card, drawn at t=0 before planning | one of 10 |
| τ | Traits | trait card, drawn at t=1 after planning | one of 20 |
| c_w | ℤ≥0 | consecutive days with W=0 at end of day | 0 |
| c_f | ℤ≥0 | consecutive days with daily kcal < 500 | 0 |

## 2. Inventory constraints (fixed at t = 0)

```
Σ_{j ∈ Items} w_j · x_j  ≤  W_max = 20 kg
Σ_{j ∈ Items} v_j · x_j  ≤  V_max = 80 L
x_j ∈ {0, 1}
```

Worn clothing is excluded from V but included in W. **[CONV]** Worn-clothing flag will be a per-item Boolean in items.csv.

## 3. Mitigation logic

Each event e ∈ Events has:

- `base_hp_e ∈ ℤ` — HP delta when **un**mitigated, before location/trait
- `mit_logic_e ∈ {ANY, ALL, NONE}` — logical structure of mitigation set
- `mit_set_e ⊆ Items` — items participating in mitigation
- `mit_hp_e ∈ ℤ` — HP delta when fully mitigated (often 0; can be e.g. -1 for "if mitigated, HP = -1")

Mitigation indicator:

```
y_e(inv) = 1   if mit_logic_e = ANY and ∃ j ∈ mit_set_e with x_j = 1
y_e(inv) = 1   if mit_logic_e = ALL and ∀ j ∈ mit_set_e, x_j = 1
y_e(inv) = 0   otherwise (including all NONE events)
```

Effective HP from event e before location and trait:

```
δ_e^0(inv) = y_e · mit_hp_e + (1 - y_e) · base_hp_e
```

This resolves the v0.0 contradiction between "at most one item is needed" and compound requirements like `tent + sleeping bag`. Every event now declares its logic explicitly.

## 4. Event categorisation

To make location and trait modifiers tractable, every event is tagged with a category. Categories are a flat set:

```
weather_cold, weather_hot, weather_wet, weather_wind, weather_neutral,
medical_injury, medical_illness, medical_sting,
navigation, slip_fall, equipment, food_spoilage, water_collection,
wildlife_calm, wildlife_attack, insect, bonus_morale, bonus_resource
```

Every event in events.csv has exactly one category.

## 5. Location modifiers

Each location ℓ provides additive HP modifiers per category, plus optional multipliers for water-gain events:

```
μ_{ℓ, c} ∈ ℤ      — additive HP modifier on un-mitigated events in category c
ρ_{ℓ, c} ∈ ℝ>0    — multiplier on water gain for events in category c
```

Convention: location modifiers apply only to un-mitigated events. **[CONV]** This avoids double-rewarding mitigation.

Modified HP after location:

```
δ_e^ℓ(inv) = δ_e^0(inv) + (1 - y_e) · μ_{ℓ, cat(e)}
```

## 6. Trait modifiers

Same structure as location modifiers:

```
ν_{τ, c} ∈ ℤ      — additive HP modifier per event category
+ optional one-shot effects (e.g. "first headlamp failure: extra -1")
```

Trait one-shot effects need a per-game flag indicating whether they've fired.

```
δ_e^{ℓ, τ}(inv, state) = δ_e^ℓ(inv) + (1 - y_e) · ν_{τ, cat(e)} + oneshot(τ, e, state)
```

## 7. Daily transition

For day t = 1, ..., T:

1. **Event draw.** Sample event(s) for day t. Default scheme: per-event independent Bernoulli with parameter p_e. Expected events per day ≈ 1.65 with current calibration. Alternative single-draw scheme available; see §10.
2. **Pre-event consumption.** Subtract baseline water and food: W ← max(0, W − w_base), F ← max(0, F − f_base). Default: w_base = 0.5 L, f_base = 500 kcal. **[CONV]**
3. **Event effects.** For each event e drawn this day:
   - Compute δ = δ_e^{ℓ, τ}(inv, state)
   - HP_t ← HP_{t-1} + δ
   - Apply event-specific water/food consumption and gains: W ← W − w_e + g_e^water, F ← F − f_e + g_e^food
4. **Carrying penalty.**
   ```
   π_t = α · max(0, weight(inv) − W_thresh)
   HP_t ← HP_t − π_t
   ```
   Default: α = 0.1 HP per kg per day above 15 kg.
5. **Counter update.**
   ```
   c_w ← c_w + 1 if W_t = 0 else 0
   c_f ← c_f + 1 if total kcal consumed today < 500 else 0
   ```
6. **Elimination check.**
   - HP_t ≤ 0  →  eliminated (death)
   - c_w ≥ 3   →  eliminated (dehydration)
   - c_f ≥ 10  →  eliminated (starvation)

## 8. End-of-game scoring

For surviving teams at t = T:

```
HP_final = HP_T + min(HP_water_cap, ⌊W_T / λ_w⌋) + min(HP_food_cap, ⌊F_T / λ_f⌋)
```

Defaults: λ_w = 1.0 L, λ_f = 1000 kcal, HP_water_cap = 5, HP_food_cap = 10.

This is Option C from our earlier discussion: a capped bonus that rewards prudent margin without making stockpiling dominant. The MILP solution should be competitive with naive stockpiling under this rule.

Eliminated teams: HP_final = −∞ (loss). Survival is the first-order criterion.

## 9. Win condition

Team with maximum HP_final wins. Ties broken by day of any elimination penalty (longer survival first), then by remaining inventory weight (lighter pack first, rewarding efficiency).

## 10. Stochastic event generation

**Scheme A (default): per-event Bernoulli.** Each day, for each e ∈ Events independently draw whether e fires with probability p_e. Expected events per day = Σ p_e ≈ 1.65.

**Scheme B: single categorical draw.** Each day, one event fires; p_e are normalised so Σ p_e = 1. Used if instructor wants tighter pacing.

**Scheme C: stratified daily draw.** Each day, draw exactly one event from each of {weather, health, navigation_or_equipment, optional bonus}. Used if instructor wants guaranteed event diversity per day.

Default is Scheme A for richness; Scheme C may be useful for the classroom version to control pacing.

## 11. Multi-period MILP for planning

Decision variables:
- x_j ∈ {0,1} for each item j
- y_e ∈ {0,1} for each event e

Parameters set from calibrated files:
- p_e, base_hp_e, mit_hp_e, mit_logic_e, mit_set_e, cat(e)
- w_j, v_j, kcal_j, litres_j
- μ_{ℓ, c}, α, W_thresh, λ_w, λ_f, HP_water_cap, HP_food_cap

Auxiliary variables:
- ovw ≥ 0  — overweight above threshold
- w_carried = Σ kcal_j · x_j, l_carried = Σ litres_j · x_j

Objective (maximise expected HP_final):

```
max  E[HP_final] = HP_0 
                 + T · Σ_e p_e · [ y_e · mit_hp_e + (1 - y_e) · (base_hp_e + μ_{ℓ, cat(e)}) ]
                 − T · α · ovw
                 + min(HP_water_cap, (l_carried + E[water_gained] − T · w_base) / λ_w)
                 + min(HP_food_cap,  (kcal_carried + E[food_gained] − T · f_base) / λ_f)
```

The end-game bonus terms are piecewise-linear and linearised with auxiliary binary or continuous variables.

Constraints:

```
weight:     Σ w_j x_j ≤ 20
volume:     Σ v_j x_j ≤ 80
overweight: ovw ≥ Σ w_j x_j − W_thresh,  ovw ≥ 0
survival_water: l_carried + E[water_gained] ≥ T · w_base · (1 − slack_w),  slack_w small
survival_food:  kcal_carried + E[food_gained] ≥ T · f_base · (1 − slack_f)
mitigation_ANY: y_e ≤ Σ_{j ∈ mit_set_e} x_j         for e with logic ANY
mitigation_ALL: y_e ≤ x_j  ∀ j ∈ mit_set_e          for e with logic ALL
mitigation_NONE: y_e = 0                             for e with logic NONE
```

The survival constraints encode expected sufficiency, not certainty; this captures the per-day average. Stochastic-programming extension: replace with chance constraints over sampled scenarios.

## 12. Calibration targets

Target outcome distributions in 1000-simulation Monte Carlo at default parameters:

| Strategy | Survival rate | Median HP_final | Notes |
|---|---|---|---|
| Random feasible backpack | 25–40% | n/a or low | should fail often |
| MILP-optimal | 70–85% | 25–35 | reward for solving the model |
| Pure stockpile (max food/water, no mitigation) | 40–55% | 15–25 | viable but inferior |
| Pure mitigation (max coverage, low food/water) | 30–45% | dies of dehydration | viable but inferior |
| Balanced human strategy | 55–70% | 20–30 | sensible play, no MILP |

If observed distributions differ significantly from these, parameters need adjustment. See Phase 2 plan.

## 13. Open questions for design review

1. **Worn clothing.** Current rule: weight counts, volume only if packed. Practical question: does "worn jacket" count differently from "packed jacket" in the MILP? Suggest simplification: every item has fixed weight and volume; volume of jackets is just smaller (1–2 L) rather than zero.
2. **Trait one-shots.** Several traits have "first time X happens, extra effect". Need a clean state representation. Suggest: each trait declares a `oneshot_flag` and the simulator tracks whether it has fired.
3. **Multi-event days.** Under Scheme A, some days will have 3+ events. Is that intended? If too chaotic, switch to Scheme B or C as default.
4. **Carrying penalty fractional HP.** α = 0.1 produces fractional HP. Options: round at end of each day, or accumulate fractional HP and only floor for elimination check. Suggest the latter.
5. **Resource consumption per event.** v0.0 had per-event water and food costs. Default in this spec is to fold them into a flat baseline w_base, f_base. Should there be per-event variation? Suggest keeping a small additive consumption only for high-effort events (severe dehydration, deep stream, heat exhaustion).
