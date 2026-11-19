"""
Explore the INPUT data of the IEEE 14-bus system.

This script does NOT solve anything. It just shows you what goes INTO the
simulation: the buses, loads, generators, lines and transformers.
It also saves each table as a CSV in the data/ folder so you can open it in Excel.

Run from the project root:   .\\.venv\\Scripts\\python.exe src\\explore_data.py
"""

from pathlib import Path

import pandas as pd
import pandapower.networks as pn

DATA = Path(__file__).resolve().parent.parent / "data"
DATA.mkdir(exist_ok=True)
pd.set_option("display.width", 200)

net = pn.case14()  # load the built-in IEEE 14-bus grid

# pandapower counts buses from 0, the IEEE diagram counts from 1 -> add 1 everywhere

# 1. LOADS: what the customers consume (these are PQ buses)
loads = pd.DataFrame({
    "bus": net.load.bus + 1,
    "P_MW (real power used)": net.load.p_mw,
    "Q_MVAr (reactive power used)": net.load.q_mvar,
})

# 2. GENERATORS: what the power plants are told to do (these are PV buses)
gens = pd.DataFrame({
    "bus": net.gen.bus + 1,
    "P_MW (fixed output)": net.gen.p_mw,
    "V_setpoint_pu (voltage it holds)": net.gen.vm_pu,
    "Q_min_MVAr": net.gen.min_q_mvar,
    "Q_max_MVAr": net.gen.max_q_mvar,
})

# 3. SLACK: the main generator that balances everything
slack = pd.DataFrame({
    "bus": net.ext_grid.bus + 1,
    "V_pu (voltage it holds)": net.ext_grid.vm_pu,
    "angle_deg (reference)": net.ext_grid.va_degree,
})

# 4. LINES: the wires and how "hard" it is for power to flow through them
#    Converted to per-unit (base 100 MVA): Z_base = V_base^2 / S_base
z_base = net.bus.vn_kv[net.line.from_bus].values ** 2 / 100
lines = pd.DataFrame({
    "from_bus": net.line.from_bus + 1,
    "to_bus": net.line.to_bus + 1,
    "R_pu (resistance -> losses)": net.line.r_ohm_per_km * net.line.length_km / z_base,
    "X_pu (reactance -> voltage drop)": net.line.x_ohm_per_km * net.line.length_km / z_base,
})

# 5. TRANSFORMERS: connect different voltage levels
trafos = pd.DataFrame({
    "from_bus (high side)": net.trafo.hv_bus + 1,
    "to_bus (low side)": net.trafo.lv_bus + 1,
})

# 6. SHUNT: a capacitor bank that supplies reactive power to hold voltage up
shunts = pd.DataFrame({
    "bus": net.shunt.bus + 1,
    "Q_MVAr supplied": -net.shunt.q_mvar,
})

tables = {"loads": loads, "generators": gens, "slack": slack,
          "lines": lines, "transformers": trafos, "shunts": shunts}

for name, df in tables.items():
    print(f"\n=== {name.upper()} ({len(df)}) ===")
    print(df.round(3).to_string(index=False))
    df.round(4).to_csv(DATA / f"{name}.csv", index=False)

print(f"\nTotal load      : {loads.iloc[:, 1].sum():.1f} MW")
print(f"Fixed generation: {gens.iloc[:, 1].sum():.1f} MW  (from PV buses)")
print("The slack bus must supply the rest + all the losses -> found by the load flow.")
print(f"\nCSV copies saved to: {DATA}")
