from __future__ import annotations
import os
from ldrestoration_fast_test import RestorationBase
from copy import deepcopy
import networkx as nx
import pandas as pd
import shutil
import json
import numpy as np
import matplotlib.pyplot as plt
import time

# calling model from Rafy
from WSU_WVU_link import get_load_considering_PV_CLPU


def faults_line_to_area_mapping(areas_data_file_path, faults_list):
    ''' this function takes failed line from to bus list and returns areas that needs to be isolated
    Basically takes any fault information and return the switch that needs to be opened for fault clearance.'''

    areas_list = pd.read_csv(os.path.join(areas_data_file_path, "first_stage", "bus_data.csv"))["name"].to_list()  # all areas name
    fault_bus_list = [_ for pair in faults_list for _ in pair]  # fault bus name , bus associated with fault directly
    fault_related_area_list = []  # areas containing those fault related buses
    for area in areas_list:
        if set(fault_bus_list).intersection(pd.read_csv(os.path.join(areas_data_file_path, area, "bus_data.csv"))["name"].to_list()):
            fault_related_area_list.append(area)

    faults_area_tuple_pair = []  # tuple of area pair that needs to be isolated from each other to clear fault

    for index, row in pd.read_csv(os.path.join(areas_data_file_path, "first_stage", "pdelements_data.csv")).iterrows():
        if row["from_bus"] in fault_related_area_list or row["to_bus"] in fault_related_area_list:
            if row["is_open"] == False:  # this assumes that no fault occurs at tie switch, correct this later please to make more general
                faults_area_tuple_pair.append((row["from_bus"], row["to_bus"]))

    return faults_area_tuple_pair, fault_related_area_list


def first_stage_restoration(parsed_data_path, faults, temp_result_file_dir, objective_function_index=1, solver_options=None, psub_a_max=5000, psub_b_max=5000, psub_c_max=5000):
    ''' implements the first stage restoration, takes data, fault information and return parent child relation dictionary'''

    rm = RestorationBase(parsed_data_path, faults=faults, base_kV_LL=4.16)  # for baseKv you can put anything since voltage does not matter that much as line are switches

    rm.constraints_base(base_kV_LL=66.4, vmax=1.05, vmin=0.95, \
                        vsub_a=1.05, vsub_b=1.05, vsub_c=1.05, \
                        psub_a_max=psub_a_max, psub_b_max=psub_b_max, psub_c_max=psub_c_max)  # be careful of psubstation maximum value

    if objective_function_index == 1:  # for objective load only, switching optimization is not considered
        rm.objective_load_only()

    elif objective_function_index == 2:  # if want to minimizwe switching operation as well
        rm.objective_load_and_switching()
    else:
        rm.objective_load_switching_and_der()  # same as 2 but with DERS present

    rm_solved, results = rm.solve_model(solver='gurobi', tee=False, solver_options=solver_options)  # solve model

    # all_switch_indices = rm_solved.sectionalizing_switch_indices + rm_solved.tie_switch_indices + rm_solved.virtual_switch_indices

    ## getting virtual switch status information and areas activated with DER
    DERs_area_activated_dict = {}
    for index, row in rm_solved.DERs.iterrows():
        virtual_switch_name = row["name"]
        connected_area = row["connected_bus"]
        from_bus = rm_solved.pdelements.loc[rm_solved.pdelements["name"] == virtual_switch_name]["from_bus"].values[0]
        to_bus = rm_solved.pdelements.loc[rm_solved.pdelements["name"] == virtual_switch_name]["to_bus"].values[0]
        if rm_solved.xij[rm_solved.edge_indices_in_tree[(from_bus, to_bus)]]():
            if connected_area in DERs_area_activated_dict.keys():
                DERs_area_activated_dict[connected_area] += row["kW_rated"]
            else:
                DERs_area_activated_dict[connected_area] = row["kW_rated"]

    ## note graph is made as digraph here to deal with error, double check this . No, this is when you use basis instead of cycle.
    Graph = nx.Graph()  # for making graph of with switch which are closed, i.e. isolated areas will not present in graph Graph
    for edge, index in rm_solved.edge_indices_in_tree.items():
        if rm_solved.xij[index]():  # if closed then add
            Graph.add_edge(*edge)
        else:
            print("open edges", edge)

    # getting status of line and power flow in first stage
    power_dataframe = pd.DataFrame(columns=["line", "Pija", "Pijb", "Pijc", "Qija", "Qijb", "Qijc", "status"])  # just to see power flowing between areas

    for edge, index in rm_solved.edge_indices_in_tree.items():
        power_dataframe.loc[index, "line"] = edge
        power_dataframe.loc[index, "Pija"] = rm_solved.Pija[index]()
        power_dataframe.loc[index, "Pijb"] = rm_solved.Pijb[index]()
        power_dataframe.loc[index, "Pijc"] = rm_solved.Pijc[index]()
        power_dataframe.loc[index, "Qija"] = rm_solved.Qija[index]()
        power_dataframe.loc[index, "Qijb"] = rm_solved.Qijb[index]()
        power_dataframe.loc[index, "Qijc"] = rm_solved.Qijc[index]()
        power_dataframe.loc[index, "Pija"] = rm_solved.Pija[index]()
        power_dataframe.loc[index, "Pijb"] = rm_solved.Pijb[index]()
        power_dataframe.loc[index, "status"] = rm_solved.xij[index]()
    # saving to temporary result directory
    power_dataframe.to_csv(os.path.abspath(temp_result_file_dir + "/line_power_first_stage.csv"), index=False)  # saving result of power flow in first stage

    # Perform DFS starting from node 1
    dfs_tree = nx.dfs_tree(Graph, source="area_1")  # here area_1 is assumed to be main substation, this is assumption, be careful on it.

    # Dictionary to store parent and children
    parent_child_dict = {}
    # Add root node (node 1) manually since it doesn't have a parent
    parent_child_dict["area_1"] = {'parent': None, 'children': list(dfs_tree["area_1"].keys())}

    for child, parent in nx.dfs_predecessors(Graph, source="area_1").items():  # add parent and child of each area which are online
        parent_child_dict[child] = {'parent': parent, 'children': list(dfs_tree[child].keys())}

    parent_child_area_df = pd.DataFrame(parent_child_dict).T

    # current_dir = os.getcwd()
    # file_path_name = os.path.normpath(os.path.join(current_dir + "/result_areas_parent", "area_2_area_3_7820kW_7_virtual_switch_tie_section.csv"))

    # parent_child_area_df.to_csv(file_path_name)

    print("virtual switch status in first stage", list(rm_solved.xij[_]() for _ in rm_solved.virtual_switch_indices))  # virtual switch status

    print("tie switch status in first stage", list(rm_solved.xij[_]() for _ in rm_solved.tie_switch_indices))

    print("number of areas in served", parent_child_area_df.shape[0])

    print("total load served in first stage", rm_solved.restoration_objective())

    return parent_child_dict, DERs_area_activated_dict  # return parent_child relationship


