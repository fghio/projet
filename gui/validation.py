"""
Sanity checks on ProJet inputs and results.

Every issue is a dict {"level": "error" | "warning" | "info", "message": str, "path": [...]}
where "path" points to the input (config keys) the issue refers to, if any.
Errors mean the case cannot (or must not) be computed; warnings flag values that are
physically questionable or outside the usual range for this kind of engine.
"""
import math

ENGINE_TYPES = ["turbojet", "turbofan_SF", "turbofan_AF", "turboprop"]
# endoreactors: not shown by the GUI yet
ROCKET_TYPES = ["idealRocket", "solidRocket", "endBurner"]

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
    if engine not in ENGINE_TYPES + ROCKET_TYPES:
        issues.error(f"Unknown engineType '{engine}'. Available: {', '.join(ENGINE_TYPES + ROCKET_TYPES)}.", "engineType")
        return issues

    comps = config.get("components")
    if not isinstance(comps, dict):
        issues.error("The 'components' section is missing.", "components")
        return issues

    if engine in ROCKET_TYPES:
        return _validate_rocket_inputs(config, issues)

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
    engine = config["engineType"]
    if engine in ROCKET_TYPES:
        return _check_rocket_results(config, results)

    issues = Issues()
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


# ---------------------------------------------------------------------------
# Rockets (endoreactors)
# ---------------------------------------------------------------------------
ROCKET_COMPONENT_KEYS = {
    "idealRocket": {
        "chamber": {"pressure", "temperature", "mixture_ratio", "thrust", "mass_flow", "throat_diameter"},
        "nozzle": {"efficiency", "area_ratio"},
    },
    "solidRocket": {
        "grain": {"segments", "outer_diameter", "core_diameter", "segment_length", "inhibited_ends"},
        "nozzle": {"throat_diameter", "area_ratio", "efficiency"},
    },
    "endBurner": {
        "grain": {"diameter"},          # plus the layer1, layer2, ... blocks
        "nozzle": {"throat_diameter", "area_ratio", "efficiency"},
    },
}
PROPELLANT_KEYS = {"density", "flame_temperature", "burn_rate_coefficient", "burn_rate_exponent"}
LAYER_KEYS = PROPELLANT_KEYS | {"length", "gamma", "R", "cp"}
ROCKET_SECTION_KEYS = {
    "idealRocket": {
        "ambientProperties": {"pressure"},
        "hotGasProperties": {"cp", "gamma", "R"},
        "flightConditions": {"altitude_km"},
    },
    "solidRocket": {
        "ambientProperties": {"pressure"},
        "hotGasProperties": {"cp", "gamma", "R"},
        "propellantProperties": PROPELLANT_KEYS,
        "flightConditions": {"altitude_km"},
    },
    "endBurner": {
        "ambientProperties": {"pressure"},
        "hotGasProperties": {"cp", "gamma", "R"},
        "flightConditions": {"altitude_km"},
    },
}
ROCKET_SIZING_KEYS = ("thrust", "mass_flow", "throat_diameter")


def critical_pressure_ratio(g):
    """p*/p_c of a choked throat"""
    return (2 / (g + 1)) ** (g / (g - 1))


def _check_rocket_structure(config, engine, issues):
    comps = config["components"]
    sections, components = ROCKET_SECTION_KEYS[engine], ROCKET_COMPONENT_KEYS[engine]

    for key, value in config.items():
        if key in ("engineType", "components"):
            continue
        if key not in sections:
            issues.warning(f"Section '{key}' is not used by a {engine} and is ignored.", key)
            continue
        if not isinstance(value, dict):
            issues.error(f"Section '{key}' must contain parameters.", key)
            continue
        for k, v in value.items():
            if k not in sections[key]:
                issues.error(f"Unknown parameter '{k}' in '{key}' (allowed: {', '.join(sorted(sections[key]))}).", key, k)
            elif not is_number(v):
                issues.error(f"'{key}.{k}' must be a finite number (got {v!r}).", key, k)

    for name in components:
        if not isinstance(comps.get(name), dict):
            issues.error(f"The {name} ('{name}') is required for a {engine}.", "components", name)
    for name, block in comps.items():
        if name not in components:
            issues.warning(f"Component '{name}' is not part of a {engine} and is ignored.", "components", name)
            continue
        if not isinstance(block, dict):
            continue
        for k, v in block.items():
            if engine == "endBurner" and name == "grain" and k.startswith("layer"):
                _check_layer_structure(k, v, issues)
                continue
            if k not in components[name]:
                issues.error(f"Unknown parameter '{k}' for the {name} "
                             f"(allowed: {', '.join(sorted(components[name]))}).", "components", name, k)
            elif k == "inhibited_ends":
                if not isinstance(v, bool) and v not in (0, 1):
                    issues.error(f"'{name}.inhibited_ends' must be True or False (got {v!r}).", "components", name, k)
            elif not is_number(v):
                issues.error(f"'{name}.{k}' must be a finite number (got {v!r}).", "components", name, k)


