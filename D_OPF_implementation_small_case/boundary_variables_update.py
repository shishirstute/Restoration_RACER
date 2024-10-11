def boundary_variables_update(area_collections,area_results):
    ''' update the boundary variables of each area'''


    for area in area_collections:

        ## updating power from child area to parent area
        if area.cShared_bus is not None:

            for child_area in area.cShared_bus.keys():
                shared_bus = area.cShared_bus[child_area]
                shared_bus = [_ for _ in shared_bus][0]  # just to get rid of set
                G = area_results[child_area].G  # getting graph, here I am getting from restoration model
                child_nodes = list(G.successors(shared_bus))  # gives child nodes
                to_child_edge_index = [str(shared_bus) + "_" + str(_) for _ in child_nodes]  # similar for child nodes

                # updating power at shared bus of parent area
                # PA
                area.cPower[shared_bus]['PLA'] = sum(area_results[child_area].model.Pija[_]() for _ in to_child_edge_index)
                # QA
                area.cPower[shared_bus]['QLA'] = sum(area_results[child_area].model.Qija[_]() for _ in to_child_edge_index)

                # PB
                area.cPower[shared_bus]['PLB'] = sum(area_results[child_area].model.Pijb[_]() for _ in to_child_edge_index)
                # QB
                area.cPower[shared_bus]['QLB'] = sum(area_results[child_area].model.Qijb[_]() for _ in to_child_edge_index)

                # PC
                area.cPower[shared_bus]['PLC'] = sum(area_results[child_area].model.Pijc[_]() for _ in to_child_edge_index)

                # QC
                area.cPower[shared_bus]['QLC'] = sum(area_results[child_area].model.Qijc[_]() for _ in to_child_edge_index)

            ## updating voltage from parent area to child area
        if area.pShared_bus is not None:
            for parent_area in area.pShared_bus.keys():
                shared_bus = area.pShared_bus[parent_area]
                shared_bus = [_ for _ in shared_bus][0]
                # Va
                area.pVoltage['Va'] = area_results[parent_area].model.Va[shared_bus]()
                # Vb
                area.pVoltage['Vb'] = area_results[parent_area].model.Vb[shared_bus]()
                # vc
                area.pVoltage['Vc'] = area_results[parent_area].model.Vc[shared_bus]()



