#!/usr/bin/env -S uv run --no-project --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["PyYAML>=6.0.3,<7"]
# ///
"""Render a workflow prompt as this skill's standalone uv script.

The calling agent owns graph execution, session creation, namespace bindings and
temporary state. This script validates input and callee context, preserves
workflow values and references skill:abyss. A referenced workflow is read only
when its interface is needed to default an omitted input type; resource contents
are not expanded into the prompt. Relative resource paths use the skill root.
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


def validate_definition(value: Any) -> dict[str, Any] | None:
    """Check the selected interface only; descendants remain opaque values."""
    if isinstance(value, str):
        if not value.startswith("workflow:") or not value.removeprefix("workflow:"):
            raise InvocationError("use must be a workflow: reference or an object")
        return None
    definition = mapping(value, "workflow")
    fields(
        definition,
        {"role", "input_type", "output_type", "instructions", "run", "graph"},
        "workflow",
    )
    skills([definition.get("role")], "workflow.role")
    for direction in ("input_type", "output_type"):
        ports = mapping(definition.get(direction), direction)
        if not ports:
            raise InvocationError(f"{direction} must have at least one enum")
        for port, description in ports.items():
            identifier(port, direction)
            text(description, f"{direction}.{port}")
    skills(definition.get("instructions", []), "workflow.instructions")
    if ("run" in definition) == ("graph" in definition):
        raise InvocationError("workflow must contain exactly one of run or graph")
    if "run" in definition:
        skills([definition["run"]], "workflow.run")
    else:
        graph = mapping(definition["graph"], "graph")
        fields(graph, {"nodes", "edges"}, "graph")
        mapping(graph.get("nodes"), "graph.nodes")
        edges = graph.get("edges")
        if not isinstance(edges, list) or not all(isinstance(e, str) for e in edges):
            raise InvocationError("graph.edges must be a list of edge strings")
    return definition


def validate_context(value: Any) -> dict[str, Any]:
    """Default and check callee context without importing the caller's namespace."""
    context = {} if value is None else mapping(value, "context")
    fields(context, {"resources", "parent", "sessions"}, "context")
    resources = mapping(context.get("resources", {}), "context.resources")
    fields(resources, {"skills", "workflows"}, "context.resources")
    resources = {**RESOURCE_DEFAULTS, **resources}
    for kind, location in resources.items():
        text(location, f"context.resources.{kind}")
    parent = mapping(context.get("parent", {}), "context.parent")
    fields(parent, {"role", "instructions"}, "context.parent")
    if "role" in parent:
        skills([parent["role"]], "context.parent.role")
        if parent["role"] == "^":
            raise InvocationError("context.parent.role must already be resolved")
    skills(parent.get("instructions", []), "context.parent.instructions")
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
    """Prepare workflow, input and callee context for an already bound call.

    ``workflow`` accepts a definition, an opaque workflow: reference or a call
    object. For a call object, the host has handled in/sessions bindings;
    only its use value is needed here. Input bodies are text; non-string JSON
    values are serialized as text, with enum tags kept as routing metadata.
    Omitted input uses the first declared input enum and an empty text body.
    For opaque references, only this default requires reading the definition.
    The original workflow, input and context are never mutated. Inheritance is
    interpreted by the receiving session from the definition and context.parent.
    """
    if isinstance(workflow, dict) and "use" in workflow:
        call = workflow
    else:
        call = {"use": workflow}
    fields(call, {"use", "in", "sessions"}, "call")
    definition = validate_definition(call["use"])
    context = validate_context(context)

    message = {} if input_message is None else mapping(input_message, "input message")
    fields(message, {"type", "value"}, "input message")
    if "type" not in message:
        if definition is None:
            directory = Path(context["resources"]["workflows"])
            if not directory.is_absolute():
                directory = Path(__file__).resolve().parents[1] / directory
            path = directory / f"{call['use'].removeprefix('workflow:')}.yaml"
            definition = validate_definition(
                parse_document(path.read_text(encoding="utf-8"))
            )
            if definition is None:
                raise InvocationError("referenced workflow must contain a definition")
        input_type = next(iter(definition["input_type"]))
    else:
        input_type = identifier(message["type"], "input.type")
    value = message.get("value", "")
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, allow_nan=False)

    if definition is not None:
        if input_type not in definition["input_type"]:
            raise InvocationError(f"unknown workflow input enum: {input_type}")
        if definition["role"] == "^" and "role" not in context.get("parent", {}):
            raise InvocationError("role: ^ requires context.parent.role")
    return {
        "workflow": call["use"],
        "input": {"type": input_type, "value": value},
        "context": context,
    }


def render_prompt(workflow: Any, input_message: Any = None, context: Any = None) -> str:
    """Reference skill:abyss and serialize the workflow, input and context."""
    invocation = prepare_invocation(workflow, input_message, context)
    payload = json.dumps(invocation, ensure_ascii=False, indent=2, allow_nan=False)
    return (
        "请读取并遵循 skill:abyss，使用以下 workflow、input 和 context 执行本次工作。\n\n"
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
    prompt = commands.add_parser("prompt", help="render one bound workflow invocation")
    prompt.add_argument(
        "workflow", help="YAML/JSON definition or call file, workflow: ref, or -"
    )
    inputs = prompt.add_mutually_exclusive_group()
    inputs.add_argument(
        "--input",
        help='optional input message as JSON: {"value": "natural-language text"}',
    )
    inputs.add_argument("--input-file", help="YAML/JSON input message file, or -")
    prompt.add_argument(
        "--context",
        help="execution context (resources, parent, sessions) as YAML/JSON, or -",
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
