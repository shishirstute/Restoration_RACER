import networkx as nx
import pandas as pd
import json
import os
import shutil
import numpy as np


class Area:
    def __init__(self, area_index = None, area_dir = None, parent_child_dict = None):

        self.circuit_data_json = json.load(open(os.path.join(area_dir, "circuit_data.json")))
        self.substation_name = self.circuit_data_json["substation"]
        self.parent = parent_child_dict[area_index]["parent"]
        self.children = parent_child_dict[area_index]["children"]
        self.DERS = pd.read_csv(os.path.join(area_dir, "DERS.csv"))
        self.DERS_rating = self.DERS["kW_rated"].sum()
        self.children_buses = [area_index + _ for _ in self.children]
        self.file_dir = area_dir
        self.substation_Va = 1.05
        self.substation_Vb = 1.05
        self.substation_Vc = 1.05
        self.substation_Pa = 0
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

        for _ in self.children_buses:
            # setattr(self,f"{_}_Pa", 0)
            # setattr(self, f"{_}_Pb",0)
            # setattr(self, f"{_}_Pc",0)
            # setattr(self, f"{_}_Qa",0)
            # setattr(self, f"{_}_Qb",0)
            # setattr(self, f"{_}_Qc",0)

            setattr(self, f"{_}_Va",1.05)
            setattr(self, f"{_}_Vb",1.05)
            setattr(self, f"{_}_Vc",1.05)

    def update_boundary_variables_after_opf(self):
        solved_model = self.solved_model
        # solved_model_substation_index = solved_model.node_indices_in_tree[self.substation_name]
        emerging_out_bus_from_substation = list(self.network_graph.neighbors(self.substation_name))
        emerging_out_edge_index_list = []
        for _ in emerging_out_bus_from_substation:
            emerging_out_edge_index_list.append(solved_model.edge_indices_in_tree[(self.substation_name, _)])

        # updating substation power
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

    def boundary_variables_exchange(self,parent_area):
        self_area_load_df = pd.read_csv(os.path.join(self.file_dir,"load_data.csv"))
        parent_area_load_df = pd.read_csv(os.path.join(parent_area.file_dir,"load_data.csv"))
        shared_bus = self.substation_name
        parent_area_load_df.loc[parent_area_load_df["bus"] == shared_bus,["P1","Q1","P2","Q2","P3","Q3"]] = self.substation_Pa,self.substation_Qa,self.substation_Pb,self.substation_Qb,self.substation_Pc,self.substation_Qc
        self.substation_Va = getattr(parent_area,f"{shared_bus}_Va")
        self.substation_Vb = getattr(parent_area, f"{shared_bus}_Vb")
        self.substation_Vc = getattr(parent_area, f"{shared_bus}_Vc")

        # saving load data file
        parent_area_load_df.to_csv(os.path.join(parent_area.file_dir,"load_data.csv"),index=False)


    def convergence_test(self):
        error_V = max(abs(self.substation_Va- self.substation_Va_pre),abs(self.substation_Vb- self.substation_Vb_pre),abs(self.substation_Vc- self.substation_Vc_pre))
        error_P = max(abs(self.substation_Pa- self.substation_Pa_pre),abs(self.substation_Pb- self.substation_Pb_pre),abs(self.substation_Pc- self.substation_Pc_pre))
        error_Q = max(abs(self.substation_Qa - self.substation_Qa_pre), abs(self.substation_Qb - self.substation_Qb_pre), abs(self.substation_Qc - self.substation_Qc_pre))
        error = max(error_V,error_P, error_Q)
        self.substation_Va_pre =  self.substation_Va
        self.substation_Vb_pre =  self.substation_Vb
        self.substation_Vc_pre = self.substation_Vc
        self.substation_Pa_pre = self.substation_Pa
        self.substation_Pb_pre = self.substation_Pb
        self.substation_Pc_pre = self.substation_Pc
        self.substation_Qa_pre = self.substation_Qa
        self.substation_Qb_pre = self.substation_Qb
        self.substation_Qc_pre = self.substation_Qc
        return error