def enapp_preprocessing_for_second_stage(areas_data_file_path, original_parsed_data_path, parent_child_area_dict=None):
    ''' based on parent child relationship, this function will create files for areas by creating dummy bus and saving them in temp folder
        also makes sure that resulting file would be handled by Lindist.'''

    current_working_dir = os.getcwd()
    # for 9500 nodes
    # parent_child_area_dict = {'area_1': {'parent': None, 'children': ['area_2']}, 'area_2': {'parent': 'area_1', 'children': ['area_3']}, 'area_3': {'parent': 'area_2', 'children': ['area_4', 'area_6']}, 'area_4': {'parent': 'area_3', 'children': ['area_5']}, 'area_5': {'parent': 'area_4', 'children': ['area_13']}, 'area_13': {'parent': 'area_5', 'children': ['area_14', 'area_74']}, 'area_14': {'parent': 'area_13', 'children': ['area_15', 'area_56']}, 'area_15': {'parent': 'area_14', 'children': ['area_16']}, 'area_16': {'parent': 'area_15', 'children': ['area_23', 'area_44']}, 'area_23': {'parent': 'area_16', 'children': ['area_60']}, 'area_60': {'parent': 'area_23', 'children': ['area_61']}, 'area_61': {'parent': 'area_60', 'children': []}, 'area_44': {'parent': 'area_16', 'children': ['area_43']}, 'area_43': {'parent': 'area_44', 'children': ['area_42', 'area_50']}, 'area_42': {'parent': 'area_43', 'children': ['area_41']}, 'area_41': {'parent': 'area_42', 'children': ['area_39']}, 'area_39': {'parent': 'area_41', 'children': ['area_40']}, 'area_40': {'parent': 'area_39', 'children': []}, 'area_50': {'parent': 'area_43', 'children': ['area_51']}, 'area_51': {'parent': 'area_50', 'children': ['area_52']}, 'area_52': {'parent': 'area_51', 'children': []}, 'area_56': {'parent': 'area_14', 'children': ['area_57']}, 'area_57': {'parent': 'area_56', 'children': []}, 'area_74': {'parent': 'area_13', 'children': []}, 'area_6': {'parent': 'area_3', 'children': ['area_7']}, 'area_7': {'parent': 'area_6', 'children': ['area_8', 'area_10']}, 'area_8': {'parent': 'area_7', 'children': ['area_9']}, 'area_9': {'parent': 'area_8', 'children': ['area_17', 'area_62', 'area_68', 'area_88']}, 'area_17': {'parent': 'area_9', 'children': ['area_18']}, 'area_18': {'parent': 'area_17', 'children': ['area_19', 'area_77']}, 'area_19': {'parent': 'area_18', 'children': ['area_20', 'area_24', 'area_75', 'area_76']}, 'area_20': {'parent': 'area_19', 'children': ['area_21']}, 'area_21': {'parent': 'area_20', 'children': ['area_22']}, 'area_22': {'parent': 'area_21', 'children': ['area_55']}, 'area_55': {'parent': 'area_22', 'children': []}, 'area_24': {'parent': 'area_19', 'children': ['area_25', 'area_26', 'area_66']}, 'area_25': {'parent': 'area_24', 'children': []}, 'area_26': {'parent': 'area_24', 'children': ['area_27', 'area_64', 'area_71']}, 'area_27': {'parent': 'area_26', 'children': ['area_54']}, 'area_54': {'parent': 'area_27', 'children': ['area_53']}, 'area_53': {'parent': 'area_54', 'children': []}, 'area_64': {'parent': 'area_26', 'children': []}, 'area_71': {'parent': 'area_26', 'children': []}, 'area_66': {'parent': 'area_24', 'children': []}, 'area_75': {'parent': 'area_19', 'children': []}, 'area_76': {'parent': 'area_19', 'children': []}, 'area_77': {'parent': 'area_18', 'children': ['area_78', 'area_80', 'area_81']}, 'area_78': {'parent': 'area_77', 'children': []}, 'area_80': {'parent': 'area_77', 'children': []}, 'area_81': {'parent': 'area_77', 'children': []}, 'area_62': {'parent': 'area_9', 'children': []}, 'area_68': {'parent': 'area_9', 'children': ['area_79']}, 'area_79': {'parent': 'area_68', 'children': []}, 'area_88': {'parent': 'area_9', 'children': ['area_89', 'area_90', 'area_91', 'area_92', 'area_93', 'area_94', 'area_95', 'area_96', 'area_97', 'area_98', 'area_99']}, 'area_89': {'parent': 'area_88', 'children': []}, 'area_90': {'parent': 'area_88', 'children': []}, 'area_91': {'parent': 'area_88', 'children': []}, 'area_92': {'parent': 'area_88', 'children': []}, 'area_93': {'parent': 'area_88', 'children': []}, 'area_94': {'parent': 'area_88', 'children': []}, 'area_95': {'parent': 'area_88', 'children': []}, 'area_96': {'parent': 'area_88', 'children': []}, 'area_97': {'parent': 'area_88', 'children': []}, 'area_98': {'parent': 'area_88', 'children': []}, 'area_99': {'parent': 'area_88', 'children': []}, 'area_10': {'parent': 'area_7', 'children': ['area_11']}, 'area_11': {'parent': 'area_10', 'children': ['area_12']}, 'area_12': {'parent': 'area_11', 'children': ['area_47']}, 'area_47': {'parent': 'area_12', 'children': ['area_46', 'area_49']}, 'area_46': {'parent': 'area_47', 'children': ['area_45', 'area_65']}, 'area_45': {'parent': 'area_46', 'children': ['area_29', 'area_73']}, 'area_29': {'parent': 'area_45', 'children': ['area_28', 'area_33']}, 'area_28': {'parent': 'area_29', 'children': []}, 'area_33': {'parent': 'area_29', 'children': ['area_32', 'area_34', 'area_35']}, 'area_32': {'parent': 'area_33', 'children': ['area_30', 'area_58', 'area_86']}, 'area_30': {'parent': 'area_32', 'children': ['area_31', 'area_63']}, 'area_31': {'parent': 'area_30', 'children': []}, 'area_63': {'parent': 'area_30', 'children': ['area_67', 'area_69', 'area_70', 'area_87']}, 'area_67': {'parent': 'area_63', 'children': []}, 'area_69': {'parent': 'area_63', 'children': []}, 'area_70': {'parent': 'area_63', 'children': []}, 'area_87': {'parent': 'area_63', 'children': []}, 'area_58': {'parent': 'area_32', 'children': ['area_82', 'area_83', 'area_84']}, 'area_82': {'parent': 'area_58', 'children': []}, 'area_83': {'parent': 'area_58', 'children': []}, 'area_84': {'parent': 'area_58', 'children': []}, 'area_86': {'parent': 'area_32', 'children': []}, 'area_34': {'parent': 'area_33', 'children': []}, 'area_35': {'parent': 'area_33', 'children': ['area_36']}, 'area_36': {'parent': 'area_35', 'children': ['area_37']}, 'area_37': {'parent': 'area_36', 'children': ['area_38']}, 'area_38': {'parent': 'area_37', 'children': ['area_59']}, 'area_59': {'parent': 'area_38', 'children': ['area_72']}, 'area_72': {'parent': 'area_59', 'children': []}, 'area_73': {'parent': 'area_45', 'children': []}, 'area_65': {'parent': 'area_46', 'children': []}, 'area_49': {'parent': 'area_47', 'children': ['area_48']}, 'area_48': {'parent': 'area_49', 'children': ['area_85']}, 'area_85': {'parent': 'area_48', 'children': []}}
    # areas_data_file_path = current_working_dir + "/Network_decomposition/results/parsed_data_9500_der"  # area-decomposed data path
    # original_parsed_data_path = current_working_dir + "/Data/parsed_data_9500_der"  # parsed data file path i.e. original which is not decomposed

    # for 123 bus system
    # parent_child_area_dict = {'area_1': {'parent': None, 'children': ['area_2']}, 'area_2': {'parent': 'area_1', 'children': ['area_4', 'area_3']}, 'area_4': {'parent': 'area_2', 'children': ['area_5', 'area_7']}, 'area_5': {'parent': 'area_4', 'children': ['area_6']}, 'area_6': {'parent': 'area_5', 'children': []}, 'area_7': {'parent': 'area_4', 'children': []}, 'area_3': {'parent': 'area_2', 'children': []}}
    # areas_data_file_path = current_working_dir + "/Network_decomposition/results/parsed_data_ieee123"
    # original_parsed_data_path = current_working_dir + "/Data/parsed_data_ieee123"

    temp_dir = os.path.abspath(current_working_dir + "/temp")  # temporary directcory for temporary purpose

    try:
        shutil.rmtree(temp_dir, onerror=lambda func, path, exc_info: os.chmod(path, 0o777) or func(path))  # remove if directory is already present
    except:
        None
    shutil.copytree(areas_data_file_path, os.path.join(temp_dir, "system_data"), dirs_exist_ok=True)  # copy entire areas data to this directory(this directory is inside of temp directory

    first_stage_pdelements_df = pd.read_csv(os.path.join(temp_dir, "system_data", "first_stage", "pdelements_data.csv"))  # first stage grouped areas pd elements data

    non_decomposed_pdelements_df = pd.read_csv(original_parsed_data_path + "\pdelements_data.csv")  # pdelements of original non-decomposed pdelements data

    for area_index in parent_child_area_dict.keys():  # iterating over each area
        # print(area_index)
        area_index_data_path = os.path.join(temp_dir, "system_data", area_index)  # corresponding area file path directory
        # reading data for current area
        bus_data = pd.read_csv(os.path.join(area_index_data_path, "bus_data.csv"))
        # DERS = pd.read_csv(os.path.join(area_index_data_path, "DERS.csv"))
        load_data = pd.read_csv(os.path.join(area_index_data_path, "load_data.csv"))
        # normally_open_components = pd.read_csv(os.path.join(area_index_data_path, "normally_open_components.csv"))
        pdelements_data = pd.read_csv(os.path.join(area_index_data_path, "pdelements_data.csv"))
        circuit_data_json = json.load(open(os.path.join(area_index_data_path, "circuit_data.json")))
        # getting parent and child of current area
        parent_area = parent_child_area_dict[area_index]["parent"]
        # child_areas = parent_child_area_dict[area_index]["children"]

        if parent_area is not None:  # if parent area is present , only update data. No need to do iterate over child as it will be automatically covered
            for _ in [parent_area]:
                # read parent area data
                area_index_data_path_p = os.path.join(temp_dir, "system_data", _)
                bus_data_p = pd.read_csv(os.path.join(area_index_data_path_p, "bus_data.csv"))
                load_data_p = pd.read_csv(os.path.join(area_index_data_path_p, "load_data.csv"))
                pdelements_data_p = pd.read_csv(os.path.join(area_index_data_path_p, "pdelements_data.csv"))

                dummy_bus_name = _ + area_index  # dummy bus name
                # finding original linking edge name connecting two areas
                linking_line_name = first_stage_pdelements_df[((first_stage_pdelements_df["from_bus"] == _) & (first_stage_pdelements_df["to_bus"] == area_index)) | ((first_stage_pdelements_df["from_bus"] == area_index) & (first_stage_pdelements_df["to_bus"] == _))]["name"].values[0]
                # getting from bus and to bus name of linking edge from original data
                from_bus, to_bus = non_decomposed_pdelements_df.loc[non_decomposed_pdelements_df["name"] == linking_line_name, ["from_bus", "to_bus"]].values[0]
                if to_bus not in bus_data["name"].astype(str).to_list():  # to make sure that from bus is in parent side and to bus is in child side
                    assert to_bus in bus_data_p["name"].to_list()
                    from_bus, to_bus = to_bus, from_bus  # if not change it

                # changing data for parent

                # bus data
                last_row = bus_data_p.iloc[-1].copy()
                last_row["name"] = dummy_bus_name
                bus_data_p = pd.concat([bus_data_p, pd.DataFrame([last_row])], ignore_index=True)
                bus_data_p.to_csv(os.path.join(area_index_data_path_p, "bus_data.csv"), index=False)

                # load_data
                last_row = load_data_p.iloc[-1].copy()
                last_row["bus"], last_row["P1"], last_row["Q1"], last_row["P2"], last_row["Q2"], last_row["P3"], last_row["Q3"] = dummy_bus_name, 0, 0, 0, 0, 0, 0
                load_data_p = pd.concat([load_data_p, pd.DataFrame([last_row])], ignore_index=True)
                load_data_p.to_csv(os.path.join(area_index_data_path_p, "load_data.csv"), index=False)

                # pdelements data
                last_row = pd.Series()
                last_row["name"] = from_bus + "_" + dummy_bus_name
                last_row["element"] = "line"
                last_row["line_unit"] = 3
                last_row["z_matrix_real"] = [[0.001, 0.0, 0.0], [0.0, 0.001, 0.0], [0.0, 0.0, 0.001]]
                last_row["z_matrix_imag"] = [[0.001, 0.0, 0.0], [0.0, 0.001, 0.0], [0.0, 0.0, 0.001]]
                last_row["length"] = 0.001
                last_row["from_bus"] = from_bus
                last_row["to_bus"] = dummy_bus_name
                last_row["num_phases"] = 3
                last_row["phases"] = {'b', 'c', 'a'}
                last_row["is_switch"] = "False"
                last_row["is_open"] = "False"
                last_row["base_kv_LL"] = 12.47  # note this, this is assumption, make it generic
                pdelements_data_p = pd.concat([pdelements_data_p, pd.DataFrame([last_row])], ignore_index=True)
                pdelements_data_p.to_csv(os.path.join(area_index_data_path_p, "pdelements_data.csv"), index=False)

                # changing data for current area

                # bus data
                last_row = bus_data.iloc[-1].copy()
                last_row["name"] = dummy_bus_name
                bus_data = pd.concat([bus_data, pd.DataFrame([last_row])], ignore_index=True)
                bus_data.to_csv(os.path.join(area_index_data_path, "bus_data.csv"), index=False)

                # load_data
                last_row = load_data.iloc[-1].copy()
                last_row["bus"], last_row["P1"], last_row["Q1"], last_row["P2"], last_row["Q2"], last_row["P3"], last_row["Q3"] = dummy_bus_name, 0, 0, 0, 0, 0, 0
                load_data = pd.concat([load_data, pd.DataFrame([last_row])], ignore_index=True)
                load_data.to_csv(os.path.join(area_index_data_path, "load_data.csv"), index=False)

                # pdelements data
                last_row = pd.Series()
                last_row["name"] = dummy_bus_name + "_" + to_bus
                last_row["element"] = "line"
                last_row["line_unit"] = 3
                last_row["z_matrix_real"] = [[0.001, 0.0, 0.0], [0.0, 0.001, 0.0], [0.0, 0.0, 0.001]]
                last_row["z_matrix_imag"] = [[0.001, 0.0, 0.0], [0.0, 0.001, 0.0], [0.0, 0.0, 0.001]]
                last_row["length"] = 0.001
                last_row["from_bus"] = dummy_bus_name
                last_row["to_bus"] = to_bus
                last_row["num_phases"] = 3
                last_row["phases"] = {'b', 'c', 'a'}
                last_row["is_switch"] = "False"
                last_row["is_open"] = "False"
                last_row["base_kv_LL"] = 12.47  # this also assumption here

                pdelements_data = pd.concat([pdelements_data, pd.DataFrame([last_row])], ignore_index=True)
                pdelements_data.to_csv(os.path.join(area_index_data_path, "pdelements_data.csv"), index=False)

                # circuit data json
                circuit_data_json["substation"] = dummy_bus_name  # substation name will be dummpy bus for other areas except area with original substation
                circuit_data_json["basekV_LL_circuit"] = bus_data["basekV"][0]
                json_object = json.dumps(circuit_data_json, indent=4)
                with open(area_index_data_path + r"/circuit_data.json", 'w') as circuit_data_file:
                    circuit_data_file.write(json_object)

    ## if pdelements data in Lindist is not in from to format, power balance equation will not be written to all nodes. so, to cope with this, pdelements from bus to bus
    # needs to be formatted accordingly.
    # also generating tree topology and graph topology of updated areas file
    for area_index in parent_child_area_dict.keys():
        area_index_data_path = os.path.join(temp_dir, "system_data", area_index)
        bus_data = pd.read_csv(os.path.join(area_index_data_path, "bus_data.csv"))
        # DERS = pd.read_csv(os.path.join(area_index_data_path, "DERS.csv"))
        # load_data = pd.read_csv(os.path.join(area_index_data_path, "load_data.csv"))
        # normally_open_components = pd.read_csv(os.path.join(area_index_data_path, "normally_open_components.csv"))
        pdelements_data = pd.read_csv(os.path.join(area_index_data_path, "pdelements_data.csv"))
        circuit_data_json = json.load(open(os.path.join(area_index_data_path, "circuit_data.json")))

        # converting to string from float if available in bus name to deal with error in Lindist
        pdelements_data["from_bus"] = pdelements_data["from_bus"].astype(str)
        pdelements_data["to_bus"] = pdelements_data["to_bus"].astype(str)
        bus_data["name"] = bus_data["name"].astype(str)

        G = nx.from_pandas_edgelist(pdelements_data, source='from_bus', target='to_bus', edge_attr=True)
        tree_edge_list = list(nx.dfs_edges(G, source=circuit_data_json["substation"]))  # it makes sure that we get from bus in desired format.
        for (fr_bus, to_bus) in tree_edge_list:
            pdelements_data.loc[(pdelements_data["from_bus"] == to_bus) & (pdelements_data["to_bus"] == fr_bus), ["from_bus", "to_bus"]] = pdelements_data.loc[(pdelements_data["from_bus"] == to_bus) & (pdelements_data["to_bus"] == fr_bus), ["to_bus", "from_bus"]].values  # does only if from bus to bus is misaligned

        pdelements_data.to_csv(os.path.join(area_index_data_path, "pdelements_data.csv"), index=False)  # saving pdelements data

        ## now  for network graph data json
        G = nx.from_pandas_edgelist(pdelements_data, source='from_bus', target='to_bus', edge_attr=True, create_using=nx.DiGraph())  # graph creation from pandas pdelements

        for index, row in bus_data.iterrows():  # adding attributes to graph
            if pd.Series(index).isin(list(G.nodes)).any():  # just to add attributes of bus present only in pdelements data
                G.add_node(index, basekV=bus_data.loc[index, 'basekV'], latitude=bus_data.loc[index, 'latitude'], longitude=bus_data.loc[index, 'longitude'])

        # getting network_tree_data.json
        network_tree_data_json = nx.node_link_data(G)  # returns json data for area
        network_tree_json_object = json.dumps(network_tree_data_json, indent=4)
        with open(area_index_data_path + r"\network_tree_data.json", 'w') as json_file:  # saving to json file
            json_file.write(network_tree_json_object)

        # getting network_graph_data.json
        # its same as network_tree_data.json since I have stored all information in tree
        # since in Lindist, data is fetched using index from json, it won't be problem if I add extra other attributes
        network_graph_data_json = nx.node_link_data(G.to_undirected())
        network_graph_json_object = json.dumps(network_graph_data_json, indent=4)
        with open(area_index_data_path + r"\network_graph_data.json", 'w') as json_file:  # saving to json file
            json_file.write(network_graph_json_object)


