
ROCKET_TYPES = ["idealRocket", "solidRocket", "endBurner"]


def generate_exercise_text(config):

    engine = config["engineType"]
    if engine in ROCKET_TYPES:
        return generate_rocket_exercise_text(config)

    air = config["airProperties"]
    comps = config["components"]
    intake = comps["intake"]

    has_postcomb = "postCombustor" in comps
    is_mixed = engine == "turbofan_AF"

    engine_name = {
        "turbojet": "turbojet",
        "turbofan_SF": "turbofan a flussi separati",
        "turbofan_AF": "turbofan a flussi associati",
        "turboprop": "turboelica"
    }[engine]

    postcomb_text = " dotato di post-combustore" if has_postcomb else ""

    mixing_text = (
        "Si considerino trascurabili le perdite di pressione all’interno "
        "della camera di miscelazione.\n\n"
        if is_mixed else ""
    )

    if engine == "turboprop":
        prop = comps["propeller"]
        propeller_text = (
            f"L’elica ha un diametro di {prop['Phi']} m"
            + (f" e assorbe una frazione α = {prop['alpha_power']} del salto entalpico disponibile"
               if "alpha_power" in prop else
               "; si determini la ripartizione ottima del salto entalpico tra elica e getto")
            + ".\n\n"
        )
    else:
        propeller_text = ""

    bpr_text = " il BPR," if is_mixed else ""

    if engine == "turboprop":
        perf_text = "(la potenza all’albero, la spinta complessiva, il consumo specifico BSFC ed i rendimenti)"
    else:
        perf_text = "(la spinta del motore, il suo consumo specifico ed i rendimenti)"

    condition_text = (
        "nelle condizioni di post-combustore spento e di post-combustore acceso"
        if has_postcomb else
        "nelle condizioni operative assegnate"
    )

    altitude = config.get("flightConditions", {}).get("altitude_km", "—")

    text = f"""
Un velivolo equipaggiato con un {engine_name}{postcomb_text} è in volo alla quota di {altitude} km
(temperatura e pressione statica dell’aria sono rispettivamente {air['temperature']} K e
{air['pressure']} Pa; la densità è pari a {air['density']} kg/m³).
Il velivolo si trova a volare in regime subsonico (Mach = {intake['mach']}).
Si supponga la sezione di cattura del flusso d’aria coincidente con la sezione di ingresso
della presa d’aria, il cui diametro è di {intake['Phi']} m.

{mixing_text}{propeller_text}Considerando i dati di seguito forniti, il candidato dimensioni il propulsore del sistema,
identificando i punti del ciclo termodinamico da esso realizzato, le portate di aria e
combustibile elaborate,{bpr_text} e le prestazioni del motore {perf_text} {condition_text}.
"""
    return text.strip()



