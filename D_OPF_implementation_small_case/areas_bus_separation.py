''' whole input system is provided
bus of each area is provided
generates each area system with bus and branch data'''

''' input files: line_data.csv, bus_data.csv, area_buses.csv'''

import os
import pandas as pd
import numpy as np
import networkx as nx
import math

def areas_bus_separation():

    dir_file = os.getcwd()
    file_path_branch = "C:\\Users\\shishir\\OneDrive - Washington State University (email.wsu.edu)\\Learning_Code\\Graph_learning\\Data\\abodh_feeder123\\shishir_modified\\line_data.csv"
    file_path_bus = "C:\\Users\\shishir\\OneDrive - Washington State University (email.wsu.edu)\\Learning_Code\\Graph_learning\\Data\\abodh_feeder123\\shishir_modified\\bus_data.csv"
    file_path_area = "C:\\Users\shishir\\OneDrive - Washington State University (email.wsu.edu)\\Learning_Code\\Graph_learning\Data\\abodh_feeder123\\shishir_modified\\area_buses.csv"
    df = pd.read_csv(file_path_branch)
    # print(df)

    # incase dataframe contains string in bus number, convert it to integer so that there is no mismatch in area file
    # and branch data file
    df['fbus'] = df['fbus'].fillna(-1).astype(int)
    df['tbus'] = df['tbus'].fillna(-1).astype(int)

    # creating graph
    G = nx.from_pandas_edgelist(df, source='fbus', target='tbus', create_using=nx.DiGraph)

    # area bus file is called
    # This file contains area and buses present in each area in column
    df_area_bus = pd.read_csv(file_path_area)
    # print(df_area_bus)

    # Removing nan and assigning bus to each area
    Area1_bus = list(df_area_bus['Area 1'])
    # removing nan
    Area1_bus = set([int(bus) for bus in Area1_bus if not math.isnan(bus)])
    # print(Area1_bus)

    # area 2
    Area2_bus = list(df_area_bus['Area 2'])
    # removing nan
    Area2_bus = set([int(bus) for bus in Area2_bus if not math.isnan(bus)])

    # area 3
    Area3_bus = list(df_area_bus['Area 3'])
    # removing nan
    Area3_bus = set([int(bus) for bus in Area3_bus if not math.isnan(bus)])

    # area 4
    Area4_bus = list(df_area_bus['Area 4'])
    # removing nan
    Area4_bus = set([int(bus) for bus in Area4_bus if not math.isnan(bus)])

    # area 5
    Area5_bus = list(df_area_bus['Area 5'])
    # removing nan
    Area5_bus = set([int(bus) for bus in Area5_bus if not math.isnan(bus)])

    # getting whole system and stored in AreaAll_bus
    AreaAll_bus = Area1_bus | Area2_bus | Area3_bus | Area4_bus | Area5_bus
    # print(AreaAll_bus)

    # Giving edge index as from_to in original graph
    # index = frombus_tobus
    ModifiedEdgeIndexGraph = {str(df['fbus'][i]) + '_' + str(df['tbus'][i]): {'fbus': df['fbus'][i], 'tbus': df['tbus'][i],
                                                                              'raa': df['raa'][i], 'rab': df['rab'][i],
                                                                              'rac': df['rac'][i], 'rbb': df['rbb'][i],
                                                                              'rbc': df['rbc'][i], 'rcc': df['rcc'][i],
                                                                              'xaa': df['xaa'][i], 'xab': df['xab'][i],
                                                                              'xac': df['xac'][i], 'xbb': df['xbb'][i],
                                                                              'xbc': df['xbc'][i], 'xcc': df['xcc'][i]} for
                              i in range(len(G.edges))}

    ### finding the subgraph i.e. radial network of each area
    ### i.e. finding the edges of actual system that belongs to given area


    Area1_graph = G.subgraph(Area1_bus)
    Area1_edges = list(Area1_graph.edges)  # gives edges only

    # getting graph with edges attributes of impedance
    Area1_graph_imp_inc = {}
    for (i, j) in Area1_edges:
        key = str(i) + '_' + str(j)
        Area1_graph_imp_inc[key] = ModifiedEdgeIndexGraph[key]
    # print(Area1_graph_imp_inc)

    # for area2
    Area2_graph = G.subgraph(Area2_bus)
    Area2_edges = list(Area2_graph.edges)
    # getting graph with edges attributes of impedance
    Area2_graph_imp_inc = {}
    for (i, j) in Area2_edges:
        key = str(i) + '_' + str(j)
        Area2_graph_imp_inc[key] = ModifiedEdgeIndexGraph[key]

    # for area3
    Area3_graph = G.subgraph(Area3_bus)
    Area3_edges = list(Area3_graph.edges)
    # getting graph with edges attributes of impedance
    Area3_graph_imp_inc = {}
    for (i, j) in Area3_edges:
        key = str(i) + '_' + str(j)
        Area3_graph_imp_inc[key] = ModifiedEdgeIndexGraph[key]

    # for area4
    Area4_graph = G.subgraph(Area4_bus)
    Area4_edges = list(Area4_graph.edges)
    # getting graph with edges attributes of impedance
    Area4_graph_imp_inc = {}
    for (i, j) in Area4_edges:
        key = str(i) + '_' + str(j)
        Area4_graph_imp_inc[key] = ModifiedEdgeIndexGraph[key]

    # for area5
    Area5_graph = G.subgraph(Area5_bus)
    Area5_edges = list(Area5_graph.edges)
    # getting graph with edges attributes of impedance
    Area5_graph_imp_inc = {}
    for (i, j) in Area5_edges:
        key = str(i) + '_' + str(j)
        Area5_graph_imp_inc[key] = ModifiedEdgeIndexGraph[key]

    # for areaAll
    AreaAll_graph = G.subgraph(AreaAll_bus)
    AreaAll_edges = list(AreaAll_graph.edges)
    # getting graph with edges attributes of impedance
    AreaAll_graph_imp_inc = {}
    for (i, j) in AreaAll_edges:
        key = str(i) + '_' + str(j)
        AreaAll_graph_imp_inc[key] = ModifiedEdgeIndexGraph[key]

    ########## Power data  #############

    df_power = pd.read_csv(file_path_bus)
    df_power['bus'] = df_power['bus'].fillna(-1).astype(int)  # to get rid of .0 as last of bus
    # print(df_power)

    # Making dictionary of power for each bus

    PowerDictOriginal = {
        str(df_power['bus'][i]): {'PLA': df_power['P_LA'][i], 'QLA': df_power['Q_LA'][i], 'PLB': df_power['P_LB'][i],
                                  'QLB': df_power['Q_LB'][i],
                                  'PLC': df_power['P_LC'][i], 'QLC': df_power['Q_LC'][i]
                                  } for i in range(len(df_power))}

    # print(PowerDictOriginal)

    # Assigning power for buses of each area
    Area1_power = {}
    for bus in Area1_bus:
        Area1_power[str(bus)] = PowerDictOriginal[str(bus)]

    # print(Area1_power)

    Area2_power = {}
    for bus in Area2_bus:
        Area2_power[str(bus)] = PowerDictOriginal[str(bus)]

    Area3_power = {}
    for bus in Area3_bus:
        Area3_power[str(bus)] = PowerDictOriginal[str(bus)]

    Area4_power = {}
    for bus in Area4_bus:
        Area4_power[str(bus)] = PowerDictOriginal[str(bus)]

    Area5_power = {}
    for bus in Area5_bus:
        Area5_power[str(bus)] = PowerDictOriginal[str(bus)]

    AreaAll_power = {}
    for bus in AreaAll_bus:
        AreaAll_power[str(bus)] = PowerDictOriginal[str(bus)]

    # bus and branch data for each area

    Area1 = {}
    Area1['branch_data'] = Area1_graph_imp_inc
    Area1['bus_data'] = Area1_power

    Area2 = {}
    Area2['branch_data'] = Area2_graph_imp_inc
    Area2['bus_data'] = Area2_power

    Area3 = {}
    Area3['branch_data'] = Area3_graph_imp_inc
    Area3['bus_data'] = Area3_power

    Area4 = {}
    Area4['branch_data'] = Area4_graph_imp_inc
    Area4['bus_data'] = Area4_power

    Area5 = {}
    Area5['branch_data'] = Area5_graph_imp_inc
    Area5['bus_data'] = Area5_power

    AreaAll = {}
    AreaAll['branch_data'] = AreaAll_graph_imp_inc
    AreaAll['bus_data'] = AreaAll_power

    # returning all areas

    return [Area1,Area2,Area3,Area4,Area5,AreaAll]

