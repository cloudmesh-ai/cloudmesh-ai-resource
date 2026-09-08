#!/usr/bin/env python
# probe_k8s.py
# -------------------------------------------------------------
# Detects the host environment and suggests the most suitable
# local‑Kubernetes tool (kind, minikube, k3d, or microk8s).
# -------------------------------------------------------------


# How to use the script
# ./probe_k8s.py
#    (or `python3 probe_k8s.py` on Windows).

# 3. **Read the output** – the script will print a short system summary, 
# list which of the four Kubernetes tools are already installed, show 
# which hypervisors are available, and finally give a clear recommendation 
# on what to install next.

# Feel free to modify the script (e.g., add more hypervisor 
# checks, change the RAM threshold, or tailor the install commands 
# for your distribution). The logic is deliberately straightforward 
# so you can adapt it to your own environment. Happy clustering!

#!/usr/bin/env python3
# probe_k8s.py
# -------------------------------------------------------------
# Detects the host environment and suggests the most suitable
# local‑Kubernetes tool (kind, minikube, k3d, or microk8s).
# Updated: hyperkit is no longer considered a recommended driver on macOS.
# -------------------------------------------------------------
#!/usr/bin/env python3
# probe_k8s.py (updated – includes OS version, total & free disk space)
# -------------------------------------------------------------------------
# Detects the host environment and suggests the most suitable local‑Kubernetes
# tool (kind, minikube, k3d, or microk8s).  The script now reports:
#   • OS name & version
#   • CPU cores
#   • RAM (GiB)
#   • Total & free disk space (GiB)
#   • Docker daemon status
#   • Which of the four local‑cluster tools are already installed
#   • Which hyper‑visors are present (including Apple’s native hypervisor)
#   • A concise recommendation
# -------------------------------------------------------------------------
#!/usr/bin/env python3
# probe_k8s.py (full version – TB disk output, threads, Docker detection,
#                Windows edition, plus all previous checks)
# -------------------------------------------------------------------------
# Detects the host environment and suggests the most suitable local‑Kubernetes
# tool (kind, minikube, k3d, or microk8s).
# New/changed features:
#   • Disk space displayed in TB (decimal) with % of total.
#   • CPU threads (logical) and, if psutil is present, physical cores.
#   • Detailed Docker detection:
#        – Docker CLI installed?
#        – Docker Desktop installed (macOS / Windows)?
#        – Docker daemon running?
#   • Windows edition added to System Summary.
#   • All previous functionality (OS version, RAM, hyper‑visors,
#     BIOS/UEFI VT flag, recommendation) remains unchanged.
# -------------------------------------------------------------------------

import os
import platform
import shutil
import subprocess
import sys
import time

