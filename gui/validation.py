"""
Sanity checks on ProJet inputs and results.

Every issue is a dict {"level": "error" | "warning" | "info", "message": str, "path": [...]}
where "path" points to the input (config keys) the issue refers to, if any.
Errors mean the case cannot (or must not) be computed; warnings flag values that are
physically questionable or outside the usual range for this kind of engine.
"""
import math

ENGINE_TYPES = ["turbojet", "turbofan_SF", "turbofan_AF", "turboprop"]

# stoichiometric fuel/air ratio of hydrocarbon (kerosene-like) fuels
F_STOICH = 0.068

COMPONENT_KEYS = {
    "intake": {"efficiency", "Phi", "mach"},
    "fan": {"pressure_ratio", "efficiency", "mechanical_efficiency", "BPR"},
    "compressor": {"pressure_ratio", "efficiency", "mechanical_efficiency", "BPR"},
    "combustor": {"outlet_temperature", "fuel_ratio", "efficiency", "mechanical_efficiency"},
    "turbine": {"efficiency", "mechanical_efficiency"},
    "turbineHigh": {"efficiency", "mechanical_efficiency"},
    "turbineLow": {"efficiency", "mechanical_efficiency"},
    "postCombustor": {"outlet_temperature", "fuel_ratio", "temperature_max", "efficiency", "mechanical_efficiency"},
    "nozzle": {"efficiency", "onlyConvergent"},
    "nozzleMain": {"efficiency", "onlyConvergent"},
    "nozzleSecondary": {"efficiency", "onlyConvergent"},
    "propeller": {"Phi", "alpha_power", "efficiency", "gearbox_efficiency"},
}

SECTION_KEYS = {
    "airProperties": {"cp", "gamma", "R", "density", "temperature", "pressure"},
    "hotGasProperties": {"cp", "gamma", "R"},
    "postcombustionProperties": {"cp", "gamma", "R"},
    "fuelProperties": {"calorific"},
    "flightConditions": {"altitude_km"},
}

REQUIRED_COMPONENTS = {
    "turbojet": ["intake", "compressor", "combustor", "turbine", "nozzle"],
    "turbofan_SF": ["intake", "fan", "compressor", "combustor", "turbineHigh", "turbineLow", "nozzleMain", "nozzleSecondary"],
    "turbofan_AF": ["intake", "fan", "compressor", "combustor", "turbineHigh", "turbineLow", "nozzle"],
    "turboprop": ["propeller", "intake", "compressor", "combustor", "turbineHigh", "turbineLow", "nozzle"],
}
OPTIONAL_COMPONENTS = {
    "turbojet": ["postCombustor"],
    "turbofan_SF": [],
    "turbofan_AF": ["postCombustor"],
    "turboprop": [],
}

# solver defaults (src/fluids)
GAS_DEFAULTS = {
    "airProperties": {"cp": 1004, "gamma": 1.4, "R": 287.0},
    "hotGasProperties": {"cp": 1155, "gamma": 1.33, "R": 286.58},
    "postcombustionProperties": {"cp": 1155, "gamma": 1.33, "R": 286.58},
}
GAS_NAMES = {
    "airProperties": "air",
    "hotGasProperties": "combustion gas",
    "postcombustionProperties": "afterburner gas",
}

COMPONENT_NAMES = {
    "intake": "intake", "fan": "fan", "compressor": "compressor", "combustor": "combustor",
    "turbine": "turbine", "turbineHigh": "HP turbine", "turbineLow": "LP turbine",
    "postCombustor": "afterburner", "nozzle": "nozzle", "nozzleMain": "core nozzle",
    "nozzleSecondary": "bypass nozzle", "propeller": "propeller",
}


class Issues(list):
    def add(self, level, message, *path):
        self.append({"level": level, "message": message, "path": list(path)})

    def error(self, message, *path):
        self.add("error", message, *path)

    def warning(self, message, *path):
        self.add("warning", message, *path)

    def info(self, message, *path):
        self.add("info", message, *path)

    @property
    def has_errors(self):
        return any(i["level"] == "error" for i in self)


