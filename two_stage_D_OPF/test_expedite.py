from __future__ import annotations
import os
from pyomo.opt import TerminationCondition
from multiprocessing import Pool, cpu_count
import shutil
import copy
import multiprocessing as mp
import pandas as pd
from pyomo.environ import Var

from expedite_functions_list import first_stage_restoration,  enapp_preprocessing_for_second_stage,\
    Area,result_saving, excel_writing_boundary_solutions, faults_line_to_area_mapping, update_first_stage_area_load, voltage_quality_assess, plot_voltage_quality,\
    track_pick_up_load, fix_restored_previous_load, calculate_restored_load, plot_power_restored, get_load_from_WVU, get_outage_restoration_time_index, initialize_bus_index_outage_restore_dict

def solve_area(args):
    key, area_object_list, pick_up_variable_dict, fix_restored_load_flag, vmin, vmax = args

    obj = copy.deepcopy(area_object_list[key])  # deepcopy for process safety

    obj.second_stage_area_solve(vmin=vmin, vmax=vmax, tee=False, objective_function_index=2)

    if fix_restored_load_flag and key in pick_up_variable_dict:
        obj.rm = fix_restored_previous_load(obj.rm, pick_up_variable_dict[key])

    pre_solved_model = obj.solved_model
    obj.solved_model, results = obj.rm.solve_model(
        solver='gurobi',
        tee=False
    )

    if results.solver.termination_condition == TerminationCondition.infeasible:
        obj.solved_model = pre_solved_model

    return key, obj




if __name__ == "__main__":

    current_working_dir = os.getcwd()
    system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123

    fix_restored_load_flag = True # fixing whether restored load need to be picked up or not in future iteration.

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


    # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_9500_der"
    # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage"
    # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_ieee123"  # for 123 bus system
    # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_ieee123\first_stage"


    # faults input. Note that there might be another function to get areas based on fault location information of line
    # faults = [("area_1","area_2"),("area_2","area_3"),("area_3","area_4"),("area_4","area_5"),("area_3","area_6"),("area_8","area_9"),("area_5","area_13"),("area_30","area_31")]
    # faults = [("area_1","area_2")]
    # faults = []

    # if want to give line faults (actual line from to )
    # faults_list = [("m1047515","m1047513")]
    # faults_list = [("d2000100_int","m2000200"),("hvmv69s1s2_1","hvmv69s1s2_2")]
    faults_list = []
    faults, fault_related_area_list = faults_line_to_area_mapping(areas_data_file_path, faults_list)

    objective_function_index = 2 # 1 for load objective only, 2 for load objective with switching operation minimization, 3 for DERs connected system with load restoration and switching minimization
    solver_options = {"mipgap": 0.0000, "ScaleFlag": 1} # option, note that with not smaller mip gap, switching operation might not work as expected, try to put very low mip gap, if not solved, increase mip gap
    psub_max = 5000 # be careful of this parameter


    ## second stage
    tolerance = 0.00005 # tolerance for convergence in second stage
    max_iteration = 40
    vmin = 0.95
    vmax = 5  # note substation voltage is made lower than this slightly .

    # input data from WVU
    # updating load file of each area with steady final value
    # final_load_data_dict = {} # final steady state value from Rafy
    # # this function will change load value in file and update the file
    # update_first_stage_area_load(areas_data_file_path=areas_data_file_path, final_load_data_dict = final_load_data_dict)


    # calling first stage restoration
    parent_child_area_dict, DERs_area_activated_dict = first_stage_restoration(parsed_data_path=os.path.join(areas_data_file_path,"first_stage"), \
                                                                               faults=faults,objective_function_index = objective_function_index,\
                                                                               solver_options = solver_options,\
                                                                               psub_a_max = psub_max, psub_b_max = psub_max, psub_c_max = psub_max,\
                                                                               temp_result_file_dir = temp_result_file_dir)


    #########Second Stage OPF solving ######################################################################
    voltage_quality_measure_list = []
    restored_load_list = []
    pick_up_variable_dict = {} # {area_index:{bus_index: binary}}
    outaged_area_list = []
    relative_restoration_index = 0 # this is just keeping track of number of restoration index in
    for current_time_index in range(5, 15):
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
                                                       parent_child_dict = parent_child_area_dict,DERs_area_activated_dict = DERs_area_activated_dict) # calling class and initializing variables
        # need to initialize dictionary for first time period depending on outaged area.
        if relative_restoration_index == 1:
            bus_index_outage_restore_dict = initialize_bus_index_outage_restore_dict(area_object_list, areas_data_file_path, outaged_area_list=outaged_area_list,\
                                                                                     current_time_index= current_time_index)
        # Input data from WVU
        # updating load value of area using estimation model
        updated_load_data_dict = {}
        # updated_load_data_dict = get_load_from_WVU(area_object_list = area_object_list, areas_data_file_path  = areas_data_file_path,\
        #                                            bus_index_outage_restore_dict = bus_index_outage_restore_dict, current_time_index = current_time_index)

        # for area_index in area_object_list.keys(): # required to input update from Rafy's putput
        #     area_dir = os.path.abspath(temp_areas_file_dir + f"/{area_index}".rstrip("_o")) # note that it changes data in temp folder file, temp_decomposed file can be used here as well if this function is defined before
        #     area_object_list[area_index].load_data_update(updated_load_data_dict = updated_load_data_dict, area_dir = area_dir, current_time_index = current_time_index) # here current_time_index if for changing parameters for testing


        convergence = False # for convergence flag
        iteration = 0 # iteration count for second stage
        while convergence is False:
            iteration += 1
            print(f"Macro iteration {iteration}")

            pool_inputs = [
                (key, area_object_list, pick_up_variable_dict, fix_restored_load_flag, vmin, vmax)
                for key in area_object_list.keys()
            ]

            with mp.Pool() as pool: #processes=5
                results = pool.map(solve_area, pool_inputs)

            updated_area_object_list = dict(results)
            area_object_list.update(updated_area_object_list)

           # paralleism ends here.

                ## updating boundary variables after solving
            for key in area_object_list.keys():
                # print(key)
                area_object_list[key].update_boundary_variables_after_opf()
                # area_object_list[key].oscillation_control(iteration) # for controlling oscilallation but did not work.
                area_object_list[key].appending_result_to_list()  # storing updated variable as list


            ## exchange boundary variables
            for key in area_object_list.keys():
                parent_area_index = area_object_list[key].parent # getting parent index
                if parent_area_index is not None: # if no parent is present , no need to exchange. Note that it can be done either from parent perspective or child perspective. here, I have done from parent perspective
                    parent_area_object = area_object_list[f"{parent_area_index}_o"]
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

        # power restored value
        restored_load = calculate_restored_load(area_object_list, pick_up_variable_dict)
        restored_load_list.append(restored_load)


        # write function to measure voltage quality (use substation voltage as 1 maybe. as 1.05 makes voltage as other node not that much less.
    print("voltage quality value is", voltage_quality_measure_list)
    plot_voltage_quality( voltage_quality_measure_list)
    print("restored load value is",restored_load_list)
    plot_power_restored(restored_load_list)
