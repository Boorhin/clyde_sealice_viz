## control the map in tab1_content
import dash_daq as daq
import dash
from dash import dcc as dcc
from dash import html as html
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
#from main import All_names,computed_farms,farm_loc
#import callbacks

# __init__
# fs = gcsfs.GCSFileSystem()
# gcs_bucket_name ='sealice_db/aggregations_{}m/master.zarr'.format(resolution_M[0])
# gcsmap = gcsfs.mapping.GCSMap(gcs_bucket_name, gcs=fs, check=True, create=False)
# super_ds=open_zarr(gcsmap)
# All_names=list(super_ds.keys())
#Filtered_names=All_names[computed_farms]

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
                    id={'type':'switch','id':i,'name':name},
                    on=True,
                    label="Desactivate farm",
                    labelPosition="top"
                    )],
                width=3),
            dbc.Col([
                html.H3('Modelled Biomass {} tons'.format(data[1])),
                html.H3('Tune Farm biomass:'),
                dcc.Slider(
                    id={'type':'biomass_slider','id':i,'name':name},
                    step=0.05,
                    marks=marks_biomass,
                    value=1,
                    included=False,
                    tooltip={"placement": "bottom"},
                    ),
                html.H3('Tune lice infestation:'),
                html.P('Unit is infective Copepodid/day/sqm'),
                dcc.Slider(
                    id={'type':'lice_slider','id':i,'name':name},
                    step=0.05,
                    marks=marks_lice,
                    value=1,
                    included=False,
                    tooltip={"placement": "bottom"}
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
