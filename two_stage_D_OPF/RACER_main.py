from __future__ import annotations
import os
from collections import defaultdict
from pyomo.opt import TerminationCondition
from concurrent.futures import ThreadPoolExecutor
import shutil
import pandas as pd
from pyomo.environ import Var

from RACER_functions_list import first_stage_restoration,  enapp_preprocessing_for_second_stage,\
    Area,result_saving, excel_writing_boundary_solutions, faults_line_to_area_mapping, update_first_stage_area_load, voltage_quality_assess, plot_voltage_quality,\
    track_pick_up_load, fix_restored_previous_load, calculate_restored_load,\
    plot_power_restored, get_load_from_WVU, get_outage_restoration_time_index,\
    initialize_bus_index_outage_restore_dict, voltage_quality_assess_number_nodes_violate

current_working_dir = os.getcwd()
system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123

fix_restored_load_flag = True # fixing whether restored load need to be picked up or not in future iteration., True means it will be fixed if it was restored in previous time steps
update_model_flag = True # whether to update mutable parameters only in model or reading from file and building model everytime, false means model will be created everytime
update_from_CLPU_flag = True # if True, update load from CLPU, if False, use static load value
get_area_substation_limit_flag = False # make it True if island is going to be formed. This is just to deal it how D-OPF works.
parent_child_limit_power_flag = False # flag whether to enforce power limit from parent to child area. , True means enforced, iteration to enforce is made as 12 inside function. you can change that later.
tie_switch_disabled_flag = False # if True, tie switch will be disabled in first stage, if False, it will be enabled
DER_disabled_flag = False # # if True, DER will be disabled in first stage, if False, it will be enabled
iteration_to_enforce_limit = 12

# decomposed data file path permanent one
decomposed_areas_data_file_path = current_working_dir + f"/Network_decomposition/results/{system_name}" # path of areas after decomposition of whole system
decomposed_areas_data_file_path = os.path.abspath(decomposed_areas_data_file_path) # absolute path of decomposed data
temp_dir_for_decomposed_data = os.path.abspath(current_working_dir + "/temp_network_decomposition")  # temporary directcory for temporary purpose


try:
     shutil.rmtree(temp_dir_for_decomposed_data, onerror= lambda func, path, exc_info: os.chmod(path, 0o777) or func(path)) # remove if directory is already present
except:
    None
shutil.copytree(decomposed_areas_data_file_path, os.path.join(temp_dir_for_decomposed_data,"system_data"), dirs_exist_ok= True)

# note that this area_data_file_path is temporary data path, but will not change for solving one OPF
areas_data_file_path = os.path.abspath(temp_dir_for_decomposed_data + "/system_data") # path of areas after decomposition of whole system
original_parsed_data_path = current_working_dir + f"/Data/{system_name}"  # path of system which is not decomposed. i.e. whole system data

temp_areas_file_dir = current_working_dir + '/temp/system_data' # for second stage temporary directory while solving for Enapp
temp_result_file_dir = current_working_dir + '/temp_results' # for result
os.makedirs(temp_areas_file_dir, exist_ok=True)
os.makedirs(temp_result_file_dir, exist_ok=True)

# print("Hello")


# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_9500_der"
# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage"
# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_ieee123"  # for 123 bus system
# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_ieee123\first_stage"


# faults input. Note that there might be another function to get areas based on fault location information of line
# faults = [("area_1","area_2"),("area_2","area_3"),("area_3","area_4"),("area_4","area_5"),("area_3","area_6"),("area_8","area_9"),("area_5","area_13"),("area_30","area_31")]
# faults = [("area_1","area_2")]
# faults_list = []

# if want to give line faults (actual line from to )
# faults_list = [("m1047515","m1047513")]
# faults_list = [("d2000100_int","m2000200"),("hvmv69s1s2_1","hvmv69s1s2_2")]
# faults_list = [("m1026354","m2000100"), ("m3032981","m3032980")]  # For DERS islanding case,
# faults_list = [("l2916234","m1047423")]
# faults_list = [("hvmv115_hsb2","regxfmr_hvmv69sub1_lsb1")] # substation fault.
# faults_list = [("m1108403","m1108406"), ("m1089188" ,"m1089189")] # fault in area 50 51
faults_list = [("m1108403","m1108406")] # fault in area 50

