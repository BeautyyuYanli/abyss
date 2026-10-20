#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6.0.3,<7"]
# ///
"""Render an Abyss execution prompt as this skill's standalone uv script.

The calling agent owns graph execution, session creation, namespace bindings and
temporary state. This script validates input and callee context, preserves
workflow/action values and references skill:abyss. The selected workflow definition
is read to check its interface and instructions. Whole-field or list-item ^ in
workflow instructions is replaced with the caller's list; this materializes a
referenced definition inline while preserving instruction order and duplicates.
Caller-only context.parent is omitted from the prompt. Nested declarations and
skill references remain unexpanded. Relative resource paths use the skill root.
It can be copied and executed from any working directory; uv provides the
dependencies declared above. Stdout contains only the prompt; errors use stderr.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")
RESOURCE_DEFAULTS = {"skills": "skills", "workflows": "workflows"}


class InvocationError(ValueError):
    """The supplied invocation cannot be rendered under the DSL contract."""


class DocumentLoader(yaml.SafeLoader):
    """Reject duplicate/non-string keys instead of silently changing bindings."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise InvocationError("document mapping keys must be strings")
            if key in result:
                raise InvocationError(f"duplicate document key: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def parse_document(text: str) -> Any:
    """Read a JSON-compatible YAML/JSON document, with no resource lookups."""
    try:
        value = yaml.load(text, Loader=DocumentLoader)
        json.dumps(value, allow_nan=False)
    except (yaml.YAMLError, TypeError, ValueError, RecursionError) as error:
        raise InvocationError(f"invalid YAML/JSON document: {error}") from error
    return value


def mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InvocationError(f"{label} must be an object")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvocationError(f"{label} must be a non-empty string")
    return value


def identifier(value: Any, label: str) -> str:
    value = text(value, label)
    if not IDENTIFIER.fullmatch(value):
        raise InvocationError(f"{label} must be an identifier")
    return value


def fields(value: dict, allowed: set[str], label: str) -> None:
    unknown = value.keys() - allowed
    if unknown:
        raise InvocationError(f"unknown {label} fields: {', '.join(sorted(unknown))}")


def skills(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise InvocationError(f"{label} must be a list of skill values")
    for skill in value:
        text(skill, label)
        if skill.startswith("skill:") and not skill.removeprefix("skill:"):
            raise InvocationError(f"{label} contains an empty skill reference")
    return value


def ports(value: Any, label: str) -> dict[str, str]:
    """Validate an explicit, nonempty enum-to-description interface."""
    value = mapping(value, label)
    if not value:
        raise InvocationError(f"{label} must have at least one enum")
    for port, description in value.items():
        identifier(port, label)
        text(description, f"{label}.{port}")
    return value


def validate_action(value: Any) -> dict[str, Any]:
    """Accept one skill or a nonempty ordered list, preserving the declaration.

    Omitted interfaces are anonymous; explicit interfaces must be nonempty.
    """
    action = mapping(value, "run action")
    fields(action, {"run", "input_type", "output_type", "instructions"}, "run action")
    run = action.get("run")
    run_skills = run if isinstance(run, list) else [run]
    if not run_skills:
        raise InvocationError("run action.run must contain at least one skill")
    skills(run_skills, "run action.run")
    for direction in ("input_type", "output_type"):
        if direction in action:
            ports(action[direction], f"run action.{direction}")
    skills(action.get("instructions", []), "run action.instructions")
    return action


def validate_use(value: Any) -> dict[str, Any]:
    """Check a workflow call's declared selector, not its runtime bindings."""
    call = mapping(value, "use call")
    fields(call, {"use", "in", "sessions"}, "use call")
    selector = mapping(call.get("in"), "use call.in")
    if set(selector) == {"ref"}:
        identifier(selector["ref"], "use call.in.ref")
    elif set(selector) == {"new"}:
        config = mapping(selector["new"], "use call.in.new")
        fields(config, {"as", "workspace", "history"}, "use call.in.new")
        if "as" in config:
            identifier(config["as"], "use call.in.new.as")
        if config.get("workspace", "^") not in ("^", "fork", "none"):
            raise InvocationError("use call.in.new.workspace must be ^, fork or none")
        if config.get("history", "none") not in ("fork", "none"):
            raise InvocationError("use call.in.new.history must be fork or none")
    else:
        raise InvocationError("use call.in must contain exactly one of ref or new")
    sessions = mapping(call.get("sessions", {}), "use call.sessions")
    for alias, binding in sessions.items():
        identifier(alias, "use call.sessions alias")
        if binding == "current":
            continue
        binding = mapping(binding, "use call.sessions binding")
        fields(binding, {"ref"}, "use call.sessions binding")
        identifier(binding.get("ref"), "use call.sessions binding.ref")
    validate_workflow(call.get("use"))
    return call


def validate_node(value: Any) -> dict[str, Any]:
    """Use the same run/use node grammar in graphs and single-node workflows."""
    node = mapping(value, "node")
    if ("run" in node) == ("use" in node):
        raise InvocationError("node must contain exactly one of run or use")
    return validate_action(node) if "run" in node else validate_use(node)


def validate_endpoint(
    value: str, direction: str, definition: dict[str, Any]
) -> tuple[str, str | None]:
    """Check visible ports; referenced workflow interfaces are resolved by the host.

    Anonymous interfaces use None internally. Named inputs may omit their label
    to select the first declaration; named outputs and start/end require labels.
    """
    parts = value.split(".")
    if len(parts) not in (1, 2):
        raise InvocationError(f"invalid edge endpoint: {value}")
    name = identifier(parts[0], "edge node")
    port = identifier(parts[1], "edge port") if len(parts) == 2 else None
    if name == "start" and direction == "output":
        interface = definition["input_type"]
    elif name == "end" and direction == "input":
        interface = definition["output_type"]
    else:
        nodes = definition["graph"]["nodes"]
        if name not in nodes:
            raise InvocationError(f"unknown or misplaced edge node: {name}")
        node = nodes[name]
        if "run" in node:
            interface = node.get(f"{direction}_type")
        elif isinstance(node["use"], str):
            if direction == "output" and port is None:
                raise InvocationError(f"workflow output requires a port: {value}")
            return name, port
        else:
            interface = node["use"][f"{direction}_type"]
    if interface is None:
        if port is not None:
            raise InvocationError(f"anonymous {direction} cannot name a port: {value}")
    elif port is None:
        if direction == "output" or name == "end":
            raise InvocationError(f"named interface requires a port: {value}")
    elif port not in interface:
        raise InvocationError(f"unknown {direction} port: {value}")
    return name, port


def validate_edges(definition: dict[str, Any]) -> None:
    """Validate sequential and fork/join edges without expanding resource refs."""
    sources = set()
    for edge in definition["graph"]["edges"]:
        segments = [part.strip() for part in edge.split("->")]
        if len(segments) not in (2, 3):
            raise InvocationError(f"invalid edge: {edge}")
        source = validate_endpoint(segments[0], "output", definition)
        if source in sources:
            raise InvocationError(f"duplicate outgoing edge: {segments[0]}")
        sources.add(source)
        if len(segments) == 3:
            group = segments[1]
            if not (group.startswith("[") and group.endswith("]")):
                raise InvocationError(f"parallel edge requires a branch group: {edge}")
            for branch in group[1:-1].split(","):
                name, _ = validate_endpoint(branch.strip(), "input", definition)
                if name == "end":
                    raise InvocationError("parallel branches must be execution nodes")
        validate_endpoint(segments[-1], "input", definition)


def validate_workflow(value: Any) -> dict[str, Any] | None:
    """Check graph or single-node workflows; resource references stay opaque.

    A single run node inherits omitted interfaces from the workflow. Explicit
    node or inline callee interfaces must match the workflow's port names for
    identity forwarding; referenced callee interfaces are checked by the host.
    Instructions may be a list with ^ entries or a whole-field ^. Inheritance is
    resolved only when selected for execution; nested declarations stay unchanged.
    """
    if isinstance(value, str):
        if not value.startswith("workflow:") or not value.removeprefix("workflow:"):
            raise InvocationError("use must be a workflow: reference or an object")
        return None
    definition = mapping(value, "workflow")
    fields(
        definition,
        {"input_type", "output_type", "instructions", "graph", "node"},
        "workflow",
    )
    for direction in ("input_type", "output_type"):
        ports(definition.get(direction), f"workflow.{direction}")
    if definition.get("instructions", []) != "^":
        skills(definition.get("instructions", []), "workflow.instructions")
    if ("node" in definition) == ("graph" in definition):
        raise InvocationError("workflow must contain exactly one of node or graph")
    if "node" in definition:
        node = validate_node(definition["node"])
        interfaces = node if "run" in node else node["use"]
        if isinstance(interfaces, dict):
            for direction in ("input_type", "output_type"):
                interface = interfaces.get(direction, definition[direction])
                if interface.keys() != definition[direction].keys():
                    raise InvocationError(
                        f"single node {direction} must match workflow ports"
                    )
        return definition
    graph = mapping(definition.get("graph"), "graph")
    fields(graph, {"nodes", "edges"}, "graph")
    nodes = mapping(graph.get("nodes"), "graph.nodes")
    for name, node in nodes.items():
        identifier(name, "graph node")
        if name in ("start", "end"):
            raise InvocationError(f"reserved graph node: {name}")
        validate_node(node)
    edges = graph.get("edges")
    if not isinstance(edges, list) or not all(isinstance(e, str) for e in edges):
        raise InvocationError("graph.edges must be a list of edge strings")
    validate_edges(definition)
    return definition


def validate_context(value: Any) -> dict[str, Any]:
    """Check resources, explicit imports and caller-only inheritance input."""
    context = {} if value is None else mapping(value, "context")
    fields(context, {"resources", "parent", "sessions"}, "context")
    resources = mapping(context.get("resources", {}), "context.resources")
    fields(resources, {"skills", "workflows"}, "context.resources")
    resources = {**RESOURCE_DEFAULTS, **resources}
    for kind, location in resources.items():
        text(location, f"context.resources.{kind}")
    parent = mapping(context.get("parent", {}), "context.parent")
    fields(parent, {"instructions"}, "context.parent")
    skills(parent.get("instructions", []), "context.parent.instructions")
    if "^" in parent.get("instructions", []):
        raise InvocationError("context.parent.instructions must already be resolved")
    sessions = context.get("sessions", [])
    if not isinstance(sessions, list):
        raise InvocationError(
            "context.sessions must be a list of {ref, value} bindings"
        )
    aliases = set()
    for binding in sessions:
        binding = mapping(binding, "context.sessions binding")
        fields(binding, {"ref", "value"}, "context.sessions binding")
        alias = identifier(binding.get("ref"), "context.sessions.ref")
        text(binding.get("value"), "context.sessions.value (session ID)")
        if alias in aliases:
            raise InvocationError(f"duplicate context.sessions ref: {alias}")
        aliases.add(alias)
    return {"resources": resources, "parent": parent, "sessions": sessions}


def prepare_invocation(
    workflow: Any,
    input_message: Any = None,
    context: Any = None,
) -> dict[str, Any]:
    """Prepare a workflow handoff or local action preview without caller context.

    ``workflow`` accepts a workflow definition/reference, a use call or a local
    run action. Workflow definitions declare graph or node and named interfaces.
    A use call must declare ref/new; the host resolves its bindings, so only its
    use value goes to the callee. A standalone run action stays local and has
    one anonymous port per omitted interface, represented internally by None.
    Anonymous input envelopes omit type; null and placeholder names are invalid.
    Non-string JSON input bodies are serialized as text, with enum tags kept
    as routing metadata.
    Omitted input uses the first declared input enum and an empty text body.
    The selected referenced definition is read even for explicit input types.
    A whole-field or list-item ^ in the selected workflow's instructions expands
    the parent's list, defaulting to []; order and duplicates are preserved.
    Referenced inheriting workflows become inline. Instructions without ^ never
    inherit. Nested workflows resolve on their own activation. The output context
    contains resources and sessions.
    The original workflow, input, context and resource files are never mutated.
    """
    is_action = isinstance(workflow, dict) and "run" in workflow
    if is_action:
        selected = workflow
        definition = validate_action(selected)
        input_ports = definition.get("input_type")
    else:
        selected = (
            validate_use(workflow)["use"]
            if isinstance(workflow, dict) and "use" in workflow
            else workflow
        )
        definition = validate_workflow(selected)
        input_ports = definition["input_type"] if definition is not None else None
    context = validate_context(context)
    if definition is None:
        directory = Path(context["resources"]["workflows"])
        if not directory.is_absolute():
            directory = Path(__file__).resolve().parents[1] / directory
        path = directory / f"{selected.removeprefix('workflow:')}.yaml"
        definition = validate_workflow(parse_document(path.read_text(encoding="utf-8")))
        if definition is None:
            raise InvocationError("referenced workflow must contain a definition")
        input_ports = definition["input_type"]
    parent = context.pop("parent")
    if not is_action:
        instructions = definition.get("instructions", [])
        if instructions == "^":
            instructions = ["^"]
        if "^" in instructions:
            resolved = []
            for instruction in instructions:
                if instruction == "^":
                    resolved.extend(parent.get("instructions", []))
                else:
                    resolved.append(instruction)
            selected = {**definition, "instructions": resolved}

    message = {} if input_message is None else mapping(input_message, "input message")
    fields(message, {"type", "value"}, "input message")
    if "type" not in message:
        input_type = next(iter(input_ports)) if input_ports is not None else None
    else:
        input_type = identifier(message["type"], "input.type")
    value = message.get("value", "")
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, allow_nan=False)

    if input_ports is None and input_type is not None:
        raise InvocationError("anonymous input must omit type")
    if input_ports is not None and input_type not in input_ports:
        raise InvocationError(f"unknown input enum: {input_type}")
    message = {"value": value}
    if input_type is not None:
        message["type"] = input_type
    return {
        "workflow": selected,
        "input": message,
        "context": context,
    }


def render_prompt(workflow: Any, input_message: Any = None, context: Any = None) -> str:
    """Serialize resolved instructions, input and context without parent metadata."""
    invocation = prepare_invocation(workflow, input_message, context)
    payload = json.dumps(invocation, ensure_ascii=False, indent=2, allow_nan=False)
    return (
        "请读取并遵循 skill:abyss，使用以下 workflow、input 和 context 执行本次工作；workflow 定义使用 graph 或 node，独立 run 声明在当前会话执行动作。\n\n"
        "```json\n" + payload + "\n```\n"
    )


def read_document(path: str):
    content = (
        sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")
    )
    return parse_document(content)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abyss")
    commands = parser.add_subparsers(dest="command", required=True)
    prompt = commands.add_parser(
        "prompt", help="render a workflow handoff or local action"
    )
    prompt.add_argument(
        "workflow",
        help="YAML/JSON workflow, use call or run action, workflow: ref, or -",
    )
    inputs = prompt.add_mutually_exclusive_group()
    inputs.add_argument(
        "--input",
        help='optional input message as JSON: {"value": "natural-language text"}',
    )
    inputs.add_argument("--input-file", help="YAML/JSON input message file, or -")
    prompt.add_argument(
        "--context",
        help="generation context (resources, caller-only parent, sessions) as YAML/JSON, or -",
    )
    prompt.add_argument(
        "-o", "--output", help="write the prompt to a UTF-8 file instead of stdout"
    )
    args = parser.parse_args(argv)
    if sum(path == "-" for path in (args.workflow, args.input_file, args.context)) > 1:
        parser.error("only one input document can use stdin (-)")
    try:
        workflow = (
            args.workflow
            if args.workflow.startswith("workflow:")
            else read_document(args.workflow)
        )
        input_message = None
        if args.input is not None:
            input_message = parse_document(args.input)
        elif args.input_file is not None:
            input_message = read_document(args.input_file)
        context = read_document(args.context) if args.context else None
        rendered = render_prompt(workflow, input_message, context)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
    except (InvocationError, OSError, UnicodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
