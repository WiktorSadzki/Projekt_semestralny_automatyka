class Parameters:
    def __init__(self):
        self.C = 100.0  # Pojemność cieplna obudowy [J/K]
        self.h = 0.05  # Współczynnik konwekcji [W/(m^2*K)]
        self.A = 40.0  # Powierzchnia wymiany ciepła [m^2]

        self.Q_max = 150.0  # Maksymalna moc chłodzenia wentylatora [W]
        self.U_max = 12.0  # Napięcie znamionowe wentylatora [V]
        self.T_in = 25.0  # Temperatura otoczenia [°C]
        self.Ts = 1.0  # Czas próbkowania [s]

        self.Q_load = 100.0  # Moc cieplna generowana przez podzespoły [W]

        self.N = 5  # Horyzont predykcji [kroki]
        self.Q_weight = 10.0  # Waga błędu regulacji (Q)
        self.R_weight = 1.0  # Waga zmian sterowania (R)

        self.simulation_steps = 100  # Liczba kroków symulacji

    def get_params_tuple(self):
        return (self.C, self.h, self.A, self.Q_max, self.U_max, self.T_in, self.Ts)

    def get_weights_tuple(self):
        return (self.Q_weight, self.R_weight)