import plotly.graph_objects as go
import os
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import re

def plot_graph_plotly(bus_data_path, branch_data_path):


    current_dir = os.path.dirname(__file__)

    #bus_data_path = current_dir + r"\..\Data\parsed_data_9500_der\bus_data.csv"
    #branch_data_path = current_dir + r"\..\Data\parsed_data_9500_der\pdelements_data.csv"

    bus_data_df = pd.read_csv(bus_data_path, index_col=0)
    branch_data_df = pd.read_csv(branch_data_path)

    G = nx.from_pandas_edgelist(branch_data_df, source='from_bus', target='to_bus',
                                edge_attr=True)  # graph creation from pandas pdelements

    for index, row in bus_data_df.iterrows():  # adding attributes to graph
        if pd.Series(index).isin(list(G.nodes)).any():  # just to add attributes of bus present only in pdeleents data
            G.add_node(index, basekv=bus_data_df.loc[index, 'basekV'], latitude=bus_data_df.loc[index, 'latitude'],
                       longitude=bus_data_df.loc[index, 'longitude'])

    # for plotting

    nodes_dict_pos = {}  # store latitide and longitude

    for node in G.nodes:
        nodes_dict_pos[node] = (G.nodes[node]['longitude'], G.nodes[node]['latitude'])

    # storing edge name
    edges_dict_name = {}

    for u, v in G.edges():
        edges_dict_name[(u, v)] = G.edges[u, v]["name"]

    ## plotly codes starts from here

    # for non-switch lines only

    edge_attr = []
    edge_x = []
    edge_y = []
    for edge in G.edges():
        if G.edges[edge[0], edge[1]]["is_switch"] == False:
            x0, y0 = nodes_dict_pos[edge[0]]
            x1, y1 = nodes_dict_pos[edge[1]]
            edge_x.append(x0)
            edge_x.append(x1)
            edge_x.append(None)
            edge_y.append(y0)
            edge_y.append(y1)
            edge_y.append(None)
            edge_attr.append(edges_dict_name[(edge[0], edge[1])])

    edge_trace_not_switch = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='black'),
        hoverinfo='text',
        mode='lines')

    # for switch elements

    edge_attr = []
    edge_x = []
    edge_y = []
    for edge in G.edges():
        if (G.edges[edge[0], edge[1]]["is_switch"] == True) & (G.edges[edge[0], edge[1]]["is_open"] == False):
            x0, y0 = nodes_dict_pos[edge[0]]
            x1, y1 = nodes_dict_pos[edge[1]]
            edge_x.append(x0)
            edge_x.append(x1)
            edge_x.append(None)
            edge_y.append(y0)
            edge_y.append(y1)
            edge_y.append(None)
            edge_attr.append(edges_dict_name[(edge[0], edge[1])])

    edge_trace_sectional_switch = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=3, color='green'),
        hoverinfo='text',
        mode='lines')

    # For tie switch:

    edge_attr = []
    edge_x = []
    edge_y = []
    for edge in G.edges():
        if (G.edges[edge[0], edge[1]]["is_switch"] == True) & (G.edges[edge[0], edge[1]]["is_open"] == True):
            x0, y0 = nodes_dict_pos[edge[0]]
            x1, y1 = nodes_dict_pos[edge[1]]
            edge_x.append(x0)
            edge_x.append(x1)
            edge_x.append(None)
            edge_y.append(y0)
            edge_y.append(y1)
            edge_y.append(None)
            edge_attr.append(edges_dict_name[(edge[0], edge[1])])

    edge_trace_tie_switch = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color='blue'),
        hoverinfo='text',
        mode='lines')


# fault trace
    edge_x = []
    edge_y = []
    fault_lines = [("hvmv69s1s2_1","hvmv69s1s2_2")]
    # fault_lines = []
    for _ in fault_lines:
        x0, y0 = nodes_dict_pos[_[0]]
        x1, y1 = nodes_dict_pos[_[1]]
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)

    fault_trace_tie_switch = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=4, color='red'),
        hoverinfo='text',
        mode='lines')



    node_x = []
    node_y = []
    for node in G.nodes():
        x, y = nodes_dict_pos[node]
        node_x.append(x)
        node_y.append(y)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        marker=dict(
            showscale=True,
            # colorscale options
            # 'Greys' | 'YlGnBu' | 'Greens' | 'YlOrRd' | 'Bluered' | 'RdBu' |
            # 'Reds' | 'Blues' | 'Picnic' | 'Rainbow' | 'Portland' | 'Jet' |
            # 'Hot' | 'Blackbody' | 'Earth' | 'Electric' | 'Viridis' |
            colorscale='YlGnBu',
            reversescale=True,
            color=["blue"],
            size=0.1,
            colorbar=dict(),
            line_width=2))

    node_text = []

    for node in G.nodes():
        node_text.append({"node": node, "kv": G.nodes[node]['basekv']})

    node_trace.text = node_text  # change this to graph attributes


    # Create a separate trace for node labels, disable if you dont want label in node, write it as None as below
    node_label_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='text',  # Use 'text' mode to display labels
        # text=[str(node.split("_")[1]) for node in G.nodes()],  # Labels for each node (you can modify this), uncomment it for aggregate
        text=[node for node in G.nodes()],
        textposition="top center",  # Position labels on top of nodes
        hoverinfo='skip',  # Disable hover for the labels
        textfont=dict(size=12, color='black')  # Customize font size and color
    )




    fig = go.Figure(data=[edge_trace_not_switch, edge_trace_sectional_switch, node_trace,edge_trace_tie_switch,fault_trace_tie_switch], #edge_trace_tie_switch, #node_label_trace
                    layout=go.Layout(
                        title='<br>Network graph made with Python',
                        titlefont_size=16,
                        showlegend=True,
                        hovermode='closest',
                        margin=dict(b=20, l=5, r=5, t=40),
                        annotations=[dict(
                            text=None,
                            showarrow=False,
                            xref="paper", yref="paper",
                            x=0.005, y=-0.002)],
                        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    dragmode = "pan")
                    )
    config = {'scrollZoom':True}

    fig.show(config=config)

    return None