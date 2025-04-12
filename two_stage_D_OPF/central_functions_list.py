
def total_load_served_calculation(rm, rm_solved):
    substation_index = rm.node_indices_in_tree[rm.circuit_data["substation"]]

    nodes_emerge_out_from_substation = list(rm.network_graph.neighbors(rm.circuit_data["substation"]))
    edge_index_list_out_from_substation = []
    for _ in  nodes_emerge_out_from_substation:
        try:
            edge_index_list_out_from_substation.append(rm.edge_indices_in_tree[(rm.circuit_data["substation"], _)])
        except:
            edge_index_list_out_from_substation.append(_, rm.edge_indices_in_tree[(rm.circuit_data["substation"])])

    total_load_served = 0
    for edge_index in edge_index_list_out_from_substation:
            total_load_served += rm_solved.Pija[edge_index]() + rm_solved.Pijb[edge_index]() + rm_solved.Pijc[edge_index]()
    return total_load_served