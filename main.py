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

import gcsfs
import xarray as xr
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

def list_blobs_with_prefix(bucket_name, prefix, delimiter=None):
    blobs = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter=delimiter)
    print("Blobs:")
    for blob in blobs:
        print(blob.name)
    if delimiter:
        print("Prefixes:")
        for prefix in blobs.prefixes:
            print(prefix)
    return list(blobs.prefixes)

def grab_farm_ds(farm_name, time_slice=None, shift=0):
    '''
    grab the data of a farm and recover the data through a slice of time
    time=slice("2000-01-01", "2000-01-02")
    '''
    fs = gcsfs.GCSFileSystem()
    gcs_bucket_name ='sealice_db/'+farm_name
    gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
    with xr.open_zarr(gcsmap) as ds:
    	if time_slice==None:
  	      time_slice=ds.time
    	subds=ds.loc[dict(time=time_slice)].where(np.greater(ds.copepodid,0), drop=True)
                #np.logical_and(
                #np.less(ds.age_seconds, timedelta(days=18).total_seconds()),
    	mask=np.ma.masked_invalid(subds['copepodid'].values).mask
    return {
        'trajectory':('trajectory', np.arange(np.array(subds['lat'].values[~mask].ravel().shape).prod())+shift),
        'lat':('trajectory',subds['lat'].values[~mask].ravel()),
        'lon':('trajectory',subds['lon'].values[~mask].ravel()),
        'copepodid':('trajectory',subds['copepodid'].values[~mask].ravel()),
        #'age_seconds':('trajectory',subds['age_seconds'][filt].values.ravel()),
            }

def get_farm_data(npfile):
    '''
    Download the farm parameters
    '''
    from google.cloud import storage
    client = storage.Client()
    bucket = client.get_bucket('sealice_db')
    blob = bucket.blob(npfile)
    blob.download_to_filename(npfile)

def scaling_func(center_lat,center_lon, resolution_M):
    '''
    Allow calculating metric resolutions near a center point.
    '''
    p=Proj("epsg:27700", preserve_units=False)
    x,y=p(center_lon,center_lat)
    res_h,res_v=[],[]
    for res in resolution_M:
        lon,lat=(p(x+res,y+res, inverse=True))
        res_h.append(lon-center_lon)
        res_v.append(lat-center_lat)
    return res_h,res_v

def is_not_computed(name):
    fs=gcsfs.GCSFileSystem()
    farm_names= fs.ls('sealice_db/Clyde_trajectories')
    ff=[]
    for n in farm_names:
    	ff.append(n.split('/')[-2])
    print (ff)
    if name in ff:
        return False
    else:
        return True

def concatenate_data(farm_names, store, time_slice=None):
    '''
    Concatenate the different trajectory dataset into a single file
    '''
    import zarr
    # should integrate zarr appending here
    ds_host=xr.Dataset()
    ds_host.attrs['computed']=[]
    selected_farms=farm_names
    #selected_farms.pop(3)
    for farm in selected_farms:
        print('Merging farm: ',farm)
        if farm not in ds_host.attrs['computed']:
            if 'trajectory' in list(ds_host.coords):
                shift+=len(ds_host.trajectory)
            else:
                shift=0
            ds_host=ds_host.combine_first(xr.Dataset(grab_farm_ds(farm, time_slice=None, shift=shift)))
            ds_host.attrs['computed'].append(farm)
            print('{} done'.format(farm))
        else:
        	print('farm already merged')
    print('All farms merged')
    ds_host.to_zarr(store)
    zarr.consolidate_metadata(store)
    return

def list_computed(farm_names, farm_loc):
    ff=[]
    for n in farm_names:
        ff.append(n.split('/')[-2])
    return (farm_loc[:,0][:,None]==np.array(ff)).any(axis=1)

