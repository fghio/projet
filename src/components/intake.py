import numpy as np
from src.fluids.air import Air

class Intake:
    def __init__(
        self, 
        air: Air,
        efficiency=1.0, 
        Phi = 1.00, # diameter of the intake
        mach=0.8,
    ):
        self.air = air
        self.efficiency = efficiency
        self.Phi = Phi
        self.inlet_velocity = 0
        self.mach = mach
    

    def calcInletV(
        self,
        static_temperature
    ):
        sound_speed = np.sqrt(self.air.gamma * self.air.R * static_temperature)
        self.inlet_velocity = sound_speed * self.mach
        return self.inlet_velocity

    
    def calcAirMass(
        self,
        static_temperature
    ):
        inlet_U = self.calcInletV(static_temperature)
        self.air.mass_flow_main = self.air.rho * inlet_U * np.pi * self.Phi ** 2 / 4
        return  self.air.mass_flow_main


    def staticToTotal(
        self, 
        static_temperature, 
        static_pressure, 
    ):
        self.calcInletV(static_temperature)
        self.calcAirMass(static_temperature)

        common_factor = 1 + (self.air.gamma - 1) /2.0 * self.mach ** 2
        total_temperature = static_temperature * common_factor
        total_pressure = static_pressure * common_factor ** (self.air.gamma / (self.air.gamma - 1))

        return total_pressure, total_temperature
    
    def evolve(
        self, 
        inlet_temperature, 
        inlet_pressure
    ):
        outlet_pressure = self.efficiency * inlet_pressure

        return outlet_pressure, inlet_temperature
