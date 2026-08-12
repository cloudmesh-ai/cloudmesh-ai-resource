import re
import paramiko
import os
import yaml
from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any
from cloudmesh.ai.common.io import console

@dataclass
class SlurmJob:
    job_id: str
    user: str
    full_name: str
    status: str
    time: str
    time_limit: str
    cpus: str
    mem: str
    gres: str

@dataclass
class SlurmNode:
    name: str
    cpu_total: int
    cpu_used: int
    mem_total_gb: int
    mem_used_gb: int
    gpu_total: int
    gpu_used: int
    status: str

@dataclass
class SlurmClusterStatus:
    nodes: List[SlurmNode]
    active_jobs: List[SlurmJob]
    pending_jobs_raw: str
    a100_summary: List[Dict[str, Any]]

class UserNameCache:
    """Handles caching of usernames to full names."""
    def __init__(self, cache_file: str = "cache-username.yaml"):
        self.cache_file = os.path.expanduser(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, str]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception:
                return {}
        return {}

    def get(self, username: str) -> Optional[str]:
        return self.cache.get(username)

    def set(self, username: str, full_name: str):
        self.cache[username] = full_name
        try:
            with open(self.cache_file, "w") as f:
                yaml.dump(self.cache, f)
        except Exception as e:
            console.debug(f"Failed to save username cache: {e}")

