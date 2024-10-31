from __future__ import annotations
import os
from ldrestoration import RestorationBase
from copy import deepcopy
import networkx as nx
import pandas as pd
import concurrent.futures

from RACER_functions_list import first_stage_restoration,  enapp_preprocessing_for_second_stage, Area,result_saving, excel_writing_boundary_solutions, faults_line_to_area_mapping

current_working_dir = os.getcwd()
system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123

areas_data_file_path = current_working_dir + f"/Network_decomposition/results/{system_name}" # path of areas after decomposition of whole system
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
faults_list = [("hvmv115_hsb2","hvmv115_hsb2")]
faults = faults_line_to_area_mapping(areas_data_file_path, faults_list)

objective_function_index = 2 # 1 for load objective only, 2 for load objective with switching operation minimization, 3 for DERs connected system with load restoration and switching minimization
solver_options = {"mipgap": 0.00005, "ScaleFlag": 1} # option, note that with not smaller mip gap, switching operation might not work as expected, try to put very low mip gap, if not solved, increase mip gap
psub_max = 15000 # be careful of this parameter


## second stage
tolerance = 0.0001 # tolerance for convergence in second stage
max_iteration = 100

# calling first stage restoration
parent_child_area_dict, DERs_area_activated_dict = first_stage_restoration(parsed_data_path=os.path.join(areas_data_file_path,"first_stage"), faults=faults,objective_function_index = objective_function_index,solver_options = solver_options,psub_max = psub_max,temp_result_file_dir = temp_result_file_dir)


#########Second Stage OPF solving ######################################################################

# calling function which does preprocessing: i,e, adding dummy bus and generating required files for Lindist using updated information
enapp_preprocessing_for_second_stage(areas_data_file_path = areas_data_file_path, original_parsed_data_path = original_parsed_data_path, parent_child_area_dict  = parent_child_area_dict )


area_object_list = {} # will contain area object with key as area number i.e. area_1 for area1.
for area_index in parent_child_area_dict.keys():
    area_dir = os.path.abspath(temp_areas_file_dir + f"/{area_index}") # temporary data path of area

    area_object_list[f"{area_index}_o"] = Area(area_index = area_index, area_dir = area_dir, parent_child_dict = parent_child_area_dict,DERs_area_activated_dict = DERs_area_activated_dict) # calling class and initializing variables

convergence = False # for convergence flag
iteration = 0 # iteration count for second stage
while convergence is False:
    iteration += 1
    for key in area_object_list.keys():
        print(f"Iteration{iteration} and area {key}")
        area_object_list[key].second_stage_area_solve(tee = False, objective_function_index=2) # solving for given area


        ## for parallel execution
    # def solve_area(key):
    #     print(f"Iteration {iteration} and area {key}")
    #     area_object_list[key].second_stage_area_solve(tee=False, objective_function_index=2)
    #
    #
    # with concurrent.futures.ThreadPoolExecutor() as executor:
    #         futures = [executor.submit(solve_area, key) for key in area_object_list.keys()]

        ## updating boundary variables after solving
    for key in area_object_list.keys():
        # print(key)
        area_object_list[key].update_boundary_variables_after_opf()
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




result_saving(temp_result_file_dir,area_object_list) # saving voltage, load piuck up result

excel_writing_boundary_solutions(area_object_list = area_object_list, temp_result_file_dir = temp_result_file_dir) # getting boundary variables track wrt iterations