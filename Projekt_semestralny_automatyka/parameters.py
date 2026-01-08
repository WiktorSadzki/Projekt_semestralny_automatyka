class Parameters:
    def __init__(self):
        # Materiały radiatorów 
        self.MATERIAL_DATA = {
            "Miedź": {"cp": 385, "rho": 8960, "lambda": 380, "epsilon": 0.78},     # cp [J/kgK], rho [kg/m³], lambda [W/mK]
            "Aluminium": {"cp": 900, "rho": 2700, "lambda": 235, "epsilon": 0.85},
            "Szkło": {"cp": 800, "rho": 2500, "lambda": 0.8, "epsilon": 0.90},
            "PVC": {"cp": 900, "rho": 1400, "lambda": 0.19, "epsilon": 0.92}
        }

        # Ciecz / powietrze chłodzące 
        self.COOLANT_DATA = {
            "Powietrze": {
                "rho": 1.184,      # gęstość powietrza [kg/m³]
                "cp": 1005.0,      # ciepło właściwe [J/(kg·K)]
                "lambda": 0.0257,  # przewodność cieplna [W/(m·K)]
                "mu": 1.85e-5,     # lepkość dynamiczna [Pa·s]
                "Pr": 0.71         # liczba Prandtla [-]
            },
            "Woda destylowana": {
                "rho": 997.0,
                "cp": 4182.0,
                "lambda": 0.598,
                "mu": 0.001,
                "Pr": 7.0
            },
            "Glikol etylenowy 50%": {
                "rho": 1064.0,
                "cp": 3380.0,
                "lambda": 0.41,
                "mu": 0.0035,
                "Pr": 30.0
            }
        }

        # Czas symulacji i MPC 
        self.Ts = 1.0                # krok czasowy [s]
        self.simulation_steps = 200  # liczba kroków symulacji
        self.N = 8                   # horyzont MPC (liczba kroków predykcji)

        # Temperatura i PWM 
        self.T_amb = 25.0   # temperatura otoczenia [°C]
        self.T_limit = 75.0 # limit temperatury CPU/GPU [°C]
        self.U_max = 100.0  # maksymalne wypełnienie PWM [%]

        # Wymiary fizyczne radiatorów i obudowy 
        self.V_rad_CPU = 1.5e-4      # objętość radiatora CPU [m³]
        self.V_rad_GPU = 2.0e-4      # objętość radiatora GPU [m³]
        self.V_rad_RAM = 5.0e-5  # objętość radiatora RAM [m³]
        self.A_CPU = 0.08             # powierzchnia wymiany ciepła CPU [m²]
        self.A_GPU = 0.12             # powierzchnia wymiany ciepła GPU [m²]
        self.A_RAM = 0.02  # powierzchnia wymiany RAM [m²]
        self.A_fan_case = 0.0113        # przekrój wentylatora case 120mm [m²]
        self.V_enclosure = 0.08       # objętość powietrza w obudowie [m³]
        self.A_enclosure = 0.1        # powierzchnia wymiany ciepła obudowy [m²]
        self.epsilon_CPU = 0.85       # emisyjność radiatora CPU
        self.epsilon_GPU = 0.85       # emisyjność radiatora GPU
        self.epsilon_enclosure = 0.7  # emisyjność obudowy
        self.epsilon_RAM = 0.85  # emisyjność radiatora RAM
        self.d_CPU = 0.015  # grubość radiatora CPU [m]
        self.d_GPU = 0.018  # grubość radiatora GPU [m]
        self.d_RAM = 0.005  # grubość radiatora RAM [m]

        # L_char
        self.L_char_CPU = 0.015  # radiator
        self.L_char_GPU = 0.018
        self.L_char_CASE = 0.4  # obudowa
        self.L_char_RAM = 0.01

        # Przepływy maksymalne (CFM lub objętość w m³/s)
        self.v_min_CPU = 0.05  # low PWM
        self.v_max_CPU = 0.46  # 80 CFM

        self.v_min_GPU = 0.05
        self.v_max_GPU = 0.23  # 59 CFM

        self.v_min_case = 0.05
        self.v_max_case = 0.23  # 59 CFM

        # Konwekcja naturalna i współczynniki
        self.h_nat = 5.0           # minimalny współczynnik konwekcji naturalnej [W/m²K]
        self.alfa_natural = 1.5    # współczynnik do obliczeń dodatkowych
        self.sigma = 5.67e-8       # stała Stefana-Boltzmanna [W/m²K⁴]

        # Limity hałasu
        self.L_max_CPU = 35.0  # limit hałasu wentylatora CPU [dB]
        self.L_max_GPU = 35.0  # limit hałasu wentylatora GPU [dB]
        self.L_max_case = 32.0 # limit hałasu wentylatora obudowy [dB]

        # Limity ciepła
        self.T_limit_CPU = 75.0  # limit CPU [°C]
        self.T_limit_GPU = 75.0  # limit GPU [°C]
        self.T_limit_RAM = 85.0  # limit RAM [°C]
        self.T_limit_AIR = 70.0  # limit powietrza [°C]

        # Radiacja włączona/wyłączona 
        self.enable_radiation = True

        # Inicjalizacja materiałów radiatorów i cieczy 
        self.update_heatsink_material("Miedź", "Miedź", "Aluminium")
        self.update_coolant("Powietrze")
        self.set_operation_mode("Standard")

    # Tryby pracy: wagi w funkcji kosztu 
    def set_operation_mode(self, mode: str):
        if mode == "Cicha praca":
            self.T_margin = 3.0      # bufor bezpieczeństwa dla temperatury
            self.n_margin  = 0.9     # mnożnik temepratury komforowej
            self.w_thermal = 100.0  # waga w funkcji kosztu temperatury
            self.w_energy = 0.5      # waga energii wentylatorów
            self.w_noise = 50.0     # waga hałasu wentylatorów
            self.w_smooth = 20.0     # waga płynności zmian PWM
        elif mode == "Wysoka wydajność":
            self.T_margin = 12.0
            self.n_margin = 0.5
            self.w_thermal = 1000.0
            self.w_energy = 0.01
            self.w_noise = 0.01
            self.w_smooth = 0.1
        else:  # Standard
            self.T_margin = 8.0
            self.n_margin = 0.8
            self.w_thermal = 300.0
            self.w_energy = 0.1
            self.w_noise = 5.0
            self.w_smooth = 10.0

    # Aktualizacja materiałów radiatorów 
    def update_heatsink_material(self, cpu_material: str, gpu_material: str, ram_material: str = "Aluminium"):
        m_cpu = self.MATERIAL_DATA[cpu_material]
        m_gpu = self.MATERIAL_DATA[gpu_material]
        m_ram = self.MATERIAL_DATA[ram_material]

        # Pojemność cieplna radiatorów: C = V * rho * cp [J/K]
        self.C_CPU = self.V_rad_CPU * m_cpu["rho"] * m_cpu["cp"]
        self.C_GPU = self.V_rad_GPU * m_gpu["rho"] * m_gpu["cp"]
        self.C_RAM = self.V_rad_RAM * m_ram["rho"] * m_ram["cp"]

        # Przewodnictwo cieplne radiatorów
        self.lambda_CPU = m_cpu["lambda"]
        self.lambda_GPU = m_gpu["lambda"]
        self.lambda_RAM = m_ram["lambda"]

        # Emisyjność
        self.epsilon_CPU = m_cpu["epsilon"]
        self.epsilon_GPU = m_gpu["epsilon"]
        self.epsilon_RAM = m_ram["epsilon"]

    # Aktualizacja właściwości cieczy / powietrza chłodzącego 
    def update_coolant(self, coolant_name: str):
        coolant = self.COOLANT_DATA[coolant_name]
        self.rho_coolant = coolant["rho"]
        self.cp_coolant = coolant["cp"]
        self.mu_coolant = coolant["mu"]
        self.lambda_coolant = coolant["lambda"]
        self.Pr_coolant = coolant["Pr"]

        if coolant_name == "Powietrze":
            self.v_min_CPU = 0.01
            self.v_max_CPU = 0.048
            self.v_min_GPU = 0.01
            self.v_max_GPU = 0.048
            self.v_min_case = 0.01
            self.v_max_case = 0.096
            self.V_enclosure = 0.08  # [m³] efektywna objętość powietrza w obudowie
        else:
            # Typowy przepływ pomp AIO / custom loop 1–6 L/min → ~0.000017–0.0001 m³/s
            self.v_min_CPU = 0.00002
            self.v_max_CPU = 0.0001
            self.v_min_GPU = 0.00002
            self.v_max_GPU = 0.0001
            self.v_min_case = 0.00002
            self.v_max_case = 0.0001

            self.V_enclosure = 0.003

        m_enclosure = 5.0  # kg
        cp_enclosure = 500  # J/(kg·K) - stal
        C_enclosure = m_enclosure * cp_enclosure
        C_fluid = self.rho_coolant * self.V_enclosure * self.cp_coolant

        # Pojemność cieplna powietrza/cieczy w obudowie
        self.C_AIR = C_fluid + C_enclosure

