''' main file to call all functions'''
from pyomo.environ import *
from copy import deepcopy
from areas_bus_separation import areas_bus_separation
from boundary_variables_setting import boundary_variables_setting
from restoration_model import restoration_model
from boundary_variables_update import boundary_variables_update

# calling area bus separation file

[Area1,Area2,Area3,Area4,Area5,AreaAll] = areas_bus_separation()


# getting boundary variables for each area
'''
area.bus_index >> gives bus index of area, 
edge_index>> edge index of area,
bus_voltage>> bus voltage of each area to be updated in every iteration,
bus_load_data>> bus load data demand which is fixed ,
cShared_bus>> dict {child area: shared bus} ,
pShared_bus>> Dict {parent_area: shared bus index} which is fixed
substation>> bus index which is actually shared bus with parent area. is fixed

pVoltage>>voltage of shared node from parent area which is updated in every iteration after solving parent area
pPower>> power limit from parent area which is updated for every iteration after solving parent area,
cPower>> dic {shared  bus: PLA,PLB,PLC,QLA,QLB,QL} i.e. power demanded by child area which is updated after solving child areas
bus_load_inj>> bus load injection which is updated in every iteration,

'''
[area1,area2,area3,area4,area5,areaAll] = boundary_variables_setting(Area1,Area2,Area3,Area4,Area5,AreaAll)

''' 
# calling total restoration
area_collections = [area1,area2,area3,area4,area5]
area_results = {}
for iterations in range(5):
    for area in area_collections:
        print(area)
        area_results[area] = restoration_model(area)
        print(f"load shed is{area_results[area].total_Pdemand_with_child - area_results[area].model.objective()}")

    # updating boundary variables
    boundary_variables_update(area_collections,area_results)'''


# calling one area only
area = deepcopy(area1)
area1_res = restoration_model(area)
for bus in area.bus_index:
    print(f"the load pick up variable for{bus} is {area1_res.model.si[bus]()}")
'''
for bus in area1_res.bus_index:
    print(f"the voltage Va for{bus} is {area1_res.model.Va[bus]()}")

for edge in area.edge_index:
    print(f"the voltage Pija Pijb Pijc for{edge} is {area1_res.model.Pija[edge]()},{area1_res.model.Pijb[edge]()}, {area1_res.model.Pijc[edge]()}")'''

