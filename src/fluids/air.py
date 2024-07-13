class Air:
    def __init__(
        self, 
        cp = 1004,
        gamma=1.4, 
        R=287.0,
        density=1.225,
        temperature=293.15,
        pressure=101325
    ):
        self.cp = cp
        self.gamma = gamma
        self.R = R
        self.cv = self.cp - self.R
        self.rho = density
        self.temperature = temperature
        self.pressure = pressure
        self.mass_flow_main = 0 # hot cycle
        self.mass_flow_secondary = 0 # cold cycle

    def separateFlows(
        self, 
        BPR
    ):
        tmp_mass_flow_main = self.mass_flow_main
        self.mass_flow_main /= 1+BPR
        self.mass_flow_secondary = tmp_mass_flow_main - self.mass_flow_main
