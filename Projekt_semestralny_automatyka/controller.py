import numpy as np
from scipy.optimize import minimize

class Controller:
    def __init__(self, p):
        self.p = p

    def compute_h(self, v, T_air, T_amb, L_char=0.04, L_wall=0.4):
        # Parametry chłodziwa
        cp, rho, mu, lam, Pr = (self.p.cp_coolant, self.p.rho_coolant,
                                self.p.mu_coolant, self.p.lambda_coolant,
                                self.p.Pr_coolant)

        # Ustalanie współczynnika konwekcji
        if v < 1e-4:
            # Konwekcja naturalna wg liczby Grashofa
            g = 9.81
            beta = 1 / (T_air + 273.15)
            nu = 1.6e-5
            delta_T = max(T_air - T_amb, 1e-3)

            Gr = g * beta * delta_T * L_wall ** 3 / nu ** 2

            if Gr < 0:
                print("Grashof number must be non-negative.")
                raise ValueError("Grashof number must be non-negative.")

            Nu = 0.59 * (Gr * Pr) ** 0.25
            h = Nu * 0.026 / L_wall
        else:
            # Konwekcja wymuszona wg Churchill-Bernstein
            Re = rho * v * L_char / mu
            Nu = 0.3 + (0.62 * Re ** 0.5 * Pr ** (1 / 3)) / (1 + (0.4 / Pr) ** (2 / 3)) ** 0.25
            Nu *= (1 + (Re / 282000) ** 0.625) ** 0.8
            h = Nu * lam / L_char

        return h

    def predict(self, T, u, Qc, Qg, Qr):
        T_CPU, T_GPU, T_AIR, T_RAM = T
        u_CPU, u_GPU, u_CASE = u
        p = self.p

        v_CPU = p.v_min_CPU + (p.v_max_CPU - p.v_min_CPU) * (u_CPU / 100) / p.A_CPU
        v_GPU = p.v_min_GPU + (p.v_max_GPU - p.v_min_GPU) * (u_GPU / 100)  / p.A_CPU
        v_CASE = p.v_min_case + (p.v_max_case - p.v_min_case) * (u_CASE / 100)  / p.A_CPU

        h_CPU = self.compute_h(v_CPU, T_AIR, p.T_amb, p.L_char_CPU)
        h_GPU = self.compute_h(v_GPU, T_AIR, p.T_amb, p.L_char_GPU)
        h_CASE = self.compute_h(v_CASE, T_AIR, p.T_amb, p.L_char_CASE, L_wall=p.L_char_CASE)
        h_RAM = self.compute_h(0.0, T_AIR, p.T_amb, p.L_char_RAM)

        # Opór przewodzenia przez radiator
        R_cond_CPU = p.d_CPU / (p.lambda_CPU * p.A_CPU)
        R_cond_GPU = p.d_GPU / (p.lambda_GPU * p.A_GPU)
        R_cond_RAM = p.d_RAM / (p.lambda_RAM * p.A_RAM)

        # Temperatura powierzchni radiatora
        T_surf_CPU = T_CPU - Qc * R_cond_CPU
        T_surf_GPU = T_GPU - Qg * R_cond_GPU
        T_surf_RAM = T_RAM - Qr * R_cond_RAM

        # Konwekcja od powierzchni
        Q_conv_CPU = h_CPU * p.A_CPU * (T_surf_CPU - T_AIR)
        Q_conv_GPU = h_GPU * p.A_GPU * (T_surf_GPU - T_AIR)
        Q_conv_RAM = h_RAM * p.A_RAM * (T_surf_RAM - T_AIR)

        #Konwekcja przez szczeliny obudowy
        Q_wall = h_CASE * p.A_enclosure * (T_AIR - p.T_amb)

        # Radiacja
        if p.enable_radiation:
            T_CPU_K = T_CPU + 273.15
            T_GPU_K = T_GPU + 273.15
            T_AIR_K = T_AIR + 273.15
            T_RAM_K = T_RAM + 273.15
            T_amb_K = p.T_amb + 273.15
            Q_rad_CPU = p.epsilon_CPU * p.sigma * p.A_CPU * (T_CPU_K ** 4 - T_AIR_K ** 4)
            Q_rad_GPU = p.epsilon_GPU * p.sigma * p.A_GPU * (T_GPU_K ** 4 - T_AIR_K ** 4)
            Q_rad_RAM = p.epsilon_RAM * p.sigma * p.A_RAM * (T_RAM_K ** 4 - T_AIR_K ** 4)
            Q_rad_CASE = p.epsilon_enclosure * p.sigma * p.A_enclosure * (T_AIR_K ** 4 - T_amb_K ** 4)
        else:
            Q_rad_CPU = Q_rad_GPU = Q_rad_CASE = Q_rad_RAM = 0

        # Bilans CPU/GPU
        dT_CPU = (Qc - Q_conv_CPU - Q_rad_CPU) / p.C_CPU
        dT_GPU = (Qg - Q_conv_GPU - Q_rad_GPU) / p.C_GPU
        dT_RAM = (Qr - Q_conv_RAM - Q_rad_RAM) / p.C_RAM # Pamięć RAM oddaje ciepło jedynie pasywnie

        m_dot = p.rho_coolant * v_CASE * p.A_fan_case # Strumień masowy
        Q_vent = m_dot * p.cp_coolant * (T_AIR - p.T_amb)

        # Bilans powietrza w obudowie
        dT_AIR = (Q_conv_CPU + Q_conv_GPU + Q_conv_RAM + Q_rad_CPU + Q_rad_GPU + Q_rad_RAM
                  - Q_vent - Q_rad_CASE - Q_wall) / p.C_AIR

        return T + np.array([dT_CPU, dT_GPU, dT_AIR, dT_RAM]) * p.Ts

    def step(self, T, u_prev, Qc, Qg, Qr):
        p = self.p
        N = p.N
        T_comfort = p.T_amb + (p.T_limit - p.T_amb) * p.n_margin
        T_comfort_RAM = p.T_amb + (p.T_limit_RAM - p.T_amb)

        def cost(u_flat):
            u_seq = u_flat.reshape((N, 3))
            T_sim = T.copy()
            cost_total = 0.0

            for k in range(N):
                u_k = u_seq[k]
                T_sim = self.predict(T_sim, u_k, Qc, Qg, Qr)

                thermal_cost = (
                        p.w_thermal * max(0, T_sim[0] - T_comfort) ** 2 +
                        p.w_thermal * max(0, T_sim[1] - T_comfort) ** 2 +
                        0.5 * p.w_thermal * max(0, T_sim[2] - T_comfort) ** 2 +
                        0.1 * p.w_thermal * max(0, T_sim[3] - T_comfort_RAM) ** 2
                )

                prev = u_prev if k == 0 else u_seq[k - 1]
                energy_cost = p.w_energy * np.sum(u_k ** 2)
                noise_cost = p.w_noise * (
                        self.fan_noise_dB([u_k[0]], p.L_max_CPU) ** 2 +
                        self.fan_noise_dB([u_k[1]], p.L_max_GPU) ** 2 +
                        self.fan_noise_dB([u_k[2]], p.L_max_case) ** 2
                )
                smooth_cost = p.w_smooth * np.sum((u_k - prev) ** 2)

                cost_total += thermal_cost + energy_cost + noise_cost + smooth_cost

            return cost_total

        u0 = np.tile(u_prev, (N, 1)).flatten()
        result = minimize(cost, u0, method='L-BFGS-B',
                       bounds=[(0, p.U_max)] * (N * 3),
                       options={'maxiter': 50, 'ftol': 1e-5})

        return result.x.reshape((N, 3))[0]

    @staticmethod
    def fan_noise_dB(u_list, L_max, L_base=20.0):
        u = np.array(u_list)
        return L_base + (L_max - L_base) * (u / 100.0) ** 1.5
