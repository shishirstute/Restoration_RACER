from __future__ import annotations
import os
from ldrestoration import RestorationBase
from copy import deepcopy
import networkx as nx
import pandas as pd


# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_9500_der"
parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage"
# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_ieee123"  # for 123 bus system
# faults = [("area_1","area_2"),("area_2","area_3"),("area_3","area_4"),("area_4","area_5"),("area_3","area_6"),("area_8","area_9"),("area_5","area_13"),("area_30","area_31")]
# faults = [("area_2","area_3")]
faults = []
rm = RestorationBase(parsed_data_path, faults = faults, base_kV_LL=4.16)

rm.constraints_base(base_kV_LL=4.16,vmax=1.05,
                                        vmin=0.95,
                                       psub_max=5000)

# rm.objective_load_only()
# rm.objective_load_and_switching()
rm.objective_load_switching_and_der()

rm_solved, results = rm.solve_model(solver='gurobi',solver_options = {"mipgap":0.005})

all_switch_indices = rm_solved.sectionalizing_switch_indices + rm_solved.tie_switch_indices + rm_solved.virtual_switch_indices


Graph = nx.Graph()
for edge,index in rm_solved.edge_indices_in_tree.items():
    if rm_solved.xij[index]():
        Graph.add_edge(*edge)
    else:
        print("open edges", edge)

# getting status of line
power_dataframe = pd.DataFrame(columns = ["line","Pija","Pijb","Pijc","Qija","Qijb","Qijc","status"])

for edge,index in rm_solved.edge_indices_in_tree.items():
    power_dataframe.loc[index,"line"] = edge
    power_dataframe.loc[index,"Pija"] = rm_solved.Pija[index]()
    power_dataframe.loc[index, "Pijb"] = rm_solved.Pijb[index]()
    power_dataframe.loc[index, "Pijc"] = rm_solved.Pijc[index]()
    power_dataframe.loc[index, "Qija"] = rm_solved.Qija[index]()
    power_dataframe.loc[index, "Qijb"] = rm_solved.Qijb[index]()
    power_dataframe.loc[index, "Qijc"] = rm_solved.Qijc[index]()
    power_dataframe.loc[index, "Pija"] = rm_solved.Pija[index]()
    power_dataframe.loc[index, "Pijb"] = rm_solved.Pijb[index]()
    power_dataframe.loc[index, "status"] = rm_solved.xij[index]()

# Perform DFS starting from node 1
dfs_tree = nx.dfs_tree(Graph, source="area_1")

# Dictionary to store parent and children
node_relationships = {}
# Add root node (node 1) manually since it doesn't have a parent
node_relationships["area_1"] = {'parent': None, 'children': list(dfs_tree["area_1"].keys())}

for child, parent in nx.dfs_predecessors(Graph, source="area_1").items():
    node_relationships[child] = {'parent': parent, 'children': list(dfs_tree[child].keys())}

parent_child_area_df = pd.DataFrame(node_relationships).T

current_dir = os.getcwd()
file_path_name = os.path.normpath(os.path.join(current_dir+"/result_areas_parent","area_2_area_3_7820kW_7_virtual_switch_tie_section.csv"))

# parent_child_area_df.to_csv(file_path_name)

print("virtual switch status",list(rm_solved.xij[_]() for _ in rm_solved.virtual_switch_indices)) # virtual switch status

print("tie switch status",list(rm_solved.xij[_]() for _ in rm_solved.tie_switch_indices))

print("number of areas in served",parent_child_area_df.shape[0])

print("total load served",rm_solved.restoration_objective())

######## for d opf #####


1+1