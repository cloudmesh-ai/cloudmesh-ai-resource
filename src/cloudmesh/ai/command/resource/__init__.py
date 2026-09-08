"""
Cloudmesh AI resource Extension
================================

This extension provides tools to monitor Slurm node resources and job status
on remote clusters via SSH, and probe local Kubernetes environments.

Usage Examples:
-------------------------------------------------------------------------------
1. Check status of a specific node:
   $ cmc resource status --node udc-an26-1

2. Check status of a node via a specific SSH host:
   $ cmc resource status --node udc-an26-1 --host uva

3. Monitor node status in real-time (watch mode):
   $ cmc resource status --node udc-an26-1 --watch

4. Probe local Kubernetes environment:
   $ cmc resource probe k8s

Usage:
    resource status [options]
    resource probe k8s

Options:
    --node <node>      Target Slurm node (default: udc-an26-1).
    --host <host>      SSH destination host (default: uva).
    --watch            Repeatedly run and update output in terminal.
    --interval <sec>   Refresh interval for watch mode in seconds (default: 10.0).
    --debug            Show SSH connection debug messages.
    -h, --help         Show this screen.
-------------------------------------------------------------------------------
"""

import json
import sys
import time
from datetime import datetime

import click

from cloudmesh.ai.common.io import console
from .slurm import SlurmClient, SlurmClusterStatus, asdict
from cloudmesh.ai.resource.k8s.probe import recommend as recommend_k8s

def parse_slurm_time(time_str: str) -> int:
    """Convert Slurm time format (days-hours:minutes:seconds) to total seconds."""
    try:
        if not time_str or time_str == "UNKNOWN":
            return 0
        
        # Split days if present
        if '-' in time_str:
            days_part, time_part = time_str.split('-')
            days = int(days_part)
        else:
            days = 0
            time_part = time_str
            
        # Split HH:MM:SS or MM:SS or SS
        parts = list(map(int, time_part.split(':')))
        if len(parts) == 3:
            # HH:MM:SS
            hours, minutes, seconds = parts
        elif len(parts) == 2:
            # MM:SS
            hours = 0
            minutes, seconds = parts
        elif len(parts) == 1:
            # SS
            hours = 0
            minutes = 0
            seconds = parts[0]
        else:
            return 0
            
        return (days * 86400) + (hours * 3600) + (minutes * 60) + seconds
    except (ValueError, IndexError):
        return 0

def format_slurm_time(seconds: int) -> str:
    """Convert total seconds back to Slurm time format (days-hours:minutes:seconds)."""
    if seconds <= 0:
        return "00:00:00"
        
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    
    time_part = f"{hours:02}:{minutes:02}:{seconds:02}"
    if days > 0:
        return f"{days}-{time_part}"
    return time_part


# Default refresh interval for watch mode (in seconds)
DEFAULT_WAIT_TIME = 10.0

