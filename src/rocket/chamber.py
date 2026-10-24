import numpy as np
from src.fluids.hotGas import HotGas

class Chamber:
    def __init__(
        self,
        hotGas: HotGas,
        pressure,
        temperature,
        mixture_ratio = None,
        thrust = None,
        mass_flow = None,
        throat_diameter = None
    ):
        self.hotGas = hotGas
        self.pressure = pressure            # total pressure p_c [Pa]
        self.temperature = temperature      # total (adiabatic flame) temperature T_c [K]
        self.mixture_ratio = mixture_ratio  # oxidizer-to-fuel mass ratio O/F

        # sizing: exactly one of thrust, mass flow or throat diameter is given
        self.thrust = thrust
        self.mass_flow = mass_flow
        self.throat_diameter = throat_diameter

        self.c_star = 0
        self.throat_pressure = 0
        self.throat_temperature = 0
        self.mass_flow_oxidizer = 0
        self.mass_flow_fuel = 0

    def characteristicVelocity(
        self
    ):
        # c* = sqrt(R T_c) / Gamma(gamma),  Gamma = sqrt(gamma) (2/(gamma+1))^((gamma+1)/(2(gamma-1)))
        gamma = self.hotGas.gamma
        Gamma = np.sqrt(gamma) * (2/(gamma+1))**((gamma+1)/(2*(gamma-1)))
        self.c_star = np.sqrt(self.hotGas.R * self.temperature) / Gamma

        return self.c_star

    def throatConditions(
        self
    ):
        # sonic throat (M = 1), isentropic convergent
        gamma = self.hotGas.gamma
        self.throat_temperature = self.temperature * 2/(gamma+1)
        self.throat_pressure = self.pressure * (2/(gamma+1))**(gamma/(gamma-1))

        return self.throat_pressure, self.throat_temperature

    def splitFlows(
        self,
        mass_flow
    ):
        # propellant mass flow split into oxidizer and fuel by O/F
        if self.mixture_ratio is None:
            return
        self.mass_flow_fuel = mass_flow / (1 + self.mixture_ratio)
        self.mass_flow_oxidizer = mass_flow - self.mass_flow_fuel

    def evolve(
        self
    ):
        self.characteristicVelocity()
        throat_pressure, throat_temperature = self.throatConditions()

        return self.pressure, self.temperature, throat_pressure, throat_temperature
