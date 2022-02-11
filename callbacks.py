from dash import Input, Output, State, callback, MATCH, ALL
#from main import app

def callbacks():
    @app.callback(
        [Output({'type':'biomass_slider', 'index':MATCH}, 'disabled'),
        Output({'type':'lice_slider', 'index':MATCH}, 'disabled')],
        Input({'type':'switch', 'index':MATCH},'on'),
        State({'type':'switch', 'index':MATCH},'on')
    )
    def desactivate_farms(dis_biom, dis_lice, switch):
        return ~switch, ~switch

    @app.callback(
        [Output({'type':'biomass_slider', 'index':ALL}, 'value'),
        Output({'type':'lice_slider', 'index':ALL}, 'value')],
        [Input('master_lice_slider', 'value'),
        Input('master_biomass_slider','value')]
    )
    def update_all_sliders(lice, biom):
        return biom, lice

    @app.callback(
        [Output('heatmap', 'figure'),
        Output('heatmap_output', 'children')],
        Input('submit_map','n_clicks'),
        [State({'type':'switch', 'index':ALL},'on'),
        State({'type':'biomass_slider', 'index':ALL},'value'),
        State({'type':'lice_slider', 'index':ALL},'value'),
        State('span-slider','value') ,
        State('resolution-slider','value'),
        State('heatmap', 'figure')]
    )
    def redraw(n_clicks,idx, biomasses, lices, span, r, fig):
        idx=np.array(idx)
        print(type(idx))
        if idx.sum()>0:
            name_list=np.array(All_names)[computed_farms][idx]
            Coeff=biomasses[idx]*lices[idx]

            super_ds, coordinates=global_store(r)

            fig['data'][0]['marker']['cmax']=span[1]
            fig['data'][0]['marker']['cmin']=span[0]
            fig['layout']['mapbox']['layers']=[
                                    {
                                        "below": 'traces',
                                        "sourcetype": "image",
                                        "source": mk_img(super_ds, name_list, span, Coeff),
                                        "coordinates": coordinates[::-1]
                                    }]
        else:
            # add a message?
            fig['layout']['mapbox']['layers']=[]
        return fig, None

    @app.callback(
        [Output({'type':'biomass_slider', 'index':MATCH}, 'disabled'),
        Output({'type':'lice_slider', 'index':MATCH}, 'disabled')],
        Input({'type':'switch', 'index':MATCH},'on')
    )
    def desactivate_farms(dis_biom, dis_lice, switch):
        if not switch:
            dis_biom, dis_lice = True, True

    @app.callback(
        [Output({'type':'biomass_slider', 'index':ALL}, 'value'),
        Output({'type':'lice_slider', 'index':ALL}, 'value')],
        [Input('master_lice_slider', 'value'),
        Input('master_biomass_slider','value')]
    )
    def update_all_sliders(lice, biom):
        return biom, lice
