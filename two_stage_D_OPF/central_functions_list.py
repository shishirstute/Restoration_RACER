import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt

from WSU_WVU_link import get_load_considering_PV_CLPU

def total_load_served_calculation(rm, rm_solved):
    ''' will calculate the total laod restored'''
    substation_index = rm.node_indices_in_tree[rm.circuit_data["substation"]]

    nodes_emerge_out_from_substation = list(rm.network_graph.neighbors(rm.circuit_data["substation"]))
    edge_index_list_out_from_substation = []
    for _ in  nodes_emerge_out_from_substation:
        try:
            edge_index_list_out_from_substation.append(rm.edge_indices_in_tree[(rm.circuit_data["substation"], _)])
        except:
            edge_index_list_out_from_substation.append(_, rm.edge_indices_in_tree[(rm.circuit_data["substation"])])

    total_load_served = 0
    for edge_index in edge_index_list_out_from_substation:
            total_load_served += rm_solved.Pija[edge_index]() + rm_solved.Pijb[edge_index]() + rm_solved.Pijc[edge_index]()
    return total_load_served


def initialize_bus_index_outage_restore_dict(parsed_data_path, outaged_bus_list = None, current_time_index = None):
    ''' initialize the bus index outage restore dict required for Rafy's inpout.'''

    bus_index_outage_restore_dict = {}

    load_df = pd.read_csv(os.path.join(parsed_data_path, "load_data.csv"))  # area load df
    load_df["bus"] = load_df["bus"].astype(str)  # converting to string

    for bus in load_df["bus"].to_list():
        if bus in outaged_bus_list:
            bus_index_outage_restore_dict[bus] = {"outage_time_index": current_time_index, "restored_time_index": 0} # load is off
    else:
        for bus in load_df["bus"].to_list():
            bus_index_outage_restore_dict[bus] = {"outage_time_index": 40, "restored_time_index": 0} # no outage happen, load is on

    return bus_index_outage_restore_dict # returning updated load data dict


def get_load_from_WVU(parsed_data_path, bus_index_outage_restore_dict, current_time_index):
    ''' returns a dictionary of bus:load value'''
    updated_load_data_dict = {}
    original_load_data_dict = {} # actual net original load yto be used to get total restored load later for post processing

    load_df = pd.read_csv(os.path.join(parsed_data_path, "load_data.csv"))  #area load df
    load_df["bus"] = load_df["bus"].astype(str) # converting to string
    for bus in load_df["bus"].to_list():
        bus_dict = {}
        bus_dict[bus] = {} # just to align with rafy's input
        bus_dict[bus]["P1"] = load_df.loc[load_df["bus"] == bus, ["P1"]].values[0][0]
        bus_dict[bus]["Q1"] = load_df.loc[load_df["bus"] == bus, ["Q1"]].values[0][0]
        bus_dict[bus]["P2"] = load_df.loc[load_df["bus"] == bus, ["P2"]].values[0][0]
        bus_dict[bus]["Q2"] = load_df.loc[load_df["bus"] == bus, ["Q2"]].values[0][0]
        bus_dict[bus]["P3"] = load_df.loc[load_df["bus"] == bus, ["P3"]].values[0][0]
        bus_dict[bus]["Q3"] = load_df.loc[load_df["bus"] == bus, ["Q3"]].values[0][0]
        original_load_data_dict[bus] = bus_dict[bus] # original load data dict

        if (bus_dict[bus]["P1"]+ bus_dict[bus]["P2"] + bus_dict[bus]["P3"]) == 0:
            Q_P_relation = 0
        else:
            Q_P_relation = (bus_dict[bus]["Q1"] + bus_dict[bus]["Q2"] + bus_dict[bus]["Q3"]) / (bus_dict[bus]["P1"]+ bus_dict[bus]["P2"] + bus_dict[bus]["P3"])


        outage_start = bus_index_outage_restore_dict[bus]["outage_time_index"] # outage start time index
        restoration_end = bus_index_outage_restore_dict[bus]["restored_time_index"] # restoration end time index

        # call WVU model here by passing this to Rafy's Pv estimation model
        #{'Bus': 'L3252336', 'P1': 4.0, 'Q1': 0, 'P2': 8.0, 'Q2': 0, 'P3': 9.0, 'Q3': 0}
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
    return updated_load_data_dict, original_load_data_dict # returning updated load data dict


