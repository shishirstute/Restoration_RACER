from __future__ import annotations
import os
from ldrestoration import RestorationBase
from copy import deepcopy
import networkx as nx
import pandas as pd


from second_stage_functions_list import Area,result_saving

# for 9500 nodes
# parent_child_area_dict = {'area_1': {'parent': None, 'children': ['area_2']}, 'area_2': {'parent': 'area_1', 'children': ['area_3']}, 'area_3': {'parent': 'area_2', 'children': ['area_4', 'area_6']}, 'area_4': {'parent': 'area_3', 'children': ['area_5']}, 'area_5': {'parent': 'area_4', 'children': ['area_13']}, 'area_13': {'parent': 'area_5', 'children': ['area_14', 'area_74']}, 'area_14': {'parent': 'area_13', 'children': ['area_15', 'area_56']}, 'area_15': {'parent': 'area_14', 'children': ['area_16']}, 'area_16': {'parent': 'area_15', 'children': ['area_23', 'area_44']}, 'area_23': {'parent': 'area_16', 'children': ['area_60']}, 'area_60': {'parent': 'area_23', 'children': ['area_61']}, 'area_61': {'parent': 'area_60', 'children': []}, 'area_44': {'parent': 'area_16', 'children': ['area_43']}, 'area_43': {'parent': 'area_44', 'children': ['area_42', 'area_50']}, 'area_42': {'parent': 'area_43', 'children': ['area_41']}, 'area_41': {'parent': 'area_42', 'children': ['area_39']}, 'area_39': {'parent': 'area_41', 'children': ['area_40']}, 'area_40': {'parent': 'area_39', 'children': []}, 'area_50': {'parent': 'area_43', 'children': ['area_51']}, 'area_51': {'parent': 'area_50', 'children': ['area_52']}, 'area_52': {'parent': 'area_51', 'children': []}, 'area_56': {'parent': 'area_14', 'children': ['area_57']}, 'area_57': {'parent': 'area_56', 'children': []}, 'area_74': {'parent': 'area_13', 'children': []}, 'area_6': {'parent': 'area_3', 'children': ['area_7']}, 'area_7': {'parent': 'area_6', 'children': ['area_8', 'area_10']}, 'area_8': {'parent': 'area_7', 'children': ['area_9']}, 'area_9': {'parent': 'area_8', 'children': ['area_17', 'area_62', 'area_68', 'area_88']}, 'area_17': {'parent': 'area_9', 'children': ['area_18']}, 'area_18': {'parent': 'area_17', 'children': ['area_19', 'area_77']}, 'area_19': {'parent': 'area_18', 'children': ['area_20', 'area_24', 'area_75', 'area_76']}, 'area_20': {'parent': 'area_19', 'children': ['area_21']}, 'area_21': {'parent': 'area_20', 'children': ['area_22']}, 'area_22': {'parent': 'area_21', 'children': ['area_55']}, 'area_55': {'parent': 'area_22', 'children': []}, 'area_24': {'parent': 'area_19', 'children': ['area_25', 'area_26', 'area_66']}, 'area_25': {'parent': 'area_24', 'children': []}, 'area_26': {'parent': 'area_24', 'children': ['area_27', 'area_64', 'area_71']}, 'area_27': {'parent': 'area_26', 'children': ['area_54']}, 'area_54': {'parent': 'area_27', 'children': ['area_53']}, 'area_53': {'parent': 'area_54', 'children': []}, 'area_64': {'parent': 'area_26', 'children': []}, 'area_71': {'parent': 'area_26', 'children': []}, 'area_66': {'parent': 'area_24', 'children': []}, 'area_75': {'parent': 'area_19', 'children': []}, 'area_76': {'parent': 'area_19', 'children': []}, 'area_77': {'parent': 'area_18', 'children': ['area_78', 'area_80', 'area_81']}, 'area_78': {'parent': 'area_77', 'children': []}, 'area_80': {'parent': 'area_77', 'children': []}, 'area_81': {'parent': 'area_77', 'children': []}, 'area_62': {'parent': 'area_9', 'children': []}, 'area_68': {'parent': 'area_9', 'children': ['area_79']}, 'area_79': {'parent': 'area_68', 'children': []}, 'area_88': {'parent': 'area_9', 'children': ['area_89', 'area_90', 'area_91', 'area_92', 'area_93', 'area_94', 'area_95', 'area_96', 'area_97', 'area_98', 'area_99']}, 'area_89': {'parent': 'area_88', 'children': []}, 'area_90': {'parent': 'area_88', 'children': []}, 'area_91': {'parent': 'area_88', 'children': []}, 'area_92': {'parent': 'area_88', 'children': []}, 'area_93': {'parent': 'area_88', 'children': []}, 'area_94': {'parent': 'area_88', 'children': []}, 'area_95': {'parent': 'area_88', 'children': []}, 'area_96': {'parent': 'area_88', 'children': []}, 'area_97': {'parent': 'area_88', 'children': []}, 'area_98': {'parent': 'area_88', 'children': []}, 'area_99': {'parent': 'area_88', 'children': []}, 'area_10': {'parent': 'area_7', 'children': ['area_11']}, 'area_11': {'parent': 'area_10', 'children': ['area_12']}, 'area_12': {'parent': 'area_11', 'children': ['area_47']}, 'area_47': {'parent': 'area_12', 'children': ['area_46', 'area_49']}, 'area_46': {'parent': 'area_47', 'children': ['area_45', 'area_65']}, 'area_45': {'parent': 'area_46', 'children': ['area_29', 'area_73']}, 'area_29': {'parent': 'area_45', 'children': ['area_28', 'area_33']}, 'area_28': {'parent': 'area_29', 'children': []}, 'area_33': {'parent': 'area_29', 'children': ['area_32', 'area_34', 'area_35']}, 'area_32': {'parent': 'area_33', 'children': ['area_30', 'area_58', 'area_86']}, 'area_30': {'parent': 'area_32', 'children': ['area_31', 'area_63']}, 'area_31': {'parent': 'area_30', 'children': []}, 'area_63': {'parent': 'area_30', 'children': ['area_67', 'area_69', 'area_70', 'area_87']}, 'area_67': {'parent': 'area_63', 'children': []}, 'area_69': {'parent': 'area_63', 'children': []}, 'area_70': {'parent': 'area_63', 'children': []}, 'area_87': {'parent': 'area_63', 'children': []}, 'area_58': {'parent': 'area_32', 'children': ['area_82', 'area_83', 'area_84']}, 'area_82': {'parent': 'area_58', 'children': []}, 'area_83': {'parent': 'area_58', 'children': []}, 'area_84': {'parent': 'area_58', 'children': []}, 'area_86': {'parent': 'area_32', 'children': []}, 'area_34': {'parent': 'area_33', 'children': []}, 'area_35': {'parent': 'area_33', 'children': ['area_36']}, 'area_36': {'parent': 'area_35', 'children': ['area_37']}, 'area_37': {'parent': 'area_36', 'children': ['area_38']}, 'area_38': {'parent': 'area_37', 'children': ['area_59']}, 'area_59': {'parent': 'area_38', 'children': ['area_72']}, 'area_72': {'parent': 'area_59', 'children': []}, 'area_73': {'parent': 'area_45', 'children': []}, 'area_65': {'parent': 'area_46', 'children': []}, 'area_49': {'parent': 'area_47', 'children': ['area_48']}, 'area_48': {'parent': 'area_49', 'children': ['area_85']}, 'area_85': {'parent': 'area_48', 'children': []}}