def render_report(status: SlurmClusterStatus, node_name: str, host: str):
    """Render the Slurm status report using formatted tables."""
    console.banner(f"SLURM NODE REPORT: {node_name}", f"SSH Host: {host}")

    for node in status.nodes:
        res_data = [
            ("CPUs", node.cpu_total - node.cpu_used, node.cpu_total, node.cpu_used),
            ("Memory", f"{node.mem_total_gb - node.mem_used_gb}GB", f"{node.mem_total_gb}GB", f"{node.mem_used_gb}GB"),
            ("GPUs", node.gpu_total - node.gpu_used, node.gpu_total, node.gpu_used),
        ]
        console.table(["Resource", "Free", "Total", "Used"], res_data, title="Resource Summary")

    if status.active_jobs:
        jobs_data = []
        for j in status.active_jobs:
            # time = time used, time_limit = total limit
            time_used_sec = parse_slurm_time(j.time)
            time_limit_sec = parse_slurm_time(j.time_limit)
            
            # Left = Limit - Time (Used)
            time_left_sec = time_limit_sec - time_used_sec
            time_left_str = format_slurm_time(time_left_sec)
            
            jobs_data.append((
                j.job_id, j.user, j.status, j.time, j.time_limit, time_left_str, j.cpus, j.mem, j.gres, j.full_name.replace('_', ' ')
            ))
        console.table(["JobID", "User", "ST", "Time", "Limit", "Left", "CPUs", "Mem", "GRES", "Full Name"], jobs_data, title="Active Jobs")
    else:
        console.msg("No active jobs found.")

    if status.pending_jobs_raw:
        console.print("\n---- PENDING JOBS (Top 10) ----")
        console.print(status.pending_jobs_raw)
    else:
        console.msg("No pending jobs found.")

    if status.a100_summary:
        a100_data = [
            (s["node"], s["total"], s["used"], s["free"], s["state"]) 
            for s in status.a100_summary
        ]
        console.table(["Node", "Total", "Used", "Free", "State"], a100_data, title="A100 GPU Nodes Status")

    console.msg(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# --- Click Group and Commands ---

@click.group()
def probe_group():
    """
    Probe local resource tools.
    """
    pass

@probe_group.command(name="k8s")
def k8s_cmd():
    """
    Probe local environment for Kubernetes tool recommendations.
    """
    recommend_k8s()

@click.group()
def resource_group():
    """
    resource tool for monitoring Slurm node resources and local infrastructure.
    """
    pass

# Register probe_group to resource_group
resource_group.add_command(probe_group, name="probe")

@resource_group.command(name="job")
@click.argument("job_id")
@click.option("-H", "--host", default="uva", show_default=True, help="SSH destination host.")
@click.option("-t", "--timeout", type=int, default=10, show_default=True, help="SSH connection timeout in seconds.")
@click.option("-d", "--debug", is_flag=True, default=False, help="Show SSH connection debug messages.")
def job_cmd(job_id: str, host: str, timeout: int, debug: bool):
    """
    Fetch detailed information for a specific Slurm job.
    """
    client = SlurmClient(host=host, timeout=timeout, debug=debug)
    try:
        details = client.fetch_job_details(job_id)
        if details:
            console.banner(f"SLURM JOB DETAILS: {job_id}", f"SSH Host: {host}")
            
            # Format the output to have dark blue attributes and black values
            # Each attribute=value pair is printed on a separate line for better readability
            import re
            for line in details.splitlines():
                if not line.strip():
                    click.echo("")
                    continue
                
                # Find all Key=Value pairs on the line
                # Regex matches non-whitespace keys and values up until the next whitespace
                pairs = re.findall(r'(\S+)=([^\s]+)', line)
                if pairs:
                    for key, val in pairs:
                        styled_key = click.style(key, fg='blue')
                        click.echo(f"{styled_key}={val}")
                else:
                    # If no pairs found, print the line as is
                    click.echo(line)
        else:
            console.error(f"No details found for job {job_id}.")
    except Exception as e:
        console.error(f"Error fetching job details: {e}")
    finally:
        client.close()

@resource_group.command(name="status")
@click.option("-n", "--node", default="udc-an26-1", show_default=True, help="Target Slurm node(s), comma-separated.")
@click.option("-H", "--host", default="uva", show_default=True, help="SSH destination host.")
@click.option("-w", "--watch", is_flag=True, default=False, help="Repeatedly run and update output in terminal.")
@click.option("-i", "--interval", type=float, default=DEFAULT_WAIT_TIME, show_default=True, help="Refresh interval for watch mode in seconds.")
@click.option("-t", "--timeout", type=int, default=10, show_default=True, help="SSH connection timeout in seconds.")
@click.option("-d", "--debug", is_flag=True, default=False, help="Show SSH connection debug messages.")
@click.option("--json", is_flag=True, default=False, help="Output data in JSON format.")
def status_cmd(node: str, host: str, watch: bool, interval: float, timeout: int, debug: bool, json: bool):
    """
    Slurm Node Resource and Job Monitor (executes remotely via SSH).
    """
    nodes = [n.strip() for n in node.split(",")]
    client = SlurmClient(host=host, timeout=timeout, debug=debug)

    if watch:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        try:
            while True:
                sys.stdout.write("\033[H")
                for n in nodes:
                    try:
                        status = client.fetch_node_status(n)
                        if json:
                            # JSON output in watch mode is unusual, but we'll print it
                            print(json.dumps(asdict(status), indent=2))
                        else:
                            render_report(status, n, host)
                    except Exception as e:
                        console.error(f"Failed to fetch data for node {n}: {e}")

                end_time = time.time() + interval
                while True:
                    remaining = int(round(max(0.0, end_time - time.time())))
                    timer_str = f"\nNext update in: {remaining}s (Ctrl+C to exit)"
                    sys.stdout.write(f"{timer_str}\033[J")
                    sys.stdout.flush()
                    if remaining <= 0:
                        sys.stdout.write("Updating...\033[K")
                        sys.stdout.flush()
                        break
                    time.sleep(1.0)
        except KeyboardInterrupt:
            click.echo("\nExiting watch mode.")
            sys.exit(0)
        finally:
            client.close()
    else:
        try:
            all_results = {}
            for n in nodes:
                status = client.fetch_node_status(n)
                if json:
                    all_results[n] = asdict(status)
                else:
                    render_report(status, n, host)
            
            if json:
                print(json.dumps(all_results, indent=2))
            else:
                console.msg("Done.")
        except Exception:
            sys.exit(1)
        finally:
            client.close()


entry_point = resource_group

def register(cli):
    cli.add_command(resource_group, name="resource")