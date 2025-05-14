from __future__ import annotations
import os
from ldrestoration import RestorationBase
from ldrestoration.utils.plotnetwork import plot_solution_map
from copy import deepcopy
import networkx as nx
import pandas as pd
import shutil
from pyomo.opt import TerminationCondition

from central_functions_list import *

# parameters flag
update_from_CLPU_flag = True # true means load is updated from CLPU
first_solve_restoration_and_fix_switch = True # True means first solve restoration using steady state value and obtain topology like what we are doing in distributed.
tie_switch_disable_flag = False # True means tie switches are disabled
DERS_disabled_flag = False # True means DERs are disabled
fix_restored_load_flag = True # True means previous restored load is fixed in the next iteration



# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_9500_der"
# # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage"
# # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_ieee123"  # for 123 bus system
# # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_ieee123\first_stage"

current_working_dir = os.getcwd()
system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123

parsed_data_path = current_working_dir + f"/Data/{system_name}"

# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\temp\system_data\area_2" # for testing

# faults = [("area_1","area_2"),("area_2","area_3"),("area_3","area_4"),("area_4","area_5"),("area_3","area_6"),("area_8","area_9"),("area_5","area_13"),("area_30","area_31")]
# faults = [("area_2","area_4")]
# faults = [("d2000100_int","m2000200")]
# faults = [("hvmv69s1s2_1","hvmv69s1s2_2")]
# faults = [("hvmv115_hsb2","regxfmr_hvmv69sub1_lsb1")]
# faults = [("m2000902","d2000901_int")] # area 88 fault
# faults = [("l2916234","m1047423")]
# faults = [("hvmv115_hsb2","regxfmr_hvmv69sub1_lsb1")]
# faults = [("l3030199","m1125934"), ("m1089162","m1089165"), ("m1125947","m1125944")] # multiple faults.
# faults = [("m1026354","m2000100"), ("m3032981","m3032980")]  # For DERS islanding case, multiple faults.
# faults = []
# faults = [("m1108403","m1108406"), ("m1089188" ,"m1089189")] # fault in area 50 51 ("l3101788","l3101787") area 87
faults = [("m1108403","m1108406")]


vmax = 1.05
vmin = 0.95
vsub_a = 1.04
vsub_b = 1.04
vsub_c = 1.04
psub_a_max = 6000
psub_b_max = 6000
psub_c_max = 6000

### updating from CLPU model and doing sequential restoration

# getting copy of data so that we can update on it and save as new file
temp_central_data_dir = current_working_dir + "//temp_central_data//"
os.makedirs(temp_central_data_dir, exist_ok=True)
temp_central_result_dir = current_working_dir + "//temp_central_result//"
os.makedirs(temp_central_result_dir, exist_ok=True)
temp_parsed_data_path = os.path.abspath(os.path.join(temp_central_data_dir, system_name))

try:
    shutil.rmtree(temp_central_data_dir, onerror=lambda func, path, exc_info: os.chmod(path, 0o777) or func(path))  # remove if directory is already present
except:
    None

shutil.copytree(parsed_data_path, temp_parsed_data_path, dirs_exist_ok=True)

