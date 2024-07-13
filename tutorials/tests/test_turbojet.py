# Example usage of components
# engines/turbojet.py
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

# Define specific Air properties
air_properties = {
    'temperature': 223,
    'pressure': 26400,
    'density': 0.413
}

# Create instances of Fluids
air = Air(**air_properties)
fuel = Fuel()
hotGas = HotGas()

# Create instances of Components
intake = Intake(air=air, Phi=1, mach=0.8, efficiency=0.97)
compressor = Compressor(air=air, pressure_ratio=15.0, efficiency=0.88, mechanical_efficiency=0.98)
combustor = Combustor(air=air, fuel=fuel, hotGas=hotGas, outlet_temperature=1450, efficiency=0.99, mechanical_efficiency=0.95)
turbine = Turbine(compressor=compressor, combustor=combustor, efficiency=0.92, mechanical_efficiency=0.98)
nozzle = Nozzle(air=air, hotGas=hotGas, efficiency=0.97)

# Create instances of Performance
performance = Performance(intake=intake, combustor=combustor, mainNozzle=nozzle)

# Create instances of Write
write = Write(performance=performance,intake=intake,combustor=combustor,mainNozzle=nozzle,engineType="turbojet")


# Simulate intake process
T_amb = air_properties['temperature']
P_amb = air_properties['pressure']

P1_tot, T1_tot = intake.staticToTotal(T_amb, P_amb)

# Intake
P2_tot, T2_tot = intake.evolve(T1_tot, P1_tot)

# Compressor
P3_tot, T3_tot, T3_Prime = compressor.evolve(T2_tot, P2_tot)

# Combustor
P4_tot, T4_tot, f = combustor.evolve(T3_tot, P3_tot)

# Turbine
P5_tot, T5_tot, T5_prime = turbine.evolve(T4_tot, P4_tot)

# Nozzle
P9, T9 = nozzle.evolve(T5_tot, P5_tot)

# Calc performance
performance.calcPerformance()

# write
write.beginCycle()

write.airConditions()
write.writeStatus("Air at entrance",P1_tot,T1_tot)

write.writeStatus("Intake",P2_tot,T2_tot)
write.writeStatus("Compressor",P3_tot,T3_tot)
write.writeStatus("Combustor",P4_tot,T4_tot)

write.writeCombustorAdditionalProperties()

write.writeStatus("Turbine HP",P5_tot,T5_tot)
write.writeStatus("Nozzle",P9,T9,total=False)

write.writePerformance()

write.endCycle()