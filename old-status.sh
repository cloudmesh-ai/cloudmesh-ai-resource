#!/usr/bin/env python3
"""Slurm Node Resource and Job Monitor.

Usage:
  status.py [options]
  status.py (-h | --help)

Options:
  -l, --local              Execute commands locally instead of remote 'uva'.
  -n NODE, --node=NODE     Target Slurm node [default: udc-an26-1].
  -w, --watch              Repeatedly run and update output in terminal.
  -i SEC, --interval=SEC   Refresh interval for watch mode in seconds [default: 2].
  -d, --debug              Show exact commands being executed.
  -h, --help               Show this screen.
"""

import os
import re
import subprocess
import sys
import time
from docopt import docopt

# Absolute paths to Slurm binaries on 'uva'
SCONTROL = "/opt/slurm/current/bin/scontrol"
SQUEUE = "/opt/slurm/current/bin/squeue"


def run_cmd(binary: str, args: list[str], use_ssh: bool = True, debug: bool = False) -> str:
    """Execute command via SSH (`ssh uva SCONTROL ...`) or locally as a list of args."""
    if use_ssh:
        exec_cmd = ["ssh", "-o", "BatchMode=yes", "uva", binary] + args
    else:
        exec_cmd = [binary] + args

    if debug:
        print(f"[DEBUG] Executing: {' '.join(exec_cmd)}", file=sys.stderr)

    try:
        result = subprocess.run(
            exec_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if debug:
            print(f"[DEBUG] Error ({e.returncode}): {e.stderr.strip()}", file=sys.stderr)
        return f"CMD_ERROR: {e.stderr.strip()}"


def get_node_summary(node: str, use_ssh: bool = True, debug: bool = False):
    """Parse scontrol output to extract total and allocated resources."""
    node_info = run_cmd(SCONTROL, ["show", "node", node], use_ssh=use_ssh, debug=debug)
    
    if not node_info or node_info.startswith("CMD_ERROR"):
        err_msg = node_info.replace("CMD_ERROR: ", "") if node_info else "No output returned"
        target = "uva via SSH" if use_ssh else "local host"
        print(f"Error executing scontrol on {target} for node '{node}':\n  {err_msg}", file=sys.stderr)
        return None

    def search_regex(pattern: str, default: int = 0) -> int:
        match = re.search(pattern, node_info)
        return int(match.group(1)) if match else default

    cfg_cpu = search_regex(r'CPUTot=(\d+)')
    cfg_mem_mb = search_regex(r'RealMemory=(\d+)')
    cfg_gpu = search_regex(r'Gres=.*gpu.*?:(\d+)')

    alloc_cpu = search_regex(r'CPUAlloc=(\d+)')
    alloc_mem_mb = search_regex(r'AllocMem=(\d+)')
    alloc_gpu = search_regex(r'AllocTRES=.*gres/gpu=(\d+)')

    free_cpu = cfg_cpu - alloc_cpu
    free_mem_mb = cfg_mem_mb - alloc_mem_mb
    free_gpu = cfg_gpu - alloc_gpu

    return {
        "cpu": (alloc_cpu, cfg_cpu, free_cpu),
        "mem": (alloc_mem_mb // 1024, cfg_mem_mb // 1024, free_mem_mb // 1024),
        "gpu": (alloc_gpu, cfg_gpu, free_gpu),
    }


def print_report(node: str, use_ssh: bool = True, debug: bool = False):
    """Fetch Slurm info and print formatted report."""
    summary = get_node_summary(node, use_ssh=use_ssh, debug=debug)
    mode_str = " (via SSH: uva)" if use_ssh else " (Local)"
    
    print("======================================")
    print(f" SLURM NODE REPORT: {node}{mode_str}")
    print("======================================")

    if summary:
        u_cpu, t_cpu, f_cpu = summary["cpu"]
        u_mem, t_mem, f_mem = summary["mem"]
        u_gpu, t_gpu, f_gpu = summary["gpu"]

        print("\n---- RESOURCE SUMMARY ----")
        print(f"CPUs:   used={u_cpu} / total={t_cpu} / free={f_cpu}")
        print(f"Mem:    used={u_mem}GB / total={t_mem}GB / free={f_mem}GB")
        print(f"GPUs:   used={u_gpu} / total={t_gpu} / free={f_gpu}")

    # Active Jobs
    print("\n---- ACTIVE JOBS & RESOURCE ALLOCATION ----")
    print(f"{'JOBID':<10} {'USER':<12} {'ST':<5} {'TIME':<10} {'CPUS':<5} {'MEM':<10} {'GRES':<15}")
    print("-" * 80)

    squeue_active = run_cmd(
        SQUEUE,
        ["-w", node, "-h", "-o", "%i %u %t %M %C %m %b"],
        use_ssh=use_ssh,
        debug=debug
    )
    if squeue_active and not squeue_active.startswith("CMD_ERROR"):
        for line in squeue_active.splitlines():
            parts = line.split(maxsplit=6)
            if len(parts) == 7:
                jobid, user, st, time_str, cpus, mem, gres = parts
                gres_val = "none" if gres in ("(null)", "N/A", "") else gres
                print(f"{jobid:<10} {user:<12} {st:<5} {time_str:<10} {cpus:<5} {mem:<10} {gres_val:<15}")

    # Pending Jobs
    print(f"\n---- PENDING JOBS on {node} (Top 10) ----")
    pending_output = run_cmd(
        SQUEUE,
        ["-t", "PD", "-w", node, "-o", "%.10i %.12u %.5t %.10M %.20R"],
        use_ssh=use_ssh,
        debug=debug
    )
    if pending_output and not pending_output.startswith("CMD_ERROR"):
        lines = pending_output.splitlines()[:11]  # Header + top 10
        print("\n".join(lines))
    else:
        print("No pending jobs found.")

    print("\nDone.")


def main():
    args = docopt(__doc__)
    
    use_ssh = not bool(args["--local"])
    node = args["--node"]
    watch = args["--watch"]
    debug = bool(args["--debug"])

    try:
        interval = float(args["--interval"])
    except ValueError:
        print("Error: --interval must be a valid number.", file=sys.stderr)
        sys.exit(1)

    if watch:
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                print_report(node, use_ssh=use_ssh, debug=debug)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nExiting watch mode.")
            sys.exit(0)
    else:
        print_report(node, use_ssh=use_ssh, debug=debug)


if __name__ == "__main__":
    main()