class Area:  # area class for each area of second stage
    def __init__(self, area_index=None, area_dir=None, parent_child_dict=None, DERs_area_activated_dict=None):  # area_index is area_1 and soon. area_dir is data path of updated area (i.e. after adding dummy bus based on parent child relation)

        self.circuit_data_json = json.load(open(os.path.join(area_dir, "circuit_data.json")))  # circuit data
        self.substation_name = self.circuit_data_json["substation"]  # substation name for given area
        self.parent = parent_child_dict[area_index]["parent"]  # parent area name
        self.children = parent_child_dict[area_index]["children"]  # childre areas name
        # self.DERS = pd.read_csv(os.path.join(area_dir, "DERS.csv")) # DERS
        # self.DERS_rating = self.DERS["kW_rated"].sum() # DERS total rating of area, useful when island is formed and used as substation limit for this area
        self.children_buses = [area_index + _ for _ in self.children]  # children areas shared buses
        self.file_dir = area_dir  # temporary area directory

        self.grid_formed = True if area_index in DERs_area_activated_dict.keys() else False  # flag whether the given area's DER is activated or not if present
        self.DERS_rating = DERs_area_activated_dict[area_index] if area_index in DERs_area_activated_dict.keys() else 0

        self.substation_Va = 1.03  # substation initialized voltage
        self.substation_Vb = 1.03
        self.substation_Vc = 1.03
        self.substation_Pa = 0  # initialized power at substation injection
        self.substation_Pb = 0
        self.substation_Pc = 0
        self.substation_Qa = 0
        self.substation_Qb = 0
        self.substation_Qc = 0

        # required during convergence test
        self.substation_Va_pre = 10
        self.substation_Vb_pre = 10
        self.substation_Vc_pre = 10
        self.substation_Pa_pre = 1000
        self.substation_Pb_pre = 1000
        self.substation_Pc_pre = 1000
        self.substation_Qa_pre = 1000
        self.substation_Qb_pre = 1000
        self.substation_Qc_pre = 1000

        # other auxiliary variables
        self.solved_model = None
        self.network_graph = None

        # just to visualize the convergence pattern
        self.substation_Va_list = []
        self.substation_Vb_list = []
        self.substation_Vc_list = []
        self.substation_Pa_list = []
        self.substation_Pb_list = []
        self.substation_Pc_list = []
        self.substation_Qa_list = []
        self.substation_Qb_list = []
        self.substation_Qc_list = []

        for _ in self.children_buses:
            # setattr(self,f"{_}_Pa", 0)
            # setattr(self, f"{_}_Pb",0)
            # setattr(self, f"{_}_Pc",0)
            # setattr(self, f"{_}_Qa",0)
            # setattr(self, f"{_}_Qb",0)
            # setattr(self, f"{_}_Qc",0)

            setattr(self, f"{_}_Va", 1.05)  # assigning voltage to shared bus child areas
            setattr(self, f"{_}_Vb", 1.05)
            setattr(self, f"{_}_Vc", 1.05)

    def second_stage_area_solve(self, tee, vmin, vmax, objective_function_index=2):
        ''' will solve for opf for given area'''

        parsed_data_path = self.file_dir  # data path file
        vsub_a = self.substation_Va  # substation voltage for area
        vsub_b = self.substation_Vb
        vsub_c = self.substation_Vc
        base_kV_LL = self.circuit_data_json["basekV_LL_circuit"]  # baseKv

        psub_a_max = 5000
        psub_b_max = 5000
        psub_c_max = 5000
        DER_rating_constr_flag = False  # DER rating constraint won't be enforce if no island is formed.
        DER_p_max = 0  # rating is made to 0.
        if self.grid_formed:  # if self grid is formed, psub_a_ma and b, c can be relaxed as der rating constraint will come into picture.
            DER_p_max = self.DERS_rating
            DER_rating_constr_flag = True

        rm = RestorationBase(parsed_data_path, base_kV_LL=base_kV_LL)  # restoration model
        rm.constraints_base(base_kV_LL=4.16, vmax=vmax, \
                            vmin=vmin, vsub_a=vsub_a, vsub_b=vsub_b, vsub_c=vsub_c, \
                            psub_a_max=psub_a_max, psub_b_max=psub_b_max, psub_c_max=psub_c_max, DER_rating_constr_flag=DER_rating_constr_flag, DER_p_max=DER_p_max)  # constraints building, DERs rating related virtual feeder constraint will be added if
        # DER is activated and corresponding power is also passed

        self.network_graph = rm.network_graph  # just to take graph information
        self.loads = rm.loads  # load information

        # choosing objective function
        if objective_function_index == 1:
            rm.objective_load_only()

        elif objective_function_index == 2:
            rm.objective_load_and_switching()
        else:
            rm.objective_load_switching_and_der()

        self.rm = rm

    def update_boundary_variables_after_opf(self):
        ''' updating shared bus power and voltage information within each area'''

        solved_model = self.solved_model  # getting solved model
        # solved_model_substation_index = solved_model.node_indices_in_tree[self.substation_name]

        # getting total substation power flowing to given area
        emerging_out_bus_from_substation = list(self.network_graph.neighbors(self.substation_name))  # out bus from substation bus
        emerging_out_edge_index_list = []
        for _ in emerging_out_bus_from_substation:
            emerging_out_edge_index_list.append(solved_model.edge_indices_in_tree[(self.substation_name, _)])  # getting out edge index

        # updating substation power i.e. power flowing out from substation for given area
        self.substation_Pa = sum(solved_model.Pija[_]() for _ in emerging_out_edge_index_list)
        self.substation_Pb = sum(solved_model.Pijb[_]() for _ in emerging_out_edge_index_list)
        self.substation_Pc = sum(solved_model.Pijc[_]() for _ in emerging_out_edge_index_list)
        self.substation_Qa = sum(solved_model.Qija[_]() for _ in emerging_out_edge_index_list)
        self.substation_Qb = sum(solved_model.Qijb[_]() for _ in emerging_out_edge_index_list)
        self.substation_Qc = sum(solved_model.Qijc[_]() for _ in emerging_out_edge_index_list)

        # updating child bus voltage
        for _ in self.children_buses:
            solved_model_child_bus_index = solved_model.node_indices_in_tree[_]
            setattr(self, f"{_}_Va", np.sqrt(solved_model.Via[solved_model_child_bus_index]()))
            setattr(self, f"{_}_Vb", np.sqrt(solved_model.Vib[solved_model_child_bus_index]()))
            setattr(self, f"{_}_Vc", np.sqrt(solved_model.Vic[solved_model_child_bus_index]()))

    def boundary_variables_exchange(self, parent_area):
        ''' now updating boundary voltage of given area from its parent area. also updating power of substation from given area to its parent area'''

        # self_area_load_df = pd.read_csv(os.path.join(self.file_dir,"load_data.csv"))
        parent_area_load_df = pd.read_csv(os.path.join(parent_area.file_dir, "load_data.csv"))  # parent area load df
        shared_bus = self.substation_name  # shared bus between given area and parent area
        # updating load information on shared bus of parent area laod dataframe
        parent_area_load_df.loc[parent_area_load_df["bus"] == shared_bus, ["P1", "Q1", "P2", "Q2", "P3", "Q3"]] = self.substation_Pa, self.substation_Qa, self.substation_Pb, self.substation_Qb, self.substation_Pc, self.substation_Qc
        self.substation_Va = getattr(parent_area, f"{shared_bus}_Va")  # updating child area substation voltage from parent area
        self.substation_Vb = getattr(parent_area, f"{shared_bus}_Vb")
        self.substation_Vc = getattr(parent_area, f"{shared_bus}_Vc")
        time.sleep(0.1)  # 0.1 ms sleep to deal with file open/close error

        # saving load data file
        parent_area_load_df.to_csv(os.path.join(parent_area.file_dir, "load_data.csv"), index=False)

    def load_data_update(self, updated_load_data_dict, area_dir, current_time_index):  # for second stage sequential load update i.e. transient one
        ''' updating load data for each area for sdequential load update'''
        load_df = pd.read_csv(os.path.join(area_dir, "load_data.csv"))  # parent area load df
        for bus in load_df["bus"].to_list():
            if "area" not in bus:
                load_df.loc[load_df["bus"] == bus, ["P1", "Q1", "P2", "Q2", "P3", "Q3"]] = updated_load_data_dict[bus]["P1"], updated_load_data_dict[bus]["Q1"], updated_load_data_dict[bus]["P2"], \
                    updated_load_data_dict[bus]["Q2"], updated_load_data_dict[bus]["P3"], updated_load_data_dict[bus]["Q3"]
            elif "area" in bus:
                load_df.loc[load_df["bus"] == bus, ["P1", "Q1", "P2", "Q2", "P3", "Q3"]] = 0, 0, 0, 0, 0, 0
            else:
                raise ValueError("bus name is not in correct format")
                # just for checking
                # load_df.loc[load_df["bus"] == bus, ["P1", "Q1", "P2", "Q2", "P3", "Q3"]] *= (1.5-0.1*current_time_index) # just to check
        # saving load data file
        load_df.to_csv(os.path.join(area_dir, "load_data.csv"), index=False)

    def oscillation_control(self, iteration):
        if iteration >= 5:  # do only after 5 iterations
            if self.substation_Pa_pre > self.substation_Pa:  # if previous value is greater than current value, then chance of oscillation
                self.substation_Pa = self.substation_Pa_pre * 0.5 + self.substation_Pa * 0.5

    def convergence_test(self):
        ''' find maximum error for given area considering subsequence differences in shared variables'''
        error_V = max(abs(self.substation_Va - self.substation_Va_pre), abs(self.substation_Vb - self.substation_Vb_pre), abs(self.substation_Vc - self.substation_Vc_pre))
        error_P = max(abs(self.substation_Pa - self.substation_Pa_pre), abs(self.substation_Pb - self.substation_Pb_pre), abs(self.substation_Pc - self.substation_Pc_pre))
        error_Q = max(abs(self.substation_Qa - self.substation_Qa_pre), abs(self.substation_Qb - self.substation_Qb_pre), abs(self.substation_Qc - self.substation_Qc_pre))
        error = max(error_V, error_P, error_Q)
        error = error_V  # only voltage error convergence considered
        self.substation_Va_pre = self.substation_Va
        self.substation_Vb_pre = self.substation_Vb
        self.substation_Vc_pre = self.substation_Vc
        self.substation_Pa_pre = self.substation_Pa
        self.substation_Pb_pre = self.substation_Pb
        self.substation_Pc_pre = self.substation_Pc
        self.substation_Qa_pre = self.substation_Qa
        self.substation_Qb_pre = self.substation_Qb
        self.substation_Qc_pre = self.substation_Qc
        return error

    def appending_result_to_list(self):
        ''' storing substation voltage, powers wrt iteration'''
        self.substation_Va_list.append(self.substation_Va)
        self.substation_Vb_list.append(self.substation_Vb)
        self.substation_Vc_list.append(self.substation_Vc)
        self.substation_Pa_list.append(self.substation_Pa)
        self.substation_Pb_list.append(self.substation_Pb)
        self.substation_Pc_list.append(self.substation_Pc)
        self.substation_Qa_list.append(self.substation_Qa)
        self.substation_Qb_list.append(self.substation_Qb)
        self.substation_Qc_list.append(self.substation_Qc)


