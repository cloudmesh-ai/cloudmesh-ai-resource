import click
import sys
import os
from cloudmesh.ai.command.resource import resource_group

def generate_man_page():
    """Generates a Markdown man page for the resource extension."""
    # Use a dummy context to extract help text
    with click.Context(resource_group, info_name="resource") as ctx:
        help_text = resource_group.get_help(ctx)

    # We can also extract help for subcommands for more detail
    subcommands_help = ""
    for cmd_name in resource_group.list_commands(ctx):
        cmd = resource_group.get_command(ctx, cmd_name)
        with click.Context(cmd, info_name=cmd_name) as sub_ctx:
            subcommands_help += f"\n## {cmd_name.capitalize()}\n\n"
            subcommands_help += f"\`\`\`text\n{cmd.get_help(sub_ctx)}\`\`\`\n"

    output = (
        "# Resource Command Reference\n\n"
        "This page is automatically generated from the command-line interface definitions.\n\n"
        "## General Usage\n\n"
        f"\`\`\`text\n{help_text}\`\`\`\n"
        f"{subcommands_help}"
    )

    output_path = "docs/man.md"
    with open(output_path, "w") as f:
        f.write(output)
    
    print(f"Successfully generated man page at {output_path}")

if __name__ == "__main__":
    generate_man_page()
