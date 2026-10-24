import numpy as np

from src.rocket.chamber import Chamber
from src.rocket.grain import BatesGrain
from src.rocket.propellant import Propellant
from src.components.nozzle import Nozzle
from src.performance.rocketPerformance import RocketPerformance, G0

class Ballistics:
    def __init__(
        self,
        chamber : Chamber,
        propellant : Propellant,
        grain : BatesGrain,
        nozzle : Nozzle,
        performance : RocketPerformance,
        steps = 400
    ):
        self.chamber = chamber
        self.propellant = propellant
        self.grain = grain
        self.nozzle = nozzle
        self.performance = performance
        self.steps = steps

        self.history = {}
        self.burn_time = 0
        self.total_impulse = 0
        self.average_thrust = 0
        self.max_thrust = 0
        self.average_pressure = 0
        self.max_pressure = 0
        self.min_pressure = 0
        self.propellant_mass = 0
        self.burnt_mass = 0
        self.specific_impulse = 0
        self.max_pressure_web = 0

    def operatingPoint(
        self,
        x
    ):
        # quasi-steady state after a burnt web x: equilibrium pressure, then nozzle and thrust
        throat_area = np.pi * self.chamber.throat_diameter**2 / 4
        burn_area = self.grain.burnArea(x)
        Kn = burn_area / throat_area
        c_star = self.chamber.characteristicVelocity()

        self.chamber.pressure = self.propellant.equilibriumPressure(Kn, c_star)
        self.chamber.evolve()
        self.nozzle.evolve(self.chamber.temperature, self.chamber.pressure)
        self.performance.calcPerformance()

        return {
            "web": x,
            "burn_area": burn_area,
            "Kn": Kn,
            "pressure": self.chamber.pressure,
            "burn_rate": self.propellant.burnRate(self.chamber.pressure),
            "thrust": self.performance.thrust,
            "mass_flow": self.performance.mass_flow,
            "exit_pressure": self.nozzle.static_pressure,
            "exit_mach": self.nozzle.mach,
            "gamma": self.nozzle.hotGas.gamma,
            "CF": self.performance.thrustCoefficient,
        }

    def burn(
        self
    ):
        # integrate over the burnt web: dt = dx / r (trapezoidal rule)
        web = self.grain.web()
        points = [self.operatingPoint(x) for x in np.linspace(0, web, self.steps + 1)]
        history = {key: np.array([p[key] for p in points]) for key in points[0]}

        dx = np.diff(history["web"])
        inverse_rate = 1 / history["burn_rate"]
        dt = 0.5 * (inverse_rate[1:] + inverse_rate[:-1]) * dx
        history["time"] = np.concatenate(([0.0], np.cumsum(dt)))
        self.history = history

        t = history["time"]
        trapz = lambda y: float(np.sum(0.5 * (y[1:] + y[:-1]) * np.diff(t)))
        self.burn_time = t[-1]
        self.total_impulse = trapz(history["thrust"])
        self.average_thrust = self.total_impulse / self.burn_time
        self.max_thrust = history["thrust"].max()
        self.average_pressure = trapz(history["pressure"]) / self.burn_time
        self.max_pressure = history["pressure"].max()
        self.min_pressure = history["pressure"].min()
        self.max_pressure_web = history["web"][history["pressure"].argmax()]

        self.propellant_mass = self.propellant.density * self.grain.volume()
        self.burnt_mass = trapz(history["mass_flow"])
        self.specific_impulse = self.total_impulse / (self.propellant_mass * G0)

        # leave chamber, nozzle and performance at the maximum-pressure point (used for the stations)
        self.operatingPoint(self.max_pressure_web)


class PhasedBallistics:
    def __init__(
        self,
        phases
    ):
        # grain layers burning one after the other (a cigarette grain from the nozzle side
        # towards the head end): one Ballistics per layer, each with its own propellant and gas
        self.phases = phases

        self.history = {}
        self.burn_time = 0
        self.total_impulse = 0
        self.average_thrust = 0
        self.max_thrust = 0
        self.average_pressure = 0
        self.max_pressure = 0
        self.min_pressure = 0
        self.propellant_mass = 0
        self.burnt_mass = 0
        self.specific_impulse = 0
        self.max_pressure_phase = 0
        self.phase_start = []

    def burn(
        self
    ):
        start = 0.0
        histories = []
        for i, phase in enumerate(self.phases):
            phase.burn()
            h = dict(phase.history)
            h["time"] = h["time"] + start
            h["web"] = h["web"] + sum(p.grain.web() for p in self.phases[:i])
            h["layer"] = np.full(len(h["time"]), i + 1)
            histories.append(h)
            self.phase_start.append(start)
            start += phase.burn_time
        # the layers follow each other: at a change of layer the pressure jumps (quasi-steady)
        self.history = {k: np.concatenate([h[k] for h in histories]) for k in histories[0]}

        self.burn_time = start
        self.total_impulse = sum(p.total_impulse for p in self.phases)
        self.average_thrust = self.total_impulse / self.burn_time
        self.max_thrust = max(p.max_thrust for p in self.phases)
        self.average_pressure = sum(p.average_pressure * p.burn_time for p in self.phases) / self.burn_time
        self.max_pressure = max(p.max_pressure for p in self.phases)
        self.min_pressure = min(p.min_pressure for p in self.phases)
        self.propellant_mass = sum(p.propellant_mass for p in self.phases)
        self.burnt_mass = sum(p.burnt_mass for p in self.phases)
        self.specific_impulse = self.total_impulse / (self.propellant_mass * G0)
        self.max_pressure_phase = max(range(len(self.phases)), key=lambda i: self.phases[i].max_pressure)
