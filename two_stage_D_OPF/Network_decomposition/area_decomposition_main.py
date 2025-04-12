import os
import pandas as pd
import networkx as nx
import re
import json
from copy import deepcopy

test_case_name = "parsed_data_9500_der" #"parsed_data_ieee123"
current_dir = os.path.dirname(__file__)

bus_data_path = current_dir + f"\\..\\Data\\{test_case_name}\\bus_data.csv" # bus data path
bus_data_path = os.path.abspath(bus_data_path)
branch_data_path = current_dir + f"\\..\\Data\\{test_case_name}\\pdelements_data.csv" # branch data path
branch_data_path = os.path.abspath(branch_data_path)
load_data_path = current_dir + f"\\..\\Data\\{test_case_name}\\load_data.csv" # load_data_path
load_data_path = os.path.abspath(load_data_path) # load data
DERS_data_path = current_dir + f"\\..\\Data\\{test_case_name}\\DERS.csv" # DERS file path
DERS_data_path = os.path.abspath(DERS_data_path)
transformer_data_path = current_dir + f"\\..\\Data\\{test_case_name}\\transformer_data.csv"
normally_open_components_file_path = current_dir + f"\\..\\Data\\{test_case_name}\\normally_open_components.csv"
circuit_data_json_file_path = current_dir + f"\\..\\Data\\{test_case_name}\\circuit_data.json"

bus_data_df = pd.read_csv(bus_data_path)
branch_data_df = pd.read_csv(branch_data_path)
load_data_df = pd.read_csv(load_data_path).fillna(" ")
DERS_data_df = pd.read_csv(DERS_data_path).fillna(" ") # loads DERS data
transformer_data_df = pd.read_csv(transformer_data_path).fillna(" ") # loads transformer data
normally_open_components_df = pd.read_csv(normally_open_components_file_path).fillna(" ")
circuit_data_json = json.load(open(circuit_data_json_file_path))

## making bus name, from bus, to bus as string, as Lindist will produce error with assuming floating sometime instead of integer bus
bus_data_df["name"] = bus_data_df["name"].astype(str)
branch_data_df["name"] = branch_data_df["name"].astype(str)
branch_data_df["from_bus"] = branch_data_df["from_bus"].astype(str)
branch_data_df["to_bus"] = branch_data_df["to_bus"].astype(str)
DERS_data_df["name"] = DERS_data_df["name"].astype(str)
DERS_data_df["connected_bus"] = DERS_data_df["connected_bus"].astype(str)
load_data_df["bus"] = load_data_df["bus"].astype(str)
normally_open_components_df["normally_open_components"] = normally_open_components_df["normally_open_components"].astype(str)

bus_data_df = bus_data_df.set_index("name") # make name as index
G = nx.from_pandas_edgelist(branch_data_df, source = 'from_bus', target = 'to_bus', edge_attr = True) # graph creation from pandas pdelements

for index, row in bus_data_df.iterrows():  # adding attributes to graph
    if pd.Series(index).isin(list(G.nodes)).any(): # just to add attributes of bus present only in pdeleents data
        G.add_node(index, basekV = bus_data_df.loc[index,'basekV'], latitude = bus_data_df.loc[index,'latitude'], longitude = bus_data_df.loc[index,'longitude'])



H = nx.Graph(G)  # copying graph to do further operation

for u,v in H.edges():
    if H[u][v]['is_switch'] == True:
        H.remove_edge(u,v)


areas_dict = {}
area_index = 1

areas_list_generator = list(nx.connected_components(H))



