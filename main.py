# This file is part of sealice visualisation tools.
#
# This app is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3
#
# The app is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details., see
# <https://www.gnu.org/licenses/>.
#
# Copyright 2022, Julien Moreau, Plastic@Bay CIC

# import googlecloudprofiler
#
# # Profiler initialization. It starts a daemon thread which continuously
# # collects and uploads profiles. Best done as early as possible.
# try:
#     # service and service_version can be automatically inferred when
#     # running on App Engine. project_id must be set if not running
#     # on GCP.
#     googlecloudprofiler.start(verbose=3)
# except (ValueError, NotImplementedError) as exc:
#     print(exc)  # Handle errors here

import gcsfs
from  xarray import open_zarr
from rasterio.enums import Resampling
from google.cloud import storage
import numpy as np
import datashader as DS
import plotly.graph_objects as go
from colorcet import fire
from datashader import transfer_functions as tf
from datetime import datetime, timedelta
import os.path
import dash
from dash import dcc as dcc
from dash import html as html
from dash.dependencies import Input, Output, State, MATCH, ALL
import dash_bootstrap_components as dbc
import dash_daq as daq

from flask_caching import Cache

#from callbacks import callbacks

def get_coordinates(agg):
    coords_lat, coords_lon = agg.coords['lat'].values, agg.coords['lon'].values
    coordinates=[[coords_lon[0], coords_lat[0]],
                       [coords_lon[-1], coords_lat[0]],
                       [coords_lon[-1], coords_lat[-1]],
                       [coords_lon[0], coords_lat[-1]]]
    return coordinates

def mk_img(ds_host, name_list, span, Coeff):
    '''
    Create an image to project on mabpox
    '''
    print('making raster...')
    subds=ds_host[name_list]
    for i in range(len(name_list)):
        subds[name_list[i]].values *=Coeff[i]
    arr= subds.to_stacked_array('v', ['lat', 'lon']).sum(dim='v').squeeze(drop=True)
    arr.rio.set_spatial_dims('lon', 'lat', inplace=True)
    arr = arr.rio.write_crs('EPSG:4326')
    shp=arr.shape
    arr2=arr.rio.reproject('EPSG:3857',
                            shape=shp,
                            resampling=Resampling.bilinear,
                            nodata=np.nan)
    return tf.shade(arr2.where(arr2>0).load(),
                    cmap=fire, how='linear',
                    span=span).to_pil()

def get_farm_data(npfile):
    '''
    Download the farm parameters
    '''
    from google.cloud import storage
    client = storage.Client()
    bucket = client.get_bucket('sealice_db')
    blob = bucket.blob(npfile.split('/')[-1])
    blob.download_to_filename(npfile)

#####################TAB 1 ###########################

def make_base_figure(farm_loc,computed_farms, center_lat, center_lon, span):
    print('Making figure ...')
    fig= go.Figure()
    fig.add_trace(go.Scatter(x=[None], y=[None],marker=go.scatter.Marker(
                        colorscale=fire,
                        cmax=span[1],
                        cmin=span[0],
                        showscale=True,

                        ),
                    name='only_scale',
                    showlegend=False),)
    fig.add_trace(go.Scattermapbox(
                        lon=farm_loc[~computed_farms][:,-1],
                        lat=farm_loc[~computed_farms][:,-2],
                        text=farm_loc[~computed_farms][:,0],
                        hovertemplate="<b>%{text}</b><br><br>" +
                                        "Biomass: %{marker.size:.0f} tons<br>",
                        name="Awaiting completion farm",
                        hoverinfo='all',
                        marker=dict(color='lightblue',
                                size=farm_loc[~computed_farms][:,1].astype('int'),
                                sizemode='area',
                                sizeref=10,
                        )
                ))
    fig.add_trace(go.Scattermapbox(
                        lon=farm_loc[computed_farms][:,-1],
                        lat=farm_loc[computed_farms][:,-2],
                        text=farm_loc[computed_farms][:,0],
                        hovertemplate="<b>%{text}</b><br><br>" +
                                        "Biomass: %{marker.size:.0f} tons<br>",
                        marker=dict(color='darkgreen',
                                size=farm_loc[computed_farms][:,1].astype('int'),
                                sizemode='area',
                                sizeref=10,
                        ),
                        name="Processed farm",
                        hoverinfo='all',
                ))
    fig.update_layout(
                height=700,
                hovermode='closest',
                showlegend=False,
                mapbox=dict(
                    bearing=0,
                    center=dict(
                        lat=center_lat,
                        lon=center_lon,
                    ),
                    pitch=0,
                    zoom=7,
                    style="carto-darkmatter",
                    ))
    return fig

