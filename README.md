# Cloudmesh AI resource Extension

This extension provides tools to monitor Slurm node resources and job status on remote clusters via SSH.

## Installation

### Recommended: Using pipx
For the best experience with CLI tools, use `pipx` to install `cloudmesh-ai-resource` in an isolated environment.

```bash
pipx install cloudmesh-ai-resource
```

To install from a local directory:
```bash
pipx install .
```

### Using pip
If you prefer a standard installation in your current environment:

```bash
pip install cloudmesh-ai-resource
```

To install from a local directory:
```bash
pip install .
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