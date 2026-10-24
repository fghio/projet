import copy
import io
import math
import os
import sys
import threading
import warnings
from contextlib import redirect_stdout

import numpy as np
from flask import Flask, jsonify, redirect, request, send_file, send_from_directory

# make the project root importable
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from engineCycle import parse_openfoam_style, run_engine
from src.write.exerciseText import generate_exercise_text, generate_data_section
from gui.validation import ENGINE_TYPES, ROCKET_TYPES, diagnose

from src.fluids.air import Air
from src.fluids.fuel import Fuel
from src.fluids.hotGas import HotGas
from src.components.mixer import Mixer


static_dir = os.path.join(os.path.dirname(__file__), 'static')
inputs_dir = os.path.join(root_dir, 'etc', 'inputs')

app = Flask(__name__, static_folder=static_dir, static_url_path='/static')

# the engines print to stdout: serialize the runs so that captured outputs don't mix
run_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Station topology: number used in the code, gas flowing out, upstream station
# ---------------------------------------------------------------------------
def station_topology(engine_type, has_postcomb):
    nozzle_gas = "post" if has_postcomb else "hot"

    if engine_type == "turbojet":
        return {
            "Air at entrance": (1, "air", "Ambient"),
            "Intake":          (2, "air", "Air at entrance"),
            "Compressor":      (3, "air", "Intake"),
            "Combustor":       (4, "hot", "Compressor"),
            "Turbine HP":      (5, "hot", "Combustor"),
            "PostCombustor":   (6, "post", "Turbine HP"),
            "Nozzle":          (9, nozzle_gas, "PostCombustor" if has_postcomb else "Turbine HP"),
        }
    if engine_type == "turbofan_SF":
        return {
            "Air at entrance":  (1, "air", "Ambient"),
            "Intake":           (2, "air", "Air at entrance"),
            "Fan":              (3, "air", "Intake"),
            "Compressor":       (4, "air", "Fan"),
            "Combustor":        (5, "hot", "Compressor"),
            "Turbine HP":       (6, "hot", "Combustor"),
            "Turbine LP":       (7, "hot", "Turbine HP"),
            "Main nozzle":      (9, "hot", "Turbine LP"),
            "Secondary nozzle": (8, "air", "Fan"),
        }
    if engine_type == "turbofan_AF":
        return {
            "Air at entrance": (1, "air", "Ambient"),
            "Intake":          (2, "air", "Air at entrance"),
            "Fan":             (3, "air", "Intake"),
            "Compressor":      (4, "air", "Fan"),
            "Combustor":       (5, "hot", "Compressor"),
            "Turbine HP":      (6, "hot", "Combustor"),
            "Turbine LP":      (7, "hot", "Turbine HP"),
            "Mixing zone":     (8, "mix", "Turbine LP"),
            "PostCombustor":   (9, "post", "Mixing zone"),
            "Nozzle":          (10, "post" if has_postcomb else "mix", "PostCombustor" if has_postcomb else "Mixing zone"),
        }
    if engine_type in ROCKET_TYPES:
        # for a solid motor: state at the maximum chamber pressure
        return {
            "Chamber":     (1, "hot", None),
            "Throat":      (2, "hot", "Chamber"),
            "Nozzle exit": (3, "hot", "Throat"),
        }
    if engine_type == "turboprop":
        return {
            "Air at entrance":        (1, "air", "Ambient"),
            "Intake":                 (2, "air", "Air at entrance"),
            "Compressor":             (3, "air", "Intake"),
            "Combustor":              (4, "hot", "Compressor"),
            "Turbine HP":             (5, "hot", "Combustor"),
            "Turbine LP | Propeller": (6, "hot", "Turbine HP"),
            "Nozzle":                 (9, "hot", "Turbine LP | Propeller"),
        }
    raise ValueError(f"Unknown engine type '{engine_type}'")