def is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------
def validate_inputs(config):
    issues = Issues()

    if not isinstance(config, dict):
        issues.error("The configuration must be a dictionary.")
        return issues

    engine = config.get("engineType")
    if engine not in ENGINE_TYPES:
        issues.error(f"Unknown engineType '{engine}'. Available: {', '.join(ENGINE_TYPES)}.", "engineType")
        return issues

    comps = config.get("components")
    if not isinstance(comps, dict):
        issues.error("The 'components' section is missing.", "components")
        return issues

    _check_structure(config, engine, issues)
    if issues.has_errors:
        return issues

    _check_ambient(config, engine, issues)
    _check_gases(config, issues)
    _check_components(config, engine, issues)
    if not issues.has_errors:
        _check_turbine_inlet_temperature(config, engine, issues)
    return issues


def compressor_exit_temperature(config, engine):
    """closed-form T3 (same relations as the solver: ram, fan, compressor)"""
    air = {**GAS_DEFAULTS["airProperties"], **config.get("airProperties", {})}
    g = air["gamma"]
    comps = config["components"]
    T = config["airProperties"]["temperature"] * (1 + (g - 1) / 2 * comps["intake"]["mach"] ** 2)
    names = ["fan", "compressor"] if engine.startswith("turbofan") else ["compressor"]
    for name in names:
        c = comps[name]
        T *= 1 + (c["pressure_ratio"] ** ((g - 1) / g) - 1) / c.get("efficiency", 1.0)
    return T


def _check_turbine_inlet_temperature(config, engine, issues):
    comb = config["components"]["combustor"]
    if "outlet_temperature" not in comb:
        return
    T3 = compressor_exit_temperature(config, engine)
    if comb["outlet_temperature"] <= T3:
        issues.error(f"The turbine inlet temperature ({comb['outlet_temperature']:g} K) must be higher than the "
                     f"compressor exit temperature ({T3:.0f} K).", "components", "combustor", "outlet_temperature")


def _check_structure(config, engine, issues):
    comps = config["components"]

    for key, value in config.items():
        if key in ("engineType", "components"):
            continue
        if key not in SECTION_KEYS:
            issues.warning(f"Section '{key}' is not used by ProJet and is ignored.", key)
            continue
        if not isinstance(value, dict):
            issues.error(f"Section '{key}' must contain parameters.", key)
            continue
        for k, v in value.items():
            if k not in SECTION_KEYS[key]:
                issues.error(f"Unknown parameter '{k}' in '{key}' (allowed: {', '.join(sorted(SECTION_KEYS[key]))}).", key, k)
            elif not is_number(v):
                issues.error(f"'{key}.{k}' must be a finite number (got {v!r}).", key, k)

    for name in REQUIRED_COMPONENTS[engine]:
        if not isinstance(comps.get(name), dict):
            issues.error(f"The {COMPONENT_NAMES[name]} ('{name}') is required for a {engine}.", "components", name)

    allowed = set(REQUIRED_COMPONENTS[engine]) | set(OPTIONAL_COMPONENTS[engine])
    for name, block in comps.items():
        if name not in allowed:
            issues.warning(f"Component '{name}' is not part of a {engine} and is ignored.", "components", name)
            continue
        if not isinstance(block, dict):
            issues.error(f"Component '{name}' must contain parameters.", "components", name)
            continue
        for k, v in block.items():
            if k not in COMPONENT_KEYS[name]:
                issues.error(f"Unknown parameter '{k}' for the {COMPONENT_NAMES[name]} "
                             f"(allowed: {', '.join(sorted(COMPONENT_KEYS[name]))}).", "components", name, k)
            elif k == "onlyConvergent":
                if not isinstance(v, bool) and v not in (0, 1):
                    issues.error(f"'{name}.onlyConvergent' must be True or False (got {v!r}).", "components", name, k)
            elif not is_number(v):
                issues.error(f"'{name}.{k}' must be a finite number (got {v!r}).", "components", name, k)