def _check_layer_structure(name, block, issues):
    P = ("components", "grain", name)
    if not name[5:].isdigit() or int(name[5:]) < 1:
        issues.error(f"Grain layers are named layer1, layer2, ... (got '{name}').", *P)
        return
    if not isinstance(block, dict):
        issues.error(f"Layer '{name}' must contain parameters.", *P)
        return
    for k, v in block.items():
        if k not in LAYER_KEYS:
            issues.error(f"Unknown parameter '{k}' for {name} (allowed: {', '.join(sorted(LAYER_KEYS))}).", *P, k)
        elif not is_number(v):
            issues.error(f"'{name}.{k}' must be a finite number (got {v!r}).", *P, k)


def _check_rocket_gas(config, issues):
    """combustion products: γ and R depend on the propellants, there is no sensible default"""
    gas = config.get("hotGasProperties", {})
    H = ("hotGasProperties",)
    _check_gas_values(issues, gas, {k: H + (k,) for k in ("gamma", "R", "cp")}, "the combustion products")


def _check_gas_values(issues, gas, paths, name):
    """gas: γ, R and optionally cp; paths: where each value comes from (for the messages)"""
    for key, label in (("gamma", "γ"), ("R", "gas constant R [J/(kg·K)]")):
        if gas.get(key) is None:
            issues.error(f"The {label} of {name} is required for a rocket "
                         "(e.g. LOX/RP-1: γ ≈ 1.22, R ≈ 380 J/(kg·K)).", *paths[key])
    if issues.has_errors:
        return
    g, R = gas["gamma"], gas["R"]
    if g <= 1:
        issues.error(f"γ of {name} must be greater than 1.", *paths["gamma"])
    elif not 1.1 <= g <= 1.4:
        issues.warning(f"γ = {g:g} is unusual for rocket combustion products (typically 1.15–1.3).", *paths["gamma"])
    if R <= 0:
        issues.error(f"R of {name} must be positive.", *paths["R"])
    elif not 250 <= R <= 900:
        issues.warning(f"R = {R:g} J/(kg·K) means a molar mass of {8314.46 / R:.1f} kg/kmol, unusual for rocket "
                       "combustion products (≈ 10–30 kg/kmol).", *paths["R"])
    if gas.get("cp") is not None and g > 1 and R > 0:
        cp_from_gamma = g * R / (g - 1)
        if gas["cp"] <= R:
            issues.error(f"cp of {name} must be larger than R.", *paths["cp"])
        elif abs(cp_from_gamma - gas["cp"]) / gas["cp"] > 0.03:
            issues.warning(f"cp, γ and R of {name} are not consistent: γR/(γ−1) = {cp_from_gamma:.0f} "
                           f"J/(kg·K) vs cp = {gas['cp']:g} J/(kg·K).", *paths["cp"])


def _check_flame_temperature(issues, T, *path):
    if T <= 0:
        issues.error("The combustion temperature must be positive (in kelvin).", *path)
    elif not 1500 <= T <= 4000:
        issues.warning(f"Combustion temperature {T:g} K is outside the usual range of rocket propellants (1500–4000 K).", *path)


