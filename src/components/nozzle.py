import numpy as np
from src.fluids.air import Air
from src.fluids.hotGas import HotGas

class Nozzle:
    def __init__(
        self, 
        air: Air,
        hotGas: HotGas,
        efficiency=1.0,
        onlyConvergent = False,
        area_ratio = None
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

        # exit-to-throat area ratio of a convergent-divergent nozzle with given geometry
        # (None: the nozzle is adapted, i.e. the flow expands down to ambient pressure)
        self.area_ratio = area_ratio

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
            error+="T_static_out > T_total_inlet: the nozzle inlet pressure is below ambient | Not acceptable. Check engine properties"
            raise Exception(error)

        self.outlet_velocity = np.sqrt(2.0 * self.hotGas.cp * (inlet_temperature-static_outlet_temperature))

        return self.outlet_velocity

    
    @staticmethod
    def supersonicMach(
        area_ratio,
        gamma
    ):
        # supersonic root of the isentropic area-Mach relation A/A* = f(M), by bisection
        def areaFunction(mach):
            return 1/mach * (2/(gamma+1) * (1 + (gamma-1)/2 * mach**2))**((gamma+1)/(2*(gamma-1)))

        mach_low = 1.0
        mach_high = 2.0
        while areaFunction(mach_high) < area_ratio:
            mach_high *= 2

        for _ in range(200):
            mach = 0.5 * (mach_low + mach_high)
            if areaFunction(mach) < area_ratio:
                mach_low = mach
            else:
                mach_high = mach

        return 0.5 * (mach_low + mach_high)

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

        if self.area_ratio is not None:
            # convergent-divergent nozzle of given geometry: the isentropic exit Mach follows
            # from the area ratio (no shock inside), so the exit pressure is generally not ambient
            gamma = self.hotGas.gamma
            mach_ideal = self.supersonicMach(self.area_ratio, gamma)
            self.static_pressure = inlet_pressure * (1 + (gamma-1)/2 * mach_ideal**2)**(-gamma/(gamma-1))
            static_temperature_ideal = inlet_temperature * (self.static_pressure / inlet_pressure) ** ((gamma-1)/gamma)
            self.static_temperature = inlet_temperature - self.efficiency * (inlet_temperature - static_temperature_ideal)

        if self.onlyConvergent == True:
            # convergent nozzle
            critical_pressure = inlet_pressure * (((self.hotGas.gamma+1)*self.efficiency - self.hotGas.gamma + 1) \
                /((self.hotGas.gamma+1)*self.efficiency))**(self.hotGas.gamma/(self.hotGas.gamma - 1))

            # choked only if the critical pressure is above ambient; otherwise
            # the flow expands to ambient pressure and the exit is subsonic
            if critical_pressure > self.air.pressure:
                self.static_pressure = critical_pressure
                self.static_temperature = inlet_temperature * (2/(self.hotGas.gamma + 1))

        outlet_velocity = self.calcOutletV(inlet_temperature,self.static_temperature)
        sound_speed = np.sqrt(self.hotGas.gamma * self.hotGas.R * self.static_temperature)
        self.mach = outlet_velocity / sound_speed

        return self.static_pressure, self.static_temperature