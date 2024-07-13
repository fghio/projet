from src.fluids.air import Air
from src.fluids.hotGas import HotGas

from src.components.turbine import Turbine

class Propeller:
    def __init__(
        self,
        air : Air, 
        hotGas : HotGas,
        turbine : Turbine,
        Phi = 1, 
        alpha_power = 0.85,
        efficiency=1.0, 
        gearbox_efficiency=1.0,
    ):
        self.air = air
        self.hotGas = hotGas
        self.turbine = turbine
        self.Phi = Phi
        self.alpha_power = alpha_power
        self.efficiency = efficiency
        self.gearbox_efficiency = gearbox_efficiency
        self.DeltaHu = 0
        self.power = 0

        # for subsequent print
        self.propeller_velocity = 0
        self.air_mass = 0

    def setOptimalAlpha(
        self,
        inlet_velocity,
        nozzle_efficiency,
        inlet_temperature, 
        inlet_pressure,
    ):
        outlet_pressure_PPrime = inlet_temperature*(self.air.pressure/inlet_pressure)**((self.hotGas.gamma-1)/self.hotGas.gamma)
        self.DeltaHu = self.hotGas.cp * (inlet_temperature - outlet_pressure_PPrime)
        self.alpha_power = 1 - inlet_velocity**2 * nozzle_efficiency/(2 * (self.efficiency * self.gearbox_efficiency * self.turbine.mechanical_efficiency * self.turbine.efficiency)**2 * self.DeltaHu)

    def evolve(
        self, 
        inlet_temperature, 
        inlet_pressure,
    ):
        outlet_pressure_PPrime = inlet_temperature*(self.air.pressure/inlet_pressure)**((self.hotGas.gamma-1)/self.hotGas.gamma)
        self.DeltaHu = self.hotGas.cp * (inlet_temperature - outlet_pressure_PPrime)
        outlet_pressure_prime = inlet_temperature - self.alpha_power*self.DeltaHu/self.hotGas.cp
        outlet_temperature = inlet_temperature + self.turbine.efficiency*(outlet_pressure_prime-inlet_temperature)
        outlet_pressure = inlet_pressure*(outlet_pressure_prime/inlet_temperature)**(self.hotGas.gamma/(self.hotGas.gamma-1))
        
        # we return the power before the application of gearbox and propeller efficiency 
        # to avoid to store two variables more (see performance)
        overallMass = self.air.mass_flow_main + self.turbine.combustor.fuel.mass_fuel
        self.power = self.turbine.mechanical_efficiency * overallMass * self.hotGas.cp * (inlet_temperature - outlet_temperature) 

        return outlet_pressure, outlet_temperature