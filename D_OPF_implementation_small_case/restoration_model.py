''' will take area as an input and gives pyomo model as an output
this area is obtained from previous functions
So, previous function will be calling this function'''


from pyomo.environ import *
import numpy as np
import networkx as nx
from copy import deepcopy

def restoration_model(area_wo_m): # area_wo_m means without pyomo model

    class Restoration:


        def __init__(self, area):

            ''' initialization of data'''

            self.area = deepcopy(area)   # area is loaded
            self.model = ConcreteModel()  # model is defined
            self.branch_data = self.area.branch_data # branch data
            self.bus_data = self.area.bus_data
            self.substation = self.area.substation
            self.bus_index = self.area.bus_index
            self.edge_index = self.area.edge_index
            self.pPower = self.area.pPower
            self.pVoltage = self.area.pVoltage
            self.cPower = self.area.cPower

            ''' getting load and impedance information by processing above data'''

            self.load = self.bus_data  # bus_index, PL, QL for eg, self.load['20']['PL'] gives Pl of bus 20
            self.total_Pdemand_perPhase = sum(np.array([[self.load[i]['PLA'], self.load[i]['PLB'], self.load[i]['PLC']] for i in self.load.keys()]))
            self.total_Pdemand = sum(self.total_Pdemand_perPhase)

            # making graph
            self.fbus = [str(self.branch_data[i]['fbus']) for i in self.branch_data.keys()]
            self.tbus = [str(self.branch_data[i]['tbus']) for i in self.branch_data.keys()]
            self.G = nx.DiGraph()
            self.G.add_edges_from(zip(self.fbus ,self.tbus))

        ###################### Initialize Variables #######################################

        def initialize_variables(self, Vmax = 1.05**2, Vmin = 0.95**2):

            ''' initialize index for various variables and  defining variables as well '''

            # big M multipliers for load
            #self.Pmax = self.total_Pdemand *1.1
            #self.Pmin = -self.total_Pdemand *1.1

            self.Pmax = 10000 # change this to total system load*1.1
            self.Pmin = -10000

            # Connectivity variables
            self.model.vi = Var(self.bus_index, bounds = (0 ,1), domain = Binary) # bus energization variable
            # self.model.si = Var(self.bus_index, bounds = (0,1), domain = Binary) # load pickup variable
            # for child bus to have continuous variable
            self.model.si = Var(self.bus_index, bounds=(0, 1), domain=lambda model, index: Reals if index in self.cPower.keys() else Binary)  # load pickup variable
            self.model.xij = Var(self.edge_index, bounds = (0 ,1), domain = Binary) # edge on/off variable

            # Power related variables
            self.model.Pija = Var(self.edge_index, bounds = (self.Pmin ,self.Pmax), domain = Reals)
            self.model.Pijb = Var(self.edge_index, bounds = (self.Pmin, self.Pmax), domain = Reals)
            self.model.Pijc = Var(self.edge_index, bounds = (self.Pmin, self.Pmax), domain = Reals)
            self.model.Qija = Var(self.edge_index, bounds = (self.Pmin, self.Pmax), domain = Reals)
            self.model.Qijb = Var(self.edge_index, bounds = (self.Pmin, self.Pmax), domain = Reals)
            self.model.Qijc = Var(self.edge_index, bounds = (self.Pmin, self.Pmax), domain = Reals)

            # Voltage
            self.model.Va = Var(self.bus_index ,bounds = (Vmin, Vmax), domain = Reals)
            self.model.Vb = Var(self.bus_index ,bounds = (Vmin, Vmax), domain = Reals)
            self.model.Vc = Var(self.bus_index ,bounds = (Vmin, Vmax), domain = Reals)

            ######## updating power of shared bus from child areas.########
            '''i.e. child area power incorporating'''

        def shared_bus_power_update(self):
            if self.cPower is not None:
                for bus in self.cPower.keys():
                    self.load[bus]['PLA'] = self.load[bus]['PLA'] + self.cPower[bus]['PLA']
                    self.load[bus]['QLA'] = self.load[bus]['QLA'] + self.cPower[bus]['QLA']
                    self.load[bus]['PLB'] = self.load[bus]['PLB'] + self.cPower[bus]['PLB']
                    self.load[bus]['QLB'] = self.load[bus]['QLB'] + self.cPower[bus]['QLB']
                    self.load[bus]['PLC'] = self.load[bus]['PLC'] + self.cPower[bus]['PLC']
                    self.load[bus]['QLC'] = self.load[bus]['QLC'] + self.cPower[bus]['QLC']


            ###################### Constraints ############################################


        def connectivity_constraint(self):

            ''' adding connectivity constraints '''

            # load pick up relation with bus energization si <= vi

            def connectivity_si_rule (model ,i):
                return model.si[i] <= model.vi[i]

            self.model.connectivity_si = Constraint(self.bus_index ,rule = connectivity_si_rule)

            # line condition with bus condition xij<=vi

            def connectivity_vi_rule(model ,ij):
                i = ij.split("_")[0] # since ij = fbus_tbus, splitting will give fbus
                return model.xij[ij] <= model.vi[i]

            self.model.connectivity_vi = Constraint(self.edge_index, rule = connectivity_vi_rule)

            # line condition with bus condition xij<=vj

            def connectivity_vj_rule(model ,ij):
                j = ij.split("_")[1] # since ij = fbus_tbus, splitting will give tbus
                return model.xij[ij] <= model.vi[j]

            self.model.connectivity_vj = Constraint(self.edge_index, rule = connectivity_vj_rule)



        ######################### Power flow constraints ########################

        def power_flow_constraints(self):

            ''' adding power flow related constraints'''
            self.model.power_flow_A = ConstraintList() # for phase A
            self.model.power_flow_B = ConstraintList()  # for phase B
            self.model.power_flow_C = ConstraintList()  # for phase C

            for k in self.edge_index:
                active_index = k.split("_")[1] # this is tbus of edge

                parent_nodes = list(self.G.predecessors(active_index)) # gives parent node
                child_nodes = list(self.G.successors(active_index))  # gives child nodes
                from_parent_edge_index = [str(_ ) +"_" +str(active_index) for _ in parent_nodes] # gets correspondig edge from parent to active node
                to_child_edge_index = [str(active_index ) +"_" +str(_) for _ in child_nodes] # similar for child nodes


                # getting active and reactive power demand for active_index bus
                PA = self.load[active_index]['PLA']
                PB = self.load[active_index]['PLB']
                PC = self.load[active_index]['PLC']
                QA = self.load[active_index]['QLA']
                QB = self.load[active_index]['QLB']
                QC = self.load[active_index]['QLC']


                ######## Phase A #####################################

                # active power
                self.model.power_flow_A.add(sum(self.model.Pija[_] for _ in from_parent_edge_index) == PA *self.model.si[active_index] \
                                            + sum(self.model.Pija[_] for _ in to_child_edge_index))

                # reactive power
                self.model.power_flow_A.add(sum(self.model.Qija[_] for _ in from_parent_edge_index) == QA *self.model.si[active_index]\
                                            + sum(self.model.Qija[_] for _ in to_child_edge_index))


                ######## Phase B #####################################

                # active power
                self.model.power_flow_B.add(sum(self.model.Pijb[_] for _ in from_parent_edge_index) == PB *self.model.si[active_index]\
                                            + sum(self.model.Pijb[_] for _ in to_child_edge_index))


                # reactive power
                self.model.power_flow_B.add(sum(self.model.Qijb[_] for _ in from_parent_edge_index) == QB *self.model.si[active_index]\
                                            + sum(self.model.Qijb[_] for _ in to_child_edge_index))


                ######## Phase C #####################################

                # active power
                self.model.power_flow_C.add(sum(self.model.Pijc[_] for _ in from_parent_edge_index) == PC *self.model.si[active_index]\
                                            + sum(self.model.Pijc[_] for _ in to_child_edge_index))

                # reactive power
                self.model.power_flow_C.add(sum(self.model.Qijc[_] for _ in from_parent_edge_index) ==QC *self.model.si[active_index]\
                                            + sum(self.model.Qijc[_] for _ in to_child_edge_index))



        ################## Bus Voltage Constraints ##############################################

        def voltage_balance_constraints(self):

            ''' adding voltage drop related constraints'''
            self.model.voltage_balance_A = ConstraintList() # for phase A
            self.model.voltage_balance_B = ConstraintList()  # for phase B
            self.model.voltage_balance_C = ConstraintList()  # for phase C

            for edge_index in self.edge_index:

                # getting impedance information
                # r matrix
                raa = self.branch_data[edge_index]['raa']
                rab = self.branch_data[edge_index]['rab']
                rac = self.branch_data[edge_index]['rac']
                rbb = self.branch_data[edge_index]['rbb']
                rbc = self.branch_data[edge_index]['rbc']
                rcc = self.branch_data[edge_index]['rcc']
                # x matrix
                xaa = self.branch_data[edge_index]['xaa']
                xab = self.branch_data[edge_index]['xab']
                xac = self.branch_data[edge_index]['xac']
                xbb = self.branch_data[edge_index]['xbb']
                xbc = self.branch_data[edge_index]['xbc']
                xcc = self.branch_data[edge_index]['xcc']

                # getting source and target index of line
                source_node_index = edge_index.split('_')[0] # getting i index in i>>j line
                target_node_index = edge_index.split('_')[1] # gettinh j index in i>>j line

                #################### for phase A ####################

                self.model.voltage_balance_A.add(self.model.Va[source_node_index] - self.model.Va[target_node_index] - 2*raa*self.model.Pija[edge_index]/1000\
                                                 - 2*xaa* self .model.Qija[edge_index]/1000 +(rab - np.sqrt(3) * xab) * self.model.Pijb[edge_index]/1000\
                                                 + (xab + np.sqrt(3) * rab) * self.model . Qijb[edge_index]/1000 +(rac + np.sqrt(3) * xac) * self.model.Pijc[edge_index]/1000\
                                                 + (xac - np.sqrt(3) * rac) * self.model . Qijc[edge_index]/1000 == 0)



                #################### for phase B ####################

                self.model.voltage_balance_B.add(self.model.Vb[source_node_index] - self.model.Vb[target_node_index]\
                                                 - 2*rbb*self.model.Pijb[edge_index]/1000 - 2*xbb * self .model.Qijb[edge_index]/1000 \
                                                 + (rab + np.sqrt(3) * xab) * self.model.Pija[edge_index]/1000 + (xab - np.sqrt(3) * rab) * self.model . Qija[edge_index]/1000 \
                                                 + (rbc - np.sqrt(3) * xbc) * self.model.Pijc[edge_index]/1000 + (xbc + np.sqrt(3) * rbc) * self.model . Qijc[edge_index]/1000 == 0)


                #################### for phase C ####################


                self.model.voltage_balance_C.add(self.model.Vc[source_node_index] - self.model.Vc[target_node_index] \
                                                 - 2*rcc*self.model.Pijc[edge_index]/1000 - 2*xcc * self.model.Qijc[edge_index]/1000 \
                                                 + (rac - np.sqrt(3) * xac) * self.model.Pija[edge_index]/1000 + (xac + np.sqrt(3) * rac) * self.model . Qija[edge_index]/1000 \
                                                 + (rbc + np.sqrt(3) * xbc) * self.model.Pijb[edge_index]/1000 + (xbc - np.sqrt(3) * rbc) * self.model . Qijb[edge_index]/1000 == 0)

                ########## branch power flow limit constraints ############################

        def branch_powerflow_constraints(self):

            ''' using big M method with self.pmax as multiplier, branch flow limit will be written here
            -M * xij <= Pij <= M * xij '''

            self.model.powerflow_limit_A = ConstraintList() # for phase A
            self.model.powerflow_limit_B = ConstraintList()  # for phase B
            self.model.powerflow_limit_C = ConstraintList()  # for phase C


            for edge_index in self.edge_index:

                ###### for Phase A ############
                self.model.powerflow_limit_A.add(self.model.Pija[edge_index] <= self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_A.add(self.model.Pija[edge_index] >= -self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_A.add(self.model.Qija[edge_index] <= self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_A.add(self.model.Qija[edge_index] >= -self.Pmax * self.model.xij[edge_index])

                ###### for Phase B ############
                self.model.powerflow_limit_B.add(self.model.Pijb[edge_index] <= self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_B.add(self.model.Pijb[edge_index] >= -self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_B.add(self.model.Qijb[edge_index] <= self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_B.add(self.model.Qijb[edge_index] >= -self.Pmax * self.model.xij[edge_index])

                ###### for Phase C ############
                self.model.powerflow_limit_C.add(self.model.Pijc[edge_index] <= self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_C.add(self.model.Pijc[edge_index] >= -self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_C.add(self.model.Qijc[edge_index] <= self.Pmax * self.model.xij[edge_index])
                self.model.powerflow_limit_C.add(self.model.Qijc[edge_index] >= -self.Pmax * self.model.xij[edge_index])


        ############# Substation Voltage constraints ##########

        def substation_voltage_constraint(self):

            ''' assigns voltage to root node '''

            self.model.substation_voltage = ConstraintList()

            # loading voltage given by parent area
            Va = self.pVoltage['Va']
            Vb = self.pVoltage['Vb']
            Vc = self.pVoltage['Vc']

            self.model.substation_voltage.add(self.model.Va[self.substation] == Va)  # phase A # list(substation)
            self.model.substation_voltage.add(self.model.Vb[self.substation] == Vb)  # phase B
            self.model.substation_voltage.add(self.model.Vc[self.substation] == Vc)  # phase C

        def all_loads_on_constraint(self):
            ''' assign si = 1 for all'''
            self.model.all_loads_on = Constraint(expr = sum(self.model.si[bus_index] for bus_index in self.bus_index) == len(self.bus_index))

        ###### power limit to each area ####################
        ''' power limit constraint for each area to be fed by parent area'''

        def power_limit_area_constraint(self):

            self.model.power_limit = ConstraintList()
            substation = self.substation
            child_nodes = list(self.G.successors(substation))  # gives child nodes
            to_child_edge_index = [str(substation) + "_" + str(_) for _ in child_nodes]  # substation to child edge

            # power limit for given area
            PA_lim = self.pPower['PLA']
            PB_lim = self.pPower['PLB']
            PC_lim = self.pPower['PLC']
            QA_lim = self.pPower['QLA']
            QB_lim = self.pPower['QLB']
            QC_lim = self.pPower['QLC']

            # getting active and reactive power demand for shared parent bus
            PA = self.load[substation]['PLA']
            PB = self.load[substation]['PLB']
            PC = self.load[substation]['PLC']
            QA = self.load[substation]['QLA']
            QB = self.load[substation]['QLB']
            QC = self.load[substation]['QLC']

            ######## Phase A #####################################

            # active power
            self.model.power_limit.add(PA + sum(self.model.Pija[_] for _ in to_child_edge_index) <= PA_lim)
            # reactive power
            self.model.power_limit.add(QA + sum(self.model.Qija[_] for _ in to_child_edge_index) <= QA_lim)

            ######## Phase B #####################################

            # active power
            self.model.power_limit.add(PB + sum(self.model.Pijb[_] for _ in to_child_edge_index) <= PB_lim)
            # reactive power
            self.model.power_limit.add(QB + sum(self.model.Qijb[_] for _ in to_child_edge_index) <= QB_lim)

            ######## Phase C #####################################

            # active power
            self.model.power_limit.add(PC + sum(self.model.Pijc[_] for _ in to_child_edge_index) <= PC_lim)
            # reactive power
            self.model.power_limit.add(QC + sum(self.model.Qijc[_] for _ in to_child_edge_index) <= QC_lim)


        ###### Objective function definition ###########################

        def objective_function(self):

            ''' objective function defined here'''
            self.model.objective = Objective(expr = sum(self.model.si[bus_index] *(self.load[bus_index]['PLA'] + self.load[bus_index]['PLB'] \
            + self.load[bus_index]['PLC']) for bus_index in self.bus_index), sense = maximize)


    area = Restoration(area_wo_m)    # name of object area with out model

    # initializing variables
    area.initialize_variables(1.06**2, 0.95**2) # Vmax**2, Vmin**2

    # updating shared bus power from child areas
    area.shared_bus_power_update()
    ## getting total power after summing child areas load
    area.total_Pdemand_with_child = sum(sum(np.array([[area.load[i]['PLA'], area.load[i]['PLB'], area.load[i]['PLC']] for i in area.load.keys()])))

    # connectivity constraint function calling
    area.connectivity_constraint()

    # calling power flow function constraint
    area.power_flow_constraints()

    # voltage balance constraints
    area.voltage_balance_constraints()

    # branch power flow constraints
    area.branch_powerflow_constraints()

    # adding substation voltage constraint
    area.substation_voltage_constraint()

    # adding power limit area by parent constraint
    area.power_limit_area_constraint()

    # all loads on
    # area.all_loads_on_constraint()

    # adding objective function to model
    area.objective_function()

    # solving

    solver = SolverFactory('gurobi')
    model = solver.solve(area.model, tee=True)
    return area
