from src.fluids.hotGas import HotGas
from src.components.combustor import Combustor
from src.components.compressor import Compressor

class Turbine:
    def __init__(
        self,
        compressor : Compressor,
        combustor : Combustor,
        efficiency=1.0, 
        mechanical_efficiency=1.0,
        engineType = ""
    ):
        self.compressor = compressor
        self.combustor = combustor
        self.efficiency = efficiency
        self.mechanical_efficiency = mechanical_efficiency
        self.engineType = engineType

    def evolve(
        self, 
        inlet_temperature, 
        inlet_pressure,
    ):
        # Solve real temperature
        compressor_power = self.compressor.power

        if self.engineType == "turbofan_AF":
            outlet_temperature_real = inlet_temperature - compressor_power / (self.mechanical_efficiency * (1 + self.combustor.fuel_ratio) * self.combustor.hotGas.cp)
        else:
            outlet_temperature_real = inlet_temperature - compressor_power / (self.mechanical_efficiency * (self.combustor.air.mass_flow_main + self.combustor.fuel.mass_fuel) * self.combustor.hotGas.cp)

        # Solve ideal temperature
        outlet_temperature_ideal = inlet_temperature + (outlet_temperature_real - inlet_temperature) / self.efficiency

        # Solve pressure
        outlet_pressure = inlet_pressure * (outlet_temperature_ideal / inlet_temperature) ** (self.combustor.hotGas.gamma / (self.combustor.hotGas.gamma - 1))

        return outlet_pressure, outlet_temperature_real, outlet_temperature_ideal
    

    def evolve_associatedFluxes(
        self,
        outlet_fan_pressure,
        inlet_temperature,
        inlet_pressure    
    ):
        # outlet pressure = outlet fan pressure
        outlet_pressure = outlet_fan_pressure

        # calc real temperature
        outlet_temperature_ideal = inlet_temperature * (outlet_fan_pressure/inlet_pressure) ** ((self.combustor.hotGas.gamma - 1) / self.combustor.hotGas.gamma)
        outlet_temperature_real = inlet_temperature - self.efficiency * (inlet_temperature - outlet_temperature_ideal)

        return outlet_pressure, outlet_temperature_real, outlet_temperature_ideal