def generate_data_section(config):

    lines = []

    comps = config["components"]
    engine = config["engineType"]
    if engine in ROCKET_TYPES:
        return generate_rocket_data_section(config)

    # -------------------
    # Rapporti di compressione
    # -------------------
    if "fan" in comps:
        lines.append(
            f"Rapporto di compressione del fan:\t\t\tβf = {comps['fan']['pressure_ratio']}"
        )
        if engine == "turbofan_SF":
            lines.append(
                f"Rapporto di by-pass:\t\t\t\tBPR = {comps['fan']['BPR']}"
            )

    if "compressor" in comps:
        lines.append(
            f"Rapporto di compressione del compressore:\t\tβc = {comps['compressor']['pressure_ratio']}"
        )

    # -------------------
    # Combustore
    # -------------------
    combustor = comps["combustor"]
    if "outlet_temperature" in combustor:
        lines.append(
            f"Temperatura massima in ingresso turbina:\t\tT = {combustor['outlet_temperature']} K"
        )
    else:
        lines.append(
            f"Rapporto combustibile–aria nel combustore:\t\tf = {combustor['fuel_ratio']}"
        )

    # -------------------
    # Post-combustore
    # -------------------
    if "postCombustor" in comps:
        ab = comps["postCombustor"]
        if "outlet_temperature" in ab:
            lines.append(
                f"Temperatura massima in uscita dal post-combustore:\tT_AB = {ab['outlet_temperature']} K"
            )
        else:
            lines.append(
                f"Rapporto combustibile–aria calda nel post-combustore:\tf_AB = {ab['fuel_ratio']}"
            )

    # -------------------
    # Rendimenti
    # -------------------
    lines.append("\nRendimenti:")

    intake = comps["intake"]
    lines.append(f"• rendimento pneumatico della presa d’aria\t\tπd = {intake.get('efficiency', 1.0)}")

    if "propeller" in comps:
        prop = comps["propeller"]
        lines.append(f"• dell’elica:\t\t\t\t\tηp = {prop.get('efficiency', 1.0)}")
        lines.append(f"• del riduttore:\t\t\t\tηgb = {prop.get('gearbox_efficiency', 1.0)}")

    if "fan" in comps:
        fan = comps["fan"]
        lines.append(
            f"• adiabatico del fan:\t\t\t\tηfan = {fan['efficiency']}"
        )
        lines.append(
            f"• meccanico del fan:\t\t\t\tηm,fan = {fan['mechanical_efficiency']}"
        )

    comp = comps["compressor"]
    lines.append(f"• adiabatico del compressore:\t\t\tηc = {comp['efficiency']}")
    lines.append(f"• meccanico del compressore:\t\t\tηm,c = {comp['mechanical_efficiency']}")

    lines.append(f"• efficienza di combustione:\t\t\tηb = {combustor['efficiency']}")
    lines.append(f"• pneumatico del combustore:\t\t\tπb = {combustor['mechanical_efficiency']}")

    if "turbineHigh" in comps:
        hpt = comps["turbineHigh"]
        lpt = comps["turbineLow"]
        lines.append(f"• adiabatico HPT:\t\t\t\tηt,HPT = {hpt['efficiency']}")
        lines.append(f"• meccanico HPT:\t\t\t\tηm,HPT = {hpt['mechanical_efficiency']}")
        lines.append(f"• adiabatico LPT:\t\t\t\tηt,LPT = {lpt['efficiency']}")
        lines.append(f"• meccanico LPT:\t\t\t\tηm,LPT = {lpt['mechanical_efficiency']}")
    else:
        turb = comps["turbine"]
        lines.append(f"• adiabatico della turbina:\t\t\tηt = {turb['efficiency']}")
        lines.append(f"• meccanico della turbina:\t\t\tηm = {turb['mechanical_efficiency']}")

    if "nozzle" in comps:
        noz = comps["nozzle"]
        lines.append(f"• adiabatico dell’ugello:\t\t\tηu = {noz['efficiency']}")
    else:
        lines.append(f"• adiabatico dell’ugello primario:\t\tηu,H = {comps['nozzleMain']['efficiency']}")
        lines.append(f"• adiabatico dell’ugello secondario:\t\tηu,C = {comps['nozzleSecondary']['efficiency']}")

    if "postCombustor" in comps:
        lines.append(f"• efficienza di combustione in post-combustore:\tηAB = {ab['efficiency']}")
        lines.append(f"• pneumatico del post-combustore:\t\tπAB = {ab['mechanical_efficiency']}")

    # -------------------
    # Gas
    # -------------------
    air = config.get("airProperties", {})
    hot = config.get("hotGasProperties", {})
    post = config.get("postcombustionProperties", {})

    lines.append("\nProprietà dei gas:")

    lines.append(
        f"• Aria in ingresso: cp = {air.get('cp', 1004)} J/kgK, "
        f"γ = {air.get('gamma', 1.4)}"
    )

    lines.append(
        f"• Miscela uscente dal combustore: cp = {hot.get('cp', 1155)} J/kgK, "
        f"γ = {hot.get('gamma', 1.33)}, R = {hot.get('R', 286.58)} J/kgK"
    )

    if "postCombustor" in comps:
        lines.append(
            f"• Miscela uscente dal post-combustore: cp = {post.get('cp', 1155)} J/kgK, "
            f"γ = {post.get('gamma', 1.33)}, R = {post.get('R', 286.58)} J/kgK"
        )

    # -------------------
    # Combustibile
    # -------------------
    fuel = config.get("fuelProperties", {})
    lines.append(
        f"\nPotere calorifico del combustibile:\t\tLHV = {fuel.get('calorific', 42e6)} J/kg"
    )

    return "\n".join(lines)


def ambient_text(config):
    p_a = config.get("ambientProperties", {}).get("pressure", 0)
    altitude = config.get("flightConditions", {}).get("altitude_km")
    if p_a <= 0:
        return "nel vuoto"
    if altitude is None:
        altitude_text = ""
    elif altitude == 0:
        altitude_text = " al livello del mare"
    else:
        altitude_text = f" alla quota di {altitude} km"
    return f"in un ambiente a pressione {p_a} Pa{altitude_text}"


