from __future__ import annotations
import os
from ldrestoration import RestorationBase
from copy import deepcopy
import networkx as nx
import pandas as pd

from central_functions_list import *


# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_9500_der"
# # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage"
# # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_ieee123"  # for 123 bus system
# # parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_ieee123\first_stage"

current_working_dir = os.getcwd()
system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123

parsed_data_path = current_working_dir + f"/Data/{system_name}"

parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\temp\system_data\area_2" # for testing

# faults = [("area_1","area_2"),("area_2","area_3"),("area_3","area_4"),("area_4","area_5"),("area_3","area_6"),("area_8","area_9"),("area_5","area_13"),("area_30","area_31")]
# faults = [("area_2","area_4")]
# faults = [("d2000100_int","m2000200")]
# faults = [("hvmv69s1s2_1","hvmv69s1s2_2")]
# faults = [("hvmv115_hsb2","regxfmr_hvmv69sub1_lsb1")]
faults = []
rm = RestorationBase(parsed_data_path, faults = faults, base_kV_LL=4.16)

rm.constraints_base(base_kV_LL=66.4,vmax=1.05,vmin=0.95, \
                    vsub_a = 1.03, vsub_b = 1.03, vsub_c = 1.03, \
                    psub_a_max=5000, psub_b_max=5000, psub_c_max=5000) # use psub_a, psub_b, psub_c

# rm.objective_load_only()
rm.objective_load_and_switching()
# rm.objective_load_switching_and_der() # alpha, beta, gamma are parameters to it.

rm_solved, results = rm.solve_model(solver='gurobi',save_results = True, solver_options = {"mipgap":0.00000000,"ScaleFlag":1})
# parent_child_area_df.to_csv(file_path_name)

print("dectionalizers switch status",list(rm_solved.xij[_]() for _ in rm_solved.sectionalizing_switch_indices))
print("virtual switch status",list(rm_solved.xij[_]() for _ in rm_solved.virtual_switch_indices)) # virtual switch status

print("tie switch status",list(rm_solved.xij[_]() for _ in rm_solved.tie_switch_indices))

print("total load served with objective value ",rm_solved.restoration_objective())


total_load_served = total_load_served_calculation(rm = rm, rm_solved = rm_solved)

print(f"Total load served is {total_load_served}")