def _check_ideal_chamber(config, issues):
    chamber = config["components"]["chamber"]
    C = ("components", "chamber")
    for key, unit in (("pressure", "Pa"), ("temperature", "K")):
        if key not in chamber:
            issues.error(f"The chamber {key} [{unit}] is required.", *C, key)
    if issues.has_errors:
        return
    p_c = chamber["pressure"]
    if p_c <= 0:
        issues.error("The chamber pressure must be positive.", *C, "pressure")
    elif p_c < 1e4:
        issues.error(f"Chamber pressure {p_c:g} Pa is too low: the pressure must be given in Pa, not MPa or bar.", *C, "pressure")
    elif not 3e5 <= p_c <= 3.5e7:
        issues.warning(f"Chamber pressure {p_c / 1e6:g} MPa is outside the usual range (0.3–35 MPa).", *C, "pressure")
    _check_flame_temperature(issues, chamber["temperature"], *C, "temperature")

    sizing = [k for k in ROCKET_SIZING_KEYS if k in chamber]
    if not sizing:
        issues.error("Size the engine with one of: thrust [N], mass_flow [kg/s] or throat_diameter [m].", *C)
    elif len(sizing) > 1:
        issues.error(f"Give only one of thrust, mass_flow, throat_diameter (got {', '.join(sizing)}).", *C, sizing[1])
    else:
        if chamber[sizing[0]] <= 0:
            issues.error(f"The {sizing[0].replace('_', ' ')} must be positive.", *C, sizing[0])

    if "mixture_ratio" in chamber:
        of = chamber["mixture_ratio"]
        if of <= 0:
            issues.error("The mixture ratio O/F must be positive.", *C, "mixture_ratio")
        elif of > 10:
            issues.warning(f"O/F = {of:g} is very high (≈ 2–3 for LOX/RP-1, 5–6 for LOX/LH2, 8 for N2O).", *C, "mixture_ratio")


def _check_propellant(config, issues):
    _check_propellant_block(config.get("propellantProperties", {}), ("propellantProperties",), issues)


def _check_propellant_block(prop, P, issues):
    labels = {"density": "density [kg/m³]", "flame_temperature": "flame temperature [K]",
              "burn_rate_coefficient": "burn rate coefficient a [mm/s, p in MPa]", "burn_rate_exponent": "pressure exponent n"}
    for key, label in labels.items():
        if key not in prop:
            issues.error(f"The propellant {label} is required.", *P, key)
    if issues.has_errors:
        return
    rho = prop["density"]
    if rho <= 0:
        issues.error("The propellant density must be positive.", *P, "density")
    elif not 1000 <= rho <= 2000:
        issues.warning(f"Propellant density {rho:g} kg/m³ is unusual (≈ 1600–1850 for composites, 1550–1650 for double base).",
                       *P, "density")
    _check_flame_temperature(issues, prop["flame_temperature"], *P, "flame_temperature")
    a = prop["burn_rate_coefficient"]
    if a <= 0:
        issues.error("The burn rate coefficient must be positive.", *P, "burn_rate_coefficient")
    elif a < 0.1 or a > 100:
        issues.warning(f"a = {a:g} mm/s at 1 MPa is far from usual propellants (≈ 1–20 mm/s): the law is r[mm/s] = a·p[MPa]ⁿ.",
                       *P, "burn_rate_coefficient")
    n = prop["burn_rate_exponent"]
    if n < 0:
        issues.error("The pressure exponent n must be ≥ 0.", *P, "burn_rate_exponent")
    elif n >= 1:
        issues.error(f"With n = {n:g} ≥ 1 the motor has no stable operating pressure: the pressure diverges.", *P, "burn_rate_exponent")
    elif n > 0.7:
        issues.warning(f"n = {n:g} is high: the chamber pressure is very sensitive to Kn (typically 0.2–0.5).", *P, "burn_rate_exponent")