def _check_ambient(config, engine, issues):
    air = config.get("airProperties", {})
    intake = config["components"]["intake"]
    P = ("airProperties",)

    for key, unit in (("temperature", "K"), ("pressure", "Pa"), ("density", "kg/m³")):
        if key not in air:
            issues.error(f"Ambient {key} [{unit}] is required.", *P, key)
    if issues.has_errors:
        return

    T, p, rho = air["temperature"], air["pressure"], air["density"]
    if T <= 0:
        issues.error(f"Ambient temperature must be positive and in kelvin (got {T}).", *P, "temperature")
    elif T < 150:
        issues.error(f"Ambient temperature {T} K is far below any atmospheric value: is it in kelvin?", *P, "temperature")
    elif not 180 <= T <= 330:
        issues.warning(f"Ambient temperature {T:g} K is outside the usual atmospheric range (180–330 K).", *P, "temperature")

    if p <= 0:
        issues.error(f"Ambient pressure must be positive (got {p}).", *P, "pressure")
    elif p < 500:
        issues.error(f"Ambient pressure {p:g} Pa is too low: the pressure must be given in Pa, not kPa or bar.", *P, "pressure")
    elif p > 110000:
        issues.warning(f"Ambient pressure {p:g} Pa is above sea-level standard (101325 Pa).", *P, "pressure")

    if rho <= 0:
        issues.error(f"Air density must be positive (got {rho}).", *P, "density")
    elif T > 0 and p > 0:
        R = air.get("R", GAS_DEFAULTS["airProperties"]["R"])
        rho_ideal = p / (R * T)
        if abs(rho - rho_ideal) / rho_ideal > 0.03:
            issues.warning(f"Density {rho:g} kg/m³ is not consistent with p/(R·T) = {rho_ideal:.4f} kg/m³ "
                           "(the intake mass flow uses the density you entered).", *P, "density")

    if "mach" not in intake:
        issues.error("The flight Mach number is required.", "components", "intake", "mach")
    else:
        M = intake["mach"]
        path = ("components", "intake", "mach")
        if M <= 0:
            issues.error("The flight Mach number must be positive (with M = 0 there is no ram air and the "
                         "propulsive quantities are undefined).", *path)
        elif M > 3:
            issues.error(f"Flight Mach {M:g} is outside the validity of this model (no shock / ramjet effects).", *path)
        elif M >= 1:
            issues.warning(f"Supersonic flight (M = {M:g}): the intake model has no shock, so its total pressure "
                           "loss must be included in the pressure recovery πd.", *path)
        if engine == "turboprop" and 0 < M < 0.15:
            issues.warning("Very low flight speed: the propeller thrust P/u₀ grows without bound as u₀ → 0.", *path)
        elif engine == "turboprop" and M > 0.75:
            issues.warning(f"Flight Mach {M:g} is high for a propeller (compressibility losses above M ≈ 0.7).", *path)

    if "Phi" not in intake:
        issues.error("The intake diameter is required.", "components", "intake", "Phi")
    else:
        D = intake["Phi"]
        if D <= 0:
            issues.error("The intake diameter must be positive.", "components", "intake", "Phi")
        elif D > 4:
            issues.warning(f"Intake diameter {D:g} m is larger than any existing engine (≈ 3.4 m).", "components", "intake", "Phi")

    alt = config.get("flightConditions", {}).get("altitude_km")
    if alt is not None and not 0 <= alt <= 20:
        issues.warning(f"Altitude {alt:g} km is outside the usual flight envelope (0–20 km).", "flightConditions", "altitude_km")


