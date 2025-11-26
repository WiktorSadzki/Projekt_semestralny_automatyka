import numpy as np
from scipy.optimize import minimize
from parameters import Parameters


class Controller:
    def __init__(self, params: Parameters):
        self.params = params
        self.N = params.N
        self.U_max = params.U_max
        self.weights = params.get_weights_tuple()
        self.params_tuple = params.get_params_tuple()

    # Zmiana temperatury
    def predict_temperature(self, T_k, u_k, Q_load):
        C, h, A, Q_max, U_max, T_in, Ts = self.params_tuple
        dT = (1 / C) * (Q_load - (h * A) * (T_k - T_in) - (Q_max / U_max) * u_k)
        return T_k + Ts * dT

    # Funkcja kosztu
    def cost_function(self, u_sequence, T_k, T_set, u_prev, Q_load):
        Q_w, R_w = self.weights
        cost = 0.0
        T_pred = T_k
        u_last = u_prev

        # Sumowanie dla błędu temperatury
        for i in range(self.N):
            T_pred = self.predict_temperature(T_pred, u_sequence[i], Q_load)
            error = T_set - T_pred
            cost += Q_w * (error ** 2)

        # Sumowanie dla zmian sterowania
        for i in range(self.N):
            if i == 0:
                delta_u = u_sequence[i] - u_prev
            else:
                delta_u = u_sequence[i] - u_sequence[i - 1]
            cost += R_w * (delta_u ** 2)

        return cost

    def optimize_control(self, T_curr, T_set, u_prev, Q_load):
        initial_guess = np.full(self.N, u_prev) # Poprzednia wartość U
        bounds = [(0.0, self.U_max) for _ in range(self.N)] # Ograniczenie napięcia

        result = minimize(
            lambda u_sequence: self.cost_function(u_sequence, T_curr, T_set, u_prev, Q_load),
            initial_guess,
            method='SLSQP', # algorytm SLSQP
            bounds=bounds
        )

        return result.x[0]