# update first stage laod for each area using values obtained from Rafy
def update_first_stage_area_load(areas_data_file_path, final_load_data_dict):
    ''' update aggregated load in each equal to the final steady state value for first stage restoration '''
    load_df = pd.read_csv(os.path.join(areas_data_file_path, "first_stage", "load_data.csv"))  # first stage laod df
    for area in load_df["bus"].to_list():
        area_bus_list = json.load(open(os.path.join(areas_data_file_path, area, "bus_collection.json")))  # getting list of bus for area
        P1, Q1 = sum(final_load_data_dict[_]["P1"] for _ in area_bus_list), sum(final_load_data_dict[_]["Q1"] for _ in area_bus_list)
        P2, Q2 = sum(final_load_data_dict[_]["P2"] for _ in area_bus_list), sum(final_load_data_dict[_]["Q2"] for _ in area_bus_list)
        P3, Q3 = sum(final_load_data_dict[_]["P3"] for _ in area_bus_list), sum(final_load_data_dict[_]["Q3"] for _ in area_bus_list)
        load_df.loc[load_df["bus"] == area, ["P1", "Q1", "P2", "Q2", "P3", "Q3"]] = P1, Q1, P2, Q2, P3, Q3

    # saving load data file
    load_df.to_csv(os.path.join(areas_data_file_path, "first_stage", "load_data.csv"), index=False)