def _check_gases(config, issues):
    for section, defaults in GAS_DEFAULTS.items():
        given = config.get(section, {})
        if section == "postcombustionProperties" and "postCombustor" not in config["components"]:
            continue
        g = {**defaults, **given}
        name = GAS_NAMES[section]
        bad = False
        if g["cp"] <= 0:
            issues.error(f"cp of the {name} must be positive.", section, "cp"); bad = True
        if g["R"] <= 0:
            issues.error(f"R of the {name} must be positive.", section, "R"); bad = True
        if g["gamma"] <= 1:
            issues.error(f"γ of the {name} must be greater than 1.", section, "gamma"); bad = True
        if bad:
            continue
        if g["cp"] <= g["R"]:
            issues.error(f"cp of the {name} must be larger than R (cv = cp − R > 0).", section, "cp")
            continue
        cp_from_gamma = g["gamma"] * g["R"] / (g["gamma"] - 1)
        if abs(cp_from_gamma - g["cp"]) / g["cp"] > 0.03 and given:
            key = next((k for k in ("cp", "gamma", "R") if k in given), "cp")
            issues.warning(f"cp, γ and R of the {name} are not consistent: γR/(γ−1) = {cp_from_gamma:.0f} J/(kg·K) "
                           f"vs cp = {g['cp']:g} J/(kg·K).", section, key)
        if section == "airProperties" and not 1.3 <= g["gamma"] <= 1.45:
            issues.warning(f"γ = {g['gamma']:g} is unusual for air (≈ 1.4).", section, "gamma")
        if section != "airProperties" and not 1.2 <= g["gamma"] <= 1.4:
            issues.warning(f"γ = {g['gamma']:g} is unusual for the {name} (typically 1.25–1.38).", section, "gamma")

    lhv = config.get("fuelProperties", {}).get("calorific")
    if lhv is not None:
        if lhv <= 0:
            issues.error("The fuel heating value must be positive.", "fuelProperties", "calorific")
        elif lhv < 1e4:
            issues.error(f"LHV = {lhv:g}: the heating value must be given in J/kg (e.g. 43e6).", "fuelProperties", "calorific")
        elif not 30e6 <= lhv <= 125e6:
            issues.warning(f"LHV = {lhv / 1e6:g} MJ/kg is outside the range of aviation fuels (≈ 42–44 MJ/kg, 120 for H₂).",
                           "fuelProperties", "calorific")


def _efficiency(issues, block, name, key, label, low):
    if key not in block:
        return
    v = block[key]
    path = ("components", name, key)
    if v <= 0 or v > 1:
        issues.error(f"{label} of the {COMPONENT_NAMES[name]} must be in (0, 1] (got {v:g}).", *path)
    elif v < low:
        issues.warning(f"{label} of the {COMPONENT_NAMES[name]} = {v:g} is unusually low (typically > {low:g}).", *path)


def _heat_addition(issues, config, name, t_max_warn):
    block = config["components"][name]
    label = COMPONENT_NAMES[name]
    hot = {**GAS_DEFAULTS["hotGasProperties" if name == "combustor" else "postcombustionProperties"],
           **config.get("hotGasProperties" if name == "combustor" else "postcombustionProperties", {})}
    lhv = config.get("fuelProperties", {}).get("calorific", 42e6)
    eta = block.get("efficiency", 1.0)

    has_T, has_f = "outlet_temperature" in block, "fuel_ratio" in block
    if not has_T and not has_f:
        issues.error(f"Specify either the outlet temperature or the fuel/air ratio of the {label}.", "components", name)
        return
    if has_T and has_f:
        issues.warning(f"Both outlet temperature and fuel/air ratio are given for the {label}: "
                       "the solver uses the temperature and ignores the fuel/air ratio.", "components", name, "fuel_ratio")
    if has_T:
        T = block["outlet_temperature"]
        path = ("components", name, "outlet_temperature")
        if T <= 0:
            issues.error(f"The {label} outlet temperature must be positive (in kelvin).", *path)
        elif lhv > 0 and 0 < eta <= 1 and eta * lhv <= hot["cp"] * T:
            issues.error(f"T = {T:g} K cannot be reached with this fuel: ηb·LHV ≤ cp·T.", *path)
        elif T > t_max_warn:
            issues.warning(f"{label.capitalize()} outlet temperature {T:g} K is beyond current material limits "
                           f"(≈ {t_max_warn:g} K).", *path)
        elif name == "combustor" and T < 900:
            issues.warning(f"Turbine inlet temperature {T:g} K is very low for a gas turbine.", *path)
    else:
        f = block["fuel_ratio"]
        path = ("components", name, "fuel_ratio")
        if f <= 0:
            issues.error(f"The {label} fuel/air ratio must be positive.", *path)
        elif f > F_STOICH:
            issues.warning(f"f = {f:g} is above the stoichiometric value (≈ {F_STOICH}): "
                           "the extra fuel cannot burn completely.", *path)


