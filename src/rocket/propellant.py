class Propellant:
    def __init__(
        self,
        density,
        flame_temperature,
        burn_rate_coefficient,
        burn_rate_exponent
    ):
        self.density = density                      # rho_p [kg/m3]
        self.flame_temperature = flame_temperature  # T_c [K]
        # Saint-Robert law r = a p^n, with r in mm/s and p in MPa (exam convention)
        self.burn_rate_coefficient = burn_rate_coefficient
        self.burn_rate_exponent = burn_rate_exponent

    def coefficientSI(
        self
    ):
        # a such that r [m/s] = a * p[Pa]^n
        return self.burn_rate_coefficient * 1e-3 / (1e6)**self.burn_rate_exponent

    def burnRate(
        self,
        pressure
    ):
        return self.coefficientSI() * pressure**self.burn_rate_exponent

    def equilibriumPressure(
        self,
        Kn,
        c_star
    ):
        # mass balance rho_p r A_b = p_c A_t / c*  ->  p_c = (a rho_p c* Kn)^(1/(1-n))
        n = self.burn_rate_exponent
        return (self.coefficientSI() * self.density * c_star * Kn)**(1/(1-n))
