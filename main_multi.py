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
import zarr
from flask_caching import Cache

from callbacks import callbacks

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
    subds=ds_host[name_list]
    for i in range(len(name_list)):
        subds[name_list[i]].values *=Coeff[i]
    arr= subds.to_stacked_array('v', ['lat', 'lon']).sum(dim='v')
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


span=[0,2] # value extent
resolution_M=[50,100,200]
center_lat,center_lon=55.7,-5.23

if 'All_names' not in locals():
    print('loading dataset')
    uri='gs://sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[1])
    fs = gcsfs.GCSFileSystem()
    gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
    gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
    super_ds=open_zarr(gcsmap)
    All_names=np.array(list(super_ds.keys()))

if 'farm_loc' not in locals():
    npfile='/tmp/modelled_farms.npy'
    if not os.path.isfile(npfile):
            get_farm_data(npfile)
    farm_loc=np.load(npfile)
    print('farm loaded')

computed_farms=(farm_loc[:,0][:,None]==np.array(All_names)).any(axis=1)
Coeff=np.ones(len(All_names[computed_farms]))

#### import the Tabs
from tabs.tab1 import tab1_layout
from tabs.tab2 import tab2_layout
from tabs.tab3 import tab3_layout

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

@cache.memoize(timeout=timeout)
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

@cache.memoize(timeout=timeout)
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



if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8080, debug=True)
