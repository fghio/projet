import numpy as np
from src.fluids.air import Air
from src.fluids.hotGas import HotGas

class Nozzle:
    def __init__(
        self, 
        air: Air,
        hotGas: HotGas,
        efficiency=1.0,
        onlyConvergent = False
    ):
        self.air = air
        self.hotGas = hotGas
        self.efficiency = efficiency

        # initialize
        self.static_pressure = self.air.pressure
        self.static_temperature = self.air.temperature

        self.outlet_velocity = 0
        self.mach = 0
        self.onlyConvergent = bool(onlyConvergent)

        if self.onlyConvergent == True:
            self.mach = 1
            self.pressureContribution = 0


    def calcOutletV(
        self,
        inlet_temperature,
        static_outlet_temperature
    ):
        if static_outlet_temperature > inlet_temperature:
            error="The code stopped with the following error:\n"
            error+="T_static_out < T_static_inlet | Not acceptable. Check engine properties"
            raise Exception(error)

        self.outlet_velocity = np.sqrt(2.0 * self.hotGas.cp * (inlet_temperature-static_outlet_temperature))

        return self.outlet_velocity

    
    def totalToStatic(
        self, 
        inlet_temperature, 
        inlet_pressure, 
    ):
        static_pressure = self.air.pressure
        outlet_temperature = inlet_temperature
        static_temperature_ideal = outlet_temperature * (static_pressure / inlet_pressure) ** ((self.hotGas.gamma -1)/self.hotGas.gamma)
        static_temperature = inlet_temperature - self.efficiency * (inlet_temperature - static_temperature_ideal)

        return static_pressure, static_temperature
    
    def evolve(
        self, 
        inlet_temperature, 
        inlet_pressure
    ):
        self.static_pressure, self.static_temperature = self.totalToStatic(inlet_temperature, inlet_pressure)

        if self.onlyConvergent == True:
            # convergent nozzle
            self.static_pressure = inlet_pressure * (((self.hotGas.gamma+1)*self.efficiency - self.hotGas.gamma + 1) \
                /((self.hotGas.gamma+1)*self.efficiency))**(self.hotGas.gamma/(self.hotGas.gamma - 1))

            self.static_temperature = inlet_temperature * (2/(self.hotGas.gamma + 1))

        outlet_velocity = self.calcOutletV(inlet_temperature,self.static_temperature)
        sound_speed = np.sqrt(self.hotGas.gamma * self.hotGas.R * self.static_temperature)
        self.mach = outlet_velocity / sound_speed

        return self.static_pressure, self.static_temperature