def result_saving(temp_result_file_dir, area_object_list):
    ''' will save post processing result of voltage and si'''
    # os.makedirs(result_dir, exist_ok=True)
    result_df = pd.DataFrame(columns=["bus name", "si", "vi", "Va", "Vb", "Vc", "Load_served_flag", "total P load"])  # si is load pickup variable, vi is bus energization variable
    for key in area_object_list.keys():
        for _ in area_object_list[key].solved_model.node_indices_in_tree.keys():
            bus_result_dict = {"bus name": _, "si": area_object_list[key].solved_model.si[area_object_list[key].solved_model.node_indices_in_tree[_]](),
                               "vi": area_object_list[key].solved_model.vi[area_object_list[key].solved_model.node_indices_in_tree[_]](),
                               "Va": np.sqrt(area_object_list[key].solved_model.Via[area_object_list[key].solved_model.node_indices_in_tree[_]]()),
                               "Vb": np.sqrt(area_object_list[key].solved_model.Vib[area_object_list[key].solved_model.node_indices_in_tree[_]]()),
                               "Vc": np.sqrt(area_object_list[key].solved_model.Vic[area_object_list[key].solved_model.node_indices_in_tree[_]]()),
                               "Load_served_flag": 0 if area_object_list[key].loads.loc[area_object_list[key].loads["bus"] == _, ["P1", "P2", "P3"]].sum(axis=1).values[0] > 0 and area_object_list[key].loads.loc[area_object_list[key].loads["bus"] == _, ["P1", "P2", "P3"]].sum(axis=1).values[0] * area_object_list[key].solved_model.si[area_object_list[key].solved_model.node_indices_in_tree[_]]() == 0 else 1,
                               "total P load": area_object_list[key].loads.loc[area_object_list[key].loads["bus"] == _, ["P1", "P2", "P3"]].sum(axis=1).values[0]}

            result_df = pd.concat([result_df, pd.DataFrame(bus_result_dict, index=[0])], axis=0, ignore_index=True)

    result_df.to_csv(os.path.join(temp_result_file_dir, "bus_result.csv"), index=False)  # saving result df


