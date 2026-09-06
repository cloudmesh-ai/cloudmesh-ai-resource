# Resource Command Reference

This page is automatically generated from the command-line interface definitions.

## General Usage

\`\`\`text
Usage: resource [OPTIONS] COMMAND [ARGS]...

  resource tool for monitoring Slurm node resources.

Options:
  --help  Show this message and exit.

Commands:
  job     Fetch detailed information for a specific Slurm job.
  status  Slurm Node Resource and Job Monitor (executes remotely via SSH).\`\`\`

## Job

\`\`\`text
Usage: job [OPTIONS] JOB_ID

  Fetch detailed information for a specific Slurm job.

Options:
  -H, --host TEXT        SSH destination host.  [default: uva]
  -t, --timeout INTEGER  SSH connection timeout in seconds.  [default: 10]
  -d, --debug            Show SSH connection debug messages.
  --help                 Show this message and exit.\`\`\`

## Status

\`\`\`text
Usage: status [OPTIONS]

  Slurm Node Resource and Job Monitor (executes remotely via SSH).

Options:
  -n, --node TEXT        Target Slurm node(s), comma-separated.  [default:
                         udc-an26-1]
  -H, --host TEXT        SSH destination host.  [default: uva]
  -w, --watch            Repeatedly run and update output in terminal.
  -i, --interval FLOAT   Refresh interval for watch mode in seconds.
                         [default: 10.0]
  -t, --timeout INTEGER  SSH connection timeout in seconds.  [default: 10]
  -d, --debug            Show SSH connection debug messages.
  --json                 Output data in JSON format.
  --help                 Show this message and exit.\`\`\`