def tab1_layout(farm_loc,computed_farms,center_lat, center_lon, span):
    return dbc.Card([
    dbc.CardHeader('Clyde area'),
    dbc.CardBody(
        dbc.Row([
            dbc.CardBody(
                dbc.Row([
                    html.P('Green dots are processed/ing farms, blue dots await processing.'),
                    html.P('The size of the dots is proportional to the biomass.'),
                    dcc.Graph(
                        id='heatmap',
                        figure=make_base_figure(farm_loc,computed_farms,
                                            center_lat, center_lon, span)
                        ),
                    dcc.Loading(
                        id='figure_loading',
                        children=html.Div(id='heatmap_output'),
                        type='graph',
                        fullscreen=True)
                    ])
                )
            ]),
            )
        ])
################# tab2 ###########################3
marks_biomass={
    0.1:'10%',
    0.25:'25%',
    0.5:'50%',
    0.75:'75%',
    1:'100%',
    1.25:'125%',
    1.5:'150%',
    1.75:'175%',
    2:'200%',
}
marks_lice={
    0.5:'0.25',
    1:'0.5',
    2:'1',
    4:'2',
    6:'3',
    8:'4',
    10:'5',
}
def mk_accordion_item(name, farm_loc, i):
    data=farm_loc[farm_loc[:,0]==name][0]
    item=dbc.Row([
            dbc.Col([
                daq.BooleanSwitch(
                    id={'type':'switch','id':i},
                    on=True,
                    label="Toggle farm on/off",
                    labelPosition="top"
                    )],
                width=3),
            dbc.Col([
                html.H3('Modelled Biomass {} tons'.format(data[1])),
                html.H3('Tune Farm biomass:'),
                dcc.Slider(
                    id={'type':'biomass_slider','id':i},
                    step=0.05,
                    marks=marks_biomass,
                    value=1,
                    included=False,
                    tooltip={"placement": "bottom"},
                    disabled=False
                    ),
                html.H3('Tune lice infestation:'),
                html.P('Unit is infective Copepodid/day/sqm'),
                dcc.Slider(
                    id={'type':'lice_slider','id':i},
                    step=0.05,
                    marks=marks_lice,
                    value=1,
                    included=False,
                    tooltip={"placement": "bottom"},
                    disabled=False,
                    )],
            width=8)
        ], align='center')
    return item

def tab2_layout(Filtered_names,farm_loc):
    layout= dbc.Card([
    dbc.Row([
    dbc.Card([
        dbc.CardHeader('Modify the global parameters'),
        dbc.CardBody([
            dbc.Row([
                dbc.Card([
                    dbc.CardHeader('Change map resolution'),
                    dbc.CardBody(
                        dbc.Row([
                            dcc.Slider(
                                id='resolution-slider',
                                min=0,
                                max=2,
                                step=None,
                                marks={
                                    0:'50m',
                                    1:'100m',
                                    2:'200m',
                                },
                                value=1,
                                #disabled=True
                                 ),
                            ]),
                        ),
                     ]),
            dbc.Row([
                dbc.CardHeader('Change map colorscale range'),
                dbc.CardBody(
                    dbc.Row([
                        html.P('(copepodid/sqm/day)'),
                        dcc.RangeSlider(
                            id='span-slider',
                            min=0,
                            max=20,
                            step=0.5,
                            marks={
                                0:'0',
                                1:'1',
                                2:'2',
                                3:'3',
                                4:'4',
                                5:'5',
                                10:'10',
                            },
                            value=[0,2]
                        ),
                        ]),
                    )
                ]),
            dbc.Row([
                dbc.CardHeader('Change global biomass compared to model'),
                dbc.CardBody(
                    dbc.Row([
                        dcc.Slider(
                            id='master_biomass_slider',
                            step=0.05,
                            marks=marks_biomass,
                            value=1,
                            tooltip={"placement": "bottom"})
                    ])
                )
            ]),
            dbc.Row([
                dbc.CardHeader('Change global lice infestation compared to model'),
                dbc.CardBody(
                    dbc.Row([
                        dcc.Slider(
                            id='master_lice_slider',
                            step=0.05,
                            marks=marks_lice,
                            value=1,
                            tooltip={"placement": "bottom"}
                        )
                    ])
                )
            ]),
            dbc.Row([
                dbc.Button("Refresh map",
                id='submit_map',
                color="primary",
                n_clicks=0,),
            ], className="d-grid gap-2"),
        ])
    ])
    ]),
    ]),
    dbc.Row([
        dbc.Card([
            dbc.CardHeader('Modify individual farm parameters'),
            dbc.CardBody([
                dbc.Accordion(
                    [dbc.AccordionItem([
                        mk_accordion_item(Filtered_names[i],farm_loc, i)],
                                    title=Filtered_names[i]) for i in range(len(Filtered_names))],
                        start_collapsed=True,
                    )
                ])
            ])
        ])
    ])
    return layout

################### TAB 3 #########################