if first_solve_restoration_and_fix_switch:
    #### do restoration first using steady state value ####
    rm = RestorationBase(parsed_data_path, faults = faults, base_kV_LL=4.16) # note we use parsed data path here.

    rm.constraints_base(base_kV_LL=66.4,vmax=vmax,vmin=vmin, \
                        vsub_a = vsub_a, vsub_b = vsub_b, vsub_c = vsub_c, \
                        psub_a_max=psub_a_max, psub_b_max=psub_b_max, psub_c_max=psub_c_max) # use psub_a, psub_b, psub_c

    # rm.objective_load_only()
    if system_name == "parsed_data_ieee123": # for 123 bus system which does n ot have DER
        rm.objective_load_and_switching()
    else:
        rm.objective_load_switching_and_der(beta = 0.4) # alpha, beta, gamma are parameters to it.beta = 0.2 is default

    # disable tie switch
    if tie_switch_disable_flag:
        for _ in rm.model.tie_switch_indices:
            rm.model.xij[_].fix(0)

    # disable DERs
    if DERS_disabled_flag:
        for _ in rm.model.virtual_switch_indices:
            rm.model.xij[_].fix(0)

    # rm_solved, results = rm.solve_model(solver='gurobi',save_results = True, solver_options = {"mipgap":0.00000000,"ScaleFlag":1})
    rm_solved, results = rm.solve_model(solver='gurobi', save_results=True, solver_options = {"mipgap":0.025/100,"ScaleFlag":1})

    # once you obtain solution, keep the topology fixed, for that saving it in dictionary.
    sectionalizing_switch_decisions = {_: rm_solved.xij[_]() for _ in rm_solved.sectionalizing_switch_indices} # pyomo index: binary value
    tie_switch_decisions = {_: rm_solved.xij[_]() for _ in rm_solved.tie_switch_indices}
    virtual_switch_decisions = {_:rm_solved.xij[_]() for _ in rm_solved.virtual_switch_indices}

    ##printing first stage decisions that is used to obtain topology ###
    print("dectionalizers switch status",list(rm_solved.xij[_]() for _ in rm_solved.sectionalizing_switch_indices))
    print("virtual switch status",list(rm_solved.xij[_]() for _ in rm_solved.virtual_switch_indices)) # virtual switch status

    print("tie switch status",list(rm_solved.xij[_]() for _ in rm_solved.tie_switch_indices))

    print("total load served with objective value ",rm_solved.restoration_objective())


### sequential load pick up start from here ###
vmax = 2 # just to simulate without considering CLPU condition.
vmin = 0

