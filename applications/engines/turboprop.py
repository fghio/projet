# engines/turboprop.py
import sys
import os

# Add the parent directory of engines to the sys.path
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, parent_dir)

from src.fluids.air import Air
from src.fluids.fuel import Fuel
from src.fluids.hotGas import HotGas

from src.components.propeller import Propeller
from src.components.intake import Intake
from src.components.compressor import Compressor
from src.components.combustor import Combustor
from src.components.turbine import Turbine
from src.components.nozzle import Nozzle

from src.performance.performance import Performance

from src.write.writeOutput import Write


def simulate(config):

    air_properties = config.get('airProperties', {})
    fuel_properties = config.get('fuelProperties', {})
    hotGas_properties = config.get('hotGasProperties', {})

    # Create instances of Fluids
    air = Air(**air_properties)
    fuel = Fuel(**fuel_properties)
    hot_gas = HotGas(**hotGas_properties)

    # Create instances of Components
    intake = Intake(air=air, **config['components']['intake'])
    compressor = Compressor(air=air, **config['components']['compressor'])
    combustor = Combustor(air=air, fuel=fuel, hotGas=hot_gas, **config['components']['combustor'])
    turbineHigh = Turbine(compressor=compressor, combustor=combustor, **config['components']['turbineHigh'])
    nozzle = Nozzle(air=air, hotGas=hot_gas, **config['components']['nozzle'])

    propeller = Propeller(
        air=air,
        hotGas=hot_gas, 
        turbine=Turbine(           #Fake turbineLow
            compressor=compressor, #dummy variable
            combustor=combustor,   #dummy variable
            **config['components']['turbineLow']
        ), 
        **config['components']['propeller']
    )

    # Create instances of Performance
    performance = Performance(intake=intake, combustor=combustor, propeller=propeller, mainNozzle=nozzle)

    # Create instances of Write
    write = Write(performance=performance,intake=intake,mainNozzle=nozzle,engineType="turboprop")


    # Begin simulation
    T_amb = air_properties['temperature']
    P_amb = air_properties['pressure']

    P1_tot, T1_tot = intake.staticToTotal(T_amb, P_amb)

    # Intake
    P2_tot, T2_tot = intake.evolve(T1_tot, P1_tot)

    # Compressor
    P3_tot, T3_tot, T3_Prime = compressor.evolve(T2_tot, P2_tot)

    # Combustor
    P4_tot, T4_tot, f = combustor.evolve(T3_tot, P3_tot)

    # Turbine High
    P5_tot, T5_tot, T5_prime = turbineHigh.evolve(T4_tot, P4_tot)

    # IF optimal alpha
    if 'alpha_power' not in config['components']['propeller']:
        propeller.setOptimalAlpha(intake.inlet_velocity, nozzle.efficiency, T5_tot, P5_tot)

    # Turbine Low | Propeller
    P6_tot, T6_tot = propeller.evolve(T5_tot, P5_tot)

    # Nozzle
    P9, T9 = nozzle.evolve(T6_tot, P6_tot)

    # Calc performance
    performance.calcPerformance()
    performance.adjustPerformanceTurboprop()

    # write
    write.beginCycle()

    write.airConditions()
    write.writeStatus("Air at entrance",P1_tot,T1_tot)

    write.writeStatus("Intake",P2_tot,T2_tot)
    write.writeStatus("Compressor",P3_tot,T3_tot)
    write.writeStatus("Combustor",P4_tot,T4_tot)
    
    write.writeCombustorAdditionalProperties(combustor)

    write.writeStatus("Turbine HP",P5_tot,T5_tot)
    write.writeStatus("Turbine LP | Propeller",P6_tot,T6_tot)
    write.writeStatus("Nozzle",P9,T9,total=False)

    write.writePerformance()

    write.endCycle()



if __name__ == "__main__":
    simulate(config) # type: ignore
