# engines/turbofan_AF.py
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
from src.components.postCombustor import PostCombustor
from src.components.mixer import Mixer
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
    fuel_ab = Fuel(**fuel_properties)
    mixture = HotGas()

    # Create instances of Components
    intake = Intake(air=air, **config['components']['intake'])
    fan = Compressor(air=air, **config['components']['fan'])
    compressor = Compressor(air=air, **config['components']['compressor'])
    combustor = Combustor(air=air, fuel=fuel, hotGas=hot_gas, **config['components']['combustor'])
    turbine_high = Turbine(compressor=compressor, combustor=combustor, engineType="turbofan_AF", **config['components']['turbineHigh'])
    turbine_low = Turbine(compressor=fan, combustor=combustor, **config['components']['turbineLow'])
    mixer = Mixer(air=air, fuel=fuel, hotGas=hot_gas, mix=mixture)
    nozzle = Nozzle(air=air, hotGas=mixture, **config['components']['nozzle'])

    if "postCombustor" in config["components"]:
        postcomb_properties = config.get('postcombustionProperties', {})
        postcomb = HotGas(**postcomb_properties)
        postCombustor = PostCombustor(air=air, pre=hot_gas, combustor=combustor, fuel=fuel_ab, post=postcomb, **config['components']['postCombustor'])

    # Create instances of Performance
    performance = Performance(intake=intake, combustor=combustor, mainNozzle=nozzle)

    # Create instances of Write
    write = Write(performance=performance,intake=intake,mainNozzle=nozzle,engineType="turbofan_AF")

    
    # Begin simulation
    T_amb = air_properties['temperature']
    P_amb = air_properties['pressure']

    P1_tot, T1_tot = intake.staticToTotal(T_amb, P_amb)

    # Intake
    P2_tot, T2_tot = intake.evolve(T1_tot, P1_tot)

    # Fan
    P3_tot, T3_tot, T3_Prime = fan.evolve(T2_tot, P2_tot)

    # we can't separate the flows because we don't know the BPR

    # Compressor
    P4_tot, T4_tot, T4_Prime = compressor.evolve(T3_tot, P3_tot)

    # Combustor
    P5_tot, T5_tot, f = combustor.evolve(T4_tot, P4_tot)

    # We did not have the mass subdivisions. We assign the 
    # compressor power now (dimensionless)
    compressor.power = 1.0/compressor.mechanical_efficiency * air.cp * abs(T4_tot - T3_tot)

    # Turbine High (associated fluxes)
    P6_tot, T6_tot, T6_prime = turbine_high.evolve(T5_tot, P5_tot)
    
    # Turbine Low
    P7_tot, T7_tot, T7_prime = turbine_low.evolve_associatedFluxes(P3_tot,T6_tot,P6_tot)
    
    # Compute BPR (now that we have the outlet conditions for LPT)
    numerator = (1+combustor.fuel_ratio) * hot_gas.cp * (T6_tot - T7_tot) * turbine_low.mechanical_efficiency 
    denominator = air.cp * (T3_tot - T2_tot) / fan.mechanical_efficiency
    fan.BPR = numerator / denominator -1
    
    # Separate the flows and update the fuel mass
    air.separateFlows(BPR=fan.BPR)
    combustor.calcFuelMass(air.mass_flow_main)

    # Mixer (mixing zone)
    mixer.updatePropertiesAfterMixing()
    P8_tot, T8_tot = mixer.evolve(T7_tot, T3_tot, P7_tot)

    # PostCombustor:
    if "postCombustor" in config["components"]:
        P9_tot, T9_tot, f_ab = postCombustor.evolve(T8_tot, P8_tot)
        hot_gas.gamma = postcomb.gamma
        hot_gas.R = postcomb.R
        hot_gas.cp = postcomb.cp
    else:
        P9_tot = P8_tot
        T9_tot = T8_tot
    
    # Nozzle main
    P10, T10 = nozzle.evolve(T9_tot, P9_tot)

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
    
    write.writeCombustorAdditionalProperties(combustor)

    write.writeStatus("Turbine HP",P6_tot,T6_tot)
    write.writeStatus("Turbine LP",P7_tot,T7_tot)
    write.writeStatus("Mixing zone",P8_tot,T8_tot)
    
    if "postCombustor" in config["components"]:
        write.writeStatus("PostCombustor",P9_tot,T9_tot)
        write.writeCombustorAdditionalProperties(postCombustor)
    
    write.writeStatus("Nozzle",P10,T10,total=False)    

    write.writePerformance()

    write.endCycle()


if __name__ == "__main__":
    simulate(config) # type: ignore