def rocket_gas(config):
    """combustion products of a rocket: cp from γ and R when not given (as in the solver)"""
    props = dict(config.get('hotGasProperties', {}))
    if 'cp' not in props:
        props['cp'] = props['gamma'] * props['R'] / (props['gamma'] - 1)
    return HotGas(**props)


def gas_properties(config, results):
    if config["engineType"] in ROCKET_TYPES:
        # layered grains: the stations belong to one layer, with its own products
        gases = {"hot": HotGas(**results["station_gas"]) if "station_gas" in results else rocket_gas(config)}
        return {k: {"cp": g.cp, "R": g.R, "gamma": g.gamma, "cp_s": g.gamma * g.R / (g.gamma - 1)}
                for k, g in gases.items()}

    air = Air(**config.get('airProperties', {}))
    hot = HotGas(**config.get('hotGasProperties', {}))
    post = HotGas(**config.get('postcombustionProperties', {}))
    gases = {"air": air, "hot": hot, "post": post}

    if config["engineType"] == "turbofan_AF":
        # same mixing rule used by the solver
        air.mass_flow_main = results["mass_flow_main"]
        air.mass_flow_secondary = results["mass_flow_secondary"]
        fuel = Fuel(**config.get('fuelProperties', {}))
        fuel.mass_fuel = next(s["fuel_mass"] for s in results["stations"] if s["name"] == "Combustor")
        mix = HotGas()
        Mixer(air=air, fuel=fuel, hotGas=hot, mix=mix).updatePropertiesAfterMixing()
        gases["mix"] = mix

    return {k: {"cp": g.cp, "R": g.R, "gamma": g.gamma, "cp_s": g.gamma * g.R / (g.gamma - 1)}
            for k, g in gases.items()}


def enrich_stations(config, results):
    """Add station number, gas and entropy (s = 0 at ambient static conditions,
    or at the chamber state for a rocket, which takes in no air)."""
    comps = config["components"]
    topology = station_topology(config["engineType"], "postCombustor" in comps)
    gases = gas_properties(config, results)

    stations = []
    by_name = {}
    if config["engineType"] not in ROCKET_TYPES:
        air_props = config.get('airProperties', {})
        ambient = {
            "name": "Ambient", "number": 0, "gas": "air", "parent": None,
            "pressure": air_props["pressure"], "temperature": air_props["temperature"],
            "total": False, "entropy": 0.0,
        }
        stations.append(ambient)
        by_name["Ambient"] = ambient

    for st in results["stations"]:
        number, gas, parent = topology[st["name"]]
        if parent is None:
            entry = dict(st, number=number, gas=gas, parent=None, entropy=0.0)
            stations.append(entry)
            by_name[st["name"]] = entry
            continue
        up = by_name[parent]
        g = gases[gas]
        # the solver's isentropic relations use γ: cp = γR/(γ-1) keeps adiabatic
        # reversible steps exactly at constant entropy
        ds = g["gamma"] * g["R"] / (g["gamma"] - 1) * math.log(st["temperature"] / up["temperature"]) \
            - g["R"] * math.log(st["pressure"] / up["pressure"])
        entry = dict(st, number=number, gas=gas, parent=parent, entropy=up["entropy"] + ds)
        stations.append(entry)
        by_name[st["name"]] = entry

    results["stations"] = stations
    results["gases"] = gases
    return results