def result_saving(result_dir,area_object_list):
    ''' will save post processing result of voltage and si'''
    os.makedirs(result_dir, exist_ok=True)
    result_df = pd.DataFrame(columns = ["bus name", "si","vi", "Va","Vb","Vc"])
    for key in area_object_list.keys():
        for _ in area_object_list[key].solved_model.node_indices_in_tree.keys():
            bus_result_dict = {"bus name":_, "si":area_object_list[key].solved_model.si[area_object_list[key].solved_model.node_indices_in_tree[_]](),
                               "vi": area_object_list[key].solved_model.vi[area_object_list[key].solved_model.node_indices_in_tree[_]](),
                               "Va":np.sqrt(area_object_list[key].solved_model.Via[area_object_list[key].solved_model.node_indices_in_tree[_]]()),
                               "Vb":np.sqrt(area_object_list[key].solved_model.Vib[area_object_list[key].solved_model.node_indices_in_tree[_]]()),
                               "Vc":np.sqrt(area_object_list[key].solved_model.Vic[area_object_list[key].solved_model.node_indices_in_tree[_]]())}

            result_df = pd.concat([result_df, pd.DataFrame(bus_result_dict, index = [0])], axis = 0, ignore_index = True)

    result_df.to_csv(os.path.join(result_dir,"bus_result.csv"),index=False)







