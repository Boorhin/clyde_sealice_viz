import dash_bootstrap_components as dbc
from dash import dcc as dcc
from dash import html as html
import plotly.graph_objects as go
from colorcet import fire
#from main import farm_loc,computed_farms,center_lat, center_lon, span
#import callbacks

#### GET SELECTION DATA
# @app.callback(
#     Output('selected-data', 'children'),
#     Input('basic-interactions', 'selectedData'))
# def display_selected_data(selectedData):
#     return json.dumps(selectedData, indent=2)
# {
#   "points": [
#     {
#       "curveNumber": 0,
#       "pointNumber": 0,
#       "pointIndex": 0,
#       "x": 1,
#       "y": 1,
#       "customdata": [
#         1
#       ]
#     },
#     {
#       "curveNumber": 1,
#       "pointNumber": 0,
#       "pointIndex": 0,
#       "x": 1,
#       "y": 3,
#       "customdata": [
#         3
#       ]
#     }
#   ],
#   "lassoPoints": {
#     "x": [
#       0.9699225729600952,
#       0.9460988683740321,
#       0.9356759976176294,
#       0.9371649791542584,
#       0.9416319237641453,
#       0.9416319237641453,
#       0.9460988683740321,
#       0.9624776652769504,
#       0.9803454437164979,
#       1.0235259082787374,
#       1.0890410958904109,
#       1.1098868374032163,
#       1.114353782013103,
#       1.1039309112567004,
#       1.0875521143537819,
#       1.0488385944014293,
#       1.0235259082787374,
#       1.0220369267421083
#     ],
#     "y": [
#       3.415192190359975,
#       3.012507626601586,
#       2.7379499694935934,
#       2.4999999999999996,
#       2.197986577181208,
#       1.1821232458816349,
#       0.8892617449664426,
#       0.7794386821232455,
#       0.724527150701647,
#       0.724527150701647,
#       0.8709579011592431,
#       0.9350213544844413,
#       1.0814521049420376,
#       2.069859670530811,
#       2.4633923123856007,
#       3.0674191580231844,
#       3.314521049420378,
#       3.3602806589383767
#     ]
#   }
# }

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