def load_data_update(updated_load_data_dict, temp_parsed_data_path, current_time_index): # for second stage sequential load update i.e. transient one
    ''' updating load data for each area for sdequential load update'''
    load_df = pd.read_csv(os.path.join(temp_parsed_data_path, "load_data.csv"))  # load df
    for bus in load_df["bus"].to_list():
        load_df.loc[load_df["bus"] == bus, ["P1", "Q1", "P2", "Q2", "P3", "Q3"]] = updated_load_data_dict[bus]["P1"], updated_load_data_dict[bus]["Q1"], updated_load_data_dict[bus]["P2"],\
            updated_load_data_dict[bus]["Q2"], updated_load_data_dict[bus]["P3"], updated_load_data_dict[bus]["Q3"]
            # just for checking
            # load_df.loc[load_df["bus"] == bus, ["P1", "Q1", "P2", "Q2", "P3", "Q3"]] *= (1.5-0.1*current_time_index) # just to check
    # saving load data file
    load_df.to_csv(os.path.join(temp_parsed_data_path, "load_data.csv"), index=False)

def fix_restored_previous_load(rm,  pick_up_variable_dict):
    ''' fixing pick up load in previous iteration'''
    model = rm.model
    for _ in  pick_up_variable_dict.keys():
        bus_index_pyomo = model.node_indices_in_tree[_]
        if pick_up_variable_dict[_] == 1:
            model.si[bus_index_pyomo].fix(1)
    rm.model = model
    return rm


def track_pick_up_load(rm_solved):
    ''' will store pick up load if picked up in previous restoration step'''
    pick_up_variable_dict = {} # {area_index:{bus_index: binary}}
    all_bus_index_pick_up_status_dict = {} #required for Rafy's input, {bus_index: status}

    for _ in rm_solved.node_indices_in_tree.keys():
        binary_pick_up = rm_solved.si[rm_solved.node_indices_in_tree[_]]()
        if binary_pick_up == 1:
            pick_up_variable_dict[_]= binary_pick_up
        all_bus_index_pick_up_status_dict[_] = binary_pick_up # required for Rafy's input, where index is bus name.

    return pick_up_variable_dict, all_bus_index_pick_up_status_dict


def get_outage_restoration_time_index(bus_index_outage_restore_dict,all_bus_index_pick_up_status_dict, current_time_index):
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
    return bus_index_outage_restore_dict # returning updated load data dict



def result_saving(temp_central_result_dir,rm, rm_solved):
    ''' will save post processing result of voltage and si'''
    # os.makedirs(result_dir, exist_ok=True)
    result_df = pd.DataFrame(columns = ["bus name", "si","vi", "Va","Vb","Vc","Load_served_flag","total P load"]) # si is load pickup variable, vi is bus energization variable

    for _ in rm_solved.node_indices_in_tree.keys():
        bus_result_dict = {"bus name":_, "si":rm_solved.si[rm_solved.node_indices_in_tree[_]](),
                           "vi": rm_solved.vi[rm_solved.node_indices_in_tree[_]](),
                           "Va":np.sqrt(rm_solved.Via[rm_solved.node_indices_in_tree[_]]()),
                           "Vb":np.sqrt(rm_solved.Vib[rm_solved.node_indices_in_tree[_]]()),
                           "Vc":np.sqrt(rm_solved.Vic[rm_solved.node_indices_in_tree[_]]()),
                           "Load_served_flag":  0 if rm.loads.loc[rm.loads["bus"] == _,["P1","P2","P3"]].sum(axis = 1).values[0] > 0 and rm.loads.loc[rm.loads["bus"] == _,["P1","P2","P3"]].sum(axis = 1).values[0]*rm_solved.si[rm_solved.node_indices_in_tree[_]]() == 0 else 1,
                           "total P load":rm.loads.loc[rm.loads["bus"] == _,["P1","P2","P3"]].sum(axis = 1).values[0]}

        result_df = pd.concat([result_df, pd.DataFrame(bus_result_dict, index = [0])], axis = 0, ignore_index = True)

    result_df.to_csv(os.path.join(temp_central_result_dir,"bus_result.csv"),index=False) # saving result df


