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

import googlecloudprofiler

# Profiler initialization. It starts a daemon thread which continuously
# collects and uploads profiles. Best done as early as possible.
try:
    # service and service_version can be automatically inferred when
    # running on App Engine. project_id must be set if not running
    # on GCP.
    googlecloudprofiler.start(verbose=3)
except (ValueError, NotImplementedError) as exc:
    print(exc)  # Handle errors here

import gcsfs
from  xarray import open_zarr
from rasterio.enums import Resampling
from google.cloud import storage
import numpy as np
import datashader as DS
import plotly.graph_objects as go
from colorcet import fire, bmy
from datashader import transfer_functions as tf
from datetime import datetime, timedelta
import os.path
import dash
from dash import dcc as dcc
from dash import html as html
from dash.dependencies import Input, Output, State, MATCH, ALL
import dash_bootstrap_components as dbc
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template

import dash_daq as daq

from flask_caching import Cache

#from callbacks import callbacks

def get_coordinates(agg):
    coords_lat, coords_lon = agg.coords['y'].values, agg.coords['x'].values
    coordinates=[[coords_lon[0], coords_lat[0]],
                       [coords_lon[-1], coords_lat[0]],
                       [coords_lon[-1], coords_lat[-1]],
                       [coords_lon[0], coords_lat[-1]]]
    return coordinates

def mk_img(ds_host, name_list, span, Coeff,cmp):
    '''
    Create an image to project on mabpox
    '''
    print('making raster...')
    subds=ds_host[name_list]
    for i in range(len(name_list)):
        subds[name_list[i]].values *=Coeff[i]
    arr= subds.to_stacked_array('v', ['y', 'x']).sum(dim='v')
    print('data stacked')
    return tf.shade(arr.where(arr>0).load(),
                    cmap=cmp, how='linear',
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

def make_base_figure(farm_loc,computed_farms, center_lat, center_lon, span, cmp, template):
    print('Making figure ...')
    fig= go.Figure()
    fig.add_trace(go.Scatter(x=[None], y=[None],marker=go.scatter.Marker(
                        colorscale=cmp,
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
                        marker=dict(color='#5bc0de',
                                size=farm_loc[~computed_farms][:,1].astype('int'),
                                sizemode='area',
                                sizeref=10,
                                showscale=False
                        )
                ))
    fig.add_trace(go.Scattermapbox(
                        lon=farm_loc[computed_farms][:,-1],
                        lat=farm_loc[computed_farms][:,-2],
                        text=farm_loc[computed_farms][:,0],
                        hovertemplate="<b>%{text}</b><br><br>" +
                                        "Biomass: %{marker.size:.0f} tons<br>",
                        marker=dict(color='#62c462',
                                size=farm_loc[computed_farms][:,1].astype('int'),
                                sizemode='area',
                                sizeref=10,
                                showscale=False
                        ),
                        name="Processed farm",
                        hoverinfo='all',
                ))
    fig.add_trace(go.Scattermapbox(name='Mapped farms'))
    fig.update_layout(
                height=500,
                hovermode='closest',
                showlegend=False,
                margin=dict(b=3, l=2, r=5, t=5),
                template=template,
                mapbox=dict(
                    bearing=0,
                    center=dict(
                        lat=center_lat,
                        lon=center_lon,
                    ),
                    pitch=0,
                    zoom=6.5,
                    style="carto-darkmatter",
                    ))
    return fig

def mk_map_pres(start, end):
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader('Legend'),
                dbc.CardBody([
                    html.Span([
                dbc.Badge('Processed/ing farms', color="success",pill=True),
                dbc.Badge('Farms awaiting processing', color='info',pill=True),
                dbc.Badge('Farms included in the map', color='light', pill=True),
                    ]),
                ])
            ]),
        ],width=3),
        dbc.Col([
            dbc.Card(
            dbc.CardBody([
                dbc.Alert('The size of the disks is proportional to the biomass', color='primary'),
                dbc.Alert('Hover a farm for more information', color='secondary'),
                dbc.Alert('Colorscale is the average density of copepodid per sqm from {} to {}'.format(start,end), color='primary'),
                dbc.Alert('A density of 2 copepodid/sqm/day leads to a 30% mortality of wild smolts each day', color='warning')
            ])
            )
        ],width=9),
    ]),

def tab1_layout(farm_loc,computed_farms,center_lat, center_lon, span, cmp, template):
    return dbc.Card([
    dbc.CardHeader('Clyde area'),
    dbc.CardBody([
        dbc.Card([
            dbc.CardBody(mk_map_pres(start, end))
        ]),
        dbc.Card([
            dbc.CardBody([
            dbc.Row([
                dcc.Graph(
                    id='heatmap',
                    figure=make_base_figure(farm_loc,computed_farms,
                                    center_lat, center_lon, span, cmp, template)
                    ),
                dcc.Loading(
                    id='figure_loading',
                    children=[html.Div(id='heatmap_output'),],
                    type='graph',
                    fullscreen=True
                )
                ])
                ])
            ]),
        ])
    ])
################# tab2 ###########################3