def excel_writing_boundary_solutions(area_object_list, temp_result_file_dir):
    with pd.ExcelWriter(os.path.join(temp_result_file_dir, "boundary_variables_iterations.xlsx")) as writer:
        for key in area_object_list.keys():
            df = pd.DataFrame({"Va": area_object_list[key].substation_Va_list, "Vb": area_object_list[key].substation_Vb_list, "Vc": area_object_list[key].substation_Vc_list, "Pa": area_object_list[key].substation_Pa_list,
                               "Pb": area_object_list[key].substation_Pb_list, "Pc": area_object_list[key].substation_Pc_list, "Qa": area_object_list[key].substation_Qa_list,
                               "Qb": area_object_list[key].substation_Qb_list, "Qc": area_object_list[key].substation_Qc_list})
            df.to_excel(writer, sheet_name=area_object_list[key].substation_name)


def voltage_quality_assess(temp_result_file_dir, vmin):
    bus_result = pd.read_csv(os.path.join(temp_result_file_dir, "bus_result.csv"))
    voltage_a = bus_result["Va"].to_list()
    voltage_a = [_ for _ in voltage_a if _ > vmin]  # only greater than vmin bevcause for floating bus. voltage is by default vmin
    voltage_b = bus_result["Vb"].to_list()
    voltage_b = [_ for _ in voltage_b if _ > vmin]
    voltage_c = bus_result["Vc"].to_list()
    voltage_c = [_ for _ in voltage_c if _ > vmin]
    deviation_from_reference = ((sum(abs(np.array(voltage_a) - 1))) + (sum(abs(np.array(voltage_b) - 1))) + (sum(abs(np.array(voltage_c) - 1)))) / (len(voltage_a) + len(voltage_b) + len(voltage_c)) * 100
    return deviation_from_reference


