from src.components.nozzle import Nozzle
from src.performance.rocketPerformance import RocketPerformance
from src.write.writeOutput import Write


class WriteRocket(Write):
    def __init__(
        self,
        performance : RocketPerformance,
        nozzle : Nozzle,
        engineType = ""
    ):
        # a rocket has no intake: only the station and cycle writers of Write are reused
        super().__init__(performance=performance, intake=None, mainNozzle=nozzle, engineType=engineType)


    def ambientConditions(
        self
    ):
        p_a = self.mainNozzle.air.pressure
        self.results["ambient_pressure"] = p_a

        if p_a > 0:
            print(f"Ambient pressure: {p_a/1000:.2f} kPa")
        else:
            print("Ambient pressure: vacuum")
        print()


    def writeChamberAdditionalProperties(
        self,
        chamber
    ):
        self.results["stations"][-1]["c_star"] = chamber.c_star
        self.results["stations"][-1]["mixture_ratio"] = chamber.mixture_ratio

        print(self.tab,f"Characteristic velocity c* = {chamber.c_star:.2f} m/s")
        if chamber.mixture_ratio is not None:
            print(self.tab,f"Mixture ratio O/F          = {chamber.mixture_ratio:.3f}")


    def writePerformance(
        self,
    ):
        perf = self.performance
        chamber = perf.chamber
        nozzle = self.mainNozzle

        self.results["mass_flow"] = perf.mass_flow
        self.results["mass_flow_oxidizer"] = chamber.mass_flow_oxidizer
        self.results["mass_flow_fuel"] = chamber.mass_flow_fuel
        self.results["performance"] = {
            "thrust": perf.thrust,
            "thrust_vacuum": perf.thrustVacuum,
            "c_star": chamber.c_star,
            "CF": perf.thrustCoefficient,
            "CF_vacuum": perf.thrustCoefficientVacuum,
            "effective_velocity": perf.effectiveVelocity,
            "Isp": perf.specificImpulse,
            "Isp_vacuum": perf.specificImpulseVacuum
        }
        self.results["mainNozzle"] = {
            "mach": nozzle.mach,
            "velocity": nozzle.outlet_velocity,
            "onlyConvergent": False,
            "adapted": nozzle.area_ratio is None,
            "area_ratio": perf.area_ratio,
            "exit_pressure": nozzle.static_pressure,
            "exit_temperature": nozzle.static_temperature
        }
        self.results["geometry"] = {
            "throat_area": perf.throat_area,
            "exit_area": perf.exit_area,
            "throat_diameter": perf.throat_diameter,
            "exit_diameter": perf.exit_diameter
        }

        print("----------------------------------------")
        print()
        print("Nozzle:")
        print()

        ratioString = f"Area ratio Ae/At     = {perf.area_ratio:.2f}"
        if nozzle.area_ratio is None:
            ratioString += " (adapted)"
        print(self.tab,ratioString)
        print(self.tab,f"Exit Mach           = {nozzle.mach:.2f}")
        print(self.tab,f"Exit velocity       = {nozzle.outlet_velocity:.2f} m/s")
        print(self.tab,f"Throat diameter     = {perf.throat_diameter:.4f} m")
        print(self.tab,f"Exit diameter       = {perf.exit_diameter:.4f} m")

        print()
        print("Performance:")
        print()

        print(self.tab,f"Propellant mass flow = {perf.mass_flow:.3f} kg/s")
        if chamber.mixture_ratio is not None:
            print(self.tab,f"  oxidizer          = {chamber.mass_flow_oxidizer:.3f} kg/s")
            print(self.tab,f"  fuel              = {chamber.mass_flow_fuel:.3f} kg/s")
        print()
        print(self.tab,f"Thrust               = {perf.thrust/1000:.2f} kN")
        print(self.tab,f"Thrust (vacuum)      = {perf.thrustVacuum/1000:.2f} kN")
        print(self.tab,f"Thrust coefficient   = {perf.thrustCoefficient:.4f} (vacuum {perf.thrustCoefficientVacuum:.4f})")
        print(self.tab,f"Effective velocity   = {perf.effectiveVelocity:.2f} m/s")
        print(self.tab,f"Specific impulse     = {perf.specificImpulse:.2f} s (vacuum {perf.specificImpulseVacuum:.2f} s)")


