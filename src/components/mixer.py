from src.fluids.air import Air
from src.fluids.fuel import Fuel
from src.fluids.hotGas import HotGas

class Mixer:
    def __init__(
        self, 
        air: Air,
        fuel: Fuel,
        hotGas: HotGas,
        mix: HotGas
    ):
        self.air = air
        self.fuel = fuel
        self.hotGas = hotGas
        self.mix = mix

    def updatePropertiesAfterMixing(
        self
    ):
        overallMass = self.air.mass_flow_main + self.air.mass_flow_secondary + self.fuel.mass_fuel
        hotGassesMas = self.air.mass_flow_main + self.fuel.mass_fuel

        self.mix.cp = ( hotGassesMas * self.hotGas.cp + self.air.mass_flow_secondary * self.air.cp ) / overallMass
        self.mix.gamma = ( hotGassesMas * self.hotGas.gamma + self.air.mass_flow_secondary * self.air.gamma ) / overallMass
        self.mix.cv = ( hotGassesMas * self.hotGas.cv + self.air.mass_flow_secondary * self.air.cv ) / overallMass
        self.mix.R = ( hotGassesMas * self.hotGas.R + self.air.mass_flow_secondary * self.air.R ) / overallMass

    def evolve(
        self,
        inlet_temperature_hot,
        inlet_temperature_cold,
        inlet_pressure
    ):
        outlet_pressure = inlet_pressure
        outlet_temperature = ((self.air.mass_flow_main + self.fuel.mass_fuel) * self.hotGas.cp * inlet_temperature_hot \
            + self.air.mass_flow_secondary * self.air.cp * inlet_temperature_cold) / \
            ((self.air.mass_flow_main + self.air.mass_flow_secondary + self.fuel.mass_fuel) * self.mix.cp)

        return outlet_pressure, outlet_temperature