for area in areas_list_generator:
    result_dir = current_dir + f"\\results\\{test_case_name}\\area_{area_index}"
    os.makedirs(result_dir, exist_ok = True)

    # added on 4/11/2025 just to get buses list in each area
    json_object = json.dumps(list(area), indent=4)
    with open(result_dir + r"/bus_collection.json", 'w') as bus_collection_file:
        bus_collection_file.write(json_object)

    #areas_dict[f"area_{area_index}"] = area
    # bus
    areas_dict[f"area_{area_index}_bus_df"] = bus_data_df.loc[list(area)] # getting bus data
    areas_dict[f"area_{area_index}_bus_df"].to_csv(result_dir + r"\bus_data.csv") # saving bus data to bus_daata,csv
    #pdelements
    # getting pdelements data
    areas_dict[f"area_{area_index}_branch_df"] = branch_data_df[(branch_data_df["from_bus"].isin(list(area))) & (branch_data_df["to_bus"].isin(list(area)))]
    areas_dict[f"area_{area_index}_branch_df"].to_csv(result_dir + r"\pdelements_data.csv", index = False) # saving pdelements data
    # normally open components
    # creating empty normally_open_components data frame since there is no tie switch or normally open switch within area
    areas_dict[f"area_{area_index}_normally_open_components_df"] = pd.DataFrame([], columns = ["normally_open_components"])
    areas_dict[f"area_{area_index}_normally_open_components_df"].to_csv(result_dir + r"\normally_open_components.csv", index = False) # saving normally open components file
    # load data
    areas_dict[f"area_{area_index}_load_data_df"] = load_data_df[load_data_df["bus"].isin(list(area))] # getting load data for buses in given area
    areas_dict[f"area_{area_index}_load_data_df"].to_csv(result_dir + r"\load_data.csv", index = False) # saving load data for each area
    # DERS data
    areas_dict[f"area_{area_index}_DERS_df"] = pd.DataFrame([], columns = ["name","kW_rated","connected_bus","phases"]) # creating empty DERS data frame
    areas_dict[f"area_{area_index}_DERS_df"].to_csv(result_dir + r"\DERS.csv") # saving DERS file
    # transformer data
    # getting transformer data for area
    areas_dict[f"area_{area_index}_transformer_df"] = transformer_data_df[(transformer_data_df["connected_from"].isin(list(area))) & (transformer_data_df["connected_to"].isin(list(area)))]
    areas_dict[f"area_{area_index}_transformer_df"].to_csv(result_dir + r"\transformer_data.csv") # saving transformer data

    # getting network_tree_data.json
    areas_dict[f"area_{area_index}_network_tree_json"] = nx.node_link_data(nx.induced_subgraph(H, area)) # returns json data for area
    json_object = json.dumps(areas_dict[f"area_{area_index}_network_tree_json"], indent = 4)
    with open(result_dir + r"\network_tree_data.json", 'w') as json_file: # saving to json file
        json_file.write(json_object)

    # getting network_graph_data.json
    # its same as network_tree_data.json since I have stored all information in tree
    # since in Lindist, data is fetched using index from json, it won't be problem if I add extra other attributes
    json_object = json.dumps(areas_dict[f"area_{area_index}_network_tree_json"], indent=4)
    with open(result_dir + r"\network_graph_data.json", 'w') as json_file: # saving to json file
        json_file.write(json_object )

    # getting circuit data.json
    # note this substation value needs to be replaced by parent bus for the given area which is obtained doing first stage optimization(reconfiguration)
    areas_dict[f"area_{area_index}_circuit_data_json"] = {"substation": circuit_data_json["substation"], "basekV_LL_circuit":H.nodes[list(area)[0]]['basekV']} # saving baseKV for that area and substation
    json_object = json.dumps(areas_dict[f"area_{area_index}_circuit_data_json"], indent = 4)
    with open(result_dir + r"/circuit_data.json",'w') as circuit_data_file:
        circuit_data_file.write(json_object)

    area_index = area_index +1


########################### creating files for first stage  #######################################################################


first_stage_bus_df = pd.DataFrame(columns = ["name", "basekV","latitude","longitude"])
first_stage_load_data_df = pd.DataFrame(columns = ["name","bus","P1","Q1","P2","Q2","P3","Q3"])
first_stage_DERS_df = deepcopy(DERS_data_df)
first_stage_circuit_data_json = deepcopy(circuit_data_json) # substation name will be modified

first_stage_branch_data_df = deepcopy(branch_data_df) # pdelements
first_stage_branch_data_df = first_stage_branch_data_df[first_stage_branch_data_df["is_switch"]] # extracting just switch


area_index = 1
for area in areas_list_generator:

    # for bus data frame
    first_stage_bus_df.loc[area_index,"name"] = f"area_{area_index}"
    first_stage_bus_df.loc[area_index, "basekV"] = areas_dict[f"area_{area_index}_bus_df"]["basekV"][list(area)[0]] # just assigning to first element
    first_stage_bus_df.loc[area_index, "latitude"] = areas_dict[f"area_{area_index}_bus_df"]["latitude"][list(area)[0]] # just assigning to first element
    first_stage_bus_df.loc[area_index, "longitude"] = areas_dict[f"area_{area_index}_bus_df"]["longitude"][list(area)[0]]

    # for load data frame
    first_stage_load_data_df.loc[area_index,"name"] = f"area_{area_index}"
    first_stage_load_data_df.loc[area_index, "bus"] = f"area_{area_index}"
    first_stage_load_data_df.loc[area_index, "P1"] = load_data_df.loc[load_data_df["bus"].isin(list(area)),"P1"].sum()
    first_stage_load_data_df.loc[area_index, "Q1"] = load_data_df.loc[load_data_df["bus"].isin(list(area)), "Q1"].sum()
    first_stage_load_data_df.loc[area_index, "P2"] = load_data_df.loc[load_data_df["bus"].isin(list(area)), "P2"].sum()
    first_stage_load_data_df.loc[area_index, "Q2"] = load_data_df.loc[load_data_df["bus"].isin(list(area)), "Q2"].sum()
    first_stage_load_data_df.loc[area_index, "P3"] = load_data_df.loc[load_data_df["bus"].isin(list(area)), "P3"].sum()
    first_stage_load_data_df.loc[area_index, "Q3"] = load_data_df.loc[load_data_df["bus"].isin(list(area)), "Q3"].sum()

    # for DERS
    first_stage_DERS_df["connected_bus"] = first_stage_DERS_df["connected_bus"].where(~ first_stage_DERS_df["connected_bus"].isin(list(area)), other = f"area_{area_index}") # just replacing connected bus by area

    # for circuit data json
    if first_stage_circuit_data_json["substation"] in area: # replacing substation name by area where it belongs to
        first_stage_circuit_data_json["substation"] = f"area_{area_index}"

    # for pdelements
    first_stage_branch_data_df["from_bus"] = first_stage_branch_data_df["from_bus"].where(~ first_stage_branch_data_df["from_bus"].isin(list(area)), other = f"area_{area_index}") # replacing from bus by area to which it is connected
    first_stage_branch_data_df["to_bus"] = first_stage_branch_data_df["to_bus"].where(~ first_stage_branch_data_df["to_bus"].isin(list(area)),other=f"area_{area_index}")  # replacing to bus by area to which it is connected


    area_index +=1