# make sure not to operate tie switch listed here below to clear fault. This is just to deal with how Abodh ahs developed model.
faults, fault_related_area_list, tie_switch_not_to_operate = faults_line_to_area_mapping(areas_data_file_path, faults_list)

# objective_function_index = 3 # 1 for load objective only, 2 for load objective with switching operation minimization, 3 for DERs connected system with load restoration and switching minimization
solver_options = {"mipgap": 0.35/100, "ScaleFlag": 1} # option, note that with not smaller mip gap, switching operation might not work as expected, try to put very low mip gap, if not solved, increase mip gap
psub_max = 5000 # be careful of this parameter, note that inside restoration model, I have used psubmax as summation of a,b, and c. be careful.

if system_name == "parsed_data_ieee123":
    objective_function_index = 2  # 1 for load objective only, 2 for load objective with switching operation minimization, 3 for DERs connected system with load restoration and switching minimization
else:
    objective_function_index = 3 # for DER related for example, 9500 nodes system.


## second stage
tolerance = 0.0005 # tolerance for convergence in second stage
max_iteration = 30
vmin = 0
vmax = 2  # note substation voltage is made lower than this slightly .
substation_Va = 1.05 # initializing voltage for each area
substation_Vb = 1.05
substation_Vc = 1.05

# voltage_quality_measure_num_violation, total_nodes = voltage_quality_assess_number_nodes_violate(temp_result_file_dir=temp_result_file_dir, vmin=vmin, vmax=vmax)

# input data from WVU
# updating load file of each area with steady final value
# final_load_data_dict = {} # final steady state value from Rafy
# # this function will change load value in file and update the file
# update_first_stage_area_load(areas_data_file_path=areas_data_file_path, final_load_data_dict = final_load_data_dict)


# calling first stage restoration, directed_graph_area is graph of areas relation in first stage
parent_child_area_dict, DERs_area_activated_dict, area_substation_limit_power, directed_graph_areas, model_first_stage_solved = first_stage_restoration(parsed_data_path=os.path.join(areas_data_file_path,"first_stage"), \
                                                                               faults=faults,objective_function_index = objective_function_index,\
                                                                               solver_options = solver_options,\
                                                                               psub_a_max = psub_max, psub_b_max = psub_max, psub_c_max = psub_max,\
                                                                               temp_result_file_dir = temp_result_file_dir, tie_switch_not_to_operate = tie_switch_not_to_operate,\
                                                                               tee = True, get_area_substation_limit_flag = get_area_substation_limit_flag,\
                                                                               tie_switch_disabled_flag = tie_switch_disabled_flag, DER_disabled_flag = DER_disabled_flag)




# getting dictionary of area and solved
area_solved_load_values_first_stage = defaultdict()
for bus_index, pyomo_id in model_first_stage_solved.node_indices_in_tree.items():
    area_solved_load_values_first_stage[bus_index] = (model_first_stage_solved.P1[pyomo_id]() + model_first_stage_solved.P2[pyomo_id]() + model_first_stage_solved.P3[pyomo_id]())*model_first_stage_solved.si[pyomo_id]()



