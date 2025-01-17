from src.fluids.air import Air
from src.fluids.fuel import Fuel
from src.fluids.hotGas import HotGas

class Combustor:
    def __init__(
        self, 
        air: Air,
        fuel: Fuel,
        hotGas: HotGas,
        outlet_temperature=0, 
        fuel_ratio=0, 
        efficiency=1.0,
        mechanical_efficiency=1.0
    ):
        self.air = air
        self.fuel = fuel
        self.hotGas = hotGas
        self.outlet_temperature = outlet_temperature
        self.fuel_ratio = fuel_ratio
        self.efficiency = efficiency
        self.mechanical_efficiency = mechanical_efficiency

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
            numerator = self.hotGas.cp * self.outlet_temperature - self.air.cp * inlet_temperature
            denominator = self.fuel.calorific * self.efficiency - self.hotGas.cp * self.outlet_temperature
            self.fuel_ratio = numerator / denominator
        else:
            # Compute outlet temperature if fuel ratio is given
            numerator = self.air.cp * inlet_temperature + self.efficiency * self.fuel_ratio * self.fuel.calorific
            denominator = (1 + self.fuel_ratio) * self.hotGas.cp
            self.outlet_temperature = numerator / denominator

        # Calculate outlet pressure
        outlet_pressure = self.mechanical_efficiency * inlet_pressure

        # compute and update the fuel mass
        self.calcFuelMass(self.air.mass_flow_main)

        return outlet_pressure, self.outlet_temperature, self.fuel_ratio
