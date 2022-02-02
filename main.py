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

#import googlecloudprofiler

# Profiler initialization. It starts a daemon thread which continuously
# collects and uploads profiles. Best done as early as possible.
#try:
    # service and service_version can be automatically inferred when
    # running on App Engine. project_id must be set if not running
    # on GCP.
#    googlecloudprofiler.start(verbose=3)
#except (ValueError, NotImplementedError) as exc:
#    print(exc)  # Handle errors here

import gcsfs
from  xarray import open_zarr
from google.cloud import storage
import numpy as np
import datashader as DS
import plotly.graph_objects as go
from colorcet import fire
from datashader import transfer_functions as tf
from datetime import datetime, timedelta
import os.path
from pyproj import Proj
import dash
from dash import dcc as dcc
from dash import html as html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import zarr
from flask_caching import Cache


def get_coordinates(agg):
    coords_lat, coords_lon = agg.coords['lat'].values, agg.coords['lon'].values
    coordinates=[[coords_lon[0], coords_lat[0]],
                       [coords_lon[-1], coords_lat[0]],
                       [coords_lon[-1], coords_lat[-1]],
                       [coords_lon[0], coords_lat[-1]]]
    return coordinates

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
                                        "Weight: %{marker.size:.0f}<br>",
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
                                        "Weight: %{marker.size:.0f}<br>",
                        marker=dict(color='darkgreen',
                                size=farm_loc[computed_farms][:,1].astype('int'),
                                sizemode='area',
                                sizeref=10,
                        ),
                        name="Processed farm",
                        hoverinfo='all',
                ))
    fig.update_layout(
                height=500,
                width=500,
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

def mk_img(ds_host, name_list, span):
    subds=ds_host[name_list]
    arr= subds.to_stacked_array('v', ['lat', 'lon']).sum(dim='v')
    return tf.shade(arr.where(arr>0).load(),
                    cmap=fire, how='linear',
                    span=span).to_pil()

##### variables ####
#r=1#choice of resolution
span=[0,2] # value extent
resolution_M=[100]
center_lat,center_lon=55.7,-5.23

print('loading dataset')
uri='gs://sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
fs = gcsfs.GCSFileSystem()
gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
super_ds=open_zarr(gcsmap)
All_names=list(super_ds.keys())

#coordinates=get_coordinates(super_ds.to_stacked_array('v', ['lat', 'lon']).sum(dim='v'))

npfile='/tmp/modelled_farms.npy'
if not os.path.isfile(npfile):
        get_farm_data(npfile)
farm_loc=np.load(npfile)
print('farm loaded')

computed_farms=(farm_loc[:,0][:,None]==np.array(All_names)).any(axis=1)
radio_items=[{'label':All_names[i],'value': All_names[i]} for i in range(len(All_names))]

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])

cache = Cache(app.server, config={
    'CACHE_TYPE': 'filesystem',
    'CACHE_DIR': '/tmp'
})
timeout = 300
app.title="Heatmap Dashboard"
app.layout = dbc.Container([
    html.Div([
        html.H1('Visualisation of the Clyde sealice densities'),
        html.P('Refrain from updating too frequently, this costs money ;)'),
        html.H3('Change resolution'),
        dcc.Slider(
            id='resolution-slider',
            min=0,
            max=3,
            step=None,
            marks={
                0:'30m',
                1:'50m',
                2:'100m',
                3:'200m',
            },
            value=2,
            disabled=True
             ),
        html.H4('Change colorscale'),
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
                18:'18'
            },
            value=[0,2]
        ),
        html.H3('Select farms'),
        dcc.Checklist(
        id='farm_names',
        options=radio_items,
        value=All_names),
        html.H3('Green dots are processed/ing farms, unit is copepodid/sqm/day'),
        dcc.Graph(
            id='heatmap',
            figure=go.Figure()
            ),

    ])
])



@cache.memoize(timeout=timeout)
def global_store():
    print('using global store')
    uri='gs://sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
    fs = gcsfs.GCSFileSystem()
    gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
    gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
    super_ds=open_zarr(gcsmap)
    All_names=list(super_ds.keys())
    coordinates=get_coordinates(super_ds.to_stacked_array('v', ['lat', 'lon']).sum(dim='v'))
    print('global store loaded')
    return super_ds,coordinates


@app.callback(
    Output('heatmap', 'figure'),
    [
    Input('span-slider','value'),
    Input('farm_names','value')
    ],
    [State('heatmap', 'figure')])
def update_figure(span, name_list, fig):

    if fig['data'] ==[]:
        fig=make_base_figure(farm_loc,computed_farms,
                            center_lat, center_lon, span)

    super_ds, coordinates=global_store()

    fig['data'][0]['marker']['cmax']=span[1]
    fig['data'][0]['marker']['cmin']=span[0]
    fig['layout']['mapbox']['layers']=[
                            {
                                "below": 'traces',
                                "sourcetype": "image",
                                "source": mk_img(super_ds, name_list, span),
                                "coordinates": coordinates[::-1]
                            }]

    return fig

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8080, debug=True)
