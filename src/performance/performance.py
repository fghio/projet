import numpy as np

from src.fluids.fuel import Fuel

from src.components.intake import Intake
from src.components.nozzle import Nozzle
from src.components.combustor import Combustor
from src.components.propeller import Propeller

class Performance:
    def __init__(
        self,
        intake : Intake,
        combustor : Combustor,
        mainNozzle : Nozzle,
        postCombustor : Combustor = None,
        secondNozzle : Nozzle = None,
        propeller : Propeller = None
    ):
        self.intake = intake
        self.combustor = combustor
        self.mainNozzle = mainNozzle
        if postCombustor is not None:
            self.postCombustor = postCombustor 
        else: 
            self.postCombustor = Combustor(air=Fuel(),fuel=Fuel(),hotGas=Fuel())
        self.secondNozzle = secondNozzle
        self.propeller = propeller
        self.thrust = 0     # [N]
        self.impulse = 0    # [m/s]
        self.TSFC = 0       # [kg/(s.N)]
        self.thermalPerformance = 0
        self.propulsivePerformance = 0
        self.globalPerformance = 0

        self.availablePower = 0
        self.propulsivePower = 0
        self.dissipatedPower = 0

    def updatePerformance(
        self
    ):
        # Performance
        self.thermalPerformance = (self.propulsivePower+self.dissipatedPower) / self.availablePower
        self.propulsivePerformance = self.propulsivePower / (self.propulsivePower+self.dissipatedPower)
        self.globalPerformance = self.thermalPerformance * self.propulsivePerformance


    def calcPerformance(
         self   
    ):
        # T_overall = (dot{m}_{a,H} + dot{m}_{f}) u_{e,H} + dot{m}_{a,C} u_{e,C} - (dot{m}_{a,H} + dot{m}_{a,C}) u_{in} + 0 (perfect expansion)
        self.thrust = (self.intake.air.mass_flow_main + self.combustor.fuel.mass_fuel + self.postCombustor.fuel.mass_fuel) * self.mainNozzle.outlet_velocity \
            - (self.intake.air.mass_flow_main + self.intake.air.mass_flow_secondary) * self.intake.inlet_velocity

        if self.secondNozzle is not None:
            # turbofan separated fluxes
            self.thrust += self.intake.air.mass_flow_secondary * self.secondNozzle.outlet_velocity
        else:
            # turbofan associated fluxes
            self.thrust += self.intake.air.mass_flow_secondary * self.mainNozzle.outlet_velocity

        if self.mainNozzle.onlyConvergent == True:
            # contribution for the pressure difference (p_e != p_amb)
            nozzle_outlet_area = (self.mainNozzle.air.mass_flow_main + self.mainNozzle.air.mass_flow_secondary + self.combustor.fuel.mass_fuel + self.postCombustor.fuel.mass_fuel) \
                * self.mainNozzle.hotGas.R * self.mainNozzle.static_temperature \
                / (self.mainNozzle.outlet_velocity * self.mainNozzle.static_pressure)
            self.thrust += (self.mainNozzle.static_pressure - self.mainNozzle.air.pressure)*nozzle_outlet_area

        # I = T / (dot{m}_{a,H} + dot{m}_{a,C})
        self.impulse = self.thrust / (self.intake.air.mass_flow_main+self.intake.air.mass_flow_secondary)

        # TSFC =  dot{m}_{f} / T
        self.TSFC = (self.combustor.fuel.mass_fuel + self.postCombustor.fuel.mass_fuel) / self.thrust 

        # calculate power(s)
        self.availablePower = self.combustor.fuel.mass_fuel * self.combustor.fuel.calorific + self.postCombustor.fuel.mass_fuel * self.combustor.fuel.calorific
        self.propulsivePower = self.thrust * self.intake.inlet_velocity
        self.dissipatedPower = 0.5 * (self.intake.air.mass_flow_main + self.combustor.fuel.mass_fuel + self.postCombustor.fuel.mass_fuel) * (self.mainNozzle.outlet_velocity - self.intake.inlet_velocity) ** 2 

        if self.secondNozzle is not None:
            # turbofan separated fluxes
            self.dissipatedPower += 0.5 * self.intake.air.mass_flow_secondary * (self.secondNozzle.outlet_velocity - self.intake.inlet_velocity) ** 2
        else:
            # turbofan associated fluxes
            self.dissipatedPower += 0.5 * self.intake.air.mass_flow_secondary * (self.mainNozzle.outlet_velocity - self.intake.inlet_velocity) ** 2

        self.updatePerformance()


    def adjustPerformanceTurboprop(
        self
    ):
        prop = self.propeller
        air = prop.air

        # shaft power has to be updated considering the efficiency of gearbox and propeller  
        shaftPower = prop.power
        self.TSFC = self.combustor.fuel.mass_fuel / (shaftPower * prop.gearbox_efficiency) * 1000 

        propellerPower = shaftPower * prop.gearbox_efficiency * prop.efficiency 
        propellerThrust = propellerPower / self.intake.inlet_velocity
        self.thrust += propellerThrust
        
        # update propellant relevant infos
        prop.air_mass = air.pressure / (air.R * air.temperature) * np.pi * prop.Phi**2 / 4 * self.intake.inlet_velocity
        prop.propeller_velocity = propellerThrust/self.propeller.air_mass + self.intake.inlet_velocity
        
        # update of the performance
        self.propulsivePower += propellerThrust * self.intake.inlet_velocity
        self.dissipatedPower += 0.5 * prop.air_mass * (prop.propeller_velocity - self.intake.inlet_velocity)**2
        self.updatePerformance()


        # finallly, improperly assign the prop.air_mass as cold flow (secondary) in air class for print
        self.intake.air.mass_flow_secondary = prop.air_mass
        

        
