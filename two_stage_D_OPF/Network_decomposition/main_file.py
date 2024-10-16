from functions_list import *
import os


current_dir = os.path.dirname(__file__)

# for overall system
bus_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage\bus_data.csv"
branch_data_path = r"C:\Users\shishir\OneDrive - Washington State University (email.wsu.edu)\made_by_me\Restoration_RACER\two_stage_D_OPF\Network_decomposition\results\parsed_data_9500_der\first_stage\pdelements_data.csv"

# for aggregated system
#bus_data_path = current_dir + r"\..\Network_decomposition\results\parsed_data_9500_der\first_stage\bus_data.csv"
#branch_data_path = current_dir + r"\..\Network_decomposition\results\parsed_data_9500_der\first_stage\pdelements_data.csv"

plot_graph_plotly(bus_data_path = bus_data_path, branch_data_path = branch_data_path)