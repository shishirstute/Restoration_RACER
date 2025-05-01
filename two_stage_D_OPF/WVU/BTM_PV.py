import numpy as np
import random
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv
from sklearn.preprocessing import MinMaxScaler


def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)

set_seed(42)

class PVLoadForecaster:
    def __init__(self, rated_p, forecast_horizon=96, phase_index=0):
        set_seed(42)
        self.rated_p = rated_p
        self.forecast_horizon = forecast_horizon
        self.phase_index = phase_index
        self._build_model()
        self._prepare_offline_data()
        self._train_stgnn()
        self._generate_24h_pv_forecast()

    # ---------- internal module -------------------------------------------------------
    def _build_model(self):
        class STGNN(nn.Module):
            def __init__(self, in_dim, hid_dim, out_dim):
                super().__init__()
                self.gcn1 = GCNConv(in_dim, hid_dim)
                self.gcn2 = GCNConv(hid_dim, hid_dim)
                self.lstm = nn.LSTM(hid_dim, hid_dim, batch_first=True)
                self.fc = nn.Linear(hid_dim, out_dim)

            def forward(self, x, edge_index, edge_attr):
                x = torch.relu(self.gcn1(x, edge_index, edge_attr))
                x = torch.relu(self.gcn2(x, edge_index, edge_attr))
                if x.dim() == 2:
                    x = x.unsqueeze(0)
                x, _ = self.lstm(x)
                x = self.fc(x.squeeze(0))
                return x
        self.STGNN = STGNN

    def _prepare_offline_data(self):
        sat = pd.read_csv("satellite_data_static_2.csv")
        obs = sat[sat["is_proxy_pv"] == 1][["latitude", "longitude"]].values
        uobs = sat[sat["is_proxy_pv"] == 0][["latitude", "longitude"]].values
        dist = np.linalg.norm(obs[0] - uobs[0])
        self.edge_index = torch.tensor([[0, 1], [1, 0]], dtype=torch.long).t().contiguous()
        self.edge_attr = torch.tensor([1.0 / dist, 1.0 / dist], dtype=torch.float)

        irr_hist = pd.read_csv("proxy_1_day_15m_interval_irrad.csv", header=None).values
        pv_hist = pd.read_csv("proxy_pv_1003.csv", header=None).values
        self.scaler_irr = MinMaxScaler().fit(irr_hist)
        self.scaler_pv = MinMaxScaler().fit(pv_hist)
        feats = np.hstack((self.scaler_irr.transform(irr_hist),
                           self.scaler_pv.transform(pv_hist)))
        self.train_data = Data(x=torch.tensor(feats, dtype=torch.float),
                               edge_index=self.edge_index,
                               edge_attr=self.edge_attr)

        self.scaler_out = MinMaxScaler(feature_range=(0, 1))
        self.scaler_out.fit(np.array([[0], [self.rated_p]]))

        self.forecasted_irr = pd.read_csv("forecasted_1_day_15m_interval_irradiance.csv",
                                          header=None).values
        self.forecasted_irr_scaled = self.scaler_irr.transform(self.forecasted_irr)

    def _train_stgnn(self, epochs=100, lr=0.01):
        model = self.STGNN(2, 32, 1)
        opt = optim.Adam(model.parameters(), lr=lr)
        crit = nn.MSELoss()
        for _ in range(epochs):
            model.train()
            opt.zero_grad()
            out = model(self.train_data.x, self.edge_index, self.edge_attr)
            loss = crit(out, self.train_data.x[:, 1].unsqueeze(1))
            loss.backward()
            opt.step()
        self.model = model.eval()

    def _generate_24h_pv_forecast(self):
        hist_pv_est = pd.read_csv("estimated_power_generation_testing_1_day_15_min.csv")[
            "estimated_power_generation"].values.reshape(-1, 1)
        hist_pv_scaled = self.scaler_out.transform(hist_pv_est)
        seq = np.hstack((self.forecasted_irr_scaled, hist_pv_scaled))
        current = torch.tensor(seq, dtype=torch.float).unsqueeze(0)

        forecasts = []
        for t in range(self.forecast_horizon):
            with torch.no_grad():
                pred = self.model(current, self.edge_index, self.edge_attr)
                pv_kW = self.scaler_out.inverse_transform(pred.numpy())[0][0]
                if self.forecasted_irr[t][0] <= 200:
                    pv_kW = 0.0
                forecasts.append(pv_kW)
                nxt = torch.tensor([[self.forecasted_irr_scaled[t][0],
                                     self.scaler_out.transform([[pv_kW]])[0][0]]],
                                   dtype=torch.float).unsqueeze(0)
                current = torch.cat((current[:, 1:, :], nxt), dim=1)
        self.pv_forecast = forecasts

    # ---------- main module ---------------------------------------------------------
    def forecast_load(self, bus_snapshot: dict, t_index: int):

        
        bus_id = list(bus_snapshot.keys())[0]
        values = bus_snapshot[bus_id]

        p1 = values["P1"]
        q1 = values["Q1"]
        p2 = values["P2"]
        q2 = values["Q2"]
        p3 = values["P3"]
        q3 = values["Q3"]
        pv_val = {"P":0}

        pv_gen = self.pv_forecast[t_index]
        # p1_forecast = pv_gen - p1

        result = {
            "Bus": bus_id,
            "P1": p1,
            "Q1": q1,
            "P2": p2,
            "Q2": q2,
            "P3": p3,
            "Q3": q3
        }

        pv_result = {"P1": 0, "P2":0, "P3":0}
        
        if self.phase_index == 1:
            result["P1"] = p1 + pv_gen
            pv_result["P1"] = pv_gen
            # pv_val = {"P1": pv_gen}
        elif self.phase_index == 2:
            result["P2"] = p2 + pv_gen
            pv_result["P2"] = pv_gen
            # pv_val = {"P2": pv_gen}
        elif self.phase_index == 3:
            result["P3"] = p3 + pv_gen
            pv_result["P3"] = pv_gen
            # pv_val = {"P3": pv_gen}
        return result, pv_result