def check_finite(obj, path=""):
    """Return the list of keys holding NaN/inf (non-physical inputs)."""
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            bad += check_finite(v, f"{path}.{k}" if path else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += check_finite(v, f"{path}[{i}]")
    elif isinstance(obj, (float, np.floating)) and not math.isfinite(obj):
        bad.append(path)
    return bad


def to_builtin(obj):
    if isinstance(obj, dict):
        return {k: to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_builtin(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def simulate(config):
    """Run the solver; return (results, console_text)."""
    buffer = io.StringIO()
    with run_lock, redirect_stdout(buffer), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with np.errstate(all="ignore"):
            results = run_engine(copy.deepcopy(config))
    return results, buffer.getvalue()


# ---------------------------------------------------------------------------
# Input file (OpenFOAM-like) writer
# ---------------------------------------------------------------------------
HEADER = r"""/* ------------------------------ * ------------------------------ *\
  ___                 _      _    |
 |  _ \ _ __ ___     | | ___| |_  |
 | |_) | '__/ _ \ _  | |/ _ \ __| |
 |  __/| | | (_) | |_| |  __/ |_  |
 |_|   |_|  \___/ \___/ \___|\__| |
                                  |
\* ------------------------------ * ------------------------------ */
"""


def format_value(v):
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, float):
        return repr(v)
    return str(v)


def write_block(name, block, indent):
    pad = "    " * indent
    out = [f"{pad}{name}", f"{pad}{{"]
    for k, v in block.items():
        if isinstance(v, dict):
            out += write_block(k, v, indent + 1)
        else:
            out.append(f"{pad}    {k} {format_value(v)};")
    out.append(f"{pad}}}")
    return out


def config_to_input(config):
    lines = [HEADER, f"engineType {config['engineType']};", ""]
    for key, value in config.items():
        if key == "engineType":
            continue
        if isinstance(value, dict):
            lines += write_block(key, value, 0)
            lines.append("")
        else:
            lines.append(f"{key} {format_value(value)};")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ISA atmosphere (troposphere + lower stratosphere)
# ---------------------------------------------------------------------------
def isa(altitude_m):
    g, R, T0, p0, L = 9.80665, 287.05, 288.15, 101325.0, 0.0065
    h_trop = 11000.0
    if altitude_m <= h_trop:
        T = T0 - L * altitude_m
        p = p0 * (T / T0) ** (g / (L * R))
    else:
        T11 = T0 - L * h_trop
        p11 = p0 * (T11 / T0) ** (g / (L * R))
        T = T11
        p = p11 * math.exp(-g * (altitude_m - h_trop) / (R * T11))
    return {"temperature": T, "pressure": p, "density": p / (R * T)}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return send_from_directory(static_dir, 'index.html')


# plotly.js shipped with the plotly python package (offline); CDN otherwise
PLOTLY_CDN = "https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.27.0/plotly.min.js"


def local_plotly_js():
    try:
        import plotly
    except ImportError:
        return None
    path = os.path.join(os.path.dirname(plotly.__file__), 'package_data', 'plotly.min.js')
    return path if os.path.isfile(path) else None


@app.route('/vendor/plotly.min.js')
def plotly_js():
    path = local_plotly_js()
    if path is None:
        return redirect(PLOTLY_CDN)
    return send_file(path, mimetype='application/javascript', max_age=86400)


@app.route('/api/presets')
def presets():
    out = {}
    for engine in ENGINE_TYPES + ROCKET_TYPES:
        path = os.path.join(inputs_dir, f"input_{engine}")
        if os.path.isfile(path):
            with open(path) as f:
                out[engine] = parse_openfoam_style(f.read())
    return jsonify(out)


def evaluate(config):
    """Validate, solve and check one case.

    Returns (results or None, console text, issues). Results are None when an
    error-level issue makes the case meaningless.
    """
    results, console, issues = diagnose(config, simulate)
    if results is None:
        return None, console, issues

    try:
        results = enrich_stations(config, results)
    except (ValueError, ZeroDivisionError) as e:
        issues.error(f"Could not post-process the stations: {e}")
        return None, console, issues

    bad = check_finite(results)
    if bad:
        issues.error("Non-physical result (NaN/inf) in: " + ", ".join(bad[:6]) + ". Check the inputs.")
        return None, console, issues

    return results, console, issues


def summary(issues):
    errors = [i["message"] for i in issues if i["level"] == "error"]
    return "\n".join(errors)


@app.route('/api/run', methods=['POST'])
def api_run():
    config = request.get_json(silent=True)
    results, console, issues = evaluate(config)
    if results is None:
        return jsonify({"ok": False, "error": summary(issues), "issues": issues, "console": console})

    try:
        exam = {"text": generate_exercise_text(config), "data": generate_data_section(config)}
    except Exception as e:
        exam = {"text": f"Exam text not available: {e!r}", "data": ""}

    return jsonify({
        "ok": True,
        "results": to_builtin(results),
        "console": console,
        "issues": issues,
        "exam": exam,
    })


@app.route('/api/sweep', methods=['POST'])
def api_sweep():
    body = request.get_json(silent=True) or {}
    config = body.get("config")
    path = body.get("path") or []          # e.g. ["components", "compressor", "pressure_ratio"]
    values = body.get("values") or []
    if not isinstance(config, dict) or not path:
        return jsonify({"ok": False, "error": "Invalid sweep request."})

    points = []
    for v in values[:500]:
        cfg = copy.deepcopy(config)
        target = cfg
        for key in path[:-1]:
            target = target.setdefault(key, {})
        target[path[-1]] = v
        res, _, issues = evaluate(cfg)
        if res is None:
            points.append({"x": v, "error": summary(issues)})
            continue
        perf = res["performance"]
        if "burn" in res:
            burn = res["burn"]
            points.append(to_builtin({
                "x": v,
                "total_impulse": burn["total_impulse"],
                "burn_time": burn["burn_time"],
                "average_thrust": burn["average_thrust"],
                "max_thrust": burn["max_thrust"],
                "average_pressure": burn["average_pressure"],
                "max_pressure": burn["max_pressure"],
                "Isp": burn["Isp"],
                "propellant_mass": res["grain"]["propellant_mass"],
                "warnings": sum(1 for i in issues if i["level"] == "warning"),
            }))
            continue
        if cfg["engineType"] in ROCKET_TYPES:
            points.append(to_builtin({
                "x": v,
                "thrust": perf["thrust"],
                "thrust_vacuum": perf["thrust_vacuum"],
                "Isp": perf["Isp"],
                "Isp_vacuum": perf["Isp_vacuum"],
                "CF": perf["CF"],
                "CF_vacuum": perf["CF_vacuum"],
                "mach": res["mainNozzle"]["mach"],
                "exit_pressure": res["mainNozzle"]["exit_pressure"],
                "mass_flow": res["mass_flow"],
                "warnings": sum(1 for i in issues if i["level"] == "warning"),
            }))
            continue
        points.append(to_builtin({
            "x": v,
            "thrust": perf["thrust"],
            "TSFC": perf["TSFC"],
            "impulse": perf["impulse"],
            "thermal": perf["thermal"],
            "propulsive": perf["propulsive"],
            "global": perf["global"],
            "mach": res["mainNozzle"]["mach"],
            "BPR": (res["mass_flow_secondary"] / res["mass_flow_main"]
                    if cfg["engineType"].startswith("turbofan") else None),
            "warnings": sum(1 for i in issues if i["level"] == "warning"),
        }))

    return jsonify({"ok": True, "points": points})


@app.route('/api/parse', methods=['POST'])
def api_parse():
    text = (request.get_json(silent=True) or {}).get("text", "")
    try:
        config = parse_openfoam_style(text)
        if config.get("engineType") not in ENGINE_TYPES + ROCKET_TYPES:
            raise ValueError(f"engineType '{config.get('engineType')}' not supported")
        return jsonify({"ok": True, "config": config})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route('/api/export', methods=['POST'])
def api_export():
    config = request.get_json(silent=True)
    if not isinstance(config, dict) or "engineType" not in config:
        return jsonify({"ok": False, "error": "Invalid configuration."})
    return jsonify({"ok": True, "text": config_to_input(config)})


@app.route('/api/isa')
def api_isa():
    try:
        altitude_km = float(request.args.get("altitude_km", 0))
    except ValueError:
        return jsonify({"error": "invalid altitude"}), 400
    if not 0 <= altitude_km <= 20:
        return jsonify({"error": "the ISA model is valid between 0 and 20 km"}), 400
    return jsonify(isa(altitude_km * 1000.0))
