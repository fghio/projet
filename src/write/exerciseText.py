def generate_exercise_text(config):

    engine = config["engineType"]
    air = config["airProperties"]
    intake = config["components"]["intake"]

    has_postcomb = "postCombustor" in config["components"]
    is_mixed = engine == "turbofan_mixed"

    engine_name = {
        "turbojet": "turbojet",
        "turbofan": "turbofan",
        "turbofan_mixed": "turbofan a flussi associati"
    }[engine]

    postcomb_text = " dotato di post-combustore" if has_postcomb else ""

    mixing_text = (
        "Si considerino trascurabili le perdite di pressione all’interno "
        "della camera di miscelazione.\n\n"
        if is_mixed else ""
    )

    bpr_text = " il BPR," if is_mixed else ""

    perf_text = (
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

{mixing_text}
Considerando i dati di seguito forniti, il candidato dimensioni il propulsore del sistema,
identificando i punti del ciclo termodinamico da esso realizzato, le portate di aria e
combustibile elaborate,{bpr_text} e le prestazioni del motore (la spinta del motore,
il suo consumo specifico ed i rendimenti) {perf_text}.
"""
    return text.strip()



def generate_data_section(config):

    lines = []

    comps = config["components"]
    engine = config["engineType"]

    # -------------------
    # Rapporti di compressione
    # -------------------
    if "fan" in comps:
        lines.append(
            f"Rapporto di compressione del fan:\t\t\tβf = {comps['fan']['pressure_ratio']}"
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
    lines.append(f"• rendimento pneumatico della presa d’aria\t\tπd = {intake['efficiency']}")

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

    noz = comps["nozzle"]
    lines.append(f"• adiabatico dell’ugello:\t\t\tηu = {noz['efficiency']}")

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
            f"• Miscela uscente dal post-combustore: cp = {post['cp']} J/kgK, "
            f"γ = {post['gamma']}, R = {post['R']} J/kgK"
        )

    # -------------------
    # Combustibile
    # -------------------
    fuel = config.get("fuelProperties", {})
    lines.append(
        f"\nPotere calorifico del combustibile:\t\tLHV = {fuel.get('calorific', 42e6)} J/kg"
    )

    return "\n".join(lines)