def rasterize(ds_host, r, resolution_M, days, res_h,res_v, span=None):
    print('rasterizing...')
    V_arc,H_arc=ds_host.lat.max()-ds_host.lat.min(),ds_host.lon.max()-ds_host.lon.min()
    ds_host['norm_cop']=ds_host.copepodid/(days*resolution_M[r]**2)
    #compute the canvas
    cvs = DS.Canvas(plot_width=int(H_arc//res_h[r]), \
                plot_height=int(V_arc//res_v[r]))

    agg = cvs.points(ds_host,
                         x='lon',
                         y='lat',
                         agg=DS.count('norm_cop'))
    coords_lat, coords_lon = agg.coords['lat'].values, agg.coords['lon'].values
    coordinates=[[coords_lon[0], coords_lat[0]],
                       [coords_lon[-1], coords_lat[0]],
                       [coords_lon[-1], coords_lat[-1]],
                       [coords_lon[0], coords_lat[-1]]]
    print('rasterizing done.')
    return tf.shade(agg, cmap=fire, how='linear', span=span).to_pil(), coordinates

def Mk_figure(span, r, farm_loc, computed_farms,ds_host,resolution_M, days, res_h,res_v):
    print('Making figure ...')
    img, coordinates = rasterize(ds_host, r, resolution_M, days, res_h,res_v, span=span)
    fig= go.Figure()
    fig.add_trace(go.Scatter(x=[None], y=[None],marker=go.scatter.Marker(
                    colorscale=fire,
                    cmax=span[1],
                    cmin=span[0],
                    showscale=True,
                    ),
                showlegend=False))
    fig.add_trace(go.Scattermapbox(
                        lon=farm_loc[:,-1],
                        lat=farm_loc[:,-2],
                        text=[farm_loc[:,0]],
                        name="Awaiting completion farm",
                        hoverinfo='all',
                        marker=dict(color='lightblue')
                ))
    fig.add_trace(go.Scattermapbox(
                        lon=farm_loc[computed_farms][:,-1],
                        lat=farm_loc[computed_farms][:,-2],
                        text=[farm_loc[computed_farms][:,0]],
                        marker={'size':8,'color':'darkgreen'},
                        name="Processed farm",
                        hoverinfo='all',
                ))
    fig.add_annotation(
                xref="x domain",
                yref="y domain",
                x=0.75,
                y=0.9,
                text="Resolution {} m".format(resolution_M[r]),
                font={
                    "color":"White",
                    'size':22,}
                )
    fig.update_layout(
            height=800,
            width=800,
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
                layers=[
                        {
                            "below": 'traces',
                            "sourcetype": "image",
                            "source": img,
                            "coordinates": coordinates[::-1]
                        }]))
    return fig


storage_client = storage.Client()
prefix='Clyde_trajectories/'
farm_names=list_blobs_with_prefix('sealice_db',prefix=prefix,delimiter='/')

### load the farm data
npfile='modelled_farms.npy'
if not os.path.isfile(npfile):
    get_farm_data(npfile)
farm_loc=np.load(npfile)

# scale
resolution_M=[30,50,100,200]
center_lat,center_lon=55.7,-5.23
res_h,res_v= scaling_func(center_lat,center_lon, resolution_M)

# build the database NEXT zarr it so that we don't recompute it each time
fs = gcsfs.GCSFileSystem()
gcs_bucket_name ='sealice_db/trajectories_archive.zarr'
gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
ds_host=xr.open_zarr(store, mode='r')

# list computed farms
computed_farms=list_computed(farm_names, farm_loc)

r=1#choice of resolution
span=[0,18] # value extent
days=31+8 # duration hardcoded will need to be added as attribute of ds_host
span=[0,18]

#img=rasterize(ds_host, r, resolution_M, days, res_h,res_v, span=span)

app = dash.Dash(__name__,
                external_stylesheets=[dbc.themes.BOOTSTRAP],
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])

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
            value=1
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
            value=[0,4]
        ),
        html.H3('Green dots are processed/ing farms, unit is copepodid/sqm/day'),
        dcc.Graph(
            id='heatmap',
            figure=Mk_figure(span, r, farm_loc, computed_farms,ds_host,resolution_M, days, res_h,res_v))
    ])
])

@app.callback(
    Output('heatmap', 'figure'),
    [Input('resolution-slider','value'),
    Input('span-slider','value'),
    ])
def update_figure(r,span):
    return Mk_figure(span, r, farm_loc, computed_farms,ds_host,resolution_M, days, res_h,res_v)

if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=9090, debug=True)
