#!/usr/bin/env python3
"""Slurm Node Resource and Job Monitor."""

import io
import os
import re
import sys
import time
from datetime import datetime
import click
import paramiko

# Remote Slurm binaries
SCONTROL = "/opt/slurm/current/bin/scontrol"
SQUEUE = "/opt/slurm/current/bin/squeue"
SINFO = "/opt/slurm/current/bin/sinfo"

# Default refresh interval for watch mode (in seconds)
DEFAULT_WAIT_TIME = 10.0


def get_ssh_config_for_host(host_alias: str) -> dict:
    """Parse ~/.ssh/config to get real connection details for host aliases."""
    ssh_config = paramiko.SSHConfig()
    user_config_file = os.path.expanduser("~/.ssh/config")
    
    if os.path.exists(user_config_file):
        with open(user_config_file) as f:
            ssh_config.parse(f)
            
    host_info = ssh_config.lookup(host_alias)
    
    connect_kwargs = {
        "hostname": host_info.get("hostname", host_alias),
        "username": host_info.get("user"),
        "port": int(host_info.get("port", 22)),
    }

    if "identityfile" in host_info:
        connect_kwargs["key_filename"] = host_info["identityfile"][0]

    return connect_kwargs


def fetch_remote_data(node: str, host: str = "uva", debug: bool = False) -> str:
    """Run a single SSH pipeline on the remote host to gather all Slurm output in one turn."""
    remote_script = f"""
    NODE="{node}"
    echo "===NODE_INFO==="
    {SCONTROL} show node "$NODE" 2>/dev/null
    
    echo "===ACTIVE_JOBS==="
    {SQUEUE} -w "$NODE" -h -o "%i|%u|%t|%M|%C|%m|%b" 2>/dev/null
    
    echo "===PENDING_JOBS==="
    {SQUEUE} -t PD -w "$NODE" -o "%.10i %.12u %.5t %.10M %.20R" 2>/dev/null | head -n 11

    echo "===A100_NODES==="
    {SINFO} -p gpu -N -O "NodeList,Gres,GresUsed,StateLong" 2>/dev/null
    """

    conn_params = get_ssh_config_for_host(host)

    if debug:
        click.echo(f"[DEBUG] Resolved SSH Config for '{host}': {conn_params}", err=True)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(**conn_params, timeout=10)
        _, stdout, stderr = ssh.exec_command(remote_script)
        
        output = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")

        if debug and err.strip():
            click.echo(f"[DEBUG SSH STDERR]:\n{err.strip()}", err=True)

        ssh.close()
        return output
    except Exception as e:
        click.echo(f"SSH Error while connecting to '{host}': {e}", err=True)
        sys.exit(1)


def parse_and_print_a100_summary(a100_raw: str, out_file=None):
    """Parse sinfo output for A100 GPU node allocation."""
    click.echo("\n---- A100 GPU NODES STATUS ----", file=out_file)
    click.echo(f"{'NODE':<15} {'TOTAL':<8} {'USED':<8} {'FREE':<8} {'STATE'}", file=out_file)
    click.echo("-" * 50, file=out_file)

    lines = [l.strip() for l in a100_raw.splitlines() if l.strip()]
    if len(lines) <= 1:
        click.echo("No A100 GPU nodes found.", file=out_file)
        return

    # Skip header line
    for line in lines[1:]:
        if "a100" in line:
            parts = line.split()
            if len(parts) >= 4:
                node, gres, gres_used, state = parts[0], parts[1], parts[2], parts[3]
                
                t_match = re.search(r"a100.*?:(\d+)", gres)
                u_match = re.search(r"a100.*?:(\d+)", gres_used)
                
                total = int(t_match.group(1)) if t_match else 0
                used = int(u_match.group(1)) if u_match else 0
                free = total - used
                
                click.echo(f"{node:<15} {total:<8} {used:<8} {free:<8} {state}", file=out_file)


