from src.fluids.air import Air

class Compressor:
    def __init__(
        self,
        air : Air, 
        pressure_ratio, 
        efficiency=1.0, 
        mechanical_efficiency=1.0,
        BPR=1.0
    ):
        self.air = air
        self.pressure_ratio = pressure_ratio
        self.efficiency = efficiency
        self.mechanical_efficiency = mechanical_efficiency
        self.power = 0
        self.BPR = BPR

    def evolve(
        self, 
        inlet_temperature, 
        inlet_pressure,
    ):
        # Solve pressure
        outlet_pressure = inlet_pressure * self.pressure_ratio

        # Solve ideal temperature
        outlet_temperature_ideal = inlet_temperature * (self.pressure_ratio ** ((self.air.gamma - 1) / self.air.gamma))
        
        # Solve real temperature
        outlet_temperature_real = inlet_temperature + (outlet_temperature_ideal - inlet_temperature) / self.efficiency

        self.power = 1/self.mechanical_efficiency * self.air.mass_flow_main * self.air.cp * abs(outlet_temperature_real - inlet_temperature)

        return outlet_pressure, outlet_temperature_real, outlet_temperature_ideal