class WriteSolidRocket(WriteRocket):
    def __init__(
        self,
        performance : RocketPerformance,
        nozzle : Nozzle,
        ballistics,
        engineType = ""
    ):
        super().__init__(performance=performance, nozzle=nozzle, engineType=engineType)
        self.ballistics = ballistics


    def writeGrain(
        self
    ):
        b = self.ballistics
        grain, prop = b.grain, b.propellant
        throat_area = self.performance.throat_area
        first = {k: v[0] for k, v in b.history.items()}

        self.results["grain"] = {
            "web": grain.web(),
            "volume": grain.volume(),
            "propellant_mass": b.propellant_mass,
            "initial_burn_area": first["burn_area"],
            "port_to_throat": grain.portArea(0) / throat_area,
            "volumetric_loading": grain.volume() / (grain.segments * grain.segment_length * 3.141592653589793 / 4 * grain.outer_diameter**2),
        }

        print("----------------------------------------")
        print("Grain (BATES):")
        print(self.tab,f"Segments                 = {grain.segments} ({'inhibited' if grain.inhibited_ends else 'burning'} ends)")
        print(self.tab,f"Web thickness            = {grain.web()*1000:.2f} mm")
        print(self.tab,f"Propellant mass          = {b.propellant_mass:.3f} kg")
        print(self.tab,f"Port-to-throat area      = {self.results['grain']['port_to_throat']:.3f}")
        print()
        print("Ignition (web = 0), for hand checks:")
        print(self.tab,f"a (SI, r in m/s, p in Pa) = {prop.coefficientSI():.6e}")
        print(self.tab,f"Burn area Ab             = {first['burn_area']:.6f} m2")
        print(self.tab,f"Throat area At           = {throat_area:.6e} m2")
        print(self.tab,f"Kn = Ab/At               = {first['Kn']:.3f}")
        print(self.tab,f"Chamber pressure pc      = {first['pressure']/1e6:.4f} MPa")
        print(self.tab,f"Burn rate r              = {first['burn_rate']*1000:.4f} mm/s")
        print(self.tab,f"Thrust F                 = {first['thrust']/1000:.4f} kN")


    def writeBallistics(
        self
    ):
        b = self.ballistics
        h = b.history
        self.results["burn"] = {
            "burn_time": b.burn_time,
            "total_impulse": b.total_impulse,
            "average_thrust": b.average_thrust,
            "max_thrust": b.max_thrust,
            "average_pressure": b.average_pressure,
            "max_pressure": b.max_pressure,
            "min_pressure": b.min_pressure,
            "Isp": b.specific_impulse,
            "burnt_mass": b.burnt_mass,
            "history": {k: [float(v) for v in values] for k, values in h.items()},
        }

        print("----------------------------------------")
        print()
        print("Burn:")
        print()
        print(self.tab,f"Burn time            = {b.burn_time:.3f} s")
        print(self.tab,f"Chamber pressure     = {b.average_pressure/1e6:.3f} MPa average, {b.max_pressure/1e6:.3f} MPa max, {b.min_pressure/1e6:.3f} MPa min")
        print(self.tab,f"Thrust               = {b.average_thrust/1000:.3f} kN average, {b.max_thrust/1000:.3f} kN max")
        print(self.tab,f"Total impulse        = {b.total_impulse/1000:.3f} kN s")
        print(self.tab,f"Specific impulse     = {b.specific_impulse:.2f} s (total impulse / propellant mass)")
        print()
        print("Operating point at maximum chamber pressure:")


class WriteEndBurner(WriteSolidRocket):
    def writeLayers(
        self
    ):
        b = self.ballistics
        first = b.phases[0]
        diameter = first.grain.diameter
        throat_area = self.performance.throat_area

        self.results["grain"] = {
            "web": sum(p.grain.web() for p in b.phases),
            "propellant_mass": b.propellant_mass,
            "initial_burn_area": first.grain.burnArea(0),
            "Kn": first.grain.burnArea(0) / throat_area,
        }
        self.results["phases"] = []
        gas = self.mainNozzle.hotGas
        self.results["station_gas"] = {"cp": gas.cp, "R": gas.R, "gamma": gas.gamma}

        print("----------------------------------------")
        print("Grain (cigarette, end burning):")
        print(self.tab,f"Diameter                 = {diameter:.4f} m")
        print(self.tab,f"Burn area Ab = pi D^2/4  = {first.grain.burnArea(0):.6f} m2")
        print(self.tab,f"Throat area At           = {throat_area:.6e} m2")
        print(self.tab,f"Kn = Ab/At               = {self.results['grain']['Kn']:.3f}")
        print(self.tab,f"Propellant mass          = {b.propellant_mass:.3f} kg")

        for i, (phase, start) in enumerate(zip(b.phases, b.phase_start)):
            prop, chamber = phase.propellant, phase.chamber
            pressure = phase.history["pressure"][0]
            rate = phase.history["burn_rate"][0]
            thrust = phase.history["thrust"][0]
            mass_flow = phase.history["mass_flow"][0]
            CF = phase.history["CF"][0]
            self.results["phases"].append({
                "layer": i + 1,
                "length": phase.grain.length,
                "start": start,
                "burn_time": phase.burn_time,
                "pressure": pressure,
                "burn_rate": rate,
                "c_star": chamber.c_star,
                "CF": CF,
                "thrust": thrust,
                "mass_flow": mass_flow,
                "mass": phase.propellant_mass,
                "impulse": phase.total_impulse,
                "Isp": phase.specific_impulse,
                "exit_pressure": phase.history["exit_pressure"][0],
                "gamma": chamber.hotGas.gamma,
                "R": chamber.hotGas.R,
            })

            print()
            print(f"Layer {i + 1} ({'nozzle side, burns first' if i == 0 else 'towards the head end'}):")
            print(self.tab,f"a (SI)                   = {prop.coefficientSI():.6e}")
            print(self.tab,f"c*                       = {chamber.c_star:.2f} m/s (gamma {chamber.hotGas.gamma:g}, R {chamber.hotGas.R:g})")
            print(self.tab,f"Chamber pressure pc      = {pressure/1e6:.4f} MPa")
            print(self.tab,f"Burn rate r              = {rate*1000:.4f} mm/s")
            print(self.tab,f"Burn time L/r            = {phase.burn_time:.4f} s (from {start:.4f} s to {start + phase.burn_time:.4f} s)")
            print(self.tab,f"Mass flow                = {mass_flow:.4f} kg/s")
            print(self.tab,f"Thrust coefficient       = {CF:.4f}")
            print(self.tab,f"Thrust F                 = {thrust/1000:.4f} kN")
            print(self.tab,f"Impulse                  = {phase.total_impulse/1000:.4f} kN s")