def _check_grain(config, issues):
    grain = config["components"]["grain"]
    nozzle = config["components"]["nozzle"]
    G = ("components", "grain")
    labels = {"segments": "number of segments", "outer_diameter": "outer diameter [m]",
              "core_diameter": "core diameter [m]", "segment_length": "segment length [m]"}
    for key, label in labels.items():
        if key not in grain:
            issues.error(f"The grain {label} is required.", *G, key)
    if issues.has_errors:
        return
    N, D, d, L = grain["segments"], grain["outer_diameter"], grain["core_diameter"], grain["segment_length"]
    if N < 1 or N != int(N):
        issues.error(f"The number of segments must be a positive integer (got {N:g}).", *G, "segments")
    if D <= 0:
        issues.error("The grain outer diameter must be positive.", *G, "outer_diameter")
    if d <= 0:
        issues.error("The core diameter must be positive (BATES grains have a port).", *G, "core_diameter")
    elif D > 0 and d >= D:
        issues.error(f"The core diameter ({d:g} m) must be smaller than the outer diameter ({D:g} m).", *G, "core_diameter")
    if L <= 0:
        issues.error("The segment length must be positive.", *G, "segment_length")
    if issues.has_errors:
        return
    if D > 5:
        issues.warning(f"Outer diameter {D:g} m is in metres? It is larger than any existing motor (≈ 3.7 m).", *G, "outer_diameter")
    if not grain.get("inhibited_ends") and L < (D - d):
        issues.info("The segments are short: they burn out along the length before the port reaches the case.", *G, "segment_length")

    Dt = nozzle.get("throat_diameter")
    if is_number(Dt) and Dt > 0:
        ratio = d ** 2 / Dt ** 2
        if ratio <= 1:
            issues.error(f"The port area is not larger than the throat area (Ap/At = {ratio:.2f}): the flow would choke in "
                         "the port. Enlarge the core or reduce the throat.", *G, "core_diameter")
        elif ratio < 2:
            issues.warning(f"Initial port-to-throat area ratio Ap/At = {ratio:.2f} < 2: high port velocity, erosive burning "
                           "(not modelled) would raise the initial pressure.", *G, "core_diameter")


def _check_rocket_nozzle(config, engine, issues):
    nozzle = config["components"]["nozzle"]
    N = ("components", "nozzle")
    _efficiency(issues, nozzle, "nozzle", "efficiency", "Adiabatic efficiency", 0.85)
    p_a = config.get("ambientProperties", {}).get("pressure", 0)
    if p_a < 0:
        issues.error("The ambient pressure must be ≥ 0 (0 = vacuum).", "ambientProperties", "pressure")

    if engine in ("solidRocket", "endBurner"):
        if "throat_diameter" not in nozzle:
            issues.error("The nozzle throat diameter [m] is required.", *N, "throat_diameter")
        elif nozzle["throat_diameter"] <= 0:
            issues.error("The throat diameter must be positive.", *N, "throat_diameter")
        if "area_ratio" not in nozzle:
            issues.error("Give the area ratio Ae/At: the chamber pressure changes during the burn, so the nozzle "
                         "cannot stay adapted.", *N, "area_ratio")

    if "area_ratio" in nozzle:
        eps = nozzle["area_ratio"]
        if eps <= 1:
            issues.error(f"The area ratio Ae/At must be > 1 for a convergent-divergent nozzle (got {eps:g}).", *N, "area_ratio")
        elif eps > 300:
            issues.warning(f"Area ratio {eps:g} is beyond existing nozzles (≈ 300 for upper stages).", *N, "area_ratio")
    elif p_a == 0 and engine == "idealRocket":
        issues.error("In vacuum an adapted nozzle would be infinitely long: give the area ratio Ae/At.", *N, "area_ratio")


def _check_end_burner(config, issues):
    from src.rocket.grain import layerBlocks
    grain, nozzle = config["components"]["grain"], config["components"]["nozzle"]
    G = ("components", "grain")
    common = config.get("hotGasProperties", {})
    layers = layerBlocks(grain)
    if not layers:
        issues.error("Give at least one grain layer (layer1 { ... }), starting from the nozzle side.", *G)
        return
    for name, layer in layers:
        L = G + (name,)
        if "length" not in layer:
            issues.error(f"The length [m] of {name} is required.", *L, "length")
        elif layer["length"] <= 0:
            issues.error(f"The length of {name} must be positive.", *L, "length")
        _check_propellant_block(layer, L, issues)
        # γ and R of the layer, or the common ones
        gas, paths = {}, {}
        for k in ("gamma", "R", "cp"):
            own = k in layer or (k == "cp" and ("gamma" in layer or "R" in layer))
            gas[k] = layer.get(k) if own else common.get(k)
            paths[k] = L + (k,) if own or k not in common else ("hotGasProperties", k)
        _check_gas_values(issues, gas, paths, f"the products of {name}")

    if "diameter" not in grain:
        issues.error("The grain diameter [m] is required.", *G, "diameter")
        return
    D = grain["diameter"]
    if D <= 0:
        issues.error("The grain diameter must be positive.", *G, "diameter")
    elif D > 5:
        issues.warning(f"Grain diameter {D:g} m is in metres? It is larger than any existing motor (≈ 3.7 m).", *G, "diameter")
    Dt = nozzle.get("throat_diameter")
    if D > 0 and is_number(Dt) and Dt > 0 and Dt >= D:
        issues.error(f"The throat ({Dt:g} m) must be smaller than the grain diameter ({D:g} m): Kn = Ab/At ≤ 1.",
                     "components", "nozzle", "throat_diameter")


