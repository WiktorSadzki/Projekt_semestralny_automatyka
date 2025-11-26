import numpy as np
import plotly.express as px
from dash import Dash, html, dcc, callback, Output, Input
from parameters import Parameters
from controller import Controller


def make_graph(x, y, title, labels):
    fig = px.line(
        x=x,
        y=y,
        title=title,
        labels=labels
    )

    fig.update_traces(line=dict(color='#add8e6', width=3))

    fig.update_layout(
        plot_bgcolor='#FFF',
        paper_bgcolor='white',
        title_font_color="#333",

        xaxis=dict(
            showline=True,
            linewidth=1,
            linecolor='black',
            mirror=True,
            gridcolor='lightgrey'
        ),
        yaxis=dict(
            showline=True,
            linewidth=1,
            linecolor='black',
            mirror=True,
            gridcolor='lightgrey'
        )
    )

    return fig


def main():
    params_static = Parameters()

    DEFAULT_C = 100.0
    DEFAULT_h = 0.05
    DEFAULT_Q_load = 100.0
    DEFAULT_Q_W = 10.0
    DEFAULT_R_W = 1.0

    app = Dash(__name__)

    app.layout = html.Div([
        html.H2("Sterowanie temperaturą obudowy"),

        # Sekcja kontrolek
        html.Div([
            html.H3("Konfiguracja Parametrów Systemu"),

            # Slider: Pojemność Cieplna (C)
            html.Div([
                html.Label(f"Pojemność cieplna C [J/K]: {DEFAULT_C}", id='label-C'),
                dcc.Slider(
                    min=50, max=200, step=10, id='input-C', value=DEFAULT_C,
                    marks={i: str(i) for i in range(50, 201, 50)}
                ),
            ], style={'marginBottom': '20px'}),

            # Slider: Współczynnik konwekcji (h)
            html.Div([
                html.Label(f"Współczynnik konwekcji h [W/(m²K)]: {DEFAULT_h}", id='label-h'),
                dcc.Slider(
                    min=0.01, max=0.1, step=0.01, id='input-h', value=DEFAULT_h,
                    marks={i / 100: str(i / 100) for i in range(1, 11, 2)}
                ),
            ], style={'marginBottom': '20px'}),

            # Slider: Moc cieplna (Q_load)
            html.Div([
                html.Label(f"Moc cieplna wytwarzana przez poddzespoły Q_load [W]: {DEFAULT_Q_load}", id='label-Q_load'),
                dcc.Slider(
                    min=50, max=200, step=10, id='input-Q_load', value=DEFAULT_Q_load,
                    marks={i: str(i) for i in range(50, 201, 50)}
                ),
            ], style={'marginBottom': '30px'}),

            # Dropdown: Waga Q
            html.Div([
                html.Label("Waga błędu Q_weight:"),
                dcc.Dropdown(
                    id='input-Q_weight',
                    options=[
                        {'label': '1', 'value': 1.0},
                        {'label': '10', 'value': 10.0},
                        {'label': '50', 'value': 50.0},
                        {'label': '100', 'value': 100.0}
                    ],
                    value=DEFAULT_Q_W,
                    clearable=False
                )
            ], style={'marginBottom': '20px'}),

            # Dropdown: Waga R
            html.Div([
                html.Label("Waga zmian sterowania R_weight:"),
                dcc.Dropdown(
                    id='input-R_weight',
                    options=[
                        {'label': '0.1', 'value': 0.1},
                        {'label': '1', 'value': 1.0},
                        {'label': '5', 'value': 5.0},
                        {'label': '10', 'value': 10.0}
                    ],
                    value=DEFAULT_R_W,
                    clearable=False
                )
            ], style={'marginBottom': '30px'}),

            # Temperatura Zadana T_set
            html.Div("Temperatura Zadana T_set [°C]:", className="mt-4"),
            dcc.Slider(
                min=30,
                max=80,
                step=1,
                id='setpoint',
                value=50,
                marks={i: str(i) for i in range(30, 81, 5)}
            ),

        ], style={'padding': '20px', 'border': '1px solid #ccc', 'borderRadius': '5px', 'marginBottom': '20px',
                  'backgroundColor': 'white'}),

        # Sekcja wykresu
        dcc.Graph(id='graph'),

    ],
        style={
            'padding': '5%',
            'margin': '0 auto',
            'backgroundColor': 'white'
        })

    @callback(
        Output('graph', 'figure'),
        Output('label-C', 'children'),
        Output('label-h', 'children'),
        Output('label-Q_load', 'children'),
        Input('setpoint', 'value'),
        Input('input-C', 'value'),
        Input('input-h', 'value'),
        Input('input-Q_load', 'value'),
        Input('input-Q_weight', 'value'),
        Input('input-R_weight', 'value')
    )
    def update_output(setpoint, C_new, h_new, Q_load_new, Q_w_new, R_w_new):
        C_label = f"Pojemność cieplna C [J/K]: {C_new}"
        h_label = f"Współczynnik konwekcji h [W/(m²K)]: {h_new:.2f}"
        Q_load_label = f"Moc cieplna CPU Q_load [W]: {Q_load_new}"

        params_static = Parameters()

        params_static.C = C_new
        params_static.h = h_new
        params_static.Q_load = Q_load_new
        params_static.Q_weight = Q_w_new
        params_static.R_weight = R_w_new

        T_in = params_static.T_in
        U_max = params_static.U_max
        Ts = params_static.Ts
        simulation_steps = params_static.simulation_steps
        Q_load = Q_load_new

        controller = Controller(params_static)

        time = [0.0]
        temperature = [T_in]
        u_history = [0.0]

        u_prev = 0.0
        T_curr = T_in

        for _ in range(simulation_steps):
            u_optimal = controller.optimize_control(
                T_curr=T_curr,
                T_set=setpoint,
                u_prev=u_prev,
                Q_load=Q_load
            )

            u_optimal = np.clip(u_optimal, 0.0, U_max)

            T_next = controller.predict_temperature(
                T_k=T_curr,
                u_k=u_optimal,
                Q_load=Q_load
            )

            time.append(time[-1] + Ts)
            temperature.append(T_next)
            u_history.append(u_optimal)

            T_curr = T_next
            u_prev = u_optimal

        graph = make_graph(
            x=time,
            y=temperature,
            title=f"Temperatura obudowy (T_set={setpoint}°C, Q={Q_w_new}, R={R_w_new})",
            labels={'x': 'Czas [s]', 'y': 'Temperatura [°C]'}
        )
        return graph, C_label, h_label, Q_load_label

    app.run(debug=True, host='127.0.0.1')


if __name__ == '__main__':
    main()