def _check_components(config, engine, issues):
    comps = config["components"]

    for name, block in comps.items():
        if name not in COMPONENT_KEYS or not isinstance(block, dict):
            continue
        adiabatic_low = 0.6 if name.startswith("nozzle") else 0.7
        if name == "intake":
            _efficiency(issues, block, name, "efficiency", "Pressure recovery πd", 0.85)
        elif name in ("combustor", "postCombustor"):
            _efficiency(issues, block, name, "efficiency", "Combustion efficiency", 0.85)
            _efficiency(issues, block, name, "mechanical_efficiency", "Pressure recovery", 0.85)
        elif name == "propeller":
            _efficiency(issues, block, name, "efficiency", "Efficiency", 0.6)
            _efficiency(issues, block, name, "gearbox_efficiency", "Gearbox efficiency", 0.9)
        else:
            _efficiency(issues, block, name, "efficiency", "Adiabatic efficiency", adiabatic_low)
            _efficiency(issues, block, name, "mechanical_efficiency", "Mechanical efficiency", 0.9)

    for name in ("fan", "compressor"):
        if name not in comps:
            continue
        block = comps[name]
        path = ("components", name, "pressure_ratio")
        if "pressure_ratio" not in block:
            issues.error(f"The {name} pressure ratio is required.", *path)
            continue
        beta = block["pressure_ratio"]
        if beta < 1:
            issues.error(f"The {name} pressure ratio must be ≥ 1 (got {beta:g}).", *path)
        elif beta == 1 and name == "compressor":
            issues.warning("Compressor pressure ratio = 1: there is no compression.", *path)
        elif name == "compressor" and beta > 60:
            issues.warning(f"Compressor pressure ratio {beta:g} is beyond existing engines (≈ 60).", *path)
        elif name == "fan" and beta > 4:
            issues.warning(f"Fan pressure ratio {beta:g} is very high (≈ 1.4–1.8 for high-BPR fans, up to ≈ 4 for low-BPR).", *path)

    if "fan" in comps and "compressor" in comps:
        opr = comps["fan"].get("pressure_ratio", 1) * comps["compressor"].get("pressure_ratio", 1)
        if opr > 70:
            issues.warning(f"Overall pressure ratio βf·βc = {opr:g} is beyond existing engines (≈ 60).",
                           "components", "compressor", "pressure_ratio")

    if engine == "turbofan_SF":
        fan = comps["fan"]
        if "BPR" not in fan:
            issues.error("The bypass ratio BPR is required for a separate-flow turbofan.", "components", "fan", "BPR")
        elif fan["BPR"] < 0:
            issues.error("The bypass ratio must be ≥ 0.", "components", "fan", "BPR")
        elif fan["BPR"] > 20:
            issues.warning(f"BPR = {fan['BPR']:g} is beyond existing turbofans (≈ 12).", "components", "fan", "BPR")
        if fan.get("pressure_ratio", 1) == 1 and fan.get("BPR", 0) > 0:
            issues.warning("Fan pressure ratio = 1: the bypass flow produces no thrust.", "components", "fan", "pressure_ratio")
        for n in ("nozzleMain", "nozzleSecondary"):
            if comps[n].get("onlyConvergent"):
                issues.warning("Convergent-only nozzles for separate flows are listed as not yet validated (see README).",
                               "components", n, "onlyConvergent")

    if engine == "turbofan_AF":
        fan = comps["fan"]
        if fan.get("pressure_ratio", 1) <= 1:
            issues.error("The fan pressure ratio must be > 1 for a mixed-flow turbofan: the BPR is computed from the "
                         "fan work.", "components", "fan", "pressure_ratio")
        if "BPR" in fan:
            issues.info("For a mixed-flow turbofan the BPR is computed (LP power balance); the given value is ignored.",
                        "components", "fan", "BPR")

    _heat_addition(issues, config, "combustor", 2100)
    if "postCombustor" in comps and "postCombustor" in OPTIONAL_COMPONENTS[engine]:
        _heat_addition(issues, config, "postCombustor", 2400)

    if engine == "turboprop":
        prop = comps["propeller"]
        if "Phi" not in prop:
            issues.error("The propeller diameter is required.", "components", "propeller", "Phi")
        elif prop["Phi"] <= 0:
            issues.error("The propeller diameter must be positive.", "components", "propeller", "Phi")
        elif prop["Phi"] < comps["intake"].get("Phi", 0):
            issues.warning("The propeller diameter is smaller than the intake diameter.", "components", "propeller", "Phi")
        if "alpha_power" in prop:
            a = prop["alpha_power"]
            if a <= 0 or a > 1:
                issues.error(f"The power split α must be in (0, 1] (got {a:g}).", "components", "propeller", "alpha_power")
            elif a == 1:
                issues.info("α = 1: all the available enthalpy goes to the propeller, the jet gives no thrust.",
                            "components", "propeller", "alpha_power")


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
SOLVER_MESSAGES = [
    ("T_static_out > T_total_inlet",
     "The flow reaches the nozzle below ambient pressure: the turbines extract more work than the gas can provide "
     "at this pressure level. Raise the turbine inlet temperature, the pressure ratio or the component efficiencies, "
     "or lower the propeller power split α / the BPR."),
    ("division by zero", "Division by zero in the solver: check for zero mass flow, efficiency or temperature."),
]


