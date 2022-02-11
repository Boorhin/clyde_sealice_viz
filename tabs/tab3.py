import dash_bootstrap_components as dbc
from dash import dcc as dcc
from dash import html as html
import gcsfs
from  xarray import open_zarr
import plotly.graph_objects as go
#import callbacks


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
