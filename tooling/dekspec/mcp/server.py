import asyncio
import sys
import subprocess
import shlex
from pathlib import Path
import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from dekspec.vendoring import library_root

server = Server("dekspec-mcp")

def get_skills_dir() -> Path:
    """Dynamically resolve the skills directory.
    
    1. Dev source-checkout layout check
    2. Wheel package-installed layout fallback
    3. Last resort fallback to current workspace plugins dir
    """
    lib_root = library_root()
    
    # Dev layout check
    dev_path = lib_root / "plugins" / "dekspec" / "skills"
    if dev_path.is_dir():
        return dev_path
        
    # Standard wheel-installed layout check
    pkg_path = lib_root / "skills"
    if pkg_path.is_dir():
        return pkg_path
        
    # Fallback to current directory
    workspace_path = Path.cwd() / "plugins" / "dekspec" / "skills"
    if workspace_path.is_dir():
        return workspace_path
        
    raise FileNotFoundError("Could not locate the DekSpec skills directory.")

def parse_skill_file(skill_md_path: Path) -> tuple[dict, str]:
    """Parse frontmatter and body from a SKILL.md file."""
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading {skill_md_path}: {e}", file=sys.stderr)
        return {}, ""

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = {}
            for line in parts[1].splitlines():
                line = line.strip()
                if not line or ":" not in line:
                    continue
                k, v = line.split(":", 1)
                frontmatter[k.strip()] = v.strip()
            return frontmatter, parts[2].strip()
                
    return {}, content.strip()


@server.list_prompts()
async def handle_list_prompts() -> list[types.Prompt]:
    """List all available spec-writing skills dynamically."""
    prompts = []
    try:
        skills_dir = get_skills_dir()
    except Exception as e:
        print(f"Error getting skills dir: {e}", file=sys.stderr)
        return []

    for path in skills_dir.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            skill_file = path / "SKILL.md"
            if skill_file.is_file():
                frontmatter, _ = parse_skill_file(skill_file)
                name = frontmatter.get("name", path.name)
                desc = frontmatter.get("description", f"Run the {name} skill.")
                
                # Check for argument hint in frontmatter
                arg_hint = frontmatter.get("argument-hint", "")
                prompt_args = []
                if arg_hint:
                    prompt_args.append(
                        types.PromptArgument(
                            name="arguments",
                            description=f"Arguments for the skill. Hint: {arg_hint}",
                            required=False
                        )
                    )
                
                prompts.append(
                    types.Prompt(
                        name=name,
                        description=desc,
                        arguments=prompt_args if prompt_args else None
                    )
                )
    return sorted(prompts, key=lambda x: x.name)