# normally open components
first_stage_normally_open_components_df = deepcopy(normally_open_components_df) # it will be same

# saving above files

result_dir = current_dir + f"\\results\\{test_case_name}\\first_stage"
os.makedirs(result_dir, exist_ok = True)

# added on 4/11/2025 just to get buses list in each area
json_object = json.dumps([list(item) for item in areas_list_generator], indent=4)
with open(result_dir + r"/bus_collection.json", 'w') as bus_collection_file:
    bus_collection_file.write(json_object)


# this is to make sure that in base condition with all sectionalizers on , tie switch are off, arrage branch data based on their topology order, just to cope with how Lindist is working
first_stage_branch_data_df_sectionalizer_only = first_stage_branch_data_df[first_stage_branch_data_df["is_open"] == False]
G = nx.from_pandas_edgelist(first_stage_branch_data_df_sectionalizer_only, source = 'from_bus', target = 'to_bus', edge_attr = True)
tree_edge_list = list(nx.dfs_edges(G, source='area_1')) # assumes area_1 as substation, if npt change it
for (fr_bus, to_bus) in tree_edge_list:
    first_stage_branch_data_df.loc[(first_stage_branch_data_df["from_bus"] == to_bus) & (first_stage_branch_data_df["to_bus"] == fr_bus),["from_bus","to_bus"]] = first_stage_branch_data_df.loc[(first_stage_branch_data_df["from_bus"] == to_bus) & (first_stage_branch_data_df["to_bus"] == fr_bus), ["to_bus","from_bus"]].values


first_stage_bus_df.to_csv(result_dir + r"\bus_data.csv", index = False) # saving bus data
first_stage_branch_data_df.to_csv(result_dir + r"\pdelements_data.csv", index = False) # saving pdelements data
first_stage_normally_open_components_df.to_csv(result_dir + r"\normally_open_components.csv", index = False) # saving normally open components data
first_stage_load_data_df.to_csv(result_dir + r"\load_data.csv", index = False) # saving load data
first_stage_DERS_df.to_csv(result_dir + r"\DERS.csv")  # saving DERS data

circuit_data_json_object = json.dumps(first_stage_circuit_data_json, indent = 4) # saving circuit data json
with open(result_dir + r"/circuit_data.json",'w') as circuit_data_file:
    circuit_data_file.write(circuit_data_json_object)

## now  for network graph data json
first_stage_branch_data_df = first_stage_branch_data_df[first_stage_branch_data_df["is_open"] == False] # to get only sectionalizers

G = nx.from_pandas_edgelist(first_stage_branch_data_df, source = 'from_bus', target = 'to_bus', edge_attr = True,create_using=nx.DiGraph()) # graph creation from pandas pdelements

for index, row in first_stage_bus_df.iterrows():  # adding attributes to graph
    if pd.Series(index).isin(list(G.nodes)).any(): # just to add attributes of bus present only in pdeleents data
        G.add_node(index, basekV = first_stage_bus_df.loc[index,'basekV'], latitude = first_stage_bus_df.loc[index,'latitude'], longitude = first_stage_bus_df.loc[index,'longitude'])


# getting network_tree_data.json
first_stage_network_tree_data_json = nx.node_link_data(G) # returns json data for area
network_tree_json_object = json.dumps(first_stage_network_tree_data_json, indent = 4)
with open(result_dir + r"\network_tree_data.json", 'w') as json_file: # saving to json file
    json_file.write(network_tree_json_object)

# getting network_graph_data.json
# its same as network_tree_data.json since I have stored all information in tree
# since in Lindist, data is fetched using index from json, it won't be problem if I add extra other attributes
first_stage_network_graph_data_json = nx.node_link_data(G.to_undirected())
network_graph_json_object = json.dumps(first_stage_network_graph_data_json, indent=4)
with open(result_dir + r"\network_graph_data.json", 'w') as json_file: # saving to json file
    json_file.write(network_graph_json_object)