def generate_rocket_exercise_text(config):

    if config["engineType"] == "solidRocket":
        return generate_solid_rocket_exercise_text(config)
    if config["engineType"] == "endBurner":
        return generate_end_burner_exercise_text(config)

    comps = config["components"]
    chamber = comps["chamber"]
    nozzle = comps["nozzle"]
    p_a = config.get("ambientProperties", {}).get("pressure", 0)

    if "area_ratio" in nozzle:
        nozzle_text = (f"L’ugello convergente-divergente ha un rapporto d’espansione Ae/At = {nozzle['area_ratio']} "
                       f"e scarica {ambient_text(config)}.")
        ratio_task = ""
    else:
        nozzle_text = f"L’ugello convergente-divergente è adattato e scarica {ambient_text(config)}."
        ratio_task = " il rapporto d’espansione dell’ugello,"

    if "thrust" in chamber:
        sizing_text = f"Il motore deve fornire una spinta di {chamber['thrust'] / 1000:g} kN."
        size_task = " la portata di propellente necessaria"
    elif "mass_flow" in chamber:
        sizing_text = f"Il motore elabora una portata di propellente di {chamber['mass_flow']} kg/s."
        size_task = " la spinta"
    else:
        sizing_text = f"La gola dell’ugello ha un diametro di {chamber['throat_diameter']} m."
        size_task = " la portata di propellente, la spinta"

    split_task = ", ripartita tra ossidante e combustibile," if "mixture_ratio" in chamber else ","
    vacuum_task = " sia nelle condizioni assegnate sia nel vuoto" if p_a > 0 else ""

    text = f"""
Un endoreattore opera con una pressione in camera di combustione di {chamber['pressure'] / 1e6:g} MPa
e una temperatura dei prodotti di combustione di {chamber['temperature']} K.
{nozzle_text}
{sizing_text}

Considerando i dati di seguito forniti, il candidato determini la velocità caratteristica c*,
le condizioni in gola e all’uscita dell’ugello,{ratio_task}{size_task}{split_task}
i diametri di gola e di uscita, il coefficiente di spinta e l’impulso specifico{vacuum_task}.
"""
    return text.strip()


def generate_solid_rocket_exercise_text(config):

    grain = config["components"]["grain"]
    nozzle = config["components"]["nozzle"]
    ends_text = ("con le facce di estremità inibite" if grain.get("inhibited_ends")
                 else "con le facce di estremità libere di bruciare")

    text = f"""
Un endoreattore a propellente solido ha un grano di tipo BATES composto da {grain['segments']} segmenti
cilindrici con perforazione circolare, di diametro esterno {grain['outer_diameter']} m, diametro della
perforazione {grain['core_diameter']} m e lunghezza {grain['segment_length']} m ciascuno, con la superficie
esterna inibita (incollata al case) e {ends_text}.
L’ugello convergente-divergente ha una gola di diametro {nozzle['throat_diameter']} m, un rapporto
d’espansione Ae/At = {nozzle['area_ratio']} e scarica {ambient_text(config)}.

Considerando i dati di seguito forniti e trascurando i transitori di accensione e di spegnimento,
il candidato determini l’andamento nel tempo della superficie di combustione, della pressione in
camera e della spinta, il tempo di combustione, la pressione massima e media, la spinta media e
massima, l’impulso totale, la massa di propellente e l’impulso specifico medio.
"""
    return text.strip()


LAYER_NAMES = ["primo", "secondo", "terzo", "quarto", "quinto", "sesto"]


def generate_end_burner_exercise_text(config):

    from src.rocket.grain import layerBlocks
    grain = config["components"]["grain"]
    nozzle = config["components"]["nozzle"]
    layers = layerBlocks(grain)
    n = len(layers)
    lengths = ", ".join(f"{layer['length']} m" for _, layer in layers)

    if n == 1:
        layers_text = f"un unico propellente, per una lunghezza di {lengths}"
        task_text = "la pressione in camera, la velocità di regressione, la spinta, il tempo di combustione"
    else:
        layers_text = (f"{n} strati di propellenti diversi, disposti in sequenza a partire dal lato ugello "
                       f"(il primo strato a bruciare è quello affacciato all’ugello), di lunghezza rispettivamente {lengths}")
        task_text = ("per ciascuna fase di combustione la pressione in camera, la velocità di regressione, "
                     "la portata, la spinta e la durata, e complessivamente il tempo di combustione")

    text = f"""
Un endoreattore a propellente solido ha un grano a sigaretta (a combustione frontale) di diametro
{grain['diameter']} m, con la superficie laterale inibita: brucia solo la faccia rivolta verso l’ugello.
Il grano è composto da {layers_text}.
L’ugello convergente-divergente ha una gola di diametro {nozzle['throat_diameter']} m, un rapporto
d’espansione Ae/At = {nozzle['area_ratio']} e scarica {ambient_text(config)}.

Considerando i dati di seguito forniti, nell’ipotesi di regime quasi stazionario (passaggio
istantaneo da uno strato al successivo, transitori trascurabili), il candidato determini
{task_text}, l’impulso totale, la massa di propellente e l’impulso specifico medio,
tracciando l’andamento nel tempo della pressione in camera e della spinta.
"""
    return text.strip()


