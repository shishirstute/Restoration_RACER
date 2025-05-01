from __future__ import annotations
import os
from ldrestoration import RestorationBase
from copy import deepcopy
import networkx as nx
import pandas as pd
import shutil
from pyomo.opt import TerminationCondition

from central_functions_list import *

# parameters flag
update_from_CLPU_flag = True

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
faults = []

vmax=1.05
vmin=0.95
vsub_a = 1.03
vsub_b = 1.03
vsub_c = 1.03

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





voltage_quality_measure_list = [] # voltage quality measure
load_without_CLPU_list = [] # load list restored not including CLPU part
load_with_CLPU_list = [] # load list including CLPU part.
pick_up_variable_dict = {}
relative_restoration_index = 0 # this is just keeping track of number of restoration index in
for current_time_index in range(50, 51):
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
                        psub_a_max=5000, psub_b_max=5000, psub_c_max=5000) # use psub_a, psub_b, psub_c

    # rm.objective_load_only()
    # rm.objective_load_and_switching()
    rm.objective_load_switching_and_der() # alpha, beta, gamma are parameters to it.

    # fixing the load restored in previous iteration
    if pick_up_variable_dict:
        rm = fix_restored_previous_load(rm = rm,  pick_up_variable_dict = pick_up_variable_dict)

    if  relative_restoration_index != 1:
        previous_model_solved = deepcopy(rm_solved)
    rm_solved, results = rm.solve_model(solver='gurobi',save_results = True, solver_options = {"mipgap":0.00000000,"ScaleFlag":1})

    if results.solver.termination_condition == TerminationCondition.infeasible:
        rm_solved = previous_model_solved

    # keeping track of loads which are picked up
    pick_up_variable_dict, all_bus_index_pick_up_status_dict = track_pick_up_load(rm_solved)  # bus_index_piuck_up dictionary contains all bus index: value 0 or 1.

    bus_index_outage_restore_dict = get_outage_restoration_time_index(bus_index_outage_restore_dict=bus_index_outage_restore_dict,\
                                                                      all_bus_index_pick_up_status_dict=all_bus_index_pick_up_status_dict,\
                                                                      current_time_index=current_time_index)
    # bus result saving
    result_saving(temp_central_result_dir, rm, rm_solved)

    # measuring voltage quality
    voltage_quality_measure = voltage_quality_assess(temp_central_result_dir, vmin)
    voltage_quality_measure_list.append(voltage_quality_measure)

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
    print("load without incorporating CLPU", load_without_CLPU_list)
    print("load with incorporating CLPU", load_with_CLPU_list)