def enapp_preprocessing_for_second_stage(parent_child_area_dict = None):
    ''' based on parent child relationship, this function will create files for given ares file by creating dummy bus and saving them in temp folder.'''

    # this dict will be input to this function
    # dictionary contains parent child relationship between areas
    current_working_dir = os.getcwd()
    # for 9500 nodes
    # parent_child_area_dict = {'area_1': {'parent': None, 'children': ['area_2']}, 'area_2': {'parent': 'area_1', 'children': ['area_3']}, 'area_3': {'parent': 'area_2', 'children': ['area_4', 'area_6']}, 'area_4': {'parent': 'area_3', 'children': ['area_5']}, 'area_5': {'parent': 'area_4', 'children': ['area_13']}, 'area_13': {'parent': 'area_5', 'children': ['area_14', 'area_74']}, 'area_14': {'parent': 'area_13', 'children': ['area_15', 'area_56']}, 'area_15': {'parent': 'area_14', 'children': ['area_16']}, 'area_16': {'parent': 'area_15', 'children': ['area_23', 'area_44']}, 'area_23': {'parent': 'area_16', 'children': ['area_60']}, 'area_60': {'parent': 'area_23', 'children': ['area_61']}, 'area_61': {'parent': 'area_60', 'children': []}, 'area_44': {'parent': 'area_16', 'children': ['area_43']}, 'area_43': {'parent': 'area_44', 'children': ['area_42', 'area_50']}, 'area_42': {'parent': 'area_43', 'children': ['area_41']}, 'area_41': {'parent': 'area_42', 'children': ['area_39']}, 'area_39': {'parent': 'area_41', 'children': ['area_40']}, 'area_40': {'parent': 'area_39', 'children': []}, 'area_50': {'parent': 'area_43', 'children': ['area_51']}, 'area_51': {'parent': 'area_50', 'children': ['area_52']}, 'area_52': {'parent': 'area_51', 'children': []}, 'area_56': {'parent': 'area_14', 'children': ['area_57']}, 'area_57': {'parent': 'area_56', 'children': []}, 'area_74': {'parent': 'area_13', 'children': []}, 'area_6': {'parent': 'area_3', 'children': ['area_7']}, 'area_7': {'parent': 'area_6', 'children': ['area_8', 'area_10']}, 'area_8': {'parent': 'area_7', 'children': ['area_9']}, 'area_9': {'parent': 'area_8', 'children': ['area_17', 'area_62', 'area_68', 'area_88']}, 'area_17': {'parent': 'area_9', 'children': ['area_18']}, 'area_18': {'parent': 'area_17', 'children': ['area_19', 'area_77']}, 'area_19': {'parent': 'area_18', 'children': ['area_20', 'area_24', 'area_75', 'area_76']}, 'area_20': {'parent': 'area_19', 'children': ['area_21']}, 'area_21': {'parent': 'area_20', 'children': ['area_22']}, 'area_22': {'parent': 'area_21', 'children': ['area_55']}, 'area_55': {'parent': 'area_22', 'children': []}, 'area_24': {'parent': 'area_19', 'children': ['area_25', 'area_26', 'area_66']}, 'area_25': {'parent': 'area_24', 'children': []}, 'area_26': {'parent': 'area_24', 'children': ['area_27', 'area_64', 'area_71']}, 'area_27': {'parent': 'area_26', 'children': ['area_54']}, 'area_54': {'parent': 'area_27', 'children': ['area_53']}, 'area_53': {'parent': 'area_54', 'children': []}, 'area_64': {'parent': 'area_26', 'children': []}, 'area_71': {'parent': 'area_26', 'children': []}, 'area_66': {'parent': 'area_24', 'children': []}, 'area_75': {'parent': 'area_19', 'children': []}, 'area_76': {'parent': 'area_19', 'children': []}, 'area_77': {'parent': 'area_18', 'children': ['area_78', 'area_80', 'area_81']}, 'area_78': {'parent': 'area_77', 'children': []}, 'area_80': {'parent': 'area_77', 'children': []}, 'area_81': {'parent': 'area_77', 'children': []}, 'area_62': {'parent': 'area_9', 'children': []}, 'area_68': {'parent': 'area_9', 'children': ['area_79']}, 'area_79': {'parent': 'area_68', 'children': []}, 'area_88': {'parent': 'area_9', 'children': ['area_89', 'area_90', 'area_91', 'area_92', 'area_93', 'area_94', 'area_95', 'area_96', 'area_97', 'area_98', 'area_99']}, 'area_89': {'parent': 'area_88', 'children': []}, 'area_90': {'parent': 'area_88', 'children': []}, 'area_91': {'parent': 'area_88', 'children': []}, 'area_92': {'parent': 'area_88', 'children': []}, 'area_93': {'parent': 'area_88', 'children': []}, 'area_94': {'parent': 'area_88', 'children': []}, 'area_95': {'parent': 'area_88', 'children': []}, 'area_96': {'parent': 'area_88', 'children': []}, 'area_97': {'parent': 'area_88', 'children': []}, 'area_98': {'parent': 'area_88', 'children': []}, 'area_99': {'parent': 'area_88', 'children': []}, 'area_10': {'parent': 'area_7', 'children': ['area_11']}, 'area_11': {'parent': 'area_10', 'children': ['area_12']}, 'area_12': {'parent': 'area_11', 'children': ['area_47']}, 'area_47': {'parent': 'area_12', 'children': ['area_46', 'area_49']}, 'area_46': {'parent': 'area_47', 'children': ['area_45', 'area_65']}, 'area_45': {'parent': 'area_46', 'children': ['area_29', 'area_73']}, 'area_29': {'parent': 'area_45', 'children': ['area_28', 'area_33']}, 'area_28': {'parent': 'area_29', 'children': []}, 'area_33': {'parent': 'area_29', 'children': ['area_32', 'area_34', 'area_35']}, 'area_32': {'parent': 'area_33', 'children': ['area_30', 'area_58', 'area_86']}, 'area_30': {'parent': 'area_32', 'children': ['area_31', 'area_63']}, 'area_31': {'parent': 'area_30', 'children': []}, 'area_63': {'parent': 'area_30', 'children': ['area_67', 'area_69', 'area_70', 'area_87']}, 'area_67': {'parent': 'area_63', 'children': []}, 'area_69': {'parent': 'area_63', 'children': []}, 'area_70': {'parent': 'area_63', 'children': []}, 'area_87': {'parent': 'area_63', 'children': []}, 'area_58': {'parent': 'area_32', 'children': ['area_82', 'area_83', 'area_84']}, 'area_82': {'parent': 'area_58', 'children': []}, 'area_83': {'parent': 'area_58', 'children': []}, 'area_84': {'parent': 'area_58', 'children': []}, 'area_86': {'parent': 'area_32', 'children': []}, 'area_34': {'parent': 'area_33', 'children': []}, 'area_35': {'parent': 'area_33', 'children': ['area_36']}, 'area_36': {'parent': 'area_35', 'children': ['area_37']}, 'area_37': {'parent': 'area_36', 'children': ['area_38']}, 'area_38': {'parent': 'area_37', 'children': ['area_59']}, 'area_59': {'parent': 'area_38', 'children': ['area_72']}, 'area_72': {'parent': 'area_59', 'children': []}, 'area_73': {'parent': 'area_45', 'children': []}, 'area_65': {'parent': 'area_46', 'children': []}, 'area_49': {'parent': 'area_47', 'children': ['area_48']}, 'area_48': {'parent': 'area_49', 'children': ['area_85']}, 'area_85': {'parent': 'area_48', 'children': []}}
    # areas_data_file_path = current_working_dir + "/Network_decomposition/results/parsed_data_9500_der"  # area-decomposed data path
    # original_parsed_data_path = current_working_dir + "/Data/parsed_data_9500_der"  # parsed data file path i.e. original which is not decomposed

    # for 123 bus system
    parent_child_area_dict = {'area_1': {'parent': None, 'children': ['area_2']}, 'area_2': {'parent': 'area_1', 'children': ['area_4', 'area_3']}, 'area_4': {'parent': 'area_2', 'children': ['area_5', 'area_7']}, 'area_5': {'parent': 'area_4', 'children': ['area_6']}, 'area_6': {'parent': 'area_5', 'children': []}, 'area_7': {'parent': 'area_4', 'children': []}, 'area_3': {'parent': 'area_2', 'children': []}}
    areas_data_file_path = current_working_dir + "/Network_decomposition/results/parsed_data_ieee123"
    original_parsed_data_path = current_working_dir + "/Data/parsed_data_ieee123"

    temp_dir = os.path.abspath(current_working_dir + "/temp")  # temporary directcory for temporary purpose

    try:
         shutil.rmtree(temp_dir, onerror= lambda func, path, exc_info: os.chmod(path, 0o777) or func(path))
    except:
        None
    shutil.copytree(areas_data_file_path, os.path.join(temp_dir,"system_data"), dirs_exist_ok= True) # copy entire areas data to this directory

    first_stage_pdelements_df = pd.read_csv(os.path.join(temp_dir,"system_data","first_stage", "pdelements_data.csv")) # first stage grouped areas pd elements data

    non_decomposed_pdelements_df = pd.read_csv(original_parsed_data_path + "\pdelements_data.csv") # pdelements of original non-decomposed pdelements data

    for area_index in parent_child_area_dict.keys(): # iterating over each area
        print(area_index)
        area_index_data_path = os.path.join(temp_dir,"system_data",area_index) # corresponding area file path directory
        # reading data for current area
        bus_data = pd.read_csv(os.path.join(area_index_data_path,"bus_data.csv"))
        # DERS = pd.read_csv(os.path.join(area_index_data_path, "DERS.csv"))
        load_data = pd.read_csv(os.path.join(area_index_data_path, "load_data.csv"))
        # normally_open_components = pd.read_csv(os.path.join(area_index_data_path, "normally_open_components.csv"))
        pdelements_data = pd.read_csv(os.path.join(area_index_data_path, "pdelements_data.csv"))
        circuit_data_json = json.load(open(os.path.join(area_index_data_path, "circuit_data.json")))
        # getting parent and child of current area
        parent_area = parent_child_area_dict[area_index]["parent"]
        # child_areas = parent_child_area_dict[area_index]["children"]

        if parent_area is not None: # if parent area is present , only update data. No need to do iterate over child as it will be automatically covered
            for _ in [parent_area]:
                # read parent area data
                area_index_data_path_p = os.path.join(temp_dir, "system_data", _)
                bus_data_p = pd.read_csv(os.path.join(area_index_data_path_p, "bus_data.csv"))
                load_data_p = pd.read_csv(os.path.join(area_index_data_path_p, "load_data.csv"))
                pdelements_data_p = pd.read_csv(os.path.join(area_index_data_path_p, "pdelements_data.csv"))

                dummy_bus_name = _ + area_index # dummy bus name
                # finding original linking edge name connecting two areas
                linking_line_name = first_stage_pdelements_df[((first_stage_pdelements_df["from_bus"] == _) & (first_stage_pdelements_df["to_bus"] == area_index)) |((first_stage_pdelements_df["from_bus"] == area_index) & (first_stage_pdelements_df["to_bus"] == _))]["name"].values[0]
                # getting from bus and to bus name of linking edge from original data
                from_bus, to_bus = non_decomposed_pdelements_df.loc[non_decomposed_pdelements_df["name"] == linking_line_name,["from_bus", "to_bus"]].values[0]
                if to_bus not in bus_data["name"].astype(str).to_list(): # to make sure that from bus is in parent side and to bus is in child side
                    assert to_bus in bus_data_p["name"].to_list()
                    from_bus, to_bus = to_bus, from_bus # if not change it

                # changing data for parent

                # bus data
                last_row =  bus_data_p.iloc[-1].copy()
                last_row["name"] = dummy_bus_name
                bus_data_p = pd.concat([bus_data_p,pd.DataFrame([last_row])], ignore_index = True)
                bus_data_p.to_csv(os.path.join(area_index_data_path_p, "bus_data.csv"),index = False)

                # load_data
                last_row = load_data_p.iloc[-1].copy()
                last_row["bus"],last_row["P1"],last_row["Q1"],last_row["P2"],last_row["Q2"],last_row["P3"],last_row["Q3"] = dummy_bus_name,0,0,0,0,0,0
                load_data_p = pd.concat([load_data_p, pd.DataFrame([last_row])], ignore_index=True)
                load_data_p.to_csv(os.path.join(area_index_data_path_p, "load_data.csv"),index = False)

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
                last_row["phases"] = {'b','c','a'}
                last_row["is_switch"] = "False"
                last_row["is_open"] = "False"
                last_row["base_kv_LL"] = 12.47
                pdelements_data_p = pd.concat([pdelements_data_p, pd.DataFrame([last_row])], ignore_index=True)
                pdelements_data_p.to_csv(os.path.join(area_index_data_path_p, "pdelements_data.csv"),index = False)

                # changing data for current area

                # bus data
                last_row = bus_data.iloc[-1].copy()
                last_row["name"] = dummy_bus_name
                bus_data = pd.concat([bus_data, pd.DataFrame([last_row])], ignore_index=True)
                bus_data.to_csv(os.path.join(area_index_data_path, "bus_data.csv"), index = False)

                # load_data
                last_row = load_data.iloc[-1].copy()
                last_row["bus"], last_row["P1"], last_row["Q1"], last_row["P2"], last_row["Q2"], last_row["P3"], last_row["Q3"] = dummy_bus_name, 0, 0, 0, 0, 0, 0
                load_data = pd.concat([load_data, pd.DataFrame([last_row])], ignore_index=True)
                load_data.to_csv(os.path.join(area_index_data_path, "load_data.csv"), index = False)

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
                last_row["base_kv_LL"] = 12.47

                pdelements_data = pd.concat([pdelements_data, pd.DataFrame([last_row])], ignore_index=True)
                pdelements_data.to_csv(os.path.join(area_index_data_path, "pdelements_data.csv"), index = False)

                # circuit data json
                circuit_data_json["substation"] = dummy_bus_name  # substation name will be dummpy bus for other areas except area with original substation
                circuit_data_json["basekV_LL_circuit"] = bus_data["basekV"][0]
                json_object = json.dumps(circuit_data_json, indent=4)
                with open(area_index_data_path + r"/circuit_data.json", 'w') as circuit_data_file:
                    circuit_data_file.write(json_object)

    ## if pdelements data in Lindist is not in from to format, power balance ewquation will not be written to all nodes. so, to cope with this, pdelements from bus to bus
    # needs to be formatted accordingly.
    # also generating tree topology and graph topology of updated areas file
    for area_index in parent_child_area_dict.keys():
        area_index_data_path = os.path.join(temp_dir, "system_data", area_index)
        bus_data = pd.read_csv(os.path.join(area_index_data_path, "bus_data.csv"))
        DERS = pd.read_csv(os.path.join(area_index_data_path, "DERS.csv"))
        load_data = pd.read_csv(os.path.join(area_index_data_path, "load_data.csv"))
        normally_open_components = pd.read_csv(os.path.join(area_index_data_path, "normally_open_components.csv"))
        pdelements_data = pd.read_csv(os.path.join(area_index_data_path, "pdelements_data.csv"))
        circuit_data_json = json.load(open(os.path.join(area_index_data_path, "circuit_data.json")))

    # converting to string from float if available in bus name to deal with error in Lindist
        pdelements_data["from_bus"] = pdelements_data["from_bus"].astype(str)
        pdelements_data["to_bus"] = pdelements_data["to_bus"].astype(str)
        bus_data["name"] = bus_data["name"].astype(str)



        G = nx.from_pandas_edgelist(pdelements_data, source = 'from_bus', target = 'to_bus', edge_attr = True)
        tree_edge_list = list(nx.dfs_edges(G, source= circuit_data_json["substation"])) # it makes sure that we get from bus in desired format.
        for (fr_bus, to_bus) in tree_edge_list:
            pdelements_data.loc[(pdelements_data["from_bus"] == to_bus) & (pdelements_data["to_bus"] == fr_bus),["from_bus","to_bus"]] = pdelements_data.loc[(pdelements_data["from_bus"] == to_bus) & (pdelements_data["to_bus"] == fr_bus), ["to_bus","from_bus"]].values

        pdelements_data.to_csv(os.path.join(area_index_data_path, "pdelements_data.csv"), index = False) # saving pdelements data

        ## now  for network graph data json
        G = nx.from_pandas_edgelist( pdelements_data, source = 'from_bus', target = 'to_bus', edge_attr = True,create_using=nx.DiGraph()) # graph creation from pandas pdelements

        for index, row in bus_data.iterrows():  # adding attributes to graph
            if pd.Series(index).isin(list(G.nodes)).any(): # just to add attributes of bus present only in pdeleents data
                G.add_node(index, basekV = bus_data.loc[index,'basekV'], latitude = bus_data.loc[index,'latitude'], longitude = bus_data.loc[index,'longitude'])


        # getting network_tree_data.json
        network_tree_data_json = nx.node_link_data(G) # returns json data for area
        network_tree_json_object = json.dumps(network_tree_data_json, indent = 4)
        with open(area_index_data_path + r"\network_tree_data.json", 'w') as json_file: # saving to json file
            json_file.write(network_tree_json_object)

        # getting network_graph_data.json
        # its same as network_tree_data.json since I have stored all information in tree
        # since in Lindist, data is fetched using index from json, it won't be problem if I add extra other attributes
        network_graph_data_json = nx.node_link_data(G.to_undirected())
        network_graph_json_object = json.dumps(network_graph_data_json, indent=4)
        with open(area_index_data_path + r"\network_graph_data.json", 'w') as json_file: # saving to json file
            json_file.write(network_graph_json_object)

# enapp_preprocessing_for_second_stage()