def generate_rocket_data_section(config):

    lines = []

    if config["engineType"] == "endBurner":
        from src.rocket.grain import layerBlocks
        hot = config.get("hotGasProperties", {})
        for i, (name, layer) in enumerate(layerBlocks(config["components"]["grain"])):
            title = f"Strato {i + 1}" + (" (lato ugello)" if i == 0 else "")
            lines.append(f"{title}:")
            lines.append(f"• lunghezza:\t\t\t\t\tL = {layer['length']} m")
            lines.append(f"• densità del propellente:\t\t\tρp = {layer['density']} kg/m³")
            lines.append(f"• temperatura di fiamma:\t\t\tTc = {layer['flame_temperature']} K")
            lines.append(f"• legge di combustione r = a·pⁿ (mm/s, MPa):\ta = {layer['burn_rate_coefficient']}, n = {layer['burn_rate_exponent']}")
            gamma, R = layer.get("gamma", hot.get("gamma")), layer.get("R", hot.get("R"))
            lines.append(f"• prodotti di combustione:\t\t\tγ = {gamma}, R = {R} J/kgK")
            lines.append("")
        lines.append(f"Pressione ambiente:\t\t\t\tpa = {config.get('ambientProperties', {}).get('pressure', 0)} Pa")
        lines.append("\nRendimenti:")
        lines.append(f"• adiabatico dell’ugello:\t\t\tηu = {config['components']['nozzle'].get('efficiency', 1.0)}")
        return "\n".join(lines)

    if config["engineType"] == "solidRocket":
        prop = config["propellantProperties"]
        lines.append(f"Densità del propellente:\t\t\tρp = {prop['density']} kg/m³")
        lines.append(f"Temperatura di fiamma:\t\t\t\tTc = {prop['flame_temperature']} K")
        lines.append(f"Legge di combustione:\t\t\t\tr = a·pⁿ  (r in mm/s, p in MPa)")
        lines.append(f"\t\t\t\t\t\ta = {prop['burn_rate_coefficient']}, n = {prop['burn_rate_exponent']}")
        lines.append(f"Pressione ambiente:\t\t\t\tpa = {config.get('ambientProperties', {}).get('pressure', 0)} Pa")
        lines.append("\nRendimenti:")
        lines.append(f"• adiabatico dell’ugello:\t\t\tηu = {config['components']['nozzle'].get('efficiency', 1.0)}")
        hot = config.get("hotGasProperties", {})
        lines.append("\nProprietà dei prodotti di combustione:")
        gas_text = f"• γ = {hot.get('gamma')}, R = {hot.get('R')} J/kgK"
        if "cp" in hot:
            gas_text += f", cp = {hot['cp']} J/kgK"
        lines.append(gas_text)
        return "\n".join(lines)

    comps = config["components"]
    chamber = comps["chamber"]
    nozzle = comps["nozzle"]

    lines.append(f"Pressione in camera di combustione:\t\tpc = {chamber['pressure']} Pa")
    lines.append(f"Temperatura in camera di combustione:\t\tTc = {chamber['temperature']} K")
    if "mixture_ratio" in chamber:
        lines.append(f"Rapporto di miscela ossidante/combustibile:\tO/F = {chamber['mixture_ratio']}")
    if "area_ratio" in nozzle:
        lines.append(f"Rapporto d’espansione dell’ugello:\t\tε = {nozzle['area_ratio']}")
    lines.append(f"Pressione ambiente:\t\t\t\tpa = {config.get('ambientProperties', {}).get('pressure', 0)} Pa")

    lines.append("\nRendimenti:")
    lines.append(f"• adiabatico dell’ugello:\t\t\tηu = {nozzle.get('efficiency', 1.0)}")

    hot = config.get("hotGasProperties", {})
    lines.append("\nProprietà dei prodotti di combustione:")
    gas_text = f"• γ = {hot.get('gamma')}, R = {hot.get('R')} J/kgK"
    if "cp" in hot:
        gas_text += f", cp = {hot['cp']} J/kgK"
    lines.append(gas_text)

    return "\n".join(lines)
