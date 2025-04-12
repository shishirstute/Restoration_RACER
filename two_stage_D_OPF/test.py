import pandas as pd
import json
import os
import networkx as nx



current_working_dir = os.getcwd()
system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123

parsed_data_path = current_working_dir + f"/Data/{system_name}"

bus_data = pd.read_csv(os.path.join(parsed_data_path, "bus_data.csv"))
# DERS = pd.read_csv(os.path.join(area_index_data_path, "DERS.csv"))
# load_data = pd.read_csv(os.path.join(area_index_data_path, "load_data.csv"))
# normally_open_components = pd.read_csv(os.path.join(area_index_data_path, "normally_open_components.csv"))
pdelements_data = pd.read_csv(os.path.join(parsed_data_path, "pdelements_data.csv"))
circuit_data_json = json.load(open(os.path.join(parsed_data_path, "circuit_data.json")))

# converting to string from float if available in bus name to deal with error in Lindist
pdelements_data["from_bus"] = pdelements_data["from_bus"].astype(str)
pdelements_data["to_bus"] = pdelements_data["to_bus"].astype(str)
bus_data["name"] = bus_data["name"].astype(str)



G = nx.from_pandas_edgelist(pdelements_data, source = 'from_bus', target = 'to_bus', edge_attr = True)
tree_edge_list = list(nx.dfs_edges(G, source= circuit_data_json["substation"])) # it makes sure that we get from bus in desired format.
for (fr_bus, to_bus) in tree_edge_list:
    pdelements_data.loc[(pdelements_data["from_bus"] == to_bus) & (pdelements_data["to_bus"] == fr_bus),["from_bus","to_bus"]] = pdelements_data.loc[(pdelements_data["from_bus"] == to_bus) & (pdelements_data["to_bus"] == fr_bus), ["to_bus","from_bus"]].values # does only if from bus to bus is misaligned

pdelements_data.to_csv(os.path.join(parsed_data_path, "pdelements_data_modified.csv"), index = False) # saving pdelements data

## now  for network graph data json
G = nx.from_pandas_edgelist( pdelements_data, source = 'from_bus', target = 'to_bus', edge_attr = True,create_using=nx.DiGraph()) # graph creation from pandas pdelements

for index, row in bus_data.iterrows():  # adding attributes to graph
    if pd.Series(index).isin(list(G.nodes)).any(): # just to add attributes of bus present only in pdelements data
        G.add_node(index, basekV = bus_data.loc[index,'basekV'], latitude = bus_data.loc[index,'latitude'], longitude = bus_data.loc[index,'longitude'])


# getting network_tree_data.json
network_tree_data_json = nx.node_link_data(G) # returns json data for area
network_tree_json_object = json.dumps(network_tree_data_json, indent = 4)
with open(parsed_data_path + r"\network_tree_data_modified.json", 'w') as json_file: # saving to json file
    json_file.write(network_tree_json_object)

# getting network_graph_data.json
# its same as network_tree_data.json since I have stored all information in tree
# since in Lindist, data is fetched using index from json, it won't be problem if I add extra other attributes
network_graph_data_json = nx.node_link_data(G.to_undirected())
network_graph_json_object = json.dumps(network_graph_data_json, indent=4)
with open(parsed_data_path + r"\network_graph_data_modified.json", 'w') as json_file: # saving to json file
    json_file.write(network_graph_json_object)
