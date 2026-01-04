import numpy as np

def cpu_load(t, mode):
    if mode == "Bezczynny":
        return 30.0

    elif mode == "Standard":
        return 100.0

    elif mode == "Stres":
        return 150.0

    elif mode == "Stres2":
        return 20.0

    elif mode == "Stres3":
        return 250.0

    elif mode == "GRA1":
        return 200.0 + 200.0 * np.sin(0.05 * t)

    elif mode == "GRA2":
        return 200.0 + 300.0 * np.sin(0.2 * t)

    elif mode == "GRA3":
        return 100.0 if t < 150 else 500.0

    return 60.0

def gpu_load(t, mode):
    if mode == "Bezczynny":
        return 20.0

    elif mode == "Standard":
        return 100.0

    elif mode == "Stres":
        return 150.0

    elif mode == "Stres2":
        return 200.0

    elif mode == "Stres3":
        return 250.0

    elif mode == "GRA1":
        return 200.0 + 200.0 * np.sin(0.1 * t)

    elif mode == "GRA2":
        return 200.0 + 150.0 * np.sin(0.2 * t)

    elif mode == "GRA3":
        return 500.0 if t < 150 else 50.0

    return 100.0