# ----------------------------------------------------------------------
# Helper utilities
# ----------------------------------------------------------------------
def run_cmd(cmd):
    """Run a command, return (returncode, stdout). Exceptions are suppressed."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        )
        return result.returncode, result.stdout.strip()
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        return 1, ""

def get_last_backup_days():
    """Get days since last Time Machine backup (macOS only) using defaults read.
    
    Because tmutil latestbackup often fails when the backup disk is not mounted,
    we parse the 'AttemptDates' or 'SnapshotDates' from the Time Machine preferences.
    """
    if platform.system() != "Darwin":
        return None
    
    # Execute the mandatory command to get TM destination info
    rc, output = run_cmd(["defaults", "read", "/Library/Preferences/com.apple.TimeMachine", "Destinations"])
    if rc != 0 or not output:
        return None
    
    # We look for the most recent date in 'AttemptDates' or 'SnapshotDates'
    # These are listed as strings like "2026-08-29 16:36:27 +0000"
    import re
    from datetime import datetime
    
    # Regex to find dates in the format "YYYY-MM-DD HH:MM:SS +ZZZZ"
    date_pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})'
    dates = re.findall(date_pattern, output)
    
    if not dates:
        return None
    
    try:
        # Parse dates and find the maximum (most recent)
        # Format: 2026-08-29 16:36:27 +0000
        parsed_dates = [datetime.strptime(d, "%Y-%m-%d %H:%M:%S %z") for d in dates]
        latest_date = max(parsed_dates)
        
        # Calculate days since latest_date
        now = datetime.now(latest_date.tzinfo)
        delta = now - latest_date
        return int(round(delta.days))
    except Exception:
        return None

def is_executable(name):
    """True if `name` exists on the current PATH."""
    return shutil.which(name) is not None

def human_readable_tb(num_bytes):
    """Format a byte count as TB (decimal, 1 TB = 10¹² bytes)."""
    tb = num_bytes / 1_000_000_000_000
    return f"{tb:.2f} TB"

def get_cpu_counts():
    """
    Return (physical_cores, logical_threads).
    physical_cores uses psutil if available; otherwise falls back to None.
    """
    logical = os.cpu_count() or 0
    physical = None
    try:
        import psutil
        physical = psutil.cpu_count(logical=False)
    except Exception:
        pass
    return physical, logical

def get_mem_gb():
    """Return total RAM in GiB (rounded). Works on Linux, macOS, Windows."""
    system = platform.system()
    if system == "Linux":
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kB = int(line.split()[1])
                        return round(kB / (1024 * 1024), 1)
        except Exception:
            pass
    elif system == "Darwin":
        rc, out = run_cmd(["sysctl", "-n", "hw.memsize"])
        if rc == 0 and out.isdigit():
            return round(int(out) / (1024**3), 1)
    elif system == "Windows":
        rc, out = run_cmd(
            ["powershell", "-Command",
             "(Get-CimInstance -ClassName Win32_ComputerSystem).TotalPhysicalMemory"]
        )
        if rc == 0:
            try:
                total_bytes = int(out.strip())
                return round(total_bytes / (1024**3), 1)
            except ValueError:
                pass
    return None

def get_disk_usage(path="/"):
    """Return (total_bytes, used_bytes, free_bytes) for the given mount point."""
    usage = shutil.disk_usage(path)
    return usage.total, usage.used, usage.free

def check_tool(name, version_cmd):
    """Return (present, version_string)."""
    rc, out = run_cmd(version_cmd)
    if rc == 0 and out:
        version_line = out.splitlines()[0]
    else:
        version_line = ""
    return rc == 0, version_line

# ----------------------------------------------------------------------
# Docker detection helpers
# ----------------------------------------------------------------------
def check_docker_cli():
    """True if the `docker` executable is present (Docker CLI installed)."""
    return is_executable("docker")

def check_docker_daemon():
    """True if Docker daemon answers to `docker info`."""
    rc, _ = run_cmd(["docker", "info"])
    return rc == 0

def check_docker_desktop_installed():
    """Detect Docker Desktop installation (macOS or Windows). Returns path or None."""
    system = platform.system()
    if system == "Darwin":
        possible = "/Applications/Docker.app"
        return possible if os.path.isdir(possible) else None
    if system == "Windows":
        candidates = [
            r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
            r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
    return None

def check_docker_desktop_running():
    """Very crude check – looks for a Docker Desktop process."""
    system = platform.system()
    if system == "Darwin":
        rc, _ = run_cmd(["pgrep", "-x", "Docker"])
        return rc == 0
    if system == "Windows":
        rc, out = run_cmd(
            ["powershell", "-Command",
             "Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue"]
        )
        return bool(out)
    return False

# ----------------------------------------------------------------------
# macOS‑specific hypervisor detection
# ----------------------------------------------------------------------
def native_hypervisor_loaded():
    """Return True if Hypervisor.framework / Virtualization.framework is loaded."""
    if platform.system() != "Darwin":
        return False
    rc, out = run_cmd(["kextstat"])
    if rc != 0:
        return False
    return ("com.apple.Hypervisor" in out) or ("com.apple.Virtualization" in out)

def runtimes_using_native_hypervisor():
    """Detect Docker Desktop, colima, and lima – the three most common runtimes."""
    runtimes = {}
    runtimes["docker_desktop"] = shutil.which("com.docker.cli") is not None
    runtimes["colima"] = is_executable("colima")
    runtimes["lima"] = is_executable("limactl")
    return runtimes

# ----------------------------------------------------------------------
# Hypervisor detection (all platforms)
# ----------------------------------------------------------------------
def check_hypervisor():
    """
    Detect usable hypervisors on the host.
    Returns a dict mapping hypervisor name → bool.
    """
    hv = {}
    system = platform.system()

    if system == "Linux":
        hv["kvm"] = is_executable("kvm-ok") or is_executable("virsh")
        hv["virtualbox"] = is_executable("VBoxManage")
    elif system == "Darwin":
        hv["virtualbox"] = is_executable("VBoxManage")
        hv["parallels"] = is_executable("prlctl")
        hv["vmware"] = is_executable("vmrun")
        hv["apple_native"] = native_hypervisor_loaded()
    elif system == "Windows":
        rc, out = run_cmd(["powershell", "-Command", "Get-Service -Name vmms"])
        hv["hyperv"] = rc == 0 and "Running" in out
        hv["virtualbox"] = is_executable("VBoxManage")
    return hv

# ----------------------------------------------------------------------
# BIOS / firmware virtualization flag detection (Linux & Windows)
# ----------------------------------------------------------------------
def linux_virtualization_enabled():
    """Parse /proc/cpuinfo for vmx (Intel) or svm (AMD) flag."""
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if line.startswith("flags"):
                    flags = line.split(":")[1].strip().split()
                    return "vmx" in flags or "svm" in flags
    except Exception:
        return None
    return None

def windows_virtualization_enabled():
    """Query WMI for VirtualizationFirmwareEnabled."""
    ps_cmd = [
        "powershell",
        "-Command",
        "(Get-CimInstance -ClassName Win32_Processor).VirtualizationFirmwareEnabled"
    ]
    rc, out = run_cmd(ps_cmd)
    if rc == 0 and out:
        val = out.strip().lower()
        if val == "true":
            return True
        if val == "false":
            return False
    return None

def get_firmware_virtualization():
    """Return True/False/None depending on OS."""
    sys = platform.system()
    if sys == "Linux":
        return linux_virtualization_enabled()
    if sys == "Windows":
        return windows_virtualization_enabled()
    # macOS does not expose a BIOS‑level flag we can query
    return None

# ----------------------------------------------------------------------
# Windows edition detection
# ----------------------------------------------------------------------
def get_windows_edition():
    """Return a string with the Windows edition (Home, Pro, Enterprise, …) or None."""
    if platform.system() != "Windows":
        return None
    # Primary method – works on recent Windows 10/11 builds
    rc, out = run_cmd([
        "powershell",
        "-Command",
        "(Get-ComputerInfo).WindowsEdition"
    ])
    if rc == 0 and out:
        return out.strip()
    # Fallback for older builds
    rc, out = run_cmd([
        "powershell",
        "-Command",
        "(Get-CimInstance -ClassName Win32_OperatingSystem).Caption"
    ])
    if rc == 0 and out:
        parts = out.strip().split()
        if len(parts) >= 3:
            return parts[-1]
    return None

# ----------------------------------------------------------------------
# Recommendation engine
# ----------------------------------------------------------------------
def recommend():
    # Basic OS info
    os_name     = platform.system()
    os_version  = platform.platform()
    windows_edition = get_windows_edition()

    # CPU & memory
    physical_cores, logical_threads = get_cpu_counts()
    mem_gb = get_mem_gb()

    # Disk
    total_b, used_b, free_b = get_disk_usage("/")
    total_hr = human_readable_tb(total_b)
    used_hr  = human_readable_tb(used_b)
    free_hr  = human_readable_tb(free_b)
    used_pct = f"{(used_b / total_b * 100):.1f}%" if total_b else "N/A"
    free_pct = f"{(free_b / total_b * 100):.1f}%" if total_b else "N/A"

    # Docker status
    docker_cli_installed   = check_docker_cli()
    docker_daemon_running  = check_docker_daemon()
    docker_desktop_path    = check_docker_desktop_installed()
    docker_desktop_running = check_docker_desktop_running()

    # Firmware VT flag
    firmware_vt = get_firmware_virtualization()

    # Detect installed cluster tools
    tools = {}
    tools["kind"],    kind_ver     = check_tool("kind",    ["kind",    "version"])
    tools["minikube"],minikube_ver = check_tool("minikube",["minikube","version"])
    tools["k3d"],     k3d_ver      = check_tool("k3d",     ["k3d",     "version"])
    tools["microk8s"],microk8s_ver = check_tool("microk8s",["microk8s","status"])

    # Last backup status (macOS only)
    last_backup_days = get_last_backup_days()

    # Hypervisors
    hypervisors = check_hypervisor()
    native_hv   = hypervisors.get("apple_native", False)
    runtime_hv  = runtimes_using_native_hypervisor()

    # --------------------------------------------------------------
    # Pretty‑print a summary
    # --------------------------------------------------------------
    print("\n=== System Summary ===")
    print(f"OS                : {os_name}")
    print(f"OS version        : {os_version}")
    if windows_edition:
        print(f"Windows edition   : {windows_edition}")
    if last_backup_days is not None:
        print(f"Last TM backup    : {last_backup_days} days ago")
    elif os_name == "Darwin":
        print(f"Last TM backup    : not found")
    print(f"CPU cores (physical) : {physical_cores if physical_cores is not None else 'unknown'}")
    print(f"CPU threads (logical) : {logical_threads}")
    print(f"Memory (GiB)      : {mem_gb if mem_gb is not None else 'unknown'}")
    print(f"Disk total        : {total_hr}")
    print(f"Disk used         : {used_hr} ({used_pct})")
    print(f"Disk free         : {free_hr} ({free_pct})")
    print(f"Docker CLI installed    : {'yes' if docker_cli_installed else 'no'}")
    print(f"Docker daemon running   : {'yes' if docker_daemon_running else 'no'}")
    print(f"Docker Desktop installed: {'yes' if docker_desktop_path else 'no'}")
    print(f"Docker Desktop running  : {'yes' if docker_desktop_running else 'no'}")
    if firmware_vt is True:
        print("Firmware VT flag  : enabled")
    elif firmware_vt is False:
        print("Firmware VT flag  : disabled")
    elif firmware_vt is None:
        print("Firmware VT flag  : not applicable / unknown")
    else:
        print("Firmware VT flag  : unknown")

    print("\n=== Detected Local‑Cluster Tools ===")
    for t, present in tools.items():
        ver = {"kind": kind_ver,
               "minikube": minikube_ver,
               "k3d": k3d_ver,
               "microk8s": microk8s_ver}[t]
        print(f"{t:<11}: {'✔' if present else '✘'}  {ver}")

    print("\n=== Detected Hypervisors ===")
    for hv, ok in hypervisors.items():
        print(f"{hv:<22}: {'✔' if ok else '✘'}")

    print("\n=== Detected Runtime Using macOS Native Hypervisor ===")
    for rt, ok in runtime_hv.items():
        print(f"{rt:<15}: {'✔' if ok else '✘'}")

    # --------------------------------------------------------------
    # Decision tree – recommendation
    # --------------------------------------------------------------
    print("\n=== Recommendation ===")

    # 1️⃣ Docker daemon is up – container‑based tools are the simplest path
    if docker_daemon_running:
        if mem_gb is not None and mem_gb < 4:
            if tools["k3d"]:
                print("Docker daemon is running and you have limited RAM (< 4 GiB).")
                print("→ Recommended: k3d – lightweight k3s inside Docker.")
            else:
                print("Docker daemon is running but k3d is not installed.")
                print("→ Install k3d:\n   curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash")
        else:
            if tools["kind"]:
                print("Docker daemon is running and you have enough RAM.")
                print("→ Recommended: kind – fast, multi‑node capable, works wherever Docker works.")
            else:
                print("Docker daemon is running but kind is not installed.")
                print("→ Install kind:\n   curl -Lo ./kind https://kind.sigs.k8s.io/download/v0.23.0/kind-$(uname -s)-$(uname -m) && \\")
                print("   chmod +x ./kind && sudo mv ./kind /usr/local/bin/")
        return

    # 2️⃣ Docker CLI present but daemon not running – suggest starting it
    if docker_cli_installed and not docker_daemon_running:
        print("Docker CLI is installed but the Docker daemon is not running.")
        if docker_desktop_path:
            print("→ Start Docker Desktop (or run `dockerd` manually) and retry.")
        else:
            print("→ Install Docker Desktop or start the Docker daemon via your init system.")
        return

    # 3️⃣ No Docker – can we use the native macOS hypervisor directly?
    if native_hv:
        if runtime_hv["colima"]:
            print("macOS native hypervisor is present and `colima` is installed.")
            print("→ Use colima (e.g. `colima start && colima nerdctl …`).")
        elif runtime_hv["lima"]:
            print("macOS native hypervisor is present and `lima` is installed.")
            print("→ Start a Lima VM (`limactl start`) and run minikube inside it.")
        else:
            print("macOS native hypervisor is present but no runtime (Docker Desktop, colima, lima) is installed.")
            print("→ Install one of the following:")
            print("   • Docker Desktop (includes Kubernetes)")
            print("   • colima (`brew install colima && colima start`)")
            print("   • lima (`brew install lima && limactl start`)")
        return

    # 4️⃣ Fallback to classic VM‑based minikube
    driver = None
    if os_name == "Linux":
        if hypervisors.get("kvm"):
            driver = "kvm2"
        elif hypervisors.get("virtualbox"):
            driver = "virtualbox"
    elif os_name == "Darwin":
        if hypervisors.get("virtualbox"):
            driver = "virtualbox"
        elif hypervisors.get("parallels"):
            driver = "parallels"
        elif hypervisors.get("vmware"):
            driver = "vmwarefusion"
    elif os_name == "Windows":
        if hypervisors.get("hyperv"):
            driver = "hyperv"
        elif hypervisors.get("virtualbox"):
            driver = "virtualbox"

    if driver:
        if tools["minikube"]:
            print(f"A supported hypervisor ({driver}) is available and Docker is not running.")
            print(f"→ Recommended: minikube with the `{driver}` driver.")
            print(f"   Start it with: minikube start --driver={driver}")
        else:
            print(f"A supported hypervisor ({driver}) is available but minikube is not installed.")
            print("→ Install minikube:\n   curl -Lo minikube https://storage.googleapis.com/minikube/releases/latest/minikube-$(uname -s)-$(uname -m) && \\")
            print("   chmod +x minikube && sudo mv minikube /usr/local/bin/")
        return

    # 5️⃣ Nothing detected – give concrete next‑step options
    print("No Docker daemon, no native macOS hypervisor runtime, and no supported VM driver were found.")
    print("\nPractical ways forward:")
    print("  1️⃣ Install Docker Desktop (or colima/lima) – then use kind/k3d/minikube with the Docker driver.")
    print("  2️⃣ Install a third‑party hypervisor (VirtualBox, Parallels, VMware Fusion) – then use minikube.")
    print("  3️⃣ On Ubuntu you could install MicroK8s via snap (not applicable on macOS).")
    print("\n--- End of recommendation ---\n")

# ----------------------------------------------------------------------
if __name__ == "__main__":
    if sys.version_info < (3, 7):
        sys.exit("Python 3.7+ is required.")
    recommend()