def mk_accordion_item(name, farm_loc, i, marks_biomass, marks_lice):
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
                html.P('Unit is lice/fish'),
                dcc.Slider(
                    id={'type':'lice_slider','id':i},
                    step=0.05,
                    marks=marks_lice,
                    value=0.5,
                    included=False,
                    tooltip={"placement": "bottom"},
                    disabled=False,
                    )],
            width=8)
        ], align='center')
    return item

def tab2_layout(Filtered_names,farm_loc):
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
        0.25:'0.25',
        0.5:'0.5',
        1:'1',
        2:'2',
        3:'3',
        4:'4',
        5:'5',
        6:'6',
        7:'7',
        8:'8'
    }
    layout= dbc.Card([
    dbc.Row([
    dbc.Card([
        dbc.CardHeader('Modify the global parameters'),
        dbc.CardBody([
            dbc.Row([
                dbc.Row([
                    dbc.Col([
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
                    ], width=8),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader('Choose the egg production model'),
                            dbc.CardBody(
                                dbc.Row([
                                    html.Div([
                                    daq.BooleanSwitch(
                                        id='egg_toggle',
                                        on=False
                                        ),
                                    html.Div(
                                        id='egg_toggle_output',
                                        style={'text-align':'center'}
                                        ),])
                                ])
                            )
                        ])
                    ], width=3),
                ]),
            dbc.Row([
                dbc.Card([
                    dbc.CardHeader('Change map colorscale range'),
                    dbc.CardBody(
                        dbc.Row([
                            html.P('(copepodid/sqm/day)'),
                            dcc.RangeSlider(
                                id='span-slider',
                                min=0,
                                max=20,
                                step=0.5,
                                marks={n:'%s' %n for n in range(21)},
                                value=[0,2]
                            ),
                            ]),
                        )
                    ])
                ]),
            dbc.Row([
                dbc.Card([
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
                ])
            ]),
            dbc.Row([
                dbc.Card([
                    dbc.CardHeader('Change global lice infestation compared to model (lice/fish)'),
                    dbc.CardBody(
                        dbc.Row([
                            dcc.Slider(
                                id='master_lice_slider',
                                step=0.05,
                                marks=marks_lice,
                                value=0.5,
                                tooltip={"placement": "bottom"},

                            )
                        ])
                    )
                ]),
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
                        mk_accordion_item(Filtered_names[i],farm_loc, i, marks_biomass, marks_lice)],
                                    title=Filtered_names[i]) for i in range(len(Filtered_names))],
                        start_collapsed=True,
                    )
                ])
            ])
        ])
    ])
    return layout

################### TAB 3 #########################


def mk_curves(start, end):
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
                                       mode='lines', stackgroup='one' ))
        except:
            print('cannot open:')
            print(file_list[i])
    fig_p.add_vrect(x0=start, x1=end,
                    annotation_text="mapped time interval",
                    annotation_position="top left",
                    opacity=0.25, line_width=0,fillcolor="gray")#"/"
    fig_p.update_layout(
        yaxis_title='Number of infective copepodids',
        margin=dict(b=15, l=15, r=5, t=5),
    )
    return fig_p

def tab3_layout(start, end):
    return dbc.Card([
    dbc.CardHeader('Computation progress'),
    dbc.CardBody(
        dbc.Row([
            dcc.Graph(
                id='progress-curves',
                figure=mk_curves(start, end)
            )
        ])
    )
])

############# VARIABLES ##########################33
span=[0,2] # value extent
resolution_M=[50,100,200]
center_lat,center_lon=55.7,-5.23
start, end = "2018-05-06", "2018-05-30"

######## fetch data #######

if 'All_names' not in globals():
    print('loading dataset')
    uri='gs://sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[1])
    fs = gcsfs.GCSFileSystem()
    gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
    gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
    super_ds=open_zarr(gcsmap).drop('spatial_ref')
    All_names=np.array(list(super_ds.keys()))

if 'farm_loc' not in globals():
    npfile='/tmp/modelled_farms.npy'
    if not os.path.isfile(npfile):
        get_farm_data(npfile)
    farm_loc=np.load(npfile)
    print('Farm loaded')

computed_farms=(farm_loc[:,0][:,None]==np.array(All_names)).any(axis=1)
Coeff=np.ones(len(All_names[computed_farms]))

coord_file='/tmp/master_coordinates.npy'
if not os.path.isfile(coord_file):
    get_farm_data(coord_file)
coordinates=np.load(coord_file)
print('Coordinates loaded')

######  manage themes #####
def mk_colorscale(cmp):
    '''
    format the colorscale for update in the callback
    '''
    idx =np.linspace(0,1,len(cmp))
    return np.vstack((idx, np.array(cmp))).T

def mk_template(template):
    '''
    Format the template for update in the callback
    '''
    fig=go.Figure()
    fig.update_layout(template=template)
    return fig['layout']['template']

template_theme1 = "slate"
template_theme2 = "sandstone"
load_figure_template([template_theme1,template_theme2])
url_theme1=dbc.themes.SLATE
url_theme2=dbc.themes.SANDSTONE
cmp1= fire
cmp2= bmy
carto_style1="carto-darkmatter"
carto_style2="carto-positron"
dbc_css = (
    "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates@V1.0.1/dbc.min.css"
)

