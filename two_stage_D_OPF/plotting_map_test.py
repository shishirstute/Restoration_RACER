from __future__ import annotations
import os
from ldrestoration import RestorationBase
from ldrestoration.utils.plotnetwork import plot_solution_map
from copy import deepcopy
import networkx as nx
import pandas as pd
import shutil
from pyomo.opt import TerminationCondition

current_working_dir = os.getcwd()
system_name = "parsed_data_9500_der" # "parsed_data_9500_der, parsed_data_ieee123

parsed_data_path = current_working_dir + f"/Data/{system_name}"
vmax=1.05
vmin=0.95
vsub_a = 1.03
vsub_b = 1.03
vsub_c = 1.03

# faults = [("d2000100_int","m2000200")]
# faults = [("hvmv69s1s2_1","hvmv69s1s2_2")]
# faults = [("hvmv115_hsb2","regxfmr_hvmv69sub1_lsb1")]
# faults = [("m1026354","m2000100")] # huge blackout as some part is isolated and can not even conenct by tie switch
faults = [("m2000902","d2000901_int")]

# faults = []

rm = RestorationBase(parsed_data_path, faults=faults, base_kV_LL=4.16)

rm.constraints_base(base_kV_LL=66.4, vmax=vmax, vmin=vmin, \
                    vsub_a=vsub_a, vsub_b=vsub_b, vsub_c=vsub_c, \
                    psub_a_max=5000, psub_b_max=5000, psub_c_max=5000)

# rm.objective_load_only()
# rm.objective_load_and_switching()
rm.objective_load_switching_and_der()  # alpha, beta, gamma are parameters to it.

rm_solved, results = rm.solve_model(solver='gurobi',save_results = False,
                                    solver_options = {"mipgap":0.00000000,"ScaleFlag":1})

plot_solution_map(rm_solved, rm.network_tree, rm.network_graph, background = "white")