import numpy as np
import plotly.express as px
import diskcache
from dash import Dash, html, dcc, callback, Output, Input, State, DiskcacheManager
import dash_bootstrap_components as dbc

from parameters import Parameters
from controller import Controller
from load_profile import cpu_load, gpu_load, ram_load

cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)

def make_graph(x, ys, title, labels, hline=None):
    fig = px.line(title=title, labels=labels)

    color_map = {}
    if hline is not None:
        if isinstance(hline, (int, float)):
            lines_to_draw = [(hline, "red", "")]
        else:
            lines_to_draw = hline

        for line, color, label in lines_to_draw:
            if label:
                color_map[label] = color

        i = 0
        for line, color, label in lines_to_draw:
            x_offset = 0.99 - (i % 2) * 0.15
            fig.add_hline(
                y=line,
                line_dash="dash",
                line_color=color,
                annotation_font_color=color,
                annotation_text=f"Limit {label}: {line}",
                annotation_x=x_offset,
                annotation_position="top right",
                annotation_font_size=10,
            )
            i += 1

    for name, y in ys.items():
        fig.add_scatter(x=x, y=y, name=name, mode='lines'),
        line = dict(color=color_map.get(name, None))

    fig.update_layout(
        title=title,
        xaxis_title=labels.get("x", ""),
        yaxis_title=labels.get("y", ""),
        plot_bgcolor='#FCF9EA',
        paper_bgcolor='#A8BBA3',
        title_font_color="#333",
        xaxis=dict(showline=True, linewidth=1, linecolor='black',
                   mirror=True, gridcolor='rgba(0,0,0,0.12)'),
        yaxis=dict(showline=True, linewidth=1, linecolor='black',
                   mirror=True, gridcolor='rgba(0,0,0,0.12)'),
    )
    return fig

@callback(
    Output("graph-temp", "figure"),
    Output("graph-pwm", "figure"),
    Output("graph-error", "figure"),
    Output("graph-sound", "figure"),
    Output("graph-fan-power", "figure"),
    Output("graph-power", "figure"),
    Input("button", "n_clicks"),
    State("mode", "value"),
    State("coolant", "value"),
    State("op_mode", "value"),
    State("mat_cpu", "value"),
    State("mat_gpu", "value"),
    State("mat_ram", "value"),
    State("T_amb", "value"),
    State("N_horizon", "value"),
    State("T_limit_CPU", "value"),
    State("T_limit_GPU", "value"),
    State("T_limit_RAM", "value"),
    State("T_limit_AIR", "value"),
    State("advanced_options", "value"),
    background=True,
    manager=background_callback_manager,
    progress=[
        Output("progress-bar", "value"),
        Output("progress-text", "children")
    ],
    running=[
        (Output("button", "disabled"), True, False),
        (Output("progress-container", "style"), {"display": "block", "margin": "20px 0"}, {"display": "none"}),
    ],
    prevent_initial_call=True
)

