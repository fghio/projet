# engines/turbofan.py
import sys
import os

# Add the parent directory of engines to the sys.path
current_dir = os.path.dirname(__file__)
parent_dir = os.path.abspath(os.path.join(current_dir, '../..'))
sys.path.insert(0, parent_dir)

from src.fluids.air import Air
from src.fluids.fuel import Fuel
from src.fluids.hotGas import HotGas

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
    fan = Compressor(air=air, **config['components']['fan'])
    compressor = Compressor(air=air, **config['components']['compressor'])
    combustor = Combustor(air=air, fuel=fuel, hotGas=hot_gas, **config['components']['combustor'])
    turbine_high = Turbine(compressor=compressor, combustor=combustor, **config['components']['turbineHigh'])
    turbine_low = Turbine(compressor=fan, combustor=combustor, **config['components']['turbineLow'])
    nozzle_main = Nozzle(air=air, hotGas=hot_gas, **config['components']['nozzleMain'])
    nozzle_secondary = Nozzle(air=air, hotGas=air, **config['components']['nozzleSecondary'])

    # Create instances of Performance
    performance = Performance(intake=intake, combustor=combustor, mainNozzle=nozzle_main, secondNozzle=nozzle_secondary)

    # Create instances of Write
    write = Write(performance=performance,intake=intake,combustor=combustor,mainNozzle=nozzle_main,secondaryNozzle=nozzle_secondary,engineType="turbofan_SF")

    
    # Begin simulation
    T_amb = air_properties['temperature']
    P_amb = air_properties['pressure']

    P1_tot, T1_tot = intake.staticToTotal(T_amb, P_amb)

    # Intake
    P2_tot, T2_tot = intake.evolve(T1_tot, P1_tot)

    # Fan
    P3_tot, T3_tot, T3_Prime = fan.evolve(T2_tot, P2_tot)

    # flow separation
    air.separateFlows(BPR=fan.BPR)

    # Compressor
    P4_tot, T4_tot, T4_Prime = compressor.evolve(T3_tot, P3_tot)

    # Combustor
    P5_tot, T5_tot, f = combustor.evolve(T4_tot, P4_tot)

    # Turbine High
    P6_tot, T6_tot, T6_prime = turbine_high.evolve(T5_tot, P5_tot)

    # Turbine Low
    P7_tot, T7_tot, T7_prime = turbine_low.evolve(T6_tot, P6_tot)

    # Nozzle main
    P9, T9 = nozzle_main.evolve(T7_tot, P7_tot)

    # Nozzle secondary
    P8, T8 = nozzle_secondary.evolve(T3_tot, P3_tot)

    # Calc performance
    performance.calcPerformance()
  
    # write
    write.beginCycle()

    write.airConditions()
    write.writeStatus("Air at entrance",P1_tot,T1_tot)

    write.writeStatus("Intake",P2_tot,T2_tot)
    write.writeStatus("Fan",P3_tot,T3_tot)
    write.writeStatus("Compressor",P4_tot,T4_tot)
    write.writeStatus("Combustor",P5_tot,T5_tot)
    
    write.writeCombustorAdditionalProperties()

    write.writeStatus("Turbine HP",P6_tot,T6_tot)
    write.writeStatus("Turbine LP",P7_tot,T7_tot)
    write.writeStatus("Main nozzle",P9,T9,total=False)
    write.writeStatus("Secondary nozzle",P8,T8,total=False)

    write.writePerformance()

    write.endCycle()




if __name__ == "__main__":
    simulate(config) # type: ignore