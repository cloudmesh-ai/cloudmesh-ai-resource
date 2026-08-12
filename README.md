# Cloudmesh AI resource Extension

This extension provides tools to monitor Slurm node resources and job status on remote clusters via SSH.

## Installation

### Using pip
If you prefer a standard installation in your current environment:

```bash
# This is not yet working as its not uploaded to pypi
pip install cloudmesh-ai-resource
```

To install from a local directory:
```bash
git clone https://github.com/cloudmesh-ai/cloudmesh-ai-resources.git
cd cloudmesh-ai-resources
pip install -e .
```


### Using pipx

**We have not yet tested pipx!**

Use `pipx` to install `cloudmesh-ai-resource` in an isolated environment.

```bash

pipx install cloudmesh-ai-resource
```

To install from a local directory:
```bash
pipx install .
```


## Usage Examples

### Resource Status
Check the resource usage and active jobs for one or more Slurm nodes.

1. Check status of a specific node:
   `cmc resource status --node udc-an26-1`

2. Check status of multiple nodes:
   `cmc resource status --node udc-an26-1,udc-an26-2`

3. Use a specific SSH jump host:
   `cmc resource status --node udc-an26-1 --host uva`

4. Monitor in real-time (watch mode):
   `cmc resource status --node udc-an26-1 --watch`

5. Export results as JSON:
   `cmc resource status --node udc-an26-1 --json`

6. Detailed output

```bash
$ cmc resource status                
```

```
# ----------------------------------------------------------------------
# SLURM NODE REPORT: udc-an26-1
# ----------------------------------------------------------------------
# SSH Host: uva
# ----------------------------------------------------------------------

Resource Summary
╭──────────┬────────┬────────┬──────╮                              
│ Resource │ Free   │ Total  │ Used │                        
├──────────┼────────┼────────┼──────┤                                                                                        │ CPUs     │ 96     │ 128    │ 32   | 
│ Memory   │ 1889GB │ 1953GB │ 64GB │                             
│ GPUs     │ 4      │ 8      │ 4    |
╰──────────┴────────┴────────┴──────╯                                                                                        

Active Jobs                                                            
╭──────────┬────────┬────┬───────┬─────────┬──────────┬──────┬─────┬─────────────────┬──────────────────────╮
│ JobID    │ User   │ ST │ Time  │ Limit   │ Left     │ CPUs │ Mem │ GRES            │ Full Name            |
├──────────┼────────┼────┼───────┼─────────┼──────────┼──────┼─────┼─────────────────┼──────────────────────┤
│ 18438406 │ abc101 │ R  │ 40:20 │ 3:00:00 │ 02:19:40 │ 32   │ 64G │ gres/gpu:a100:4 │ Gregor von Laszewski |
╰──────────┴────────┴────┴───────┴─────────┴──────────┴──────┴─────┴─────────────────┴──────────────────────╯                                                                                   

---- PENDING JOBS (Top 10) ----
JOBID         USER    ST       TIME     NODELIST(REASON)
MSG: Report generated on: 2026-08-12 13:28:50
MSG: Done.
```

### Job Details
Get a deep-dive into a specific Slurm job:
`cmc resource job 18438406`

### Key Features
- **Resource Summary**: Real-time view of Free, Total, and Used CPUs, Memory, and GPUs.
- **Active Jobs Table**: Detailed list of running jobs including:
    - **Time**: Time already used.
    - **Limit**: Total scheduled time limit.
    - **Left**: Calculated remaining time (`Limit - Time`).
    - **Full Name**: Resolved user names (with local caching for performance).
- **Performance**: Uses persistent SSH connections and configurable timeouts to ensure stability and speed.

## Core Dependencies
This project depends on the following core components of the Cloudmesh AI ecosystem:
- [cloudmesh-ai-common](https://github.com/cloudmesh-ai/cloudmesh-ai-common)
- [cloudmesh-ai-cmc](https://github.com/cloudmesh-ai/cloudmesh-ai-cmc)


