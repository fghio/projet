# rockets/idealRocket.py
import sys
import os

# Add the project root to the sys.path
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, parent_dir)

from src.fluids.air import Air
from src.fluids.hotGas import HotGas

from src.rocket.chamber import Chamber
from src.components.nozzle import Nozzle

from src.performance.rocketPerformance import RocketPerformance

from src.write.writeRocket import WriteRocket


def simulate(config):

    ambient_properties = config.get('ambientProperties', {})
    hotGas_properties = dict(config.get('hotGasProperties', {}))

    # combustion products: if cp is not given it follows from gamma and R
    if 'cp' not in hotGas_properties:
        gamma = hotGas_properties.get('gamma', HotGas().gamma)
        R = hotGas_properties.get('R', HotGas().R)
        hotGas_properties['cp'] = gamma * R / (gamma - 1)

    # Create instances of Fluids (only the ambient pressure matters for a rocket)
    ambient = Air(pressure=ambient_properties.get('pressure', 0))
    hot_gas = HotGas(**hotGas_properties)

    # Create instances of Components
    chamber = Chamber(hotGas=hot_gas, **config['components']['chamber'])
    nozzle = Nozzle(air=ambient, hotGas=hot_gas, **config['components']['nozzle'])

    # Create instances of Performance
    performance = RocketPerformance(chamber=chamber, nozzle=nozzle)

    # Create instances of Write
    write = WriteRocket(performance=performance, nozzle=nozzle, engineType="idealRocket")


    # Begin simulation

    # Combustion chamber
    Pc_tot, Tc_tot, P_throat, T_throat = chamber.evolve()

    # Nozzle
    Pe, Te = nozzle.evolve(Tc_tot, Pc_tot)

    # Calc performance (and size the engine)
    performance.calcPerformance()

    # write
    write.beginCycle()

    write.ambientConditions()

    write.writeStatus("Chamber",Pc_tot,Tc_tot)
    write.writeChamberAdditionalProperties(chamber)

    write.writeStatus("Throat",P_throat,T_throat,total=False)

    write.writeStatus("Nozzle exit",Pe,Te,total=False)

    write.writePerformance()

    write.endCycle()

    return write.results



if __name__ == "__main__":
    simulate(config) # type: ignore