@server.get_prompt()
async def handle_get_prompt(name: str, arguments: dict[str, str] | None = None) -> types.GetPromptResult:
    """Serve a highly developed prompt verbatim, enriched with dynamic workspace variables."""
    try:
        skills_dir = get_skills_dir()
    except Exception as e:
        raise ValueError(f"Could not locate skills directory: {e}")

    # Find the skill folder by matching name or folder name
    skill_file = None
    for path in skills_dir.iterdir():
        if path.is_dir() and not path.name.startswith("_"):
            candidate = path / "SKILL.md"
            if candidate.is_file():
                frontmatter, _ = parse_skill_file(candidate)
                if frontmatter.get("name") == name or path.name == name:
                    skill_file = candidate
                    break
                    
    if not skill_file:
        raise ValueError(f"Skill not found: {name}")

    frontmatter, markdown_body = parse_skill_file(skill_file)
    
    # Context enrichment
    context_lines = []
    lib_root = library_root()
    
    # 1. Dynamic template injection
    template_name = ""
    if name == "write-adr":
        template_name = "adr-template.md"
    elif name == "write-ae":
        template_name = "ae-template.md"
    elif name == "write-ic":
        template_name = "ic-template.md"
    elif name == "write-ws":
        template_name = "ws-template.md"
    elif name == "write-intent":
        template_name = "intent-template.md"
    elif name == "write-mission":
        template_name = "mission-template.md"
        
    if template_name:
        t_paths = [
            lib_root / "templates" / template_name,
            lib_root / "skills" / "_lib" / "templates" / template_name,
            Path.cwd() / "dekspec" / "templates" / template_name
        ]
        template_file = None
        for tp in t_paths:
            if tp.is_file():
                template_file = tp
                break
                
        if template_file:
            try:
                t_content = template_file.read_text(encoding="utf-8")
                context_lines.append(f"\n### CANONICAL TEMPLATE ({template_name})\n```markdown\n{t_content}\n```")
            except Exception as e:
                print(f"Error reading template {template_name}: {e}", file=sys.stderr)

    # 2. Dynamic next ID calculations
    if name in ("write-adr", "write-ae", "write-intent", "write-mission", "write-ws", "write-ic", "write-ibs"):
        try:
            from dekspec._vendored.skills._lib.scripts.artifact_ops import next_id as get_next_id
            kind_map = {
                "write-adr": "adr",
                "write-ae": "ae",
                "write-intent": "intent",
                "write-mission": "mission",
                "write-ws": "ws",
                "write-ic": "ic",
                "write-ibs": "ib",
            }
            kind = kind_map[name]
            next_val = get_next_id(kind, Path.cwd())
            context_lines.append(f"* DETERMINISTIC NEXT ID FOR THIS ARTIFACT: {next_val}")
        except Exception as e:
            print(f"Error calculating next ID: {e}", file=sys.stderr)

    # 3. Dynamic glossary injections
    glossary_paths = [
        lib_root / "docs" / "dekspec-methodology.md",
        Path.cwd() / "dekspec" / "domain-glossary.md"
    ]
    for gp in glossary_paths:
        if gp.is_file():
            try:
                g_content = gp.read_text(encoding="utf-8")
                # Keep it reasonably bounded
                if len(g_content) > 10000:
                    g_content = g_content[:10000] + "\n... [truncated]"
                context_lines.append(f"\n### DOMAIN GLOSSARY REFERENCE\n```markdown\n{g_content}\n```")
                break
            except Exception:
                pass

    # 4. User arguments
    args_str = ""
    if arguments and "arguments" in arguments:
        args_str = arguments["arguments"]
        context_lines.append(f"\n### DEVELOPER INPUT ARGUMENTS\n{args_str}")

    context_block = "\n".join(context_lines)
    prompt_text = (
        "You are operating in a specialized Spec-Driven Development mode under the Google Antigravity CLI.\n"
        "You must conform to the highly developed instructions, workflows, and guardrails defined in the "
        "governing instruction set below:\n\n"
        "========================================= INSTRUCTIONS =========================================\n"
        f"{markdown_body}\n"
        "================================================================================================\n\n"
        "### REAL-TIME ACTIVE CONTEXT\n"
        f"{context_block}"
    )

    return types.GetPromptResult(
        description=f"Prompt for {name}",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=prompt_text
                )
            )
        ]
    )

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available type-safe DekSpec CLI tools and dynamic skills."""
    tools = [
        types.Tool(
            name="dekspec_compile",
            description="Run 'dekspec check compile' - parse LOCKED DekSpec artifacts and emit typed IR JSON.",
            inputSchema={
                "type": "object",
                "properties": {
                    "arguments": {
                        "type": "string",
                        "description": "Additional arguments to pass to the compiler (e.g. PATH --resolve-aes)"
                    }
                }
            }
        ),
        types.Tool(
            name="dekspec_audit",
            description="Run 'dekspec audit linkage' - graph-level consistency audit across the DekSpec artifact set.",
            inputSchema={
                "type": "object",
                "properties": {
                    "arguments": {
                        "type": "string",
                        "description": "Additional arguments to pass to the audit tool"
                    }
                }
            }
        ),
        types.Tool(
            name="dekspec_doctor",
            description="Run 'dekspec audit doctor' - full fidelity audit + drift check over the DekSpec artifact tree.",
            inputSchema={
                "type": "object",
                "properties": {
                    "arguments": {
                        "type": "string",
                        "description": "Additional arguments to pass to the doctor"
                    }
                }
            }
        ),
        types.Tool(
            name="dekspec_validate",
            description="Run 'dekspec check validate' - single-artifact schema validation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the artifact to validate"
                    },
                    "arguments": {
                        "type": "string",
                        "description": "Additional arguments to pass to the validator"
                    }
                },
                "required": ["path"]
            }
        ),
        types.Tool(
            name="dekspec_relink",
            description="Stitch the spec graph backlinks (runs 'dekspec relink'). Required step after writing any artifact.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="dekspec_session_status",
            description="Check the current status of the SDD session.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

    try:
        skills_dir = get_skills_dir()
        for path in skills_dir.iterdir():
            if path.is_dir() and not path.name.startswith("_"):
                skill_file = path / "SKILL.md"
                if skill_file.is_file():
                    frontmatter, _ = parse_skill_file(skill_file)
                    name = frontmatter.get("name", path.name)
                    desc = frontmatter.get("description", f"Load instructions and template for the {name} skill.")
                    
                    tool_name = f"dekspec_skill_{name.replace('-', '_')}"
                    tools.append(
                        types.Tool(
                            name=tool_name,
                            description=desc,
                            inputSchema={
                                "type": "object",
                                "properties": {
                                    "arguments": {
                                        "type": "string",
                                        "description": f"Developer input arguments or details for the skill. Hint: {frontmatter.get('argument-hint', '')}"
                                    }
                                }
                            }
                        )
                    )
    except Exception as e:
        print(f"Error registering skill tools: {e}", file=sys.stderr)

    return tools


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None = None) -> list[types.TextContent]:
    """Execute a DekSpec tool cleanly using the active Python environment CLI entry point."""
    if name.startswith("dekspec_skill_"):
        skill_name = name[len("dekspec_skill_"):].replace("_", "-")
        # Call the existing handle_get_prompt logic!
        prompt_res = await handle_get_prompt(skill_name, arguments)
        prompt_text = prompt_res.messages[0].content.text
        return [
            types.TextContent(
                type="text",
                text=prompt_text
            )
        ]

    subcommands = {
        "dekspec_compile": ["check", "compile"],
        "dekspec_audit": ["audit", "linkage"],
        "dekspec_doctor": ["audit", "doctor"],
        "dekspec_validate": ["check", "validate"],
        "dekspec_relink": ["relink"],
        "dekspec_session_status": ["session", "status"]
    }
    
    if name not in subcommands:
        raise ValueError(f"Unsupported tool name: {name}")
        
    cmd = [sys.executable, "-m", "dekspec.cli"] + subcommands[name]
    
    if arguments:
        if name == "dekspec_validate" and "path" in arguments:
            cmd.append(arguments["path"])
        if "arguments" in arguments and arguments["arguments"]:
            cmd.extend(shlex.split(arguments["arguments"]))
            
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30
        )
        
        output_parts = []
        if result.stdout:
            output_parts.append(result.stdout)
        if result.stderr:
            output_parts.append(result.stderr)
            
        output = "\n".join(output_parts).strip()
        if not output:
            output = f"Command exited with code {result.returncode} (no output)"
            
        return [
            types.TextContent(
                type="text",
                text=output
            )
        ]
    except subprocess.TimeoutExpired:
        return [
            types.TextContent(
                type="text",
                text="Error: The command timed out after 30 seconds."
            )
        ]
    except Exception as e:
        return [
            types.TextContent(
                type="text",
                text=f"Error running command: {e}"
            )
        ]

def main():
    """Start the stdio transport MCP server listener loop."""
    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    asyncio.run(run())

if __name__ == "__main__":
    main()
