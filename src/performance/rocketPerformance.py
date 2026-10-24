import numpy as np

from src.components.nozzle import Nozzle
from src.rocket.chamber import Chamber

# standard gravity, used to express the specific impulse in seconds
G0 = 9.80665

class RocketPerformance:
    def __init__(
        self,
        chamber : Chamber,
        nozzle : Nozzle
    ):
        self.chamber = chamber
        self.nozzle = nozzle

        self.area_ratio = 0             # A_e / A_t
        self.thrustCoefficient = 0      # C_F = F / (p_c A_t)
        self.thrustCoefficientVacuum = 0
        self.thrust = 0                 # [N]
        self.thrustVacuum = 0           # [N]
        self.mass_flow = 0              # [kg/s]
        self.effectiveVelocity = 0      # c = F / m_dot [m/s]
        self.specificImpulse = 0        # I_sp = c / g0 [s]
        self.specificImpulseVacuum = 0  # [s]

        self.throat_area = 0
        self.exit_area = 0
        self.throat_diameter = 0
        self.exit_diameter = 0

    def calcPerformance(
        self
    ):
        chamber = self.chamber
        nozzle = self.nozzle
        p_c = chamber.pressure
        p_a = nozzle.air.pressure
        p_e = nozzle.static_pressure
        c_star = chamber.c_star

        # area ratio: given by the geometry, or the one of the adapted nozzle
        # A_t = m_dot c* / p_c,  A_e = m_dot R T_e / (p_e u_e)
        if nozzle.area_ratio is not None:
            self.area_ratio = nozzle.area_ratio
        else:
            self.area_ratio = p_c * nozzle.hotGas.R * nozzle.static_temperature / (p_e * nozzle.outlet_velocity * c_star)

        # C_F = u_e / c* + (p_e - p_a) / p_c * A_e / A_t  (independent of the engine size)
        self.thrustCoefficient = nozzle.outlet_velocity / c_star + (p_e - p_a) / p_c * self.area_ratio
        self.thrustCoefficientVacuum = nozzle.outlet_velocity / c_star + p_e / p_c * self.area_ratio

        # size the engine
        if chamber.thrust is not None:
            self.throat_area = chamber.thrust / (self.thrustCoefficient * p_c)
        elif chamber.throat_diameter is not None:
            self.throat_area = np.pi * chamber.throat_diameter**2 / 4
        else:
            self.throat_area = chamber.mass_flow * c_star / p_c

        self.exit_area = self.area_ratio * self.throat_area
        self.throat_diameter = np.sqrt(4 * self.throat_area / np.pi)
        self.exit_diameter = np.sqrt(4 * self.exit_area / np.pi)

        self.mass_flow = p_c * self.throat_area / c_star
        chamber.splitFlows(self.mass_flow)

        self.thrust = self.thrustCoefficient * p_c * self.throat_area
        self.thrustVacuum = self.thrustCoefficientVacuum * p_c * self.throat_area

        self.effectiveVelocity = self.thrust / self.mass_flow
        self.specificImpulse = self.effectiveVelocity / G0
        self.specificImpulseVacuum = self.thrustVacuum / self.mass_flow / G0
