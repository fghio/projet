from src.components.intake import Intake
from src.components.nozzle import Nozzle
from src.performance.performance import Performance


class Write:
    def __init__(
        self,
        performance : Performance,
        intake : Intake,
        mainNozzle : Nozzle,
        secondaryNozzle : Nozzle = None,
        engineType = ""
    ):
        self.tab = "  "
        self.performance = performance
        self.intake = intake
        self.mainNozzle = mainNozzle
        self.secondaryNozzle = secondaryNozzle
        self.engineType = engineType

        # structured copy of everything printed (used by the GUI)
        self.results = {"engineType": engineType, "stations": []}


    def beginCycle(
        self
    ):
        print()
        print("---------------- ProJet ----------------")
        print("Engine Cycle")
        print(f"Engine Type = {self.engineType}")

    def airConditions(
        self
    ):
        print(f"Inlet Flow velocity: {self.intake.inlet_velocity:.2f} m/s")
        print()

        massFlowTotal = self.intake.air.mass_flow_main + self.intake.air.mass_flow_secondary

        self.results["inlet_velocity"] = self.intake.inlet_velocity
        self.results["mass_flow_main"] = self.intake.air.mass_flow_main
        self.results["mass_flow_secondary"] = self.intake.air.mass_flow_secondary
        
        if self.engineType != "turboprop":
            print(f"Air Mass Flow: {massFlowTotal:.2f} kg/s")

        if self.engineType == "turbofan_SF" or self.engineType == "turbofan_AF":
            print(self.tab,f"Main flow: {self.intake.air.mass_flow_main:.2f} kg/s")
            print(self.tab,f"Sec. flow: {self.intake.air.mass_flow_secondary:.2f} kg/s")
        elif self.engineType == "turboprop":
            print(f"Intake    flow: {self.intake.air.mass_flow_main:.2f} kg/s")
            print(f"Propeller flow: {self.intake.air.mass_flow_secondary:.2f} kg/s")


    def writeStatus(
        self,
        componentName,
        pressure,
        temperature,
        total=True
    ):
        keyPressure = "Pressure"
        keyTemperature = "Temperature"

        if total:
            keyPressure += " total"
            keyTemperature += " total"
        else:
            keyPressure += " static"
            keyTemperature += " static"

        self.results["stations"].append({
            "name": componentName,
            "pressure": pressure,
            "temperature": temperature,
            "total": total
        })

        print("----------------------------------------")
        print(f"Output from {componentName}:")
        print(self.tab,f"{keyPressure}    = {pressure/1000:.2f} kPa")
        print(self.tab,f"{keyTemperature} = {temperature:.2f} K")


    def writeCombustorAdditionalProperties(
        self,
        combustor
    ):
        self.results["stations"][-1]["fuel_ratio"] = combustor.fuel_ratio
        self.results["stations"][-1]["fuel_mass"] = combustor.fuel.mass_fuel

        print(self.tab,f"Fuel Ratio        = {combustor.fuel_ratio:.4f}")
        print(self.tab,f"Fuel mass         = {combustor.fuel.mass_fuel:.2f} kg/s")


    def writePerformance(
        self,
    ):
        perf = self.performance
        self.results["performance"] = {
            "thrust": perf.thrust,
            "impulse": perf.impulse,
            "TSFC": perf.TSFC,
            "thermal": perf.thermalPerformance,
            "propulsive": perf.propulsivePerformance,
            "global": perf.globalPerformance,
            "availablePower": perf.availablePower,
            "propulsivePower": perf.propulsivePower,
            "dissipatedPower": perf.dissipatedPower
        }
        self.results["mainNozzle"] = {
            "mach": self.mainNozzle.mach,
            "velocity": self.mainNozzle.outlet_velocity,
            "onlyConvergent": self.mainNozzle.onlyConvergent
        }
        if self.secondaryNozzle is not None:
            self.results["secondaryNozzle"] = {
                "mach": self.secondaryNozzle.mach,
                "velocity": self.secondaryNozzle.outlet_velocity,
                "onlyConvergent": self.secondaryNozzle.onlyConvergent
            }
        if perf.propeller is not None:
            self.results["propeller"] = {
                "alpha_power": perf.propeller.alpha_power,
                "shaft_power": perf.propeller.power,
                "air_mass": perf.propeller.air_mass,
                "velocity": perf.propeller.propeller_velocity
            }

        print("----------------------------------------")
        print()
        print("Performance:")
        print()

        machString = f"Mach main nozzle      = {self.mainNozzle.mach:.2f}"

        if self.mainNozzle.mach > 1.01:
            machString += " (Conv-div required)"
        elif self.mainNozzle.mach < 0.99:
            machString += " (conv nozzle is enough)"

        print(self.tab,machString)       

        if self.engineType == "turbofan_SF":
            machString = f"Mach secondary nozzle = {self.secondaryNozzle.mach:.2f}"
            if self.secondaryNozzle.mach > 1.01:
                machString += " (Conv-div required)"

            print(self.tab,machString)       
            
        print()

        print(self.tab,f"Thrust  = {self.performance.thrust/1000:.2f} kN")
        
        if self.engineType == "turboprop":
            print(self.tab,f"BSFC    = {self.performance.TSFC*3600:.4f} kg/(h.kW)")
        else:
            print(self.tab,f"Impulse = {self.performance.impulse:.2f} m/s => {self.performance.impulse/9.81:.2f} s")
            print(self.tab,f"TSFC    = {self.performance.TSFC*3600:.4f} kg/(h.N)")

        print()

        print(self.tab,f"Thermal Performance (eta_th) = {self.performance.thermalPerformance:.3f}")
        print(self.tab,f"Propul. Performance (eta_pr) = {self.performance.propulsivePerformance:.3f}")
        print(self.tab,f"Global  Performance (eta_g)  = {self.performance.globalPerformance:.3f}")




    def endCycle(
        self
    ):
        print()
        print("----------------------------------------")