def track_pick_up_load(area_object_list):
    ''' will store pick up load if picked up in previous restoration step'''
    pick_up_variable_dict = {}  # {area_index:{bus_index: binary}}
    all_bus_index_pick_up_status_dict = {}  # required for Rafy's input, {bus_index: status}
    for key in area_object_list.keys():
        # area_index = key.rstrip("_o") # area index
        area_index = key
        pick_up_variable_dict[area_index] = {}
        for _ in area_object_list[key].solved_model.node_indices_in_tree.keys():
            if "area" not in _:
                binary_pick_up = area_object_list[key].solved_model.si[area_object_list[key].solved_model.node_indices_in_tree[_]]()
                if binary_pick_up == 1:
                    pick_up_variable_dict[area_index][_] = binary_pick_up
                all_bus_index_pick_up_status_dict[_] = binary_pick_up  # required for Rafy's input, where index is bus name.

    return pick_up_variable_dict, all_bus_index_pick_up_status_dict


def get_outage_restoration_time_index(bus_index_outage_restore_dict, all_bus_index_pick_up_status_dict, current_time_index):
    ''' gives outage and restored time index based on previous value and current restoration results'''
    for bus_index in all_bus_index_pick_up_status_dict.keys():
        if all_bus_index_pick_up_status_dict[bus_index] == 0:
            if bus_index_outage_restore_dict[bus_index]["restored_time_index"] == 0:
                outage_time_index = bus_index_outage_restore_dict[bus_index]["outage_time_index"]
                restoration_time_index = 0
            else:
                outage_time_index = current_time_index
                restoration_time_index = 0
        else:
            outage_time_index = bus_index_outage_restore_dict[bus_index]["outage_time_index"]

            if bus_index_outage_restore_dict[bus_index]["outage_time_index"] == 0 and bus_index_outage_restore_dict[bus_index]["restored_time_index"] == 0:
                restoration_time_index = 0
            elif bus_index_outage_restore_dict[bus_index]["outage_time_index"] > 0 and bus_index_outage_restore_dict[bus_index]["restored_time_index"] == 0:
                restoration_time_index = current_time_index
            else:
                restoration_time_index = bus_index_outage_restore_dict[bus_index]["restored_time_index"]
        bus_index_outage_restore_dict[bus_index]["outage_time_index"] = outage_time_index
        bus_index_outage_restore_dict[bus_index]["restored_time_index"] = restoration_time_index
    return bus_index_outage_restore_dict  # returning updated load data dict