def explain_exception(exc, config=None):
    """(message, path) for an exception raised by the solver"""
    text = str(exc) or exc.__class__.__name__
    for key, message in SOLVER_MESSAGES:
        if key in text:
            path = []
            if key.startswith("T_static") and config is not None:
                comb = config["components"]["combustor"]
                path = ["components", "combustor", "outlet_temperature" if "outlet_temperature" in comb else "fuel_ratio"]
            return message, path
    return f"The solver failed: {text}", []


def diagnose(config, solve):
    """Validate the inputs, run solve(config) and check the results.

    Returns (results or None, console text, issues); results are None when an
    error-level issue makes the case meaningless. solve must return (results, console).
    """
    issues = validate_inputs(config)
    if issues.has_errors:
        return None, "", tidy(issues)
    try:
        results, console = solve(config)
    except Exception as e:  # noqa: BLE001 - every solver failure is reported to the user
        message, path = explain_exception(e, config)
        issues.error(message, *path)
        return None, "", tidy(issues)
    issues += check_results(config, results)
    return (None if issues.has_errors else results), console, tidy(issues)


def tidy(issues):
    """errors first; drop warnings/infos on an input that already has an error"""
    order = {"error": 0, "warning": 1, "info": 2}
    error_paths = {tuple(i["path"]) for i in issues if i["level"] == "error" and i["path"]}
    kept = [i for i in issues if i["level"] == "error" or tuple(i["path"]) not in error_paths]
    return Issues(sorted(kept, key=lambda i: order[i["level"]]))