app = dash.Dash(__name__,
                external_stylesheets=[url_theme1],#, dbc_css
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
    return "it is warm"
    # Handle your warmup logic here, e.g. set up a database connection pool


app.title="Heatmap Dashboard"
app.layout = dbc.Container([
    #Store
    html.Div([
        dcc.Store(id='my-store'),
    #header
        html.Div([
            html.H1('Visualisation of the Clyde sealice infestation'),
            ThemeSwitchAIO(aio_id='theme',
                    icons={"left": "fa fa-sun", "right": "fa fa-moon"},
                    themes=[url_theme1, url_theme2])
            #html.P('Refrain from updating too frequently, this costs money ;)'),
            ]),
    # Define tabs
        html.Div([
            dbc.Tabs([
                dbc.Tab(tab1_layout(farm_loc,computed_farms,center_lat, center_lon, span, cmp1, template_theme1),label='Interactive map',tab_id='tab-main',),
                dbc.Tab(tab2_layout(All_names[computed_farms],farm_loc),label='Tuning dashboard',tab_id='tab-tunning',),
                dbc.Tab(tab3_layout(start, end),label='Live progress graph',tab_id='tab-graph',),
                ])
            ])
        ])
], fluid=True, className='dbc')


@cache.memoize()
def global_store(r):
    print('using global store')
    fs = gcsfs.GCSFileSystem()
    gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[r])
    gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
    super_ds=open_zarr(gcsmap).drop('spatial_ref')
    All_names=list(super_ds.keys())
    coordinates=np.load(coord_file)
    #get_coordinates(super_ds.to_stacked_array('v', ['y', 'x']).sum(dim='v'))
    print('global store loaded')
    return super_ds,coordinates



@app.callback(
    [Output({'type':'biomass_slider', 'id':MATCH}, 'disabled'),
    Output({'type':'lice_slider', 'id':MATCH}, 'disabled')],
    Input({'type':'switch', 'id':MATCH},'on'),
)
def desactivate_farms(switch):
    return not switch, not switch

@app.callback(
    Output('egg_toggle_output','children'),
    Input('egg_toggle','on')
)
def toggle_egg_models(eggs):
    if eggs:
        return 'Stien (2005)'
    else:
        return 'Rittenhouse et al. (2016)'

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
    Output('progress-curves','figure'),
    Output('heatmap_output', 'children')],
    [Input('submit_map','n_clicks'),
    Input(ThemeSwitchAIO.ids.switch("theme"), "value"),
    ],
    [
    State('egg_toggle','on'),
    State({'type':'switch', 'id':ALL},'on'),
    State({'type':'biomass_slider', 'id':ALL},'value'),
    State({'type':'lice_slider', 'id':ALL},'value'),
    State('span-slider','value') ,
    State('resolution-slider','value'),
    State('heatmap', 'figure'),
    State('progress-curves','figure'),
    ]
)
def redraw(n_clicks, toggle, egg, idx, biomasses, lices, span, r, fig, curves):
    ctx = dash.callback_context
    ### toggle themes
    template = template_theme1 if toggle else template_theme2
    cmp= cmp1 if toggle else cmp2
    carto_style= carto_style1 if toggle else carto_style2
    fig['layout']['template']=mk_template(template)
    curves['layout']['template']=mk_template(template)
    fig['layout']['mapbox']['style']=carto_style
    #fig.update_traces(marker=dict(colorscale=cmp))
    fig['data'][0]['marker']['colorscale']=mk_colorscale(cmp)
    #print(fig['data'][0]['marker']['colorscale'])

    ### update heatmap
    if ctx.triggered[0]['prop_id'] == 'submit_map.n_clicks':
        idx=np.array(idx)
        biomasses=np.array(biomasses)
        lices=np.array(lices, dtype='float')*2
        # modify egg model from Rittenhouse (16.9) to Stein (30)
        if egg:
            lices *= 30/16.9
        if idx.sum()>0:
            name_list=np.array(All_names)[computed_farms][idx]
            Coeff=biomasses[idx]*lices[idx]
            super_ds, coordinates=global_store(r)

            selected_farms=(farm_loc[:,0][:,None]==name_list).any(axis=1)
            fig['data'][0]['marker']['cmax']=span[1]
            fig['data'][0]['marker']['cmin']=span[0]
            fig['data'][3]=go.Scattermapbox(lat=farm_loc[selected_farms][:,-2],
                                lon=farm_loc[selected_farms][:,-1],
                                marker=dict(color='#e9ecef', size=4, showscale=False),
                                name='Mapped farms')
            fig['layout']['mapbox']['layers']=[
                                    {
                                        "below": 'traces',
                                        "sourcetype": "image",
                                        "source": mk_img(super_ds, name_list, span, Coeff,cmp),
                                        "coordinates": coordinates[::-1]
                                    }]
        else:
            # add a message?
            fig['data'][3]={}
            fig['layout']['mapbox']['layers']=[]
    return fig, curves, None

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8080, debug=True)