voltage_quality_measure_list = [] # voltage quality measure
voltage_quality_measure_num_violation_list = [] # measures number of voltage violation nodes.
load_without_CLPU_list = [] # load list restored not including CLPU part
load_with_CLPU_list = [] # load list including CLPU part.
pick_up_variable_dict = {}
relative_restoration_index = 0 # this is just keeping track of number of restoration index in
for current_time_index in range(60, 80):
    relative_restoration_index += 1  # just for tracking how many steps of restoration is done
    if relative_restoration_index == 1:
        bus_index_outage_restore_dict = initialize_bus_index_outage_restore_dict(temp_parsed_data_path,\
                                                                             outaged_bus_list = [],\
                                                                             current_time_index = current_time_index)


    updated_load_data_dict = {}
    updated_load_data_dict, original_load_data_dict = get_load_from_WVU(parsed_data_path = parsed_data_path, \
                                                                        bus_index_outage_restore_dict = bus_index_outage_restore_dict,\
                                                                        current_time_index = current_time_index)
    if update_from_CLPU_flag:
        load_data_update(updated_load_data_dict=updated_load_data_dict, temp_parsed_data_path=temp_parsed_data_path,\
                         current_time_index=current_time_index)

    rm = RestorationBase(temp_parsed_data_path, faults = faults, base_kV_LL=4.16)

    rm.constraints_base(base_kV_LL=66.4,vmax=vmax,vmin=vmin, \
                        vsub_a = vsub_a, vsub_b = vsub_b, vsub_c = vsub_c, \
                        psub_a_max=psub_a_max, psub_b_max=psub_b_max, psub_c_max=psub_c_max) # use psub_a, psub_b, psub_c

    if first_solve_restoration_and_fix_switch: # if first solved for switching using steady value and fix topology
        for _ in sectionalizing_switch_decisions.keys():
            rm.model.xij[_].fix(sectionalizing_switch_decisions[_])
        for _ in tie_switch_decisions.keys():
            rm.model.xij[_].fix(tie_switch_decisions[_])
        for _ in virtual_switch_decisions.keys():
            rm.model.xij[_].fix(virtual_switch_decisions[_])

            # just for simulating, comment out later.
        # for _ in sectionalizing_switch_decisions.keys():
        #     rm.model.xij[_].fix(1)
        # for _ in tie_switch_decisions.keys():
        #     rm.model.xij[_].fix(0)
        # for _ in virtual_switch_decisions.keys():
        #     rm.model.xij[_].fix(0)

    if system_name == "parsed_data_ieee123":  # for 123 bus system which does n ot have DER
        rm.objective_load_and_switching()
    else:
        rm.objective_load_switching_and_der()  # alpha, beta, gamma are parameters to it.


    # fixing the load restored in previous iteration
    if fix_restored_load_flag:
        if pick_up_variable_dict:
            rm = fix_restored_previous_load(rm = rm,  pick_up_variable_dict = pick_up_variable_dict)

    if  relative_restoration_index != 1:
        previous_model_solved = deepcopy(rm_solved)
    # rm_solved, results = rm.solve_model(solver='gurobi',save_results = True, solver_options = {"mipgap":0.00000000,"ScaleFlag":1})
    rm_solved, results = rm.solve_model(solver='gurobi', save_results=True, solver_options={"ScaleFlag": 1, "mipgap": 0.035 / 100})


    if results.solver.termination_condition == TerminationCondition.infeasible:
        print("relative restoration index", relative_restoration_index)
        rm_solved = previous_model_solved

    # keeping track of loads which are picked up
    pick_up_variable_dict, all_bus_index_pick_up_status_dict = track_pick_up_load(rm_solved)  # bus_index_piuck_up dictionary contains all bus index: value 0 or 1.

    bus_index_outage_restore_dict = get_outage_restoration_time_index(bus_index_outage_restore_dict=bus_index_outage_restore_dict,\
                                                                      all_bus_index_pick_up_status_dict=all_bus_index_pick_up_status_dict,\
                                                                      current_time_index=current_time_index)
    # bus result saving
    result_saving(temp_central_result_dir, rm, rm_solved)

    # measuring voltage quality
    voltage_quality_measure = voltage_quality_assess(temp_central_result_dir = temp_central_result_dir, vmin = vmin, vmax = vmax)
    voltage_quality_measure_list.append(voltage_quality_measure)

    # measuring voltage quality based on violation of number of nodes voltage
    voltage_quality_measure_num_violation, total_nodes = voltage_quality_assess_number_nodes_violate(temp_central_result_dir = temp_central_result_dir, vmin=vmin, vmax=vmax)
    voltage_quality_measure_num_violation_list.append(voltage_quality_measure_num_violation)
    # restored load

    # power restored value
    load_without_CLPU, load_with_CLPU = calculate_restored_load(rm_solved, pick_up_variable_dict, original_load_data_dict)
    load_without_CLPU_list.append(load_without_CLPU)
    load_with_CLPU_list.append(load_with_CLPU)

    print("dectionalizers switch status",list(rm_solved.xij[_]() for _ in rm_solved.sectionalizing_switch_indices))
    print("virtual switch status",list(rm_solved.xij[_]() for _ in rm_solved.virtual_switch_indices)) # virtual switch status

    print("tie switch status",list(rm_solved.xij[_]() for _ in rm_solved.tie_switch_indices))

    print("total load served with objective value ",rm_solved.restoration_objective())


    total_load_served = total_load_served_calculation(rm = rm, rm_solved = rm_solved)

    print(f"Total load served is {total_load_served}")

    print("from post processing and printing list of voltage quality and load restrored")
    print("voltage quality list", voltage_quality_measure_list)
    print("# nodes voltage violation list", voltage_quality_measure_num_violation_list)
    print("load without incorporating CLPU", load_without_CLPU_list)
    print("load with incorporating CLPU", load_with_CLPU_list)

    plot_power_restored(load_without_CLPU_list)
    # plot_power_restored(load_with_CLPU_list, title="with CLPU part")

    # plotting in map
    plot_solution_map(rm_solved, rm.network_tree, rm.network_graph, background="white", filename = f"power_flow_{relative_restoration_index}.html")