def update_output(set_progress, n_clicks, mode, coolant, op_mode, mat_cpu, mat_gpu, mat_ram,
                  T_amb, N_horizon, T_limit_CPU, T_limit_GPU, T_limit_RAM, T_limit_AIR, advanced_options):
    # Inicjalizacja parametrów
    p = Parameters()
    p.T_limit_CPU = T_limit_CPU
    p.T_limit_GPU = T_limit_GPU
    p.T_limit_RAM = T_limit_RAM
    p.T_limit_AIR = T_limit_AIR
    p.T_amb = T_amb
    p.N = N_horizon

    # Radiacja
    p.enable_radiation = "radiation" in (advanced_options or [])

    # Aktualizacja materiałów radiatorów
    p.update_heatsink_material(mat_cpu, mat_gpu, mat_ram)

    # Aktualizacja cieczy chłodzącej
    p.update_coolant(coolant)

    # Aktualizacja wag MPC
    p.set_operation_mode(op_mode)

    # Inicjalizacja kontrolera
    controller = Controller(p)

    # Stan początkowy
    T = np.array([T_amb, T_amb, T_amb, T_amb])
    u_prev = np.array([0.0, 0.0, 0.0])

    # Tablice do zapisu wyników
    time = [0.0]
    T_CPU_hist = [T[0]]
    T_GPU_hist = [T[1]]
    T_AIR_hist = [T[2]]
    T_RAM_hist = [T[3]]

    U_CPU_hist = [0.0]
    U_GPU_hist = [0.0]
    U_CASE_hist = [0.0]

    Q_load_CPU_hist = []
    Q_load_GPU_hist = []
    Q_load_RAM_hist = []

    total_steps = p.simulation_steps
    for k in range(total_steps+1):
        percent = int((k / total_steps) * 100)
        set_progress((percent, f"Trwa symulacja: {percent}% ({k}/{total_steps})"))

        # Obciążenie cieplne
        Qc = cpu_load(k, mode)
        Qg = gpu_load(k, mode)
        Qr = ram_load(k, mode)

        # MPC - obliczenie optymalnego sterowania
        u = controller.step(T, u_prev, Qc, Qg, Qr)
        u = np.clip(u, 0.0, p.U_max)

        # Predykcja nowego stanu
        T = controller.predict(T, u, Qc, Qg, Qr)

        # Zapis
        time.append(time[-1] + p.Ts)
        T_CPU_hist.append(T[0])
        T_GPU_hist.append(T[1])
        T_AIR_hist.append(T[2])
        T_RAM_hist.append(T[3])

        U_CPU_hist.append(u[0])
        U_GPU_hist.append(u[1])
        U_CASE_hist.append(u[2])

        Q_load_CPU_hist.append(Qc)
        Q_load_GPU_hist.append(Qg)
        Q_load_RAM_hist.append(Qr)

        u_prev = u

    # Uchyb regulacji
    CPU_error = [T_limit_CPU - t for t in T_CPU_hist]
    GPU_error = [T_limit_GPU - t for t in T_GPU_hist]
    RAM_error = [p.T_limit_RAM - t for t in T_RAM_hist]
    AIR_error = [T_limit_AIR - t for t in T_AIR_hist]

    # Hałas [dB]
    CPU_dB = controller.fan_noise_dB(U_CPU_hist, p.L_max_CPU)
    GPU_dB = controller.fan_noise_dB(U_GPU_hist, p.L_max_GPU)
    CASE_dB = controller.fan_noise_dB(U_CASE_hist, p.L_max_case)

    # Całkowity hałas
    total_dB = 10 * np.log10(10 ** (CPU_dB / 10) + 10 ** (GPU_dB / 10) + 10 ** (CASE_dB / 10))

    # Przybliżona moc wentylatorów (W)
    P_max_CPU = 5.0
    P_max_GPU = 7.0
    P_max_CASE = 5.0

    P_CPU_hist = [(u / 100) ** 3 * P_max_CPU for u in U_CPU_hist]
    P_GPU_hist = [(u / 100) ** 3 * P_max_GPU for u in U_GPU_hist]
    P_CASE_hist = [(u / 100) ** 3 * P_max_CASE for u in U_CASE_hist]

    title_suffix = f" ({mode} | {coolant} | {op_mode})"

    fig_T = make_graph(
        time,
        {
            "Procesor": T_CPU_hist,
            "Karta graficzna": T_GPU_hist,
            "Pamięć RAM": T_RAM_hist,
            "Wnętrze obudowy": T_AIR_hist
        },
        f"Temperatury systemu" + title_suffix,
        {"x": "Czas [s]", "y": "Temperatura [°C]"},
        hline=[
            (T_limit_CPU, "red", "temperatury CPU"),
            (T_limit_GPU, "blue", "temperatury GPU"),
            (T_limit_RAM, "orange", "temperatury RAM"),
            (T_limit_AIR, "green", "temperatury w obudowie"),
        ]
    )

    fig_U = make_graph(
        time,
        {
            "Wentylator procesora": U_CPU_hist,
            "Wentylator karty graficznej": U_GPU_hist,
            "Wentylator obdudowy": U_CASE_hist
        },
        f"Sterowanie PWM" + title_suffix,
        {"x": "Czas [s]", "y": "PWM [%]"},
        hline=[(100, "red", "")]
    )

    fig_E = make_graph(
        time,
        {
            "Procesor": CPU_error,
            "Karta graficzna": GPU_error,
            "Pamięć RAM": RAM_error,
            "Wnętrze obudowy": AIR_error
        },
        f"Uchyb regulacji (zapas do limitu)" + title_suffix,
        {"x": "Czas [s]", "y": "Zapas [°C]"}
    )

    fig_S = make_graph(
        time,
        {
            "Wentyltaor procesora": CPU_dB,
            "Wentylator karty graficznej": GPU_dB,
            "Wentylator obudowy": CASE_dB,
            "Całkowity": total_dB
        },
        f"Hałas wentylatorów" + title_suffix,
        {"x": "Czas [s]", "y": "Poziom dźwięku [dB]"}
    )

    fig_FP = make_graph(
        time,
        {
            "Wentylator CPU": P_CPU_hist,
            "Wentylator GPU": P_GPU_hist,
            "Wentylator obudowy": P_CASE_hist,
            "Łącznie": [cpu + gpu + case for cpu, gpu, case in zip(P_CPU_hist, P_GPU_hist, P_CASE_hist)]
        },
        f"Zużycie energii przez wentylatory" + title_suffix,
        {"x": "Czas [s]", "y": "Moc [W]"}
    )

    time_power = time[1:]  # Przesunięcie czasu (bo Q_load ma len-1)
    fig_P = make_graph(
        time_power,
        {
            "Obciążenie procesora": Q_load_CPU_hist,
            "Obciążenie karty graficznej": Q_load_GPU_hist,
            "Obciążenie pamięci RAM": Q_load_RAM_hist,
        },
        f"Obciążenie cieplne" + title_suffix,
        {"x": "Czas [s]", "y": "Moc [W]"}
    )

    return fig_T, fig_U, fig_E, fig_S, fig_FP, fig_P