def format_report(raw_data: str, node: str, host: str) -> str:
    """Parse output collected from SSH and format the display into a string buffer."""
    buf = io.StringIO()

    sections = raw_data.split("===")
    data = {}

    for i in range(1, len(sections), 2):
        sec_name = sections[i].strip()
        sec_content = sections[i + 1].strip() if i + 1 < len(sections) else ""
        data[sec_name] = sec_content

    node_info = data.get("NODE_INFO", "")
    active_jobs_raw = data.get("ACTIVE_JOBS", "")
    pending_jobs_raw = data.get("PENDING_JOBS", "")
    a100_nodes_raw = data.get("A100_NODES", "")

    click.echo("======================================", file=buf)
    click.echo(f" SLURM NODE REPORT: {node} (via SSH: {host})", file=buf)
    click.echo("======================================", file=buf)

    def extract_val(pattern: str, text: str, default: int = 0) -> int:
        match = re.search(pattern, text)
        return int(match.group(1)) if match else default

    if node_info:
        cfg_cpu = extract_val(r'CPUTot=(\d+)', node_info)
        cfg_mem_mb = extract_val(r'RealMemory=(\d+)', node_info)
        cfg_gpu = extract_val(r'Gres=.*gpu.*?:(\d+)', node_info)

        alloc_cpu = extract_val(r'CPUAlloc=(\d+)', node_info)
        alloc_mem_mb = extract_val(r'AllocMem=(\d+)', node_info)
        alloc_gpu = extract_val(r'AllocTRES=.*gres/gpu=(\d+)', node_info)

        free_cpu = cfg_cpu - alloc_cpu
        free_mem_mb = cfg_mem_mb - alloc_mem_mb
        free_gpu = cfg_gpu - alloc_gpu

        click.echo("\n---- RESOURCE SUMMARY ----", file=buf)
        click.echo(f"CPUs:   used={alloc_cpu} / total={cfg_cpu} / free={free_cpu}", file=buf)
        click.echo(f"Mem:    used={alloc_mem_mb // 1024}GB / total={cfg_mem_mb // 1024}GB / free={free_mem_mb // 1024}GB", file=buf)
        click.echo(f"GPUs:   used={alloc_gpu} / total={cfg_gpu} / free={free_gpu}", file=buf)

    click.echo("\n---- ACTIVE JOBS & RESOURCE ALLOCATION ----", file=buf)
    click.echo(f"{'JOBID':<10} {'USER':<12} {'ST':<5} {'TIME':<10} {'CPUS':<5} {'MEM':<10} {'GRES':<15}", file=buf)
    click.echo("-" * 80, file=buf)

    if active_jobs_raw:
        for line in active_jobs_raw.splitlines():
            parts = line.split("|")
            if len(parts) == 7:
                jobid, user, st, time_str, cpus, mem, gres = parts
                gres_val = "none" if gres in ("(null)", "N/A", "") or not gres else gres
                click.echo(f"{jobid:<10} {user:<12} {st:<5} {time_str:<10} {cpus:<5} {mem:<10} {gres_val:<15}", file=buf)

    click.echo(f"\n---- PENDING JOBS on {node} (Top 10) ----", file=buf)
    if pending_jobs_raw:
        click.echo(pending_jobs_raw, file=buf)
    else:
        click.echo("No pending jobs found.", file=buf)

    # A100 GPU Summary section
    if a100_nodes_raw:
        parse_and_print_a100_summary(a100_nodes_raw, out_file=buf)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    click.echo(f"\nReport generated on: {now_str}", file=buf)
    return buf.getvalue()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-n", "--node", default="udc-an26-1", show_default=True, help="Target Slurm node.")
@click.option("-H", "--host", default="uva", show_default=True, help="SSH destination host.")
@click.option("-w", "--watch", is_flag=True, default=False, help="Repeatedly run and update output in terminal.")
@click.option("-i", "--interval", type=float, default=DEFAULT_WAIT_TIME, show_default=True, help="Refresh interval for watch mode in seconds.")
@click.option("-d", "--debug", is_flag=True, default=False, help="Show SSH connection debug messages.")
def main(node: str, host: str, watch: bool, interval: float, debug: bool):
    """Slurm Node Resource and Job Monitor (executes remotely via SSH)."""
    if watch:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        try:
            while True:
                raw_data = fetch_remote_data(node=node, host=host, debug=debug)
                report = format_report(raw_data, node=node, host=host)
                
                # Countdown timer updated in integer 1-second intervals
                end_time = time.time() + interval
                while True:
                    remaining = int(round(max(0.0, end_time - time.time())))
                    timer_str = f"Next update in: {remaining}s (Ctrl+C to exit)"
                    
                    sys.stdout.write(f"\033[H{report}{timer_str}\033[J")
                    sys.stdout.flush()
                    
                    if remaining <= 0:
                        sys.stdout.write(f"\033[H{report}Updating...\033[K\033[J")
                        sys.stdout.flush()
                        break
                    
                    time.sleep(1.0)
        except KeyboardInterrupt:
            click.echo("\nExiting watch mode.")
            sys.exit(0)
    else:
        raw_data = fetch_remote_data(node=node, host=host, debug=debug)
        report = format_report(raw_data, node=node, host=host)
        sys.stdout.write(f"{report}Done.\n")


if __name__ == "__main__":
    main()