def calculate_restored_load(area_object_list, pick_up_variable_dict):
    ''' calculate load restored in each restoration step'''
    restored_load = []
    for key in area_object_list.keys():  # iteration over areas
        load = 0

        # for bus_id in pick_up_variable_dict[key].keys(): # iteation over buses picked up
        #     pyomo_id = area_object_list[key].rm.model.node_indices_in_tree[bus_id]
        #     load += area_object_list[key].rm.model.active_demand_each_node[pyomo_id] * pick_up_variable_dict[key][bus_id]
        # load present in given bus of given area restored

        # just for debugging
        for pyomo_id in area_object_list[key].rm.model.node_indices_in_tree.values():
            bus_id = next((key for key, val in area_object_list[key].rm.model.node_indices_in_tree.items() if val == pyomo_id), None)
            if "area" in bus_id:
                continue
            elif bus_id in pick_up_variable_dict[key].keys():
                load += area_object_list[key].rm.model.active_demand_each_node[pyomo_id] * pick_up_variable_dict[key][bus_id]
            elif area_object_list[key].rm.model.active_demand_each_node[pyomo_id] > 0 and bus_id not in pick_up_variable_dict[key].keys():
                print(f"bus id not picked up {bus_id} with load {area_object_list[key].rm.model.active_demand_each_node[pyomo_id]}")
        restored_load.append(load)

    return sum(restored_load)


def fix_restored_previous_load(rm, pick_up_variable_dict):
    ''' fixing pick up load in previous iteration'''
    model = rm.model
    for _ in pick_up_variable_dict.keys():
        bus_index_pyomo = model.node_indices_in_tree[_]
        if pick_up_variable_dict[_] == 1:
            model.si[bus_index_pyomo].fix(1)
    rm.model = model
    return rm


def initialize_bus_index_outage_restore_dict(area_object_list, areas_data_file_path, outaged_area_list=None, current_time_index=None):
    bus_index_outage_restore_dict = {}
    for area_index in area_object_list.keys():
        area_dir = os.path.abspath(areas_data_file_path + f"/{area_index}".rstrip("_o"))
        load_df = pd.read_csv(os.path.join(area_dir, "load_data.csv"))  # area load df
        load_df["bus"] = load_df["bus"].astype(str)  # converting to string
        if f"/{area_index}".rstrip("_o") in outaged_area_list:
            for bus in load_df["bus"].to_list():
                bus_index_outage_restore_dict[bus] = {"outage_time_index": current_time_index, "restored_time_index": 0}  # load is off
        else:
            for bus in load_df["bus"].to_list():
                bus_index_outage_restore_dict[bus] = {"outage_time_index": 1, "restored_time_index": 0}  # no outage happen, load is on

    return bus_index_outage_restore_dict  # returning updated load data dict


def get_load_from_WVU(area_object_list, areas_data_file_path, bus_index_outage_restore_dict, current_time_index):
    ''' returns a dictionary of bus:load value'''
    updated_load_data_dict = {}
    for area_index in area_object_list.keys():
        area_dir = os.path.abspath(areas_data_file_path + f"/{area_index}".rstrip("_o"))
        load_df = pd.read_csv(os.path.join(area_dir, "load_data.csv"))  # area load df
        load_df["bus"] = load_df["bus"].astype(str)  # converting to string
        for bus in load_df["bus"].to_list():
            bus_dict = {}
            bus_dict[bus] = {}  # just to align with rafy's input
            bus_dict[bus]["P1"] = load_df.loc[load_df["bus"] == bus, ["P1"]].values[0][0]
            bus_dict[bus]["Q1"] = load_df.loc[load_df["bus"] == bus, ["Q1"]].values[0][0]
            bus_dict[bus]["P2"] = load_df.loc[load_df["bus"] == bus, ["P2"]].values[0][0]
            bus_dict[bus]["Q2"] = load_df.loc[load_df["bus"] == bus, ["Q2"]].values[0][0]
            bus_dict[bus]["P3"] = load_df.loc[load_df["bus"] == bus, ["P3"]].values[0][0]
            bus_dict[bus]["Q3"] = load_df.loc[load_df["bus"] == bus, ["Q3"]].values[0][0]

            if (bus_dict[bus]["P1"] + bus_dict[bus]["P2"] + bus_dict[bus]["P3"]) == 0:
                Q_P_relation = 0
            else:
                Q_P_relation = (bus_dict[bus]["Q1"] + bus_dict[bus]["Q2"] + bus_dict[bus]["Q3"]) / (bus_dict[bus]["P1"] + bus_dict[bus]["P2"] + bus_dict[bus]["P3"])

            outage_start = bus_index_outage_restore_dict[bus]["outage_time_index"]  # outage start time index
            restoration_end = bus_index_outage_restore_dict[bus]["restored_time_index"]  # restoration end time index

            # call WVU model here by passing this to Rafy's Pv estimation model
            # {'Bus': 'L3252336', 'P1': 4.0, 'Q1': 0, 'P2': 8.0, 'Q2': 0, 'P3': 9.0, 'Q3': 0}
            estimated_load_dict = get_load_considering_PV_CLPU(t_index=current_time_index, outage_start=outage_start, restoration_end=restoration_end, bus_snapshot=bus_dict)
            updated_load_data_dict[bus] = {}
            if bus_dict[bus]["P1"] == 0:
                updated_load_data_dict[bus]["P1"] = 0
            else:
                updated_load_data_dict[bus]["P1"] = estimated_load_dict["P1"]
            if bus_dict[bus]["P2"] == 0:
                updated_load_data_dict[bus]["P2"] = 0
            else:
                updated_load_data_dict[bus]["P2"] = estimated_load_dict["P2"]
            if bus_dict[bus]["P3"] == 0:
                updated_load_data_dict[bus]["P3"] = 0
            else:
                updated_load_data_dict[bus]["P3"] = estimated_load_dict["P3"]
            updated_load_data_dict[bus]["Q1"] = estimated_load_dict["P1"] * Q_P_relation
            updated_load_data_dict[bus]["Q2"] = estimated_load_dict["P2"] * Q_P_relation
            updated_load_data_dict[bus]["Q3"] = estimated_load_dict["P3"] * Q_P_relation
    return updated_load_data_dict  # returning updated load data dict


def plot_voltage_quality(voltage_quality_measure_list):
    ''' plots voltage measure quality wrt iteration'''
    plt.figure(figsize=(7, 4))
    plt.plot(voltage_quality_measure_list)
    plt.xlabel("#discrete time steps")
    plt.ylabel("voltage quality measure")
    plt.show()


def plot_power_restored(restored_load_list):
    ''' plots restored load wrt iteration'''
    plt.figure(figsize=(7, 4))
    plt.plot(restored_load_list)
    plt.xlabel("#discrete time steps")
    plt.ylabel("restored load")
    plt.show()