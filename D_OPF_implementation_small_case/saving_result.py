
''' saves required result in cvx file'''


import numpy as np

def save_result(area):

    # storing line flow data

    edge_index = ModifiedEdgeIndexGraph.keys()
    Pija= np.array([area.model.Pija[_]() for _ in edge_index])
    Pijb= np.array([area.model.Pijb[_]() for _ in edge_index])
    Pijc= np.array([area.model.Pijc[_]() for _ in edge_index])
    Power = pd.DataFrame()
    Power['edge_index'] = edge_index
    Power['Pija'] = Pija
    Power['Pijb'] = Pijb
    Power['Pijc'] = Pijc
    # save to csv file
    Power.to_csv('LineFlow_solution.csv', index = False)

    # storing Voltage solution data

    bus_index = sorted([int(_) for _ in area.bus_index])
    bus_index = [str(_) for _ in bus_index]
    Va= np.array([area.model.Va[_]() for _ in bus_index])
    Va = np.sqrt(Va)
    Vb= np.array([area.model.Vb[_]() for _ in bus_index])
    Vb = np.sqrt(Vb)
    Vc= np.array([area.model.Vc[_]() for _ in bus_index])
    Vc = np.sqrt(Vc)
    Voltage = pd.DataFrame()
    Voltage['bus'] = bus_index
    Voltage['Va'] = Va
    Voltage['Vb'] = Vb
    Voltage['Vc'] = Vc

    # save to csv file
    Voltage.to_csv('voltage_solution.csv', index = False)