def check_results(config, results):
    issues = Issues()
    engine = config["engineType"]
    comps = config["components"]
    p0 = config["airProperties"]["pressure"]
    st = {s["name"]: s for s in results["stations"]}
    perf = results["performance"]

    def finite(v):
        return isinstance(v, (int, float)) and math.isfinite(v)

    bad = [s["name"] for s in results["stations"]
           if not (finite(s["temperature"]) and finite(s["pressure"]) and s["temperature"] > 0 and s["pressure"] > 0)]
    if bad:
        issues.error("Non-physical state (negative or undefined temperature/pressure) at: " + ", ".join(bad)
                     + ". The turbine cannot deliver the work required by the compressor/fan: raise the turbine "
                       "inlet temperature or lower the pressure ratios / BPR.", "components", "combustor")
        return issues

    # combustor
    comb = st["Combustor"]
    T_in = st["Compressor"]["temperature"]
    if comb["fuel_ratio"] <= 0:
        issues.error(f"The turbine inlet temperature ({comb['temperature']:.0f} K) must be higher than the compressor "
                     f"exit temperature ({T_in:.0f} K).", "components", "combustor", "outlet_temperature")
    elif "outlet_temperature" not in comps["combustor"]:
        if comb["temperature"] > 2100:
            issues.warning(f"The resulting turbine inlet temperature {comb['temperature']:.0f} K is beyond current "
                           "material limits (≈ 2100 K).", "components", "combustor", "fuel_ratio")
    elif comb["fuel_ratio"] > F_STOICH:
        issues.warning(f"The required fuel/air ratio f = {comb['fuel_ratio']:.4f} is above stoichiometric "
                       f"(≈ {F_STOICH}).", "components", "combustor", "outlet_temperature")

    # afterburner
    if "PostCombustor" in st:
        ab = st["PostCombustor"]
        upstream = st["Mixing zone" if engine == "turbofan_AF" else "Turbine HP"]
        key = "outlet_temperature" if "outlet_temperature" in comps["postCombustor"] else "fuel_ratio"
        if ab["fuel_ratio"] <= 0:
            issues.error(f"The afterburner outlet temperature ({ab['temperature']:.0f} K) must be higher than its inlet "
                         f"temperature ({upstream['temperature']:.0f} K).", "components", "postCombustor", key)
        else:
            if key == "fuel_ratio" and ab["temperature"] > 2400:
                issues.warning(f"The resulting afterburner temperature {ab['temperature']:.0f} K is very high (≈ 2400 K max).",
                               "components", "postCombustor", key)
            # fuel/air ratio of the whole air flowing through the afterburner
            air_total = results["mass_flow_main"] + (results["mass_flow_secondary"] if engine == "turbofan_AF" else 0)
            f_overall = (comb["fuel_mass"] + ab["fuel_mass"]) / air_total
            if f_overall > F_STOICH:
                issues.warning(f"The overall fuel/air ratio with afterburner ({f_overall:.4f}) is above stoichiometric "
                               f"(≈ {F_STOICH}): not all the fuel can burn.", "components", "postCombustor", key)

    # mixed-flow turbofan
    if engine == "turbofan_AF":
        bpr = results["mass_flow_secondary"] / results["mass_flow_main"]
        if st["Turbine HP"]["pressure"] <= st["Fan"]["pressure"]:
            issues.error("The HP turbine exit pressure is already below the fan exit pressure: the LP turbine cannot "
                         "expand to the mixer pressure. Raise the turbine inlet temperature or lower βc.",
                         "components", "compressor", "pressure_ratio")
        elif bpr <= 0:
            issues.error(f"The LP turbine cannot drive the fan (computed BPR = {bpr:.3f} ≤ 0): raise the turbine inlet "
                         "temperature or lower the fan pressure ratio.", "components", "fan", "pressure_ratio")
        elif bpr > 15:
            issues.warning(f"The computed BPR = {bpr:.2f} is unusually high for a mixed-flow turbofan.",
                           "components", "fan", "pressure_ratio")
        if bpr > 0 and st["Turbine LP"]["temperature"] < st["Fan"]["temperature"]:
            issues.warning("The core stream reaches the mixer colder than the bypass stream.", "components", "fan", "pressure_ratio")

    # turboprop power split
    if engine == "turboprop" and "propeller" in results:
        a = results["propeller"]["alpha_power"]
        if "alpha_power" not in comps["propeller"] and not 0 < a <= 1:
            issues.error(f"The optimal power split α = {a:.3f} is outside (0, 1]: at this flight speed the propeller "
                         "is not convenient. Specify α explicitly.", "components", "propeller", "alpha_power")

    # nozzles
    def nozzle_info(noz, key):
        n = results.get(key)
        if n and n["onlyConvergent"] and n["mach"] < 0.999:
            issues.info(f"The convergent {noz} is not choked (critical pressure below ambient): "
                        f"the exit is subsonic (M = {n['mach']:.2f}) and adapted.")
    nozzle_info("nozzle", "mainNozzle")
    nozzle_info("bypass nozzle", "secondaryNozzle")

    # performance
    if not all(finite(perf[k]) for k in ("thrust", "TSFC", "thermal", "propulsive", "global")):
        issues.error("The performance figures are undefined (division by zero): check the inputs.")
        return issues
    if perf["thrust"] <= 0:
        issues.warning(f"Net thrust is {perf['thrust'] / 1000:.2f} kN (≤ 0): the exhaust is slower than the flight speed. "
                       "TSFC and efficiencies are not meaningful.")
    if perf["thermal"] >= 1:
        issues.error("Thermal efficiency ≥ 1: the inputs are inconsistent (check LHV and gas properties).")
    elif perf["thermal"] <= 0:
        issues.warning("Thermal efficiency ≤ 0: the cycle does not convert fuel energy into jet kinetic energy.")

    return issues