def voltage_quality_assess(temp_central_result_dir, vmin, vmax):
    bus_result = pd.read_csv(os.path.join(temp_central_result_dir, "bus_result.csv"))
    voltage_a = bus_result["Va"].to_list()
    voltage_a = [_ for _ in voltage_a if _ > vmin] # only greater than vmin bevcause for floating bus. voltage is by default vmin
    voltage_b = bus_result["Vb"].to_list()
    voltage_b = [_ for _ in voltage_b if _ > vmin]
    voltage_c = bus_result["Vc"].to_list()
    voltage_c = [_ for _ in voltage_c if _ > vmin]
    deviation_from_reference = ((sum(abs(np.array(voltage_a) - 1))) + (sum(abs(np.array(voltage_b) - 1))) + (sum(abs(np.array(voltage_c) - 1))))/(len(voltage_a) + len(voltage_b) + len(voltage_c))*100
    return deviation_from_reference

def voltage_quality_assess_number_nodes_violate(temp_central_result_dir, vmin, vmax):
    bus_result = pd.read_csv(os.path.join(temp_central_result_dir, "bus_result.csv"))
    voltage_a = bus_result["Va"].to_list()
    voltage_a = [_ for _ in voltage_a if _ > vmin] # only greater than vmin bevcause for floating bus. voltage is by default vmin
    voltage_b = bus_result["Vb"].to_list()
    voltage_b = [_ for _ in voltage_b if _ > vmin]
    voltage_c = bus_result["Vc"].to_list()
    voltage_c = [_ for _ in voltage_c if _ > vmin]
    violated_voltage_a = [_ for _ in voltage_a if _ < 0.95 or _ >1.05]
    violated_voltage_b = [_ for _ in voltage_b if _ < 0.95 or _ > 1.05]
    violated_voltage_c = [_ for _ in voltage_c if _ < 0.95 or _ > 1.05]
    total_nodes_violated = len(violated_voltage_a) + len(violated_voltage_b) + len(violated_voltage_c)
    total_nodes_present = len(voltage_a) + len(voltage_b) + len(voltage_c)
    return total_nodes_violated, total_nodes_present


def calculate_restored_load(rm_solved, pick_up_variable_dict, original_load_data_dict):
    ''' calculate load restored in each restoration step'''
    restored_load = []

    load_without_CLPU = 0
    load_with_CLPU = 0

    # for bus_id in pick_up_variable_dict[key].keys(): # iteation over buses picked up
    #     pyomo_id = area_object_list[key].rm.model.node_indices_in_tree[bus_id]
    #     load += area_object_list[key].rm.model.active_demand_each_node[pyomo_id] * pick_up_variable_dict[key][bus_id]
    # load present in given bus of given area restored

    # just for debugging
    for pyomo_id in rm_solved.node_indices_in_tree.values():
        bus_id = next((key for key, val in rm_solved.node_indices_in_tree.items() if val == pyomo_id), None) # real bus id
        if bus_id in pick_up_variable_dict.keys():
            # original means from your base file obrained, no chnage in load
            load_without_CLPU += (original_load_data_dict[bus_id]["P1"] + original_load_data_dict[bus_id]["P2"] + original_load_data_dict[bus_id]["P3"]) * pick_up_variable_dict[bus_id]
            load_with_CLPU += (rm_solved.P1[pyomo_id]() +rm_solved.P2[pyomo_id]() + rm_solved.P3[pyomo_id]()) * pick_up_variable_dict[bus_id]
        # in model.P1, it is what we are taking as load. i.e. CLPU is reflected in this value
        elif (rm_solved.P1[pyomo_id]() +rm_solved.P2[pyomo_id]() + rm_solved.P3[pyomo_id]()  > 0) and (bus_id not in pick_up_variable_dict.keys()):
            # print(f"bus id not picked up {bus_id} with load {rm_solved.P1[pyomo_id]() +rm_solved.P2[pyomo_id]() + rm_solved.P3[pyomo_id]()}" )
            pass

    return load_without_CLPU, load_with_CLPU


def plot_power_restored( restored_load_list, title = None):
    ''' plots restored load wrt iteration'''
    plt.figure(figsize=(6, 4))
    plt.plot(restored_load_list)
    plt.xlabel("load restoration steps")
    plt.ylabel("restored load (kW)")
    plt.title(title)
    plt.tight_layout()
    plt.show()