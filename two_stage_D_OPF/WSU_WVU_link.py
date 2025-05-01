from BTM_PV import PVLoadForecaster
from CLPU import CLPULoadCalculator
import pandas as pd
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv
from sklearn.preprocessing import MinMaxScaler
import os

def get_load_considering_PV_CLPU(t_index, outage_start, restoration_end, bus_snapshot):
    ## node mapping...Need to be run outside the loop for restoration/BTM PV with or without CLPU
    network_map = pd.read_csv("database_9600_model_network.csv")
    primary_bus = list(bus_snapshot.keys())[0]
    network_map = pd.read_csv("database_9600_model_network.csv")
    match = network_map['PrimaryBus'].str.contains(rf'\b{primary_bus}\b', case=False, na=False)
    p_rated = 0
    phase_index = 0
    if match.any():
        p_rated_candidate = network_map.loc[match, 'PV_kW'].values[0]
        if not pd.isna(p_rated_candidate):
            p_rated = p_rated_candidate
            full_match = network_map.loc[match, 'PrimaryBus'].values[0]
            if '.' in full_match:
                try:
                    suffix = int(full_match.split('.')[-1])
                    if suffix in [1, 2, 3]:
                        phase_index = suffix
                except ValueError:
                    pass
    ## node mapping ends
    forecaster = PVLoadForecaster(rated_p=p_rated, phase_index=phase_index)

    gross_load, pv_forecast = forecaster.forecast_load(bus_snapshot, t_index=t_index)
    # print(gross_load)
    # print(pv_forecast)

    # -------------------------------------------------Load Estimates With CLPU---------------------------------------------
    ## Example input for CLPU based BTM PV
    ## gross_load = {'Bus': 'L3252336', 'P1': 4, 'Q1': 0.4234, 'P2': 2.375150203704834, 'Q2': 0, 'P3': 9, 'Q3': 0}
    ## pv_forecasted = {'P1': 0, 'P2': 5.62485, 'P3': 0}
    calc = CLPULoadCalculator()
    for k in range(96):
        res = calc.step(forecast_dict=gross_load, pv_dict=pv_forecast, outage_start=outage_start, restoration_end=restoration_end)
        if k == t_index:
            # print(f"t={k} ----  {res}")
            return res
#
# bus_snapshot = {"L3252336":{
#         "P1": 4,
#         "Q1": 0.4234,
#         "P2": 8,
#         "Q2": 0,
#         "P3": 0,
#         "Q3": 0}
#                  }
# res = get_load_considering_PV_CLPU(t_index=50, outage_start=1, restoration_end=0, bus_snapshot=bus_snapshot)
