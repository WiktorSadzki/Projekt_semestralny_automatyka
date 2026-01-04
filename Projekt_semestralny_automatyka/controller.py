import numpy as np
from scipy.optimize import minimize

class Controller:
    def __init__(self, p):
        self.p = p

    def compute_h(self, v, L_char=0.04):
        # Konwekcja wymuszona wg Churchill-Bernstein
        cp, rho, mu, lam, Pr = (self.p.cp_coolant, self.p.rho_coolant,
                                self.p.mu_coolant, self.p.lambda_coolant,
                                self.p.Pr_coolant)
        if v < 1e-4:
            return self.p.h_nat  # minimalna konwekcja naturalna

        Re = rho * v * L_char / mu
        Nu = 0.3 + (0.62 * Re ** 0.5 * Pr ** (1 / 3)) / (1 + (0.4 / Pr) ** (2 / 3)) ** 0.25
        Nu *= (1 + (Re / 282000) ** 0.625) ** 0.8
        h = Nu * lam / L_char
        return h

    def predict(self, T, u, Qc, Qg):
        T_CPU, T_GPU, T_AIR = T
        u_CPU, u_GPU, _ = u
        p = self.p

        v_CPU = p.v_min + (p.v_max - p.v_min) * u_CPU / 100
        v_GPU = p.v_min + (p.v_max - p.v_min) * u_GPU / 100

        h_CPU = self.compute_h(v_CPU)
        h_GPU = self.compute_h(v_GPU)

        # Bezpośrednie chłodzenie do T_amb
        Q_CPU_to_AMB = h_CPU * p.A_CPU * (T_CPU - p.T_amb)
        Q_GPU_to_AMB = h_GPU * p.A_GPU * (T_GPU - p.T_amb)

        # Radiacja
        if p.enable_radiation:
            T_CPU_K = T_CPU + 273.15
            T_GPU_K = T_GPU + 273.15
            T_AIR_K = T_AIR + 273.15
            T_amb_K = p.T_amb + 273.15
            Q_rad_CPU = p.epsilon_CPU * p.sigma * p.A_CPU * (T_CPU_K ** 4 - T_amb_K ** 4)
            Q_rad_GPU = p.epsilon_GPU * p.sigma * p.A_GPU * (T_GPU_K ** 4 - T_amb_K ** 4)
            Q_rad_AIR = p.epsilon_enclosure * p.sigma * p.A_enclosure * (T_AIR_K ** 4 - T_amb_K ** 4)
        else:
            Q_rad_CPU = Q_rad_GPU = Q_rad_AIR = 0

        # Równania różniczkowe
        dT_CPU = (Qc - Q_CPU_to_AMB - Q_rad_CPU) / p.C_CPU
        dT_GPU = (Qg - Q_GPU_to_AMB - Q_rad_GPU) / p.C_GPU

        # T_AIR: wycieki ciepła + konwekcja + radiacja do otoczenia
        Q_leak_to_AIR = p.leak_factor * (Q_CPU_to_AMB + Q_GPU_to_AMB)
        h_enclosure = 10.0
        Q_AIR_to_AMB = h_enclosure * p.A_enclosure * (T_AIR - p.T_amb)
        dT_AIR = (Q_leak_to_AIR - Q_AIR_to_AMB - Q_rad_AIR) / p.C_AIR

        return T + np.array([dT_CPU, dT_GPU, dT_AIR]) * p.Ts

    def step(self, T, u_prev, Qc, Qg):
        p = self.p
        N = p.N
        T_comfort = p.T_amb + (p.T_limit - p.T_amb) * p.n_margin

        def optimize_component(T_init, u_prev_val, Q, area, capacity, L_max):
            def cost(u_flat):
                u_seq = u_flat.reshape((N, 1))
                T_sim = T_init
                cost_total = 0.0

                for k in range(N):
                    u_k = u_seq[k, 0]
                    v = p.v_min + (p.v_max - p.v_min) * u_k / 100
                    h = self.compute_h(v)
                    Q_out = h * area * (T_sim - p.T_amb)
                    T_sim += (Q - Q_out) / capacity * p.Ts

                    prev = u_prev_val if k == 0 else u_seq[k - 1, 0]
                    cost_total += (
                            p.w_thermal * max(0, T_sim - T_comfort) ** 3 +
                            p.w_energy * u_k ** 2 +
                            p.w_noise * self.fan_noise_dB([u_k], L_max) ** 2 +
                            p.w_smooth * (u_k - prev) ** 2
                    )

                return cost_total

            u0 = np.tile(u_prev_val, N)
            res = minimize(cost, u0, method='L-BFGS-B',
                           bounds=[(0, p.U_max)] * N,
                           options={'maxiter': 50, 'ftol': 1e-5})
            return res.x[0]

        components = [
            (T[0], u_prev[0], Qc, p.A_CPU, p.C_CPU, p.L_max_CPU),
            (T[1], u_prev[1], Qg, p.A_GPU, p.C_GPU, p.L_max_GPU)
        ]

        u_opt = [optimize_component(*params) for params in components]
        return np.array([u_opt[0], u_opt[1], 0.0])

    @staticmethod
    def fan_noise_dB(u_list, L_max, L_base=20.0):
        u = np.array(u_list)
        return L_base + (L_max - L_base) * (u / 100.0) ** 1.5