def main():
    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        background_callback_manager=background_callback_manager
    )

    app.layout = html.Div(className="main", children=[

        html.H2("Model MPC chłodzenia PC z radiacją",
                style={"textAlign": "center", "color": "#84946A"}),

        html.Div(className="parameters", children=[
            html.Label("Tryb obciążenia"),
            dcc.Dropdown(
                id="mode",
                options=["Bezczynny", "Standard", "Stres", "Stres2", "Stres3", "GRA1", "GRA2", "GRA3"],
                value="Stres",
                clearable=False,
                className="parameters-dropdown",
            ),

            html.Br(),

            html.Label("Medium chłodzące"),
            dcc.Dropdown(
                id="coolant",
                options=["Powietrze", "Woda destylowana", "Glikol etylenowy 50%"],
                value="Powietrze",
                clearable=False,
                className="parameters-dropdown",
            ),

            html.Br(),

            html.Label("Tryb pracy"),
            dcc.Dropdown(
                id="op_mode",
                options=["Cicha praca", "Standard", "Wysoka wydajność"],
                value="Standard",
                clearable=False,
                className="parameters-dropdown",
            ),

            html.Br(),

            html.Label("Materiał radiatora procesora"),
            dcc.Dropdown(
                id="mat_cpu",
                options=["Aluminium", "Miedź", "Szkło", "PVC"],
                value="Miedź",
                clearable=False,
                className="parameters-dropdown",
            ),

            html.Br(),
            html.Label("Materiał radiatora karty graficznej"),
            dcc.Dropdown(
                id="mat_gpu",
                options=["Aluminium", "Miedź", "Szkło", "PVC"],
                value="Miedź",
                clearable=False,
                className="parameters-dropdown",
            ),

            html.Br(),
            html.Label("Materiał radiatora pamięci RAM"),
            dcc.Dropdown(
                id="mat_ram",
                options=["Aluminium", "Miedź", "Szkło", "PVC"],
                value="Aluminium",
                clearable=False,
                className="parameters-dropdown",
            ),

            html.Br(),

            html.Label("Temperatura otoczenia [°C]"),
            dcc.Slider(15, 40, 1, value=22, id="T_amb",
                       marks={i: str(i) for i in range(15, 41, 5)}),

            html.Br(),
            html.Label("Horyzont MPC (N)"),
            dcc.Slider(2, 20, 1, value=8, id="N_horizon",
                       marks={i: str(i) for i in range(2, 21, 2)}),

            html.Br(),
            html.Label("Temperatura krytyczna CPU [°C]"),
            dcc.Slider(40, 95, 1, value=75, id="T_limit_CPU",
                       marks={i: str(i) for i in range(40, 96, 5)}),

            html.Br(),
            html.Label("Temperatura krytyczna GPU [°C]"),
            dcc.Slider(40, 95, 1, value=75, id="T_limit_GPU",
                       marks={i: str(i) for i in range(40, 96, 5)}),

            html.Br(),
            html.Label("Temperatura krytyczna RAM [°C]"),
            dcc.Slider(40, 95, 1, value=85, id="T_limit_RAM",
                       marks={i: str(i) for i in range(40, 96, 5)}),

            html.Br(),
            html.Label("Temperatura krytyczna AIR [°C]"),
            dcc.Slider(40, 95, 1, value=70, id="T_limit_AIR",
                       marks={i: str(i) for i in range(40, 96, 5)}),

            html.Br(),

            dcc.Checklist(
                id="advanced_options",
                options=[
                    {"label": " Uwzględnij radiację (promieniowanie cieplne)",
                     "value": "radiation"}
                ],
                value=["radiation"],
                style={"fontSize": "14px"}
            ),

            html.Br(),
            html.Button("Symuluj", id="button", n_clicks=0,
                        style={"fontSize": "16px", "padding": "10px 20px"}),

        ]),

        html.Div(id="progress-container", children=[
            dbc.Progress(id="progress-bar", value=0, max=100, striped=True, animated=True, color="success", style={"height": "30px", "width": "80%", "marginLeft": "auto", "marginRight": "auto"}),
            html.P(id="progress-text", style={"textAlign": "center", "marginTop": "10px", "color": "black"}),
        ], style={"display": "none"}),

        html.Div(className="graphs", children=[

            dcc.Loading(
                id="loading-temp",
                type="dot",
                children=dcc.Graph(
                    id="graph-temp",
                    figure=make_graph([], {}, "Temperatury", {})
                )
            ),

            dcc.Loading(
                id="loading-pwm",
                type="dot",
                children=dcc.Graph(
                    id="graph-pwm",
                    figure=make_graph([], {}, "Sterowanie PWM", {})
                )
            ),

            dcc.Loading(
                id="loading-error",
                type="dot",
                children=dcc.Graph(
                    id="graph-error",
                    figure=make_graph([], {}, "Uchyb regulacji", {})
                )
            ),

            dcc.Loading(
                id="loading-sound",
                type="dot",
                children=dcc.Graph(
                    id="graph-sound",
                    figure=make_graph([], {}, "Hałas wentylatorów", {})
                )
            ),

            dcc.Loading(
                id="loading-fan-power",
                type="dot",
                children=dcc.Graph(
                    id="graph-fan-power",
                    figure=make_graph([], {}, "Bilans mocy", {})
                )
            ),

            dcc.Loading(
                id="loading-power",
                type="dot",
                children=dcc.Graph(
                    id="graph-power",
                    figure=make_graph([], {}, "Bilans mocy", {})
                )
            )
        ])
    ])

    app.run(debug=True, host='127.0.0.1')

if __name__ == "__main__":
    main()