# for 123 bus system
parent_child_area_dict = {'area_1': {'parent': None, 'children': ['area_2']}, 'area_2': {'parent': 'area_1', 'children': ['area_4', 'area_3']}, 'area_4': {'parent': 'area_2', 'children': ['area_5', 'area_7']}, 'area_5': {'parent': 'area_4', 'children': ['area_6']}, 'area_6': {'parent': 'area_5', 'children': []}, 'area_7': {'parent': 'area_4', 'children': []}, 'area_3': {'parent': 'area_2', 'children': []}}
current_working_dir = os.getcwd()
areas_file_dir = current_working_dir + '/temp/system_data'
result_file_dir = current_working_dir + '/temp/results'
os.makedirs(areas_file_dir, exist_ok=True)
os.makedirs(result_file_dir, exist_ok=True)

area_object_list = {}
for area_index in parent_child_area_dict.keys():
    area_dir = os.path.abspath(areas_file_dir + f"/{area_index}")

    area_object_list[f"{area_index}_o"] = Area(area_index = area_index, area_dir = area_dir, parent_child_dict = parent_child_area_dict)

# for key in area_object_list.keys(): # now area_1_o is object corresponding to area_1
#     key = area_object_list[key]
convergence = False
tolerance = 0.0001
iteration = 0
while convergence is False:
    iteration += 1
    for key in area_object_list.keys():
        print(f"Iteration{iteration} and area {key}")
        parsed_data_path = area_object_list[key].file_dir
        vsub_a = area_object_list[key].substation_Va
        vsub_b = area_object_list[key].substation_Vb
        vsub_c = area_object_list[key].substation_Vc
        base_kV_LL = area_object_list[key].circuit_data_json["basekV_LL_circuit"]
        rm = RestorationBase(parsed_data_path, base_kV_LL=base_kV_LL)
        rm.constraints_base(base_kV_LL=4.16, vmax=1.05,
                            vmin=0.95,
                            psub_max=5000, vsub_a=vsub_a, vsub_b=vsub_b, vsub_c=vsub_c)

        area_object_list[key].network_graph = rm.network_graph # just to take graph information

        # rm.objective_load_only()
        rm.objective_load_and_switching()
        # rm.objective_load_switching_and_der()
        area_object_list[key].solved_model, results = rm.solve_model(solver='gurobi')

    ## updating boundary variables after solving
    for key in area_object_list.keys():
        area_object_list[key].update_boundary_variables_after_opf()

    ## exchange boundary variables
    for key in area_object_list.keys():
        parent_area_index = area_object_list[key].parent
        if parent_area_index is not None:
            parent_area_object = area_object_list[f"{parent_area_index}_o"]
            area_object_list[key].boundary_variables_exchange(parent_area_object)

    ## convergence test
    error_max = 0
    for key in area_object_list.keys():
        error = area_object_list[key].convergence_test()
        if error > error_max:
            error_max = error
    print(error_max)
    if error_max <= tolerance:
        convergence = True


result_saving(result_file_dir,area_object_list)





