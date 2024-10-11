''' this file will take areas information as inout and generates boundary variables based on their shared nodes
input: needs parent area and child area for each areabwhere parent and child area has information about branch and bus data of its own
 output : will give shared bus, parent area, child areas and shared bus, variables for power of parent area and powers of child areas
'''

def boundary_variables_setting(Area1,Area2,Area3,Area4,Area5,AreaAll):
    class Area:

        def __init__(self, area):
            self.bus_index = set(area['bus_data'].keys())
            self.edge_index = set(area['branch_data'].keys())
            self.bus_data = area['bus_data']
            self.branch_data = area['branch_data']
            self.bus_voltage = {bus :{'Va':1.05,'Vb':1.05,'Vc':1.05} for bus in self.bus_index}
            self.bus_load_data = \
                {bus: {'PLA': self.bus_data[bus]['PLA'], 'QLA': self.bus_data[bus]['QLA'], 'PLB': self.bus_data[bus]['PLB'],
                      'QLB': self.bus_data[bus]['QLB']
                    , 'PLC': self.bus_data[bus]['PLC'], 'QLC': self.bus_data[bus]['QLC']} for bus in self.bus_index}
            self.bus_load_inj = {bus: {'PLA': 0, 'QLA': 0, 'PLB': 0, 'QLB': 0, 'PLC': 0, 'QLC': 0} for bus in
                                 self.bus_index}  # injected power obtained only after solving

        def boundary_variables(self, pArea, cArea):

            self.shared_area = [pArea, cArea]

            if (pArea is None and cArea is not None):

                self.pShared_bus = None
                self.pVoltage = {'Va':1.05**2,'Vb':1.05**2,'Vc':1.05**2} # substation voltage for root node
                self.pPower = {'PLA': 10000, 'QLA':10000, 'PLB': 10000, 'QLB': 10000, 'PLC': 10000, 'QLC': 10000} # substation power limit

                # for child areas
                self.cShared_bus = {}
                for child in cArea:
                    self.cShared_bus[child] = self.bus_index & child.bus_index  # {child:shared_bus}

                self.cPower = {}  # {shared_bus: power of child}
                for child in self.cShared_bus:
                    shared_cbus = list(self.cShared_bus[child])
                    self.cPower[shared_cbus[0]] = child.bus_load_inj[shared_cbus[0]]


            elif (cArea is None and pArea is not None):

                self.pShared_bus = {pArea: self.bus_index & pArea.bus_index}
                shared_pbus = list(self.pShared_bus[pArea])  # only one parent area is there
                self.pVoltage = pArea.bus_voltage[shared_pbus[0]]  # voltage from parent area
                #self.pPower = pArea.bus_load_inj[shared_pbus[0]]  # power limit from parent area
                self.pPower = {'PLA': 10000, 'QLA': 10000, 'PLB': 10000, 'QLB': 10000, 'PLC': 10000, 'QLC': 10000}

                self.cShared_bus = None  # since no child is present
                self.cPower = None

            elif (cArea is None and pArea is None):

                self.pShared_bus = None
                self.pVoltage = 1.05
                self.pPower = {'PLA': 10000, 'QLA':10000, 'PLB': 10000, 'QLB': 10000, 'PLC': 10000, 'QLC': 10000} # substation power limit
                self.cPower = None
                self.cShared_bus = None

            else:

                self.pShared_bus = {pArea: self.bus_index & pArea.bus_index}
                shared_pbus = list(self.pShared_bus[pArea])  # only one parent area is there
                self.pVoltage = pArea.bus_voltage[shared_pbus[0]]  # voltage from parent area
                #self.pPower = pArea.bus_load_inj[shared_pbus[0]]  # power limit from parent area
                self.pPower = {'PLA': 10000, 'QLA': 10000, 'PLB': 10000, 'QLB': 10000, 'PLC': 10000,'QLC': 10000}  # substation power limit


                # for child areas
                self.cShared_bus = {}
                for child in cArea:
                    self.cShared_bus[child] = self.bus_index & child.bus_index  # {child:shared_bus}

                self.cPower = {}  # {shared_bus: power of child}
                for child in self.cShared_bus:
                    shared_cbus = list(self.cShared_bus[child])
                    self.cPower[shared_cbus[0]] = child.bus_load_inj[shared_cbus[0]]

            self.get_area_substation()

        def get_area_substation(self):

            ''' getting substation of each area, i.e. slack bus index for each area'''

            try:
                substation = self.pShared_bus[self.shared_area[0]]
                self.substation = [substation for substation in substation][0] # just to get rid of set

            except TypeError:

                ''' if no parent area is found, it will be fed by feeder'''

                self.substation = str(125)  # assuming 1 as feeder node


    # object creation of each area

    area1 = Area(Area1)  # area1 is object of class Area
    area2 = Area(Area2)
    area3 = Area(Area3)
    area4 = Area(Area4)
    area5 = Area(Area5)
    areaAll = Area(AreaAll)

    # initializing boundary variables
    area1.boundary_variables(None, [area2, area3])
    area2.boundary_variables(area1, None)
    area3.boundary_variables(area1, [area4,area5])
    area4.boundary_variables(area3, None)
    area5.boundary_variables(area3, None)
    areaAll.boundary_variables(None, None)

    return [area1,area2,area3,area4,area5,areaAll]