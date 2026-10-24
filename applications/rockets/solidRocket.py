# rockets/solidRocket.py
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
from src.rocket.grain import BatesGrain
from src.rocket.ballistics import Ballistics
from src.components.nozzle import Nozzle

from src.performance.rocketPerformance import RocketPerformance

from src.write.writeRocket import WriteSolidRocket


def simulate(config):

    ambient_properties = config.get('ambientProperties', {})
    hotGas_properties = dict(config.get('hotGasProperties', {}))
    propellant_properties = config['propellantProperties']

    # combustion products: if cp is not given it follows from gamma and R
    if 'cp' not in hotGas_properties:
        gamma = hotGas_properties.get('gamma', HotGas().gamma)
        R = hotGas_properties.get('R', HotGas().R)
        hotGas_properties['cp'] = gamma * R / (gamma - 1)

    # Create instances of Fluids
    ambient = Air(pressure=ambient_properties.get('pressure', 0))
    hot_gas = HotGas(**hotGas_properties)
    propellant = Propellant(**propellant_properties)

    # Create instances of Components (the chamber pressure follows from the grain)
    nozzle_properties = dict(config['components']['nozzle'])
    throat_diameter = nozzle_properties.pop('throat_diameter')
    chamber = Chamber(hotGas=hot_gas, pressure=0, temperature=propellant.flame_temperature, throat_diameter=throat_diameter)
    grain = BatesGrain(**config['components']['grain'])
    nozzle = Nozzle(air=ambient, hotGas=hot_gas, **nozzle_properties)

    # Create instances of Performance
    performance = RocketPerformance(chamber=chamber, nozzle=nozzle)
    ballistics = Ballistics(chamber=chamber, propellant=propellant, grain=grain, nozzle=nozzle, performance=performance)

    # Create instances of Write
    write = WriteSolidRocket(performance=performance, nozzle=nozzle, ballistics=ballistics, engineType="solidRocket")


    # Begin simulation: burn the grain, then stay at the maximum-pressure point
    ballistics.burn()

    # write
    write.beginCycle()

    write.ambientConditions()

    write.writeGrain()

    write.writeBallistics()

    write.writeStatus("Chamber",chamber.pressure,chamber.temperature)
    write.writeChamberAdditionalProperties(chamber)

    write.writeStatus("Throat",chamber.throat_pressure,chamber.throat_temperature,total=False)

    write.writeStatus("Nozzle exit",nozzle.static_pressure,nozzle.static_temperature,total=False)

    write.writePerformance()

    write.endCycle()

    return write.results



if __name__ == "__main__":
    simulate(config) # type: ignore
