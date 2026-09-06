# Usage Guide

The `cloudmesh-ai-resources` extension provides a set of high-level commands to monitor Slurm cluster resources and individual job details.

## 📊 Resource Status (`cmc resource status`)

The `status` command is the primary tool for monitoring node health and usage. It connects to the remote cluster, gathers data from Slurm, and presents it in a human-readable report.

### Basic Usage
To check the current state of a specific node:
```bash
cmc resource status --node udc-an26-1
```

### 🛠️ Advanced Options

#### 1. Multi-Node Monitoring
You can monitor multiple nodes in a single command by providing a comma-separated list. This is useful for checking a set of allocated nodes for a specific project.
```bash
cmc resource status --node udc-an26-1,udc-an26-2,udc-an26-3
```

#### 2. Jump Host Configuration
If your cluster is behind a gateway, use the `--host` option to specify the jump host as defined in your `~/.ssh/config`.
```bash
cmc resource status --node udc-an26-1 --host uva
```

#### 3. Real-time Monitoring (Watch Mode)
For active debugging or monitoring a job's resource consumption, use the `--watch` flag. This clears the terminal and updates the report in place.
```bash
cmc resource status --node udc-an26-1 --watch
```

**Pro Tip**: Combine `--watch` with `--interval` to control the refresh rate (default is 10s).
```bash
cmc resource status --node udc-an26-1 --watch --interval 5
```

#### 4. JSON Output for Automation
To integrate resource data into other scripts or dashboards, export the output as JSON.
```bash
cmc resource status --node udc-an26-1 --json
```

### 📉 Understanding the Output

The status report is divided into three main sections:

**1. Resource Summary**
A table showing the capacity and usage of the node:
- **CPUs**: Total vs. Allocated (Used).
- **Memory**: Real memory in GB.
- **GPUs**: Total vs. Allocated GPUs.

**2. Active Jobs Table**
A detailed list of jobs currently running on the node:
- **JobID**: The Slurm Job ID.
- **User**: The username of the job owner.
- **ST**: Status (e.g., `R` for Running).
- **Time**: Elapsed time since start.
- **Limit**: The maximum time requested for the job.
- **Left**: (Calculated) The remaining time before the job is killed.
- **GRES**: Generic resources requested (e.g., `gres/gpu:a100:4`).

**3. Pending Jobs**
A list of the top 10 jobs waiting for this node, including the **Reason** for pending (e.g., `Priority`, `Resources`, `ReqNodeNotAvail`).

---

## 🔍 Job Details (`cmc resource job`)

When you need a deep dive into a specific job's configuration, environment, and precise resource allocation, use the `job` command.

### Usage
```bash
cmc resource job <job_id>
```

**Example:**
```bash
cmc resource job 18438406
```

### What it does
This command executes `scontrol show job <job_id>` on the remote cluster. It provides comprehensive information including:
- **Job State**: Detailed state (e.g., `RUNNING`, `PENDING`, `COMPLETING`).
- **Node List**: The exact nodes the job is running on.
- **TRES**: Total Resource Specification (exact CPUs, memory, and GPUs).
- **Work Dir**: The directory where the job was submitted.
- **Standard Output/Error**: Paths to the log files.

---

## ⚙️ Configuration & Setup

### SSH Configuration
The extension relies on `paramiko` and respects your `~/.ssh/config` file. To ensure seamless connectivity, we recommend adding your cluster and jump host to your config:

```ssh-config
Host uva
    HostName uva.example.edu
    User your_user
    IdentityFile ~/.ssh/id_rsa

Host cluster-node
    HostName internal-node-name
    ProxyJump uva
    User your_user
```

### Timeouts and Debugging
If you experience connection issues, you can increase the timeout or enable debug logs:
```bash
cmc resource status --node udc-an26-1 --timeout 30 --debug
```

## ❓ Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Connection Timeout** | Network lag or firewall blocking SSH | Increase `--timeout` or check `~/.ssh/config` |
| **Permission Denied** | SSH Key not accepted by cluster | Ensure your public key is in the cluster's `authorized_keys` |
| **Slurm Error** | Slurm binaries not in `/opt/slurm/current/bin/` | Contact cluster admin to verify binary paths |
| **Empty Job Details** | Job ID no longer exists in Slurm | Verify the JobID using `squeue` |