class SlurmClient:
    """Client to interact with Slurm cluster via SSH."""
    
    SCONTROL = "/opt/slurm/current/bin/scontrol"
    SQUEUE = "/opt/slurm/current/bin/squeue"
    SINFO = "/opt/slurm/current/bin/sinfo"

    def __init__(self, host: str, timeout: int = 10, debug: bool = False):
        self.host = host
        self.timeout = timeout
        self.debug = debug
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.cache = UserNameCache()

    def _get_ssh_config(self) -> dict:
        """Parse ~/.ssh/config to get connection details."""
        ssh_config = paramiko.SSHConfig()
        config_path = os.path.expanduser("~/.ssh/config")
        if os.path.exists(config_path):
            with open(config_path) as f:
                ssh_config.parse(f)
        
        host_info = ssh_config.lookup(self.host)
        return {
            "hostname": host_info.get("hostname", self.host),
            "username": host_info.get("user"),
            "port": int(host_info.get("port", 22)),
            "key_filename": host_info["identityfile"][0] if "identityfile" in host_info else None
        }

    def connect(self):
        """Establish or verify the SSH connection."""
        if self.ssh_client and self.ssh_client.get_transport() and self.ssh_client.get_transport().is_active():
            return

        if self.debug:
            console.debug(f"Connecting to {self.host}...")

        try:
            params = self._get_ssh_config()
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(**params, timeout=self.timeout)
        except Exception as e:
            console.error(f"SSH Connection failed to {self.host}: {e}")
            raise

    def close(self):
        """Close the SSH connection."""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None

    def get_user_full_name(self, username: str) -> str:
        """Resolve username to full name using cache or remote getent."""
        # 1. Check cache
        full_name = self.cache.get(username)
        if full_name:
            # Apply correction even to cached names in case they were cached incorrectly
            return full_name.replace("vonLLaszewski", "von Laszewski").replace("vonLaszewski", "von Laszewski")

        # 2. Fetch from remote system using getent (more reliable than grep /etc/passwd)
        self.connect()
        try:
            # getent passwd username returns: username:x:uid:gid:gecos:home:shell
            cmd = f"getent passwd {username}"
            _, stdout, _ = self.ssh_client.exec_command(cmd)
            line = stdout.read().decode("utf-8").strip()
            if line:
                fields = line.split(":")
                if len(fields) >= 5:
                    # The 5th field (index 4) contains the GECOS data.
                    # We split by comma to grab just the full name.
                    full_name = fields[4].split(",")[0].strip()
                    if full_name:
                        # Fix both variants of the name
                        full_name = full_name.replace("vonLLaszewski", "von Laszewski").replace("vonLaszewski", "von Laszewski")
                        if full_name != username:
                            self.cache.set(username, full_name)
                            return full_name
        except Exception as e:
            if self.debug:
                console.debug(f"Failed to resolve name for {username}: {e}")

        return username.replace("vonLLaszewski", "von Laszewski").replace("vonLaszewski", "von Laszewski") # Fallback to username

    def fetch_node_status(self, node_name: str) -> SlurmClusterStatus:
        """Fetch and parse status for a specific node."""
        self.connect()
        
        remote_script = f"""
        NODE="{node_name}"
        echo "===NODE_INFO==="
        {self.SCONTROL} show node "$NODE" 2>/dev/null
        echo "===ACTIVE_JOBS==="
        {self.SQUEUE} -w "$NODE" -h -o "%i|%u|%t|%M|%l|%C|%m|%b" 2>/dev/null
        echo "===PENDING_JOBS==="
        {self.SQUEUE} -t PD -w "$NODE" -o "%.10i %.12u %.5t %.10M %.20R" 2>/dev/null | head -n 11
        echo "===A100_NODES==="
        {self.SINFO} -p gpu -N -O "NodeList,Gres,GresUsed,StateLong" 2>/dev/null
        """
        
        try:
            # Use timeout on the command execution to prevent hangs
            _, stdout, stderr = self.ssh_client.exec_command(remote_script, timeout=self.timeout)
            output = stdout.read().decode("utf-8", errors="replace")
            if self.debug and stderr.read():
                console.debug(f"SSH STDERR: {stderr.read().decode()}")
            
            return self._parse_output(output, node_name)
        except Exception as e:
            # If connection dropped or timed out, try to reconnect once
            if self.debug:
                console.debug(f"Fetch failed for {node_name}, attempting reconnect: {e}")
            if self.ssh_client:
                self.close()
            self.connect()
            try:
                _, stdout, stderr = self.ssh_client.exec_command(remote_script, timeout=self.timeout)
                output = stdout.read().decode("utf-8", errors="replace")
                return self._parse_output(output, node_name)
            except Exception as re_e:
                console.error(f"Fetch failed again for {node_name}: {re_e}")
                raise

    def _parse_output(self, output: str, node_name: str) -> SlurmClusterStatus:
        sections = output.split("===")
        data = {}
        for i in range(1, len(sections), 2):
            sec_name = sections[i].strip()
            sec_content = sections[i + 1].strip() if i + 1 < len(sections) else ""
            data[sec_name] = sec_content

        # Parse Node Info
        node_info = data.get("NODE_INFO", "")
        node = SlurmNode(name=node_name, cpu_total=0, cpu_used=0, mem_total_gb=0, mem_used_gb=0, gpu_total=0, gpu_used=0, status="Unknown")
        if node_info:
            def ext(p, t, d=0):
                m = re.search(p, t)
                return int(m.group(1)) if m else d
            
            node.cpu_total = ext(r'CPUTot=(\d+)', node_info)
            node.cpu_used = ext(r'CPUAlloc=(\d+)', node_info)
            node.mem_total_gb = ext(r'RealMemory=(\d+)', node_info) // 1024
            node.mem_used_gb = ext(r'AllocMem=(\d+)', node_info) // 1024
            node.gpu_total = ext(r'Gres=.*gpu.*?:(\d+)', node_info)
            node.gpu_used = ext(r'AllocTRES=.*gres/gpu=(\d+)', node_info)
            
            # Basic status extraction
            status_match = re.search(r'State=(\S+)', node_info)
            if status_match:
                node.status = status_match.group(1)

        # Parse Active Jobs
        active_jobs = []
        active_raw = data.get("ACTIVE_JOBS", "")
        if active_raw:
            for line in active_raw.splitlines():
                p = line.split("|")
                if len(p) == 8:
                    job_id, user, status, time_str, time_limit, cpus, mem, gres = p
                    full_name = self.get_user_full_name(user)
                    active_jobs.append(SlurmJob(
                        job_id=job_id, 
                        user=user, 
                        full_name=full_name, 
                        status=status, 
                        time=time_str, 
                        time_limit=time_limit,
                        cpus=cpus, 
                        mem=mem, 
                        gres=gres
                    ))

        # Parse A100 Summary
        a100_summary = []
        a100_raw = data.get("A100_NODES", "")
        if a100_raw:
            lines = [l.strip() for l in a100_raw.splitlines() if l.strip()]
            for line in lines[1:]:
                if "a100" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        n, g, gu, s = parts[0], parts[1], parts[2], parts[3]
                        tm = re.search(r"a100.*?:(\d+)", g)
                        um = re.search(r"a100.*?:(\d+)", gu)
                        total = int(tm.group(1)) if tm else 0
                        used = int(um.group(1)) if um else 0
                        a100_summary.append({"node": n, "total": total, "used": used, "free": total-used, "state": s})

        return SlurmClusterStatus(
            nodes=[node],
            active_jobs=active_jobs,
            pending_jobs_raw=data.get("PENDING_JOBS", ""),
            a100_summary=a100_summary
        )

    def fetch_job_details(self, job_id: str) -> str:
        """Fetch detailed information for a specific Slurm job."""
        self.connect()
        try:
            cmd = f"{self.SCONTROL} show job {job_id}"
            _, stdout, stderr = self.ssh_client.exec_command(cmd, timeout=self.timeout)
            output = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            if err:
                console.error(f"Slurm Error: {err.strip()}")
            return output
        except Exception as e:
            console.error(f"Failed to fetch job details for {job_id}: {e}")
            return ""