def _validate_rocket_inputs(config, issues):
    engine = config["engineType"]
    _check_rocket_structure(config, engine, issues)
    if issues.has_errors:
        return issues

    if engine == "endBurner":
        _check_end_burner(config, issues)
        _check_rocket_nozzle(config, engine, issues)
        alt = config.get("flightConditions", {}).get("altitude_km")
        if alt is not None and alt < 0:
            issues.warning(f"Altitude {alt:g} km is negative.", "flightConditions", "altitude_km")
        return issues

    _check_rocket_gas(config, issues)
    if issues.has_errors:
        return issues
    if engine == "idealRocket":
        _check_ideal_chamber(config, issues)
    else:
        _check_propellant(config, issues)
        _check_grain(config, issues)
    _check_rocket_nozzle(config, engine, issues)

    g = config["hotGasProperties"]["gamma"]
    p_a = config.get("ambientProperties", {}).get("pressure", 0)
    if engine == "idealRocket" and not issues.has_errors and p_a > 0:
        p_c = config["components"]["chamber"]["pressure"]
        critical = critical_pressure_ratio(g)
        if p_a >= p_c * critical:
            issues.error(f"The ambient pressure is above the critical pressure ({p_c * critical:g} Pa): the throat is "
                         "not choked and the rocket model does not apply. Raise the chamber pressure.",
                         "components", "chamber", "pressure")

    alt = config.get("flightConditions", {}).get("altitude_km")
    if alt is not None and alt < 0:
        issues.warning(f"Altitude {alt:g} km is negative.", "flightConditions", "altitude_km")

    return issues


def exit_shock_pressure(p_e, M_e, g):
    """pressure behind a normal shock standing at the exit section"""
    return p_e * (1 + 2 * g / (g + 1) * (M_e ** 2 - 1))


def _check_rocket_results(config, results):
    issues = Issues()
    nozzle = results["mainNozzle"]
    perf = results["performance"]
    p_a = results["ambient_pressure"]
    p_e, M_e = nozzle["exit_pressure"], nozzle["mach"]
    N = ("components", "nozzle", "area_ratio")
    if "burn" in results:
        return _check_burn(config, results, issues)
    g = config["hotGasProperties"]["gamma"]

    if p_a > 0 and not nozzle["adapted"]:
        p_shock = exit_shock_pressure(p_e, M_e, g)
        if p_shock < p_a:
            issues.error(f"Strongly over-expanded nozzle: even a normal shock at the exit ({p_shock / 1000:.1f} kPa) does "
                         f"not reach ambient pressure ({p_a / 1000:.1f} kPa), so the shock moves inside the nozzle and the "
                         "isentropic model does not apply. Lower the area ratio.", *N)
            return issues
        if p_e < 0.4 * p_a:
            issues.warning(f"Exit pressure {p_e / 1000:.1f} kPa is below 40% of ambient (Summerfield criterion): the jet "
                           "likely separates from the wall and the computed thrust is not reliable.", *N)
        elif p_e < 0.99 * p_a:
            issues.info(f"The nozzle is over-expanded (pe = {p_e / 1000:.1f} kPa < pa): a smaller area ratio would give more thrust.", *N)
        elif p_e > 1.01 * p_a:
            issues.info(f"The nozzle is under-expanded (pe = {p_e / 1000:.1f} kPa > pa): a larger area ratio would give more thrust.", *N)

    values = [perf[k] for k in ("thrust", "Isp", "CF", "c_star")]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
        issues.error("The performance figures are undefined: check the inputs.")
    elif perf["thrust"] <= 0:
        issues.warning(f"Thrust is {perf['thrust'] / 1000:.2f} kN (≤ 0): the pressure thrust loss exceeds the jet thrust.", *N)

    return issues


