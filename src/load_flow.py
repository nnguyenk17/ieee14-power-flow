"""
IEEE 14-Bus Load Flow Analysis
==============================
Runs three studies on the IEEE 14-bus test system using pandapower:

  1. Base case load flow (Newton-Raphson)
  2. Load stress test  - scale all loads up until the system fails
  3. N-1 contingency   - take each line out one at a time

All tables (CSV) and plots (PNG) are saved to the results/ folder.
Run from the project root:   python src/load_flow.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pandapower as pp
import pandapower.networks as pn

RESULTS = Path(__file__).resolve().parent.parent / "results"
RESULTS.mkdir(exist_ok=True)

V_MIN, V_MAX = 0.95, 1.05  # common voltage limits in per-unit (pu)
CAPACITOR_MVAR = 0 # adding capacitor to supply reactive power (Q) locally, which holds voltage up

def run_load_flow(net):
    """Run Newton-Raphson load flow. Returns True if it converged."""
    try:
        pp.runpp(net, algorithm="nr", enforce_q_lims=True, numba=False)
        return True
    except pp.LoadflowNotConverged:
        return False


def total_losses_mw(net):
    return net.res_line.pl_mw.sum() + net.res_trafo.pl_mw.sum()


# --------------------------------------------------------------------------
# STUDY 1: Base case
# --------------------------------------------------------------------------
def base_case():
    print("\n=== STUDY 1: Base case ===")
    net = pn.case14()
    run_load_flow(net)

    # Bus results (bus numbers 1-14 instead of pandapower's 0-13)
    bus = net.res_bus[["vm_pu", "va_degree", "p_mw", "q_mvar"]].copy()
    bus.index = bus.index + 1
    bus.index.name = "bus"
    bus.round(4).to_csv(RESULTS / "base_bus_results.csv")

    # Line results
    # (loading_percent is skipped: the IEEE 14 data has no real line ratings)
    line = net.res_line[["p_from_mw", "q_from_mvar", "pl_mw", "ql_mvar"]].copy()
    line.insert(0, "from_bus", net.line.from_bus + 1)
    line.insert(1, "to_bus", net.line.to_bus + 1)
    line.round(3).to_csv(RESULTS / "base_line_results.csv", index=False)

    gen_mw = net.res_ext_grid.p_mw.sum() + net.res_gen.p_mw.sum()
    load_mw = net.load.p_mw.sum()
    losses = total_losses_mw(net)

    print(bus.round(4))
    print(f"\nTotal generation : {gen_mw:8.2f} MW")
    print(f"Total load       : {load_mw:8.2f} MW")
    print(f"Total losses     : {losses:8.2f} MW ({losses / gen_mw * 100:.2f}% of generation)")
    print(f"Min voltage      : {bus.vm_pu.min():.4f} pu at bus {bus.vm_pu.idxmin()}")
    print(f"Max voltage      : {bus.vm_pu.max():.4f} pu at bus {bus.vm_pu.idxmax()}")

    # Plot: voltage profile
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.bar(bus.index, bus.vm_pu, color="#3b7dd8")
    ax.axhline(V_MIN, color="red", linestyle="--", label=f"Limits ({V_MIN}-{V_MAX} pu)")
    ax.axhline(V_MAX, color="red", linestyle="--")
    ax.set_xticks(bus.index)
    ax.set_ylim(0.9, 1.12)
    ax.set_xlabel("Bus number")
    ax.set_ylabel("Voltage magnitude (pu)")
    ax.set_title("IEEE 14-Bus System - Base Case Voltage Profile")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "voltage_profile.png", dpi=200)
    plt.close(fig)

    # Plot: real power flow on each line
    labels = [f"{f}-{t}" for f, t in zip(line.from_bus, line.to_bus)]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(labels, line.p_from_mw.abs(), color="#e08a2c")
    ax.set_xlabel("Line (from bus - to bus)")
    ax.set_ylabel("Real power flow (MW)")
    ax.set_title("IEEE 14-Bus System - Base Case Line Flows")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=45)
    fig.tight_layout()
    fig.savefig(RESULTS / "line_flows.png", dpi=200)
    plt.close(fig)


# --------------------------------------------------------------------------
# STUDY 2: Load stress test
# --------------------------------------------------------------------------
def stress_test():
    print("\n=== STUDY 2: Load stress test ===")
    rows = []
    factor = 1.0
    while factor <= 4.0:
        net = pn.case14()
        if CAPACITOR_MVAR > 0:
            pp.create_shunt(net, bus=13, q_mvar=-CAPACITOR_MVAR) 
        net.load.p_mw *= factor
        net.load.q_mvar *= factor
        if not run_load_flow(net):
            print(f"Load flow FAILED at {factor:.2f}x load -> beyond the system's limit")
            break
        rows.append({
            "load_factor": round(factor, 2),
            "total_load_mw": net.load.p_mw.sum(),
            "min_voltage_pu": net.res_bus.vm_pu.min(),
            "weakest_bus": net.res_bus.vm_pu.idxmin() + 1,
            "losses_mw": total_losses_mw(net),
        })
        factor += 0.05  # stress test step (ex : 10% is 0.1, 5% is 0.05)

    df = pd.DataFrame(rows)
    df.round(4).to_csv(RESULTS / "stress_test.csv", index=False)
    print(df.round(4).to_string(index=False))

    below = df[df.min_voltage_pu < V_MIN]
    if not below.empty:
        first = below.iloc[0]
        print(f"\nVoltage first drops below {V_MIN} pu at {first.load_factor}x load "
              f"(bus {int(first.weakest_bus)})")

    # Plot: min voltage vs load (a simple "PV / nose curve" style plot)
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(df.total_load_mw, df.min_voltage_pu, "o-", color="#3b7dd8")
    ax.axhline(V_MIN, color="red", linestyle="--", label=f"{V_MIN} pu limit")
    ax.set_xlabel("Total system load (MW)")
    ax.set_ylabel("Lowest bus voltage (pu)")
    ax.set_title("Load Stress Test - Lowest Voltage vs Total Load")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(RESULTS / "stress_test.png", dpi=200)
    plt.close(fig)


# --------------------------------------------------------------------------
# STUDY 3: N-1 contingency (remove one line or transformer at a time)
# --------------------------------------------------------------------------
def n_minus_1():
    print("\n=== STUDY 3: N-1 contingency (lines and transformers) ===")
    base = pn.case14()
    outages = [("line", i, f"Line {base.line.from_bus[i] + 1}-{base.line.to_bus[i] + 1}")
               for i in base.line.index]
    outages += [("trafo", i, f"Trafo {base.trafo.hv_bus[i] + 1}-{base.trafo.lv_bus[i] + 1}")
                for i in base.trafo.index]

    rows = []
    for table, i, name in outages:
        net = pn.case14()
        net[table].at[i, "in_service"] = False

        if not run_load_flow(net):
            rows.append({"outage": name, "result": "FAILED (no solution)"})
            continue

        islanded = int(net.res_bus.vm_pu.isna().sum())  # isolated buses show as NaN
        min_v = net.res_bus.vm_pu.min()
        rows.append({
            "outage": name,
            "result": f"{islanded} bus islanded" if islanded else
                      ("LOW VOLTAGE" if min_v < V_MIN else "OK"),
            "min_voltage_pu": min_v,
            "weakest_bus": net.res_bus.vm_pu.idxmin() + 1,
            "max_line_flow_mw": net.res_line.p_from_mw.abs().max(),
            "losses_mw": total_losses_mw(net),
        })

    # Most severe first: failed, then islanded, then lowest voltage
    df = pd.DataFrame(rows)
    df["severity"] = df.result.map(lambda r: 0 if r.startswith("FAILED") else 1 if "islanded" in r else 2)
    df = df.sort_values(["severity", "min_voltage_pu"]).drop(columns="severity")
    df.round(3).to_csv(RESULTS / "n_minus_1.csv", index=False)
    print(df.round(3).to_string(index=False))
    print(f"\nMost severe outage: {df.iloc[0].outage} -> {df.iloc[0].result}")

    # Plot: lowest bus voltage after each outage that solved
    ok = df[~df.result.str.startswith("FAILED")].sort_values("min_voltage_pu")
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.bar(ok.outage, ok.min_voltage_pu, color="#c94c4c")
    ax.axhline(V_MIN, color="black", linestyle="--", label=f"{V_MIN} pu limit")
    ax.set_ylim(0.9, 1.05)
    ax.set_xlabel("Element taken out of service")
    ax.set_ylabel("Lowest bus voltage after outage (pu)")
    failed = ", ".join(df[df.result.str.startswith("FAILED")].outage)
    ax.set_title("N-1 Contingency - Lowest Voltage per Outage"
                 + (f"\n(No solution, not shown: {failed})" if failed else ""))
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=60, ha="right")
    fig.tight_layout()
    fig.savefig(RESULTS / "n_minus_1.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    base_case()
    stress_test()
    n_minus_1()
    print(f"\nDone. Results saved to: {RESULTS}")