tab3_layout= dbc.Card([
    dbc.CardHeader('Computation progress'),
    dbc.CardBody(
        dbc.Row([
            dcc.Graph(
                id='progress-curves',
                figure=go.Figure()
            )
        ])
    )
])

############# VARIABLES ##########################33
span=[0,2] # value extent
resolution_M=[50,100,200]
center_lat,center_lon=55.7,-5.23

if 'All_names' not in globals():
    print('loading dataset')
    uri='gs://sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[1])
    fs = gcsfs.GCSFileSystem()
    gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
    gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
    super_ds=open_zarr(gcsmap)
    All_names=np.array(list(super_ds.keys()))

if 'farm_loc' not in globals():
    npfile='/tmp/modelled_farms.npy'
    if not os.path.isfile(npfile):
            get_farm_data(npfile)
    farm_loc=np.load(npfile)
    print('farm loaded')

computed_farms=(farm_loc[:,0][:,None]==np.array(All_names)).any(axis=1)
Coeff=np.ones(len(All_names[computed_farms]))

#### import the Tabs
#from tabs.tab1 import tab1_layout
#from tabs.tab2 import tab2_layout
#from tabs.tab3 import tab3_layout

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
server=app.server
cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': '/tmp'
})
timeout = 300

@server.route('/_ah/warmup')
def warmup():
    """Warm up an instance of the app."""
    pass
    # Handle your warmup logic here, e.g. set up a database connection pool


app.title="Heatmap Dashboard"
app.layout = dbc.Container([
    #Store
    html.Div([
        dcc.Store(id='my-store'),
    #header
        html.Div([
            html.H1('Visualisation of the Clyde sealice densities'),
            html.P('Refrain from updating too frequently, this costs money ;)'),
            ]),
    # Define tabs
        html.Div([
            dbc.Tabs([
                dbc.Tab(tab1_layout(farm_loc,computed_farms,center_lat, center_lon, span),label='Interactive map',tab_id='tab-main',),
                dbc.Tab(tab2_layout(All_names[computed_farms],farm_loc),label='Tuning dashboard',tab_id='tab-tunning',),
                dbc.Tab(tab3_layout,label='Live progress graph',tab_id='tab-graph',),
                ])
            ])
        ])
])

@cache.memoize()
def global_store(r):
    print('using global store')
    fs = gcsfs.GCSFileSystem()
    gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[r])
    gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
    super_ds=open_zarr(gcsmap)
    All_names=list(super_ds.keys())
    coordinates=get_coordinates(super_ds.to_stacked_array('v', ['lat', 'lon']).sum(dim='v'))
    print('global store loaded')
    return super_ds,coordinates

@cache.memoize()
def mk_curves():
    fs= gcsfs.GCSFileSystem()
    file_list=fs.ls('sealice_db/Clyde_trajectories/')
    fig_p=go.Figure()
    for i in range(len(file_list)):
        gcs=gcsfs.mapping.GCSMap(file_list[i]+'/',
                                gcs=fs, check=True, create=False)
        try:
            with open_zarr(gcs) as ds:
                fig_p.add_trace(go.Scatter(x=ds.time,
                                       y=ds.copepodid.sum(axis=1).values,
                                       name=file_list[i].split('/')[-1],
                                       mode='lines'))
        except:
            print('cannot open:')
            print(file_list[i])
    return fig_p

@app.callback(
    [Output({'type':'biomass_slider', 'id':MATCH}, 'disabled'),
    Output({'type':'lice_slider', 'id':MATCH}, 'disabled')],
    Input({'type':'switch', 'id':MATCH},'on'),
    #State({'type':'switch', 'id':MATCH},'on')
)
def desactivate_farms(switch):
    return not switch, not switch

@app.callback(
    [Output({'type':'biomass_slider', 'id':ALL}, 'value'),
    Output({'type':'lice_slider', 'id':ALL}, 'value')],
    [Input('master_lice_slider', 'value'),
    Input('master_biomass_slider','value')],
    [State({'type':'biomass_slider', 'id':ALL},'value')]
)
def update_all_sliders(lice, biom, l):
    Nb=len(l)
    return (np.ones(Nb)*biom).tolist(), (np.ones(Nb)*lice).tolist()

@app.callback(
    [Output('heatmap', 'figure'),
    Output('heatmap_output', 'children')],
    Input('submit_map','n_clicks'),
    [State({'type':'switch', 'id':ALL},'on'),
    State({'type':'biomass_slider', 'id':ALL},'value'),
    State({'type':'lice_slider', 'id':ALL},'value'),
    State('span-slider','value') ,
    State('resolution-slider','value'),
    State('heatmap', 'figure')]
)
def redraw(n_clicks,idx, biomasses, lices, span, r, fig):
    idx=np.array(idx)
    biomasses=np.array(biomasses)
    lices=np.array(lices)
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

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8080, debug=True)