#########Second Stage OPF solving ######################################################################
voltage_quality_measure_list = []
voltage_quality_measure_num_violation_list = [] # measures number of voltage violation nodes.
restored_load_without_CLPU_list = []
restored_load_with_CLPU_list = []
pick_up_variable_dict = {} # {area_index:{bus_index: binary}}
outaged_area_list = []
relative_restoration_index = 0 # this is just keeping track of number of restoration index in
for current_time_index in range(60, 80):
    relative_restoration_index += 1 # just for tracking how many steps of restoration is done
    print("current restoration step index is", current_time_index)
    # calling function which does preprocessing: i,e, adding dummy bus and generating required files for Lindist using updated information
    # since l;oad will be updated later from Rafy input, any laod can be used here, areas data file path contains static load value
    # it will make copy of data to temp folder.
    enapp_preprocessing_for_second_stage(areas_data_file_path = areas_data_file_path, original_parsed_data_path = original_parsed_data_path, parent_child_area_dict  = parent_child_area_dict )


    area_object_list = {} # will contain area object with key as area number i.e. area_1 for area1.
    for area_index in parent_child_area_dict.keys():
        area_dir = os.path.abspath(temp_areas_file_dir + f"/{area_index}") # temporary data path of area

        area_object_list[f"{area_index}_o"] = Area(area_index = area_index, area_dir = area_dir, \
                                                   parent_child_dict = parent_child_area_dict,DERs_area_activated_dict = DERs_area_activated_dict,\
                                                   substation_Va = substation_Va, substation_Vb = substation_Vb, substation_Vc = substation_Vc) # calling class and initializing variables
    # need to initialize dictionary for first time period depending on outaged area.
    if relative_restoration_index == 1:
        bus_index_outage_restore_dict = initialize_bus_index_outage_restore_dict(area_object_list, areas_data_file_path, outaged_area_list=outaged_area_list,\
                                                                                 current_time_index= current_time_index)
    # Input data from WVU
    # updating load value of area using estimation model
    updated_load_data_dict = {}
    updated_load_data_dict, original_load_data_dict = get_load_from_WVU(area_object_list = area_object_list, areas_data_file_path  = areas_data_file_path,\
                                               bus_index_outage_restore_dict = bus_index_outage_restore_dict, current_time_index = current_time_index)

    if update_from_CLPU_flag:
        for area_index in area_object_list.keys():  # required to input update from Rafy's putput
            area_dir = os.path.abspath(temp_areas_file_dir + f"/{area_index}".rstrip("_o")) # note that it changes data in temp folder file, temp_decomposed file can be used here as well if this function is defined before
            area_object_list[area_index].load_data_update(updated_load_data_dict = updated_load_data_dict, area_dir = area_dir, current_time_index = current_time_index) # here current_time_index if for changing parameters for testing


    convergence = False # for convergence flag
    iteration = 0 # iteration count for second stage
    while convergence is False:
        iteration += 1
        print(f"Macro iteration {iteration}")
        for key in area_object_list.keys():
            # print(f"Iteration{iteration} and area {key}")

            # getting model
            if iteration == 1 or update_model_flag == False: # if first iteration or model is not updated, then read model from file
                area_object_list[key].second_stage_area_solve(vmin =vmin, vmax = vmax, tee = False, area_substation_limit_power =  area_substation_limit_power,\
                                                              get_area_substation_limit_flag = get_area_substation_limit_flag,\
                                                              objective_function_index=2, iteration = iteration, parent_child_limit_power_flag = parent_child_limit_power_flag,\
                                                              iteration_to_enforce_limit = iteration_to_enforce_limit) # solving for given area
            # rm = area_object_list[key].rm # getting model for given area

            # fixing previous restored load
            if fix_restored_load_flag:
                if pick_up_variable_dict.keys():
                    # calling function to fix restored load
                    area_object_list[key].rm = fix_restored_previous_load(area_object_list[key].rm,  pick_up_variable_dict[key])

            pre_solved_model = area_object_list[key].solved_model # if infeasible, use previous decision
            area_object_list[key].solved_model, results = area_object_list[key].rm.solve_model(solver='gurobi', tee=False)

            # if infeasible in certain area, no load will be picked up, so make status of laod to 0
            # if results.solver.termination_condition == TerminationCondition.infeasible:
            #     [setattr(var, 'fixed', False) for var in area_object_list[key].rm.model.component_data_objects(Var, descend_into=True) if var.fixed]
            #     area_object_list[key].solved_model, results = area_object_list[key].rm.solve_model(solver='gurobi', tee=False)
            if results.solver.termination_condition == TerminationCondition.infeasible: # if again infeasible, then use previous model.
                area_object_list[key].solved_model = pre_solved_model # if infeasible, use previous decision


            ## updating boundary variables after solving
        for key in area_object_list.keys():
            # print(key)
            area_object_list[key].update_boundary_variables_after_opf(iteration = iteration, parent_child_limit_power_flag = parent_child_limit_power_flag,\
                                                                      iteration_to_enforce_limit = iteration_to_enforce_limit)
            # area_object_list[key].oscillation_control(iteration) # for controlling oscilallation but did not work.
            area_object_list[key].appending_result_to_list()  # storing updated variable as list


        ## exchange boundary variables
        for key in area_object_list.keys():
            parent_area_index = area_object_list[key].parent # getting parent index
            if parent_area_index is not None: # if no parent is present , no need to exchange. Note that it can be done either from parent perspective or child perspective. here, I have done from parent perspective
                parent_area_object = area_object_list[f"{parent_area_index}_o"]
                if update_model_flag == True: # just updating within model rather than writing model again
                    # we just have to update parent model shared bus power, and current model substation voltage, so why to build model continuously :D
                    area_object_list[key].rm, area_object_list[f"{parent_area_index}_o"].rm = area_object_list[key].boundary_variables_exchange(parent_area_object = parent_area_object,\
                                                                                                                                                update_model_flag = update_model_flag,\
                                                                                                                                                iteration = iteration,\
                                                                                                                                                parent_child_limit_power_flag = parent_child_limit_power_flag,\
                                                                                                                                                iteration_to_enforce_limit = iteration_to_enforce_limit)

                else:
                    area_object_list[key].boundary_variables_exchange(parent_area_object)


        ## convergence test
        error_max = 0
        for key in area_object_list.keys():
            error = area_object_list[key].convergence_test()
            if error > error_max:
                error_max = error
        print(f"maximum subsequence difference is {error_max}")
        if error_max <= tolerance or iteration >= max_iteration:
            convergence = True


    # keeping track of loads which are picked up
    pick_up_variable_dict, all_bus_index_pick_up_status_dict = track_pick_up_load(area_object_list) # bus_index_piuck_up dictionary contains all bus index: value 0 or 1.

    # changing bus outage time index and restored time index, this dictionary will be passed to rafy's CLPU model.
    # consider we have dictionary like this: outage_restored_bus_dict = {"bus_index": {"outage_time_index": 0, "restored_time_index": 0}}

    bus_index_outage_restore_dict = get_outage_restoration_time_index(bus_index_outage_restore_dict = bus_index_outage_restore_dict, all_bus_index_pick_up_status_dict = all_bus_index_pick_up_status_dict,\
                                                                 current_time_index = current_time_index)



    result_saving(temp_result_file_dir,area_object_list) # saving voltage, load pick up result

    excel_writing_boundary_solutions(area_object_list = area_object_list, temp_result_file_dir = temp_result_file_dir) # getting boundary variables track wrt iterations

    # post processing solutions
    # write function to measure total load restored
    voltage_quality_measure = voltage_quality_assess(temp_result_file_dir, vmin)
    voltage_quality_measure_list.append(voltage_quality_measure)
    voltage_quality_measure_num_violation, total_nodes = voltage_quality_assess_number_nodes_violate(temp_result_file_dir=temp_result_file_dir, vmin=vmin, vmax=vmax)
    voltage_quality_measure_num_violation_list.append(voltage_quality_measure_num_violation)

    # power restored value
    load_without_CLPU, load_with_CLPU,area_solved_load_values_without_CLPU_second_stage, area_solved_load_values_with_CLPU_second_stage = calculate_restored_load(area_object_list, pick_up_variable_dict, original_load_data_dict)
    restored_load_without_CLPU_list.append(load_without_CLPU)
    restored_load_with_CLPU_list.append(load_with_CLPU)
    # print("restored load value without CLPU is", restored_load_without_CLPU_list)
    # print("restored load value with CLPU is", restored_load_with_CLPU_list)
    # plot_power_restored(restored_load_without_CLPU_list)
    #
        # write function to measure voltage quality (use substation voltage as 1 maybe. as 1.05 makes voltage as other node not that much less.
    print("voltage quality value is", voltage_quality_measure_list)
    # plot_voltage_quality( voltage_quality_measure_list)
    print("restored load value without CLPU is",restored_load_without_CLPU_list)
    print("restored load value with CLPU is",restored_load_with_CLPU_list)
    print("voltage number violation list is", voltage_quality_measure_num_violation_list)
    # plot_power_restored(restored_load_without_CLPU_list)
    # plot_power_restored(restored_load_with_CLPU_list, title = "with CLPU part")