def _check_burn(config, results, issues):
    """checks along the whole burn: the nozzle sees every chamber pressure from ignition to burnout"""
    burn = results["burn"]
    h = burn["history"]
    p_a = results["ambient_pressure"]
    N = ("components", "nozzle")
    T = ("components", "nozzle", "throat_diameter")

    values = [burn[k] for k in ("burn_time", "total_impulse", "max_pressure", "Isp")]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values) or burn["burn_time"] <= 0:
        issues.error("The burn could not be computed: check the inputs.")
        return issues

    # each point carries its own γ and exit Mach (the layers of a cigarette grain may differ)
    if p_a > 0 and min(p * critical_pressure_ratio(g) for p, g in zip(h["pressure"], h["gamma"])) <= p_a:
        issues.error(f"The chamber pressure drops to {burn['min_pressure'] / 1e6:.3f} MPa: the throat is no longer choked "
                     "and the model does not apply. Reduce the throat diameter.", *T)
        return issues

    p_max, p_min = burn["max_pressure"], burn["min_pressure"]
    if p_max > 2e7:
        issues.warning(f"Maximum chamber pressure {p_max / 1e6:.1f} MPa is very high for a solid motor case (≈ 3–15 MPa): "
                       "enlarge the throat.", *T)
    if p_min < 1e6:
        issues.warning(f"The chamber pressure falls to {p_min / 1e6:.2f} MPa: below ≈ 1–2 MPa composite propellants burn "
                       "irregularly (combustion stability limit).", *T)

    if p_a > 0:
        times, pressures = h["time"], h["exit_pressure"]
        points = list(zip(pressures, h["exit_mach"], h["gamma"]))
        dt = [times[i + 1] - times[i] for i in range(len(times) - 1)]
        def fraction(cond):
            return sum(d for d, a, b in zip(dt, points[:-1], points[1:]) if cond(*a) or cond(*b)) / burn["burn_time"]
        shock = fraction(lambda pe, M, g: exit_shock_pressure(pe, M, g) < p_a)
        separated = fraction(lambda pe, M, g: pe < 0.4 * p_a)
        if shock > 0:
            issues.warning(f"For {shock:.0%} of the burn the nozzle is so over-expanded that a shock stands inside it: "
                           "the thrust in that part is not reliable. Lower the area ratio.", *N, "area_ratio")
        elif separated > 0:
            issues.warning(f"For {separated:.0%} of the burn the exit pressure is below 40% of ambient (Summerfield): "
                           "the jet likely separates.", *N, "area_ratio")
        else:
            p_e_min, p_e_max = min(pressures), max(pressures)
            if p_e_max < 0.99 * p_a:
                issues.info(f"The nozzle is over-expanded for the whole burn (pe = {p_e_min / 1000:.1f}–{p_e_max / 1000:.1f} kPa).", *N, "area_ratio")
            elif p_e_min > 1.01 * p_a:
                issues.info(f"The nozzle is under-expanded for the whole burn (pe = {p_e_min / 1000:.1f}–{p_e_max / 1000:.1f} kPa).", *N, "area_ratio")

    if config["engineType"] == "endBurner":
        if min(h["thrust"]) <= 0:
            issues.warning("The thrust is ≤ 0 during part of the burn: the pressure thrust loss exceeds the jet thrust.", *N, "area_ratio")
        return issues

    ratio = max(h["burn_area"]) / min(h["burn_area"])
    shape = "neutral" if ratio < 1.05 else "progressive-regressive" if h["burn_area"][0] < max(h["burn_area"]) > h["burn_area"][-1] \
        else "progressive" if h["burn_area"][-1] > h["burn_area"][0] else "regressive"
    issues.info(f"Burn area varies by {(ratio - 1):.0%} (max/min) during the burn: {shape} grain.", "components", "grain")

    if min(h["thrust"]) <= 0:
        issues.warning("The thrust is ≤ 0 during part of the burn: the pressure thrust loss exceeds the jet thrust.", *N, "area_ratio")
    return issues
