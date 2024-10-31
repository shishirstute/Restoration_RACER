
import os
import pandas as pd


current_working_dir = os.getcwd()
system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123
faults_list = [("hvmv115_hsb2", "regxfmr_hvmv69sub1_lsb1")]
areas_data_file_path = current_working_dir + f"/results/{system_name}" # path of areas after decomposition of whole system
areas_list = pd.read_csv(os.path.join(areas_data_file_path,"first_stage","bus_data.csv"))["name"].to_list()
fault_bus_list = [_ for pair in faults_list for _ in pair]
fault_related_area_list = []
for area in areas_list:
    if set(fault_bus_list ).intersection(pd.read_csv(os.path.join(areas_data_file_path,area,"bus_data.csv"))["name"].to_list()):
        fault_related_area_list.append(area)

faults_area_tuple_pair = []

for index,row in pd.read_csv(os.path.join(areas_data_file_path,"first_stage","pdelements_data.csv")).iterrows():
    if row["from_bus"] in fault_related_area_list or  row["to_bus"] in fault_related_area_list:
        faults_area_tuple_pair.append((row["from_bus"], row["to_bus"]))

return faults_area_tuple_pair