# ## -------------------- example usage --------------------


# import pandas as pd


# ## node mapping...Need to be run outside the loop for restoration/BTM PV with or without CLPU
# network_map = pd.read_csv("database_9600_model_network.csv")
# primary_bus = list(bus_snapshot.keys())[0]
# network_map = pd.read_csv("database_9600_model_network.csv")
# match = network_map['PrimaryBus'].str.contains(rf'\b{primary_bus}\b', case=False, na=False)
# p_rated = 0
# phase_index = 0
# if match.any():
#     p_rated_candidate = network_map.loc[match, 'PV_kW'].values[0]
#     if not pd.isna(p_rated_candidate):
#         p_rated = p_rated_candidate
#         full_match = network_map.loc[match, 'PrimaryBus'].values[0]
#         if '.' in full_match:
#             try:
#                 suffix = int(full_match.split('.')[-1])
#                 if suffix in [1, 2, 3]:
#                     phase_index = suffix
#             except ValueError:
#                 pass
# ## node mapping ends

# ## input dict from restoration module
## Example of input_data format:
# bus_snapshot = {"L3216348":{
#         "P1": 0,
#         "Q1": 0,
#         "P2": 0,
#         "Q2": 0,
#         "P3": 0,
#         "Q3": 0}
#                  }
# bus_snapshot = input_data
# time_step = 0
# total_time = 96
# forecaster = PVLoadForecaster(rated_p=p_rated, phase_index=phase_index)

# # for loop to get the results for every 15-minute time step
# for time in range(total_time):
    # forecasted_load, pv_forecast = forecaster.forecast_load(bus_snapshot, t_index=time_step)
    # print(forecasted_load)
    # print(pv_forecast)

## dummy forecasted_load and pv_forecast result format for example
## >> {'Bus': 'Ldf3179674', 'P1': 0.1155821, 'Q1': 0, 'P2': 0.1155821, 'Q2': 0, 'P3': 0.1155821, 'Q3': 0}
## >> {'P1': 0, 'P2': 5.864221, 'P3': 0}