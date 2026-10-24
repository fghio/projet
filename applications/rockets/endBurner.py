# rockets/endBurner.py
import sys
import os

# Add the project root to the sys.path
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, parent_dir)

from src.fluids.air import Air
from src.fluids.hotGas import HotGas

from src.rocket.chamber import Chamber
from src.rocket.propellant import Propellant
from src.rocket.grain import EndBurnerLayer, layerBlocks
from src.rocket.ballistics import Ballistics, PhasedBallistics
from src.components.nozzle import Nozzle

from src.performance.rocketPerformance import RocketPerformance

from src.write.writeRocket import WriteEndBurner

PROPELLANT_KEYS = ("density", "flame_temperature", "burn_rate_coefficient", "burn_rate_exponent")
GAS_KEYS = ("gamma", "R", "cp")


def layerGas(common, layer):
    # gamma and R of a layer default to the common ones; cp follows from them unless given
    gas = {k: layer.get(k, common.get(k)) for k in ("gamma", "R")}
    if "cp" in layer:
        gas["cp"] = layer["cp"]
    elif "cp" in common and "gamma" not in layer and "R" not in layer:
        gas["cp"] = common["cp"]
    else:
        gas["cp"] = gas["gamma"] * gas["R"] / (gas["gamma"] - 1)
    return HotGas(**gas)


def simulate(config):

    ambient_properties = config.get('ambientProperties', {})
    common_gas = config.get('hotGasProperties', {})
    grain_config = config['components']['grain']
    nozzle_properties = dict(config['components']['nozzle'])
    throat_diameter = nozzle_properties.pop('throat_diameter')

    # Create instances of Fluids
    ambient = Air(pressure=ambient_properties.get('pressure', 0))

    # one burning phase per layer, each with its own propellant and combustion products
    phases = []
    for name, layer in layerBlocks(grain_config):
        hot_gas = layerGas(common_gas, layer)
        propellant = Propellant(**{k: layer[k] for k in PROPELLANT_KEYS})
        chamber = Chamber(hotGas=hot_gas, pressure=0, temperature=propellant.flame_temperature, throat_diameter=throat_diameter)
        grain = EndBurnerLayer(diameter=grain_config['diameter'], length=layer['length'])
        nozzle = Nozzle(air=ambient, hotGas=hot_gas, **nozzle_properties)
        performance = RocketPerformance(chamber=chamber, nozzle=nozzle)
        # the burn area is constant within a layer: the end points are enough
        phases.append(Ballistics(chamber=chamber, propellant=propellant, grain=grain, nozzle=nozzle,
                                 performance=performance, steps=1))

    ballistics = PhasedBallistics(phases)


    # Begin simulation: burn the layers in sequence, then stay at the maximum-pressure layer
    ballistics.burn()
    reference = phases[ballistics.max_pressure_phase]

    # Create instances of Write
    write = WriteEndBurner(performance=reference.performance, nozzle=reference.nozzle, ballistics=ballistics,
                           engineType="endBurner")

    # write
    write.beginCycle()

    write.ambientConditions()

    write.writeLayers()

    write.writeBallistics()

    write.writeStatus("Chamber",reference.chamber.pressure,reference.chamber.temperature)
    write.writeChamberAdditionalProperties(reference.chamber)

    write.writeStatus("Throat",reference.chamber.throat_pressure,reference.chamber.throat_temperature,total=False)

    write.writeStatus("Nozzle exit",reference.nozzle.static_pressure,reference.nozzle.static_temperature,total=False)

    write.writePerformance()

    write.endCycle()

    return write.results



if __name__ == "__main__":
    simulate(config) # type: ignore
