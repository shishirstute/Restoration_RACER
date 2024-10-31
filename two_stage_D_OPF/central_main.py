from __future__ import annotations
import os
from ldrestoration import RestorationBase
from copy import deepcopy
import networkx as nx
import pandas as pd


parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_9500_der"
# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage"
# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Data\parsed_data_ieee123"  # for 123 bus system
# parsed_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_ieee123\first_stage"


# faults = [("area_1","area_2"),("area_2","area_3"),("area_3","area_4"),("area_4","area_5"),("area_3","area_6"),("area_8","area_9"),("area_5","area_13"),("area_30","area_31")]
# faults = [("area_2","area_4")]
faults = [("hvmv115_hsb2","regxfmr_hvmv69sub1_lsb1")]

rm = RestorationBase(parsed_data_path, faults = faults, base_kV_LL=4.16)

rm.constraints_base(base_kV_LL=4.16,vmax=1.05,
                                        vmin=0.95,
                                       psub_max=15000)

# rm.objective_load_only()
# rm.objective_load_and_switching()
rm.objective_load_switching_and_der()

rm_solved, results = rm.solve_model(solver='gurobi',save_results = True, solver_options = {"mipgap":0.000000005,"ScaleFlag":1})
# parent_child_area_df.to_csv(file_path_name)

print("virtual switch status",list(rm_solved.xij[_]() for _ in rm_solved.virtual_switch_indices)) # virtual switch status

print("tie switch status",list(rm_solved.xij[_]() for _ in rm_solved.tie_switch_indices))

print("total load served",rm_solved.restoration_objective())

######## for d opf #####


1+1