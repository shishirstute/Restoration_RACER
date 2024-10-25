
""" this is just for getting values of various components for reusable purpose"""

# getting objective value
rm_solved.restoration_objective()
# getting line index of tree
rm_solved.edge_indices_in_tree[("area_1","area_88")]

# finding value of element
rm_solved.Pijb[rm_solved.edge_indices_in_tree[("area_30","area_63")]]()
# getting node indices in tree
rm_solved.node_indices_in_tree[("area_1")]

# getting list of virtual switch indices in tree (mapped)
virtual_switch_indices = rm_solved.virtual_switch_indices # note that it is not dictionary

# getting list of tie switch indices in tree (mapped)
tie_switch_indices = rm_solved.tie_switch_indices # note that it is not dictionary and it does not include virtual switch


# getting list of sectionalizing switch indices in tree (mapped)
sectionalizing_switch_indices = rm_solved.sectionalizing_switch_indices # note that it is not dictionary

# getting data frame of virtual switch
virtual_switch_df = rm_solved.virtual_switches

# getting data frame of tie switch
tie_switch_df = rm_solved.tie_switches

# getting data frame of sectionalizing switch
sectionalizing_switch_df = rm_solved.sectionalizing_switches


# getting data frame of pd elements
pdelements_df = rm_solved.pdelements
