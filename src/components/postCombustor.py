from src.components.combustor import Combustor
from src.components.compressor import Compressor

from src.fluids.air import Air
from src.fluids.fuel import Fuel
from src.fluids.hotGas import HotGas

class PostCombustor:
    def __init__(
        self, 
        air: Air,
        pre: HotGas,
        combustor: Combustor,
        fuel: Fuel,
        post: HotGas,
        outlet_temperature=0, 
        fuel_ratio=0, 
        temperature_max=0,
        efficiency=1.0,
        mechanical_efficiency=1.0,
        compressor : Compressor = None
    ):
        self.air = air
        self.pre = pre
        self.combustor = combustor
        self.fuel = fuel
        self.post = post
        self.outlet_temperature = outlet_temperature
        self.fuel_ratio = fuel_ratio
        self.temperature_max = temperature_max
        self.efficiency = efficiency
        self.mechanical_efficiency = mechanical_efficiency
        self.compressor = compressor

    def calcFuelMass(
        self, 
        air_mass_flow
    ):
        self.fuel.mass_fuel = self.fuel_ratio * air_mass_flow
        return self.fuel.mass_fuel

    def evolve(
        self, 
        inlet_temperature, 
        inlet_pressure
    ):
        if self.outlet_temperature > 0:
            # Compute fuel ratio if outlet temperature is given
            numerator = (1+self.combustor.fuel_ratio)*(self.post.cp*self.outlet_temperature - self.pre.cp*inlet_temperature)
            denominator = self.fuel.calorific * self.efficiency - self.post.cp * self.outlet_temperature
            if self.compressor:
                numerator = numerator + self.compressor.BPR * (self.post.cp*self.outlet_temperature - self.pre.cp*inlet_temperature)

            self.fuel_ratio = numerator / denominator
        else:
            # Compute outlet temperature if fuel ratio is given
            numerator = (1+self.combustor.fuel_ratio)*self.pre.cp * inlet_temperature + self.efficiency * self.fuel_ratio * self.fuel.calorific
            denominator = (1 + self.combustor.fuel_ratio + self.fuel_ratio) * self.post.cp
            if self.compressor:
                numerator = numerator + self.compressor.BPR * self.pre.cp * inlet_temperature
                denominator = denominator + self.compressor.BPR * self.post.cp
            
            self.outlet_temperature = numerator / denominator

        # Calculate outlet pressure
        outlet_pressure = self.mechanical_efficiency * inlet_pressure

        # compute and update the fuel mass
        self.calcFuelMass(self.air.mass_flow_main)

        return outlet_pressure, self.outlet_temperature, self.fuel_ratio
