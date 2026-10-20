"""Public prompt/validation contracts for local actions and bound workflows."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "abyss.py"


def load_cli(script):
    spec = importlib.util.spec_from_file_location("abyss_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


abyss = load_cli(SCRIPT)


@contextmanager
def installed_workflow(definition):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        script = root / "scripts" / "abyss.py"
        script.parent.mkdir()
        script.write_bytes(SCRIPT.read_bytes())
        resource = root / "workflows" / "example.yaml"
        resource.parent.mkdir()
        resource.write_text(json.dumps(definition))
        yield load_cli(script), resource


def workflow():
    return {
        "input_type": {"task": "Work to perform."},
        "output_type": {"done": "Completed work."},
        "graph": {
            "nodes": {"act": {"run": "skill:example"}},
            "edges": ["start.task -> act", "act -> end.done"],
        },
    }


def single_step_workflow():
    definition = workflow()
    del definition["graph"]
    definition["node"] = {"run": "skill:example"}
    return definition


class InvocationTests(unittest.TestCase):
    def test_minimal_action_uses_anonymous_input_and_preserves_declaration(self):
        action = {"run": "skill:example"}
        result = abyss.prepare_invocation(action, {"value": {"work": "example"}})
        self.assertEqual(result["workflow"], action)
        self.assertEqual(
            result["input"],
            {
                "value": '{"work": "example"}',
            },
        )

    def test_run_list_survives_handoffs_in_actions_graphs_and_single_nodes(self):
        action = {
            "run": ["skill:example", "Refine the previous result.", "skill:example"]
        }
        graph = workflow()
        graph["graph"]["nodes"]["act"] = action
        single = single_step_workflow()
        single["node"] = action
        parent = workflow()
        parent["graph"]["nodes"]["act"] = {"use": single, "in": {"new": {}}}
        parent["graph"]["edges"] = ["start.task -> act.task", "act.done -> end.done"]
        for declaration in (action, graph, single, parent):
            with self.subTest(declaration=declaration):
                original = copy.deepcopy(declaration)
                prompt = abyss.render_prompt(declaration, {"value": "Review the work."})
                payload = json.loads(
                    prompt.split("```json\n", 1)[1].split("\n```", 1)[0]
                )
                self.assertEqual(payload["workflow"], original)
                self.assertEqual(payload["input"]["value"], "Review the work.")
                self.assertEqual(declaration, original)

    def test_run_list_requires_at_least_one_valid_skill_and_checks_every_item(self):
        for run in (
            [],
            ["skill:example", ""],
            ["skill:example", "skill:"],
            ["skill:example", None],
            [["skill:example"]],
            [{"run": "skill:example"}],
        ):
            with self.subTest(run=run), self.assertRaises(abyss.InvocationError):
                abyss.prepare_invocation({"run": run})

    def test_action_interfaces_replace_anonymous_ports_without_mutating_inputs(self):
        action = {
            "run": "skill:example",
            "input_type": {"revision": "Existing work.", "task": "New work."},
            "output_type": {"retry": "More work needed.", "done": "Finished."},
            "instructions": ["Keep the change focused."],
        }
        original = copy.deepcopy(action)
        result = abyss.prepare_invocation(action)
        self.assertEqual(result["input"], {"type": "revision", "value": ""})
        self.assertEqual(result["workflow"], original)
        self.assertEqual(action, original)
        with self.assertRaises(abyss.InvocationError):
            abyss.prepare_invocation(action, {"type": "input"})

    def test_anonymous_input_rejects_placeholder_names_and_null_type(self):
        for name in ("input", "done", "default", None):
            with self.subTest(name=name), self.assertRaises(abyss.InvocationError):
                abyss.prepare_invocation({"run": "skill:example"}, {"type": name})

    def test_explicit_input_and_done_names_remain_valid(self):
        action = {
            "run": "skill:example",
            "input_type": {"input": "Named input."},
            "output_type": {"done": "Named result."},
        }
        result = abyss.prepare_invocation(action)
        self.assertEqual(result["input"], {"type": "input", "value": ""})
        definition = workflow()
        definition["graph"] = {
            "nodes": {"act": action},
            "edges": ["start.task -> act.input", "act.done -> end.done"],
        }
        self.assertEqual(abyss.prepare_invocation(definition)["workflow"], definition)

    def test_single_step_workflow_preserves_interfaces_and_instructions(self):
        definition = single_step_workflow()
        definition["input_type"] = {
            "revision": "Existing work.",
            "task": "New work.",
        }
        definition["output_type"] = {
            "retry": "More work needed.",
            "done": "Finished.",
        }
        definition["instructions"] = [
            "skill:persona-eden",
            "Keep the change focused.",
        ]
        original = copy.deepcopy(definition)
        result = abyss.prepare_invocation(definition, {"value": "Update work."})
        self.assertEqual(result["workflow"], original)
        self.assertEqual(result["input"], {"type": "revision", "value": "Update work."})
        self.assertEqual(definition, original)

    def test_single_step_run_node_can_inherit_either_interface(self):
        for direction in ("input_type", "output_type"):
            with self.subTest(direction=direction):
                definition = single_step_workflow()
                definition["node"][direction] = copy.deepcopy(definition[direction])
                self.assertEqual(
                    abyss.prepare_invocation(definition)["workflow"], definition
                )
                definition["node"][direction] = {"other": "Different port."}
                with self.assertRaises(abyss.InvocationError):
                    abyss.prepare_invocation(definition)

    def test_single_step_use_node_forwards_matching_callee_interfaces(self):
        for callee in (workflow(), single_step_workflow()):
            with self.subTest(callee=callee):
                definition = single_step_workflow()
                definition["node"] = {"use": callee, "in": {"new": {}}}
                self.assertEqual(
                    abyss.prepare_invocation(definition)["workflow"], definition
                )
        for direction in ("input_type", "output_type"):
            with self.subTest(direction=direction):
                definition = single_step_workflow()
                callee = single_step_workflow()
                callee[direction] = {"other": "Different port."}
                definition["node"] = {"use": callee, "in": {"new": {}}}
                with self.assertRaises(abyss.InvocationError):
                    abyss.prepare_invocation(definition)

    def test_single_step_use_node_keeps_referenced_callee_opaque(self):
        definition = single_step_workflow()
        definition["node"] = {
            "use": "workflow:unavailable",
            "in": {"ref": {"id": "session-worker"}},
            "sessions": {"peer": "current"},
        }
        self.assertEqual(abyss.prepare_invocation(definition)["workflow"], definition)

    def test_action_cannot_declare_role_or_select_a_session(self):
        for field, value in (
            ("role", "skill:persona-eden"),
            ("in", "current"),
            ("in", {"new": {}}),
            ("sessions", {}),
            ("use", "workflow:example"),
        ):
            with (
                self.subTest(field=field, value=value),
                self.assertRaises(abyss.InvocationError),
            ):
                abyss.prepare_invocation({"run": "skill:example", field: value})

    def test_omitted_interfaces_are_distinct_from_empty_or_invalid_interfaces(self):
        for direction in ("input_type", "output_type"):
            for value in ({}, None, [], {"port": ""}, {"invalid.port": "Text."}):
                with (
                    self.subTest(direction=direction, value=value),
                    self.assertRaises(abyss.InvocationError),
                ):
                    abyss.prepare_invocation({"run": "skill:example", direction: value})

    def test_use_requires_a_valid_explicit_selector(self):
        selectors = (
            None,
            "current",
            {},
            {"ref": "worker", "new": {}},
            {"ref": ""},
            {"ref": "invalid.alias"},
            {"new": None},
            {"new": {"history": "current"}},
            {"new": {"workspace": "current"}},
        )
        for selector in selectors:
            call = {"use": "workflow:example"}
            if selector is not None:
                call["in"] = selector
            definition = single_step_workflow()
            definition["node"] = call
            with (
                self.subTest(selector=selector),
                self.assertRaises(abyss.InvocationError),
            ):
                abyss.prepare_invocation(definition, {"type": "task"})

    def test_generation_rejects_outer_use_calls(self):
        definition = single_step_workflow()
        definition["node"] = {
            "use": "workflow:unavailable",
            "in": {"ref": "peer"},
        }
        for selector in (
            {"ref": "worker"},
            {"ref": {"id": "session-worker"}},
            {"new": {"as": "worker"}},
        ):
            call = {
                "use": definition,
                "in": selector,
                "sessions": {"peer": "current"},
            }
            original = copy.deepcopy(call)
            with (
                self.subTest(selector=selector),
                self.assertRaisesRegex(
                    abyss.InvocationError, "pass the use call's use value"
                ),
            ):
                abyss.prepare_invocation(call, sessions={"peer": "session-123"})
            self.assertEqual(call, original)

    def test_resolved_session_ids_are_opaque_and_work_in_selectors_and_imports(self):
        definition = single_step_workflow()
        definition["node"] = {
            "use": "workflow:unavailable",
            "in": {"ref": {"id": "123:host/session"}},
            "sessions": {"peer": {"ref": {"id": "456:host/session"}}},
        }
        result = abyss.prepare_invocation(definition, sessions={"peer": "other-id"})
        self.assertEqual(result["workflow"], definition)
        self.assertEqual(set(result), {"workflow", "input"})

    def test_invalid_resolved_refs_are_rejected_in_selectors_and_imports(self):
        for ref in (
            {},
            {"id": ""},
            {"id": " "},
            {"id": None},
            {"id": 1},
            {"id": "session-123", "name": "peer"},
            ["session-123"],
        ):
            for use_as_selector in (True, False):
                call = {"use": "workflow:unavailable", "in": {"new": {}}}
                if use_as_selector:
                    call["in"] = {"ref": ref}
                else:
                    call["sessions"] = {"peer": {"ref": ref}}
                definition = single_step_workflow()
                definition["node"] = call
                with (
                    self.subTest(ref=ref, selector=use_as_selector),
                    self.assertRaises(abyss.InvocationError),
                ):
                    abyss.prepare_invocation(definition)

    def test_imported_refs_expand_only_in_the_selected_workflow_scope(self):
        child = single_step_workflow()
        child["instructions"] = ["^", "Use peer for review."]
        child["node"] = {
            "use": "workflow:unavailable",
            "in": {"ref": "peer"},
        }
        definition = workflow()
        definition["instructions"] = ["Use peer for review."]
        definition["graph"]["nodes"] = {
            "create": {"use": "workflow:unavailable", "in": {"new": {"as": "worker"}}},
            "act": {
                "use": child,
                "in": {"ref": "peer"},
                "sessions": {
                    "peer": {"ref": "peer"},
                    "worker": {"ref": "worker"},
                    "caller": "current",
                },
            },
            "reuse": {"use": "workflow:unavailable", "in": {"ref": "worker"}},
        }
        definition["graph"]["edges"] = [
            "start.task -> create",
            "create.done -> act",
            "act.done -> reuse",
            "reuse.done -> end.done",
        ]
        original = copy.deepcopy(definition)
        sessions = {"peer": "session-123", "unused": "session-unused"}
        message = {"value": "Use peer; preserve this text."}
        result = abyss.prepare_invocation(definition, message, sessions=sessions)
        expected = copy.deepcopy(definition)
        call = expected["graph"]["nodes"]["act"]
        call["in"]["ref"] = {"id": "session-123"}
        call["sessions"]["peer"]["ref"] = {"id": "session-123"}
        self.assertEqual(result["workflow"], expected)
        self.assertEqual(result["input"]["value"], message["value"])
        self.assertEqual(set(result), {"workflow", "input"})
        self.assertEqual(definition, original)
        self.assertEqual(sessions, {"peer": "session-123", "unused": "session-unused"})
        self.assertNotIn("session-unused", json.dumps(result))

        nested = abyss.prepare_invocation(
            call["use"],
            sessions={
                "peer": "session-123",
                "worker": "session-worker",
                "caller": "session-caller",
            },
        )
        self.assertEqual(nested["workflow"]["node"]["in"]["ref"], {"id": "session-123"})
        self.assertEqual(child["node"]["in"]["ref"], "peer")

    def test_imports_do_not_capture_child_local_aliases(self):
        child = single_step_workflow()
        child["node"] = {"use": "workflow:unavailable", "in": {"new": {"as": "peer"}}}
        definition = single_step_workflow()
        definition["node"] = {"use": child, "in": {"ref": "peer"}}
        result = abyss.prepare_invocation(definition, sessions={"peer": "session-123"})
        self.assertEqual(result["workflow"]["node"]["in"]["ref"], {"id": "session-123"})
        self.assertEqual(result["workflow"]["node"]["use"], child)

    def test_session_imports_and_new_aliases_cannot_collide(self):
        declaration = {"use": "workflow:unavailable", "in": {"new": {"as": "peer"}}}
        definition = single_step_workflow()
        definition["node"] = declaration
        with self.assertRaisesRegex(abyss.InvocationError, "duplicate session alias"):
            abyss.prepare_invocation(definition, sessions={"peer": "session-123"})
        definition = workflow()
        definition["graph"]["nodes"] = {"act": declaration, "duplicate": declaration}
        definition["graph"]["edges"] = ["start.task -> act", "act.done -> end.done"]
        with self.assertRaisesRegex(abyss.InvocationError, "duplicate session alias"):
            abyss.prepare_invocation(definition)

    def test_session_generation_parameter_is_an_alias_to_id_mapping(self):
        for sessions in (
            [],
            "peer",
            {"invalid.alias": "session-123"},
            {"peer": ""},
            {"peer": None},
            {"peer": {"id": "session-123"}},
        ):
            with (
                self.subTest(sessions=sessions),
                self.assertRaises(abyss.InvocationError),
            ):
                abyss.prepare_invocation(single_step_workflow(), sessions=sessions)

    def test_use_requires_workflow_interfaces_and_exactly_one_body(self):
        missing_body = single_step_workflow()
        del missing_body["node"]
        definitions = [
            {"run": "skill:example"},
            {**workflow(), "run": "skill:example"},
            {**workflow(), "node": {"run": "skill:example"}},
            missing_body,
            {**single_step_workflow(), "node": {"run": ""}},
        ]
        for node in (
            None,
            {},
            {"run": "skill:example", "use": "workflow:example"},
            {"run": "skill:example", "role": "skill:persona-eden"},
        ):
            definitions.append({**single_step_workflow(), "node": node})
        for field in ("input_type", "output_type"):
            definition = single_step_workflow()
            del definition[field]
            definitions.append(definition)
        for definition in definitions:
            wrapper = single_step_workflow()
            wrapper["node"] = {"use": definition, "in": {"new": {}}}
            with (
                self.subTest(definition=definition),
                self.assertRaises(abyss.InvocationError),
            ):
                abyss.prepare_invocation(wrapper)

    def test_unbound_aliases_fail_in_selectors_and_import_sources(self):
        for graph in (False, True):
            for selector in (False, True):
                call = {"use": "workflow:unavailable", "in": {"new": {}}}
                if selector:
                    call["in"] = {"ref": "missing"}
                else:
                    call["sessions"] = {"peer": {"ref": "missing"}}
                definition = workflow() if graph else single_step_workflow()
                if graph:
                    definition["graph"]["nodes"]["act"] = call
                    definition["graph"]["edges"] = [
                        "start.task -> act",
                        "act.done -> end.done",
                    ]
                else:
                    definition["node"] = call
                with (
                    self.subTest(graph=graph, selector=selector),
                    self.assertRaisesRegex(
                        abyss.InvocationError, "unbound session reference: missing"
                    ),
                ):
                    abyss.prepare_invocation(
                        definition, sessions={"other": "session-123"}
                    )

    def test_new_aliases_allow_forward_references_and_runtime_reuse(self):
        definition = workflow()
        definition["graph"]["nodes"] = {
            "reuse": {
                "use": "workflow:unavailable",
                "in": {"ref": "worker"},
                "sessions": {"peer": {"ref": "worker"}},
            },
            "create": {"use": "workflow:unavailable", "in": {"new": {"as": "worker"}}},
        }
        definition["graph"]["edges"] = [
            "start.task -> create",
            "create.done -> reuse",
            "reuse.done -> create",
        ]
        self.assertEqual(abyss.prepare_invocation(definition)["workflow"], definition)

    def test_resource_paths_require_identifier_segments(self):
        for path in (
            "",
            "../outside",
            "/outside",
            "group/../outside",
            "group//review",
            "group/",
            "review.yaml",
            "group\\review",
            ".",
            "group/./review",
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(
                    abyss.InvocationError, "invalid workflow: reference"
                ):
                    abyss.prepare_invocation(f"workflow:{path}")
                for action in (
                    {"run": f"skill:{path}"},
                    {"run": "Review.", "instructions": [f"skill:{path}"]},
                ):
                    with self.assertRaisesRegex(
                        abyss.InvocationError, "invalid skill: reference"
                    ):
                        abyss.prepare_invocation(action)

    def test_nested_resource_paths_resolve_inside_the_installed_library(self):
        definition = single_step_workflow()
        definition["node"]["run"] = "skill:group_1/Review-v2"
        with installed_workflow(definition) as (installed, path):
            nested = path.parent / "group_1" / "Review-v2.yaml"
            nested.parent.mkdir()
            path.rename(nested)
            result = installed.prepare_invocation("workflow:group_1/Review-v2")
            self.assertEqual(result["workflow"], "workflow:group_1/Review-v2")
            self.assertEqual(result["input"], {"type": "task", "value": ""})

    def test_nested_resource_declarations_are_checked_without_loading_them(self):
        definition = single_step_workflow()
        definition["node"] = {"use": "workflow:../outside", "in": {"new": {}}}
        with self.assertRaisesRegex(
            abyss.InvocationError, "invalid workflow: reference"
        ):
            abyss.prepare_invocation(definition)

    def test_nested_inline_workflow_declarations_are_validated(self):
        child = workflow()
        child["graph"]["nodes"]["act"] = {
            "use": "workflow:example",
            "in": "current",
        }
        parent = workflow()
        parent["graph"]["nodes"]["act"] = {"use": child, "in": {"new": {}}}
        parent["graph"]["edges"] = ["start.task -> act", "act.done -> end.done"]
        with self.assertRaises(abyss.InvocationError):
            abyss.prepare_invocation(parent)

    def test_local_or_omitted_instructions_do_not_inherit_or_expose_parent(self):
        for base in (workflow(), single_step_workflow(), {"run": "skill:example"}):
            for instructions in (None, [], ["skill:persona-eden", "Review only."]):
                definition = copy.deepcopy(base)
                if instructions is not None:
                    definition["instructions"] = instructions
                parent = ["Keep this within the parent."]
                original_definition = copy.deepcopy(definition)
                with self.subTest(definition=definition):
                    result = abyss.prepare_invocation(
                        definition,
                        parent_instructions=parent,
                        sessions={"peer": "session-123"},
                    )
                    self.assertEqual(result["workflow"], original_definition)
                    self.assertEqual(set(result), {"workflow", "input"})
                    self.assertEqual(definition, original_definition)
                    self.assertEqual(parent, ["Keep this within the parent."])

    def test_whole_field_instruction_inheritance_is_resolved_before_handoff(self):
        for definition in (workflow(), single_step_workflow()):
            definition["instructions"] = "^"
            parent = ["skill:persona-mei", "Stay in scope."]
            original_definition = copy.deepcopy(definition)
            expected = {**definition, "instructions": parent}
            result = abyss.prepare_invocation(definition, parent_instructions=parent)
            self.assertEqual(result["workflow"], expected)
            self.assertEqual(set(result), {"workflow", "input"})
            self.assertEqual(definition, original_definition)
            self.assertEqual(parent, ["skill:persona-mei", "Stay in scope."])

    def test_instruction_list_splices_parent_at_each_marker_in_order(self):
        parent = ["skill:persona-mei", "Keep the task in scope."]
        for instructions, expected in (
            (["Before.", "^", "After."], ["Before.", *parent, "After."]),
            (["^", "Local.", "^"], [*parent, "Local.", *parent]),
            (["^", "skill:persona-mei"], [*parent, "skill:persona-mei"]),
        ):
            definition = single_step_workflow()
            definition["instructions"] = instructions
            original_definition = copy.deepcopy(definition)
            with self.subTest(instructions=instructions):
                result = abyss.prepare_invocation(
                    definition, parent_instructions=parent
                )
                self.assertEqual(result["workflow"]["instructions"], expected)
                self.assertEqual(set(result), {"workflow", "input"})
                self.assertEqual(definition, original_definition)
                self.assertEqual(
                    parent, ["skill:persona-mei", "Keep the task in scope."]
                )

    def test_instruction_markers_expand_an_empty_parent_by_default(self):
        for parent in (None, []):
            for instructions, expected in (
                ("^", []),
                (["Before.", "^", "After."], ["Before.", "After."]),
            ):
                definition = single_step_workflow()
                definition["instructions"] = instructions
                with self.subTest(parent=parent, instructions=instructions):
                    result = abyss.prepare_invocation(
                        definition, parent_instructions=parent
                    )
                    self.assertEqual(result["workflow"]["instructions"], expected)
                    self.assertEqual(set(result), {"workflow", "input"})

    def test_nested_inheritance_is_resolved_at_each_workflows_own_activation(self):
        grandchild = single_step_workflow()
        grandchild["instructions"] = ["^", "Grandchild instruction."]
        child = workflow()
        child["instructions"] = ["^", "Child instruction."]
        child["graph"]["nodes"]["act"] = {"use": grandchild, "in": {"new": {}}}
        child["graph"]["edges"] = ["start.task -> act.task", "act.done -> end.done"]
        original = copy.deepcopy(child)

        result = abyss.prepare_invocation(
            child, parent_instructions=["Parent instruction."]
        )
        self.assertEqual(
            result["workflow"]["instructions"],
            ["Parent instruction.", "Child instruction."],
        )
        call = result["workflow"]["graph"]["nodes"]["act"]
        self.assertEqual(call["use"]["instructions"], ["^", "Grandchild instruction."])
        nested = abyss.prepare_invocation(
            call["use"],
            parent_instructions=result["workflow"]["instructions"],
        )
        self.assertEqual(
            nested["workflow"]["instructions"],
            ["Parent instruction.", "Child instruction.", "Grandchild instruction."],
        )
        self.assertEqual(child, original)

    def test_parent_instructions_must_already_be_resolved(self):
        for instructions in ("^", ["^"], ["Local instruction.", "^"], {}, [None]):
            definition = single_step_workflow()
            definition["instructions"] = "^"
            with (
                self.subTest(instructions=instructions),
                self.assertRaisesRegex(abyss.InvocationError, "parent instructions"),
            ):
                abyss.prepare_invocation(definition, parent_instructions=instructions)

    def test_workflows_reject_role_context_and_resource_fields(self):
        for definition in (workflow(), single_step_workflow()):
            for key, value in (
                ("role", "skill:persona-mei"),
                ("context", {}),
                ("resources", {}),
            ):
                with (
                    self.subTest(definition=definition, key=key),
                    self.assertRaisesRegex(abyss.InvocationError, "workflow fields"),
                ):
                    abyss.prepare_invocation({**definition, key: value})

    def test_reference_lookup_uses_installation_and_input_declaration_order(self):
        for definition in (workflow(), single_step_workflow()):
            with self.subTest(definition=definition):
                definition["input_type"] = {
                    "revision": "Existing work.",
                    "task": "New work.",
                }
                if "graph" in definition:
                    definition["graph"]["edges"].insert(0, "start.revision -> act")
                with installed_workflow(definition) as (installed, _):
                    result = installed.prepare_invocation("workflow:example")
                self.assertEqual(result["workflow"], "workflow:example")
                self.assertEqual(result["input"], {"type": "revision", "value": ""})

    def test_noninheriting_reference_stays_unexpanded_with_explicit_input(self):
        definition = workflow()
        definition["instructions"] = ["Local instruction."]
        definition["graph"]["nodes"]["act"] = {
            "use": "workflow:unavailable",
            "in": {"ref": {"id": "session-worker"}},
        }
        definition["graph"]["edges"] = ["start.task -> act", "act.done -> end.done"]
        with installed_workflow(definition) as (installed, _):
            result = installed.prepare_invocation(
                "workflow:example",
                {"type": "task", "value": None},
                parent_instructions=["Parent instruction."],
            )
            self.assertEqual(result["workflow"], "workflow:example")
            self.assertEqual(result["input"], {"type": "task", "value": "null"})
            self.assertEqual(set(result), {"workflow", "input"})

    def test_inheriting_reference_is_materialized_even_with_explicit_input(self):
        for instructions in ("^", ["Before.", "^", "After."]):
            definition = single_step_workflow()
            definition["instructions"] = instructions
            for message in (None, {"type": "task", "value": "Review the work."}):
                with (
                    self.subTest(instructions=instructions, message=message),
                    installed_workflow(definition) as (installed, path),
                ):
                    resource = json.dumps(definition)
                    result = installed.prepare_invocation(
                        "workflow:example",
                        message,
                        parent_instructions=["Parent instruction."],
                    )
                    expected = (
                        ["Parent instruction."]
                        if instructions == "^"
                        else ["Before.", "Parent instruction.", "After."]
                    )
                    self.assertEqual(
                        result["workflow"], {**definition, "instructions": expected}
                    )
                    self.assertEqual(set(result), {"workflow", "input"})
                    self.assertEqual(path.read_text(), resource)

    def test_imported_bindings_materialize_referenced_workflows_without_mutation(self):
        for definition in (workflow(), single_step_workflow()):
            call = {"use": "workflow:unavailable", "in": {"ref": "peer"}}
            if "node" in definition:
                definition["node"] = call
            else:
                definition["graph"]["nodes"]["act"] = call
                definition["graph"]["edges"] = [
                    "start.task -> act",
                    "act.done -> end.done",
                ]
            with (
                self.subTest(definition=definition),
                installed_workflow(definition) as (installed, path),
            ):
                resource = path.read_text()
                result = installed.prepare_invocation(
                    "workflow:example", sessions={"peer": "session-123"}
                )
                expected = copy.deepcopy(definition)
                target = (
                    expected["node"]
                    if "node" in expected
                    else expected["graph"]["nodes"]["act"]
                )
                target["in"]["ref"] = {"id": "session-123"}
                self.assertEqual(result["workflow"], expected)
                self.assertEqual(set(result), {"workflow", "input"})
                self.assertEqual(path.read_text(), resource)
                with self.assertRaisesRegex(
                    installed.InvocationError, "unbound session reference: peer"
                ):
                    installed.prepare_invocation(
                        "workflow:example", sessions={"unused": "session-unused"}
                    )

    def test_builtin_workflows_render_with_inline_definitions(self):
        for path in (ROOT / "workflows").glob("*.yaml"):
            with self.subTest(workflow=path.stem):
                result = abyss.prepare_invocation(f"workflow:{path.stem}")
                self.assertEqual(result["input"], {"type": "task", "value": ""})


class GraphTests(unittest.TestCase):
    def test_inline_single_step_workflow_exposes_named_input_and_output_ports(self):
        child = single_step_workflow()
        child["input_type"] = {
            "draft": "Initial draft.",
            "revision": "Requested edits.",
        }
        child["output_type"] = {"accepted": "Approved.", "rejected": "Needs changes."}
        definition = workflow()
        definition["graph"]["nodes"]["act"] = {"use": child, "in": {"new": {}}}
        definition["graph"]["edges"] = [
            "start.task -> act.revision",
            "act.accepted -> end.done",
            "act.rejected -> end.done",
        ]
        self.assertEqual(abyss.prepare_invocation(definition)["workflow"], definition)
        definition["graph"]["edges"][0] = "start.task -> act.unknown"
        with self.assertRaises(abyss.InvocationError):
            abyss.prepare_invocation(definition)

    def test_anonymous_sequence_can_feed_explicit_branch_outputs(self):
        definition = workflow()
        definition["graph"]["nodes"]["classify"] = {
            "run": "skill:classify-priority",
            "output_type": {"p0": "Urgent work.", "p1": "Important work."},
        }
        definition["graph"]["edges"] = [
            "start.task -> act",
            "act -> classify",
            "classify.p0 -> end.done",
            "classify.p1 -> end.done",
        ]
        self.assertEqual(abyss.prepare_invocation(definition)["workflow"], definition)

    def test_parallel_group_accepts_anonymous_and_named_branches(self):
        child = workflow()
        child["output_type"] = {"checked": "Review outcome."}
        child["graph"]["edges"] = ["start.task -> act", "act -> end.checked"]
        definition = workflow()
        definition["graph"] = {
            "nodes": {
                "worker": {"use": child, "in": {"new": {}}},
                "local": {"run": "skill:example"},
                "join": {"run": "skill:example"},
            },
            "edges": [
                "start.task -> [worker.task, local] -> join",
                "join -> end.done",
            ],
        }
        self.assertEqual(abyss.prepare_invocation(definition)["workflow"], definition)

    def test_referenced_workflow_edges_keep_its_interface_opaque(self):
        definition = workflow()
        definition["graph"]["nodes"]["act"] = {
            "use": "workflow:unavailable",
            "in": {"ref": {"id": "session-worker"}},
        }
        definition["graph"]["edges"] = ["start.task -> act", "act.done -> end.done"]
        self.assertEqual(abyss.prepare_invocation(definition)["workflow"], definition)

    def test_anonymous_and_named_ports_cannot_be_confused_in_edges(self):
        cases = (
            ["start.task -> act.input", "act -> end.done"],
            ["start.task -> act", "act.done -> end.done"],
            ["start -> act", "act -> end.done"],
            ["start.task -> act", "act -> end"],
            ["start.task -> act", "act -> end.unknown"],
            ["start.task -> missing", "act -> end.done"],
            ["start.task -> act", "act -> end.done", "act -> end.done"],
            ["start.task -> act -> end.done"],
            ["start.task -> [] -> act", "act -> end.done"],
        )
        for edges in cases:
            definition = workflow()
            definition["graph"]["edges"] = edges
            with self.subTest(edges=edges), self.assertRaises(abyss.InvocationError):
                abyss.prepare_invocation(definition)

    def test_named_output_requires_an_explicit_label(self):
        for node in (
            {"run": "skill:example", "output_type": {"done": "Named result."}},
            {"use": "workflow:unavailable", "in": {"new": {}}},
        ):
            definition = workflow()
            definition["graph"]["nodes"]["act"] = node
            with self.subTest(node=node), self.assertRaises(abyss.InvocationError):
                abyss.prepare_invocation(definition)


class CliTests(unittest.TestCase):
    def invoke(self, declaration, *arguments):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "-", *arguments],
            input=json.dumps(declaration),
            cwd=tempfile.gettempdir(),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_action_prompt_from_an_unrelated_working_directory(self):
        for run in (
            "skill:example",
            ["skill:example", "Refine the result.", "skill:example"],
        ):
            with self.subTest(run=run):
                completed = self.invoke({"run": run})
                self.assertEqual(completed.returncode, 0, completed.stderr)
                payload = json.loads(
                    completed.stdout.split("```json\n", 1)[1].split("\n```", 1)[0]
                )
                self.assertEqual(payload["input"], {"value": ""})
                self.assertEqual(payload["workflow"], {"run": run})

    def test_single_step_workflow_prompt_from_an_unrelated_working_directory(self):
        definition = single_step_workflow()
        completed = self.invoke(definition)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(
            completed.stdout.split("```json\n", 1)[1].split("\n```", 1)[0]
        )
        self.assertEqual(payload["input"], {"type": "task", "value": ""})
        self.assertEqual(payload["workflow"], definition)

    def test_generation_parameters_expand_without_entering_the_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            parent_path = Path(directory, "parent.yaml")
            parent_path.write_text("- Parent instruction.\n")
            sessions_path = Path(directory, "sessions.yaml")
            sessions_path.write_text("peer: session-123\nunused: session-unused\n")
            message = {"value": "Review 'quoted' $value and `code`.\n第二行。"}
            input_path = Path(directory, "input.json")
            input_path.write_text(json.dumps(message))
            workflow_path = Path(directory, "workflow.json")
            for instructions, expected in (
                ("^", ["Parent instruction."]),
                (
                    ["Before.", "^", "After."],
                    ["Before.", "Parent instruction.", "After."],
                ),
                (["Local instruction."], ["Local instruction."]),
            ):
                definition = single_step_workflow()
                definition["instructions"] = instructions
                definition["node"] = {
                    "use": "workflow:unavailable",
                    "in": {"ref": "peer"},
                }
                workflow_path.write_text(json.dumps(definition))
                for stdin_parameter in (
                    "inline",
                    None,
                    "--input-file",
                    "--parent-instructions-file",
                    "--sessions-file",
                ):
                    with self.subTest(instructions=instructions, stdin=stdin_parameter):
                        command = [
                            sys.executable,
                            str(SCRIPT),
                            "-"
                            if stdin_parameter in (None, "inline")
                            else str(workflow_path),
                        ]
                        stdin = json.dumps(definition)
                        for flag, path, inline_value in (
                            ("--input-file", input_path, message),
                            (
                                "--parent-instructions-file",
                                parent_path,
                                ["Parent instruction."],
                            ),
                            (
                                "--sessions-file",
                                sessions_path,
                                {"peer": "session-123", "unused": "session-unused"},
                            ),
                        ):
                            if stdin_parameter == "inline":
                                command.extend(
                                    [
                                        flag.removesuffix("-file"),
                                        json.dumps(inline_value),
                                    ]
                                )
                            else:
                                command.extend(
                                    [
                                        flag,
                                        "-" if stdin_parameter == flag else str(path),
                                    ]
                                )
                            if stdin_parameter == flag:
                                stdin = path.read_text()
                        completed = subprocess.run(
                            command,
                            input=stdin,
                            cwd=directory,
                            capture_output=True,
                            text=True,
                            check=False,
                        )
                        self.assertEqual(completed.returncode, 0, completed.stderr)
                        payload = json.loads(
                            completed.stdout.split("```json\n", 1)[1].split("\n```", 1)[
                                0
                            ]
                        )
                        resolved = copy.deepcopy(definition)
                        resolved["instructions"] = expected
                        resolved["node"]["in"]["ref"] = {"id": "session-123"}
                        self.assertEqual(payload["workflow"], resolved)
                        self.assertEqual(payload["input"], {"type": "task", **message})
                        self.assertEqual(set(payload), {"workflow", "input"})
                        self.assertNotIn("session-unused", completed.stdout)

    def test_workflow_reference_uses_the_installed_resource_from_an_unrelated_directory(
        self,
    ):
        definition = single_step_workflow()
        definition["instructions"] = "^"
        definition["node"] = {"use": "workflow:unavailable", "in": {"ref": "peer"}}
        with (
            installed_workflow(definition) as (installed, resource),
            tempfile.TemporaryDirectory() as directory,
        ):
            cwd = Path(directory)
            (cwd / "workflows").mkdir()
            (cwd / "workflows" / "example.yaml").write_text(
                "Not the installed workflow."
            )
            (cwd / "parent.yaml").write_text("- Parent instruction.\n")
            (cwd / "sessions.yaml").write_text("peer: session-123\n")
            completed = subprocess.run(
                [
                    sys.executable,
                    installed.__file__,
                    "workflow:example",
                    "--input",
                    '{"value":"Review this."}',
                    "--parent-instructions-file",
                    "parent.yaml",
                    "--sessions-file",
                    "sessions.yaml",
                    "--output",
                    "prompt.md",
                ],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(completed.stdout, "")
            payload = json.loads(
                (cwd / "prompt.md")
                .read_text()
                .split("```json\n", 1)[1]
                .split("\n```", 1)[0]
            )
            self.assertEqual(set(payload), {"workflow", "input"})
            self.assertEqual(
                payload["workflow"]["node"]["in"]["ref"], {"id": "session-123"}
            )
            self.assertEqual(
                payload["workflow"]["instructions"], ["Parent instruction."]
            )
            self.assertEqual(
                payload["input"], {"type": "task", "value": "Review this."}
            )
            self.assertEqual(resource.read_text(), json.dumps(definition))

    def test_context_flag_is_removed(self):
        completed = self.invoke(single_step_workflow(), "--context", "context.yaml")
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("unrecognized arguments", completed.stderr)

    def test_only_one_document_can_use_stdin(self):
        for flag in ("--input-file", "--parent-instructions-file", "--sessions-file"):
            with self.subTest(flag=flag):
                completed = self.invoke(single_step_workflow(), flag, "-")
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("only one input document", completed.stderr)

    def test_duplicate_imported_session_aliases_fail_before_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "sessions.yaml")
            path.write_text("peer: session-123\npeer: session-456\n")
            completed = self.invoke(
                single_step_workflow(), "--sessions-file", str(path)
            )
            self.assertEqual(completed.returncode, 2)
            self.assertEqual(completed.stdout, "")
            self.assertIn("duplicate document key", completed.stderr)

    def test_rejected_current_selector_has_exit_two_and_empty_stdout(self):
        definition = single_step_workflow()
        definition["node"] = {"use": workflow(), "in": "current"}
        completed = self.invoke(definition)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("use call.in", completed.stderr)

    def test_inline_and_file_parameters_are_mutually_exclusive(self):
        for name, value in (
            ("input", "{}"),
            ("parent-instructions", "[]"),
            ("sessions", "{}"),
        ):
            with self.subTest(parameter=name):
                completed = self.invoke(
                    single_step_workflow(),
                    f"--{name}",
                    value,
                    f"--{name}-file",
                    "missing.yaml",
                )
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("not allowed with argument", completed.stderr)

    def test_unbound_refs_fail_with_no_prompt_or_output_file(self):
        for in_selector in (False, True):
            definition = single_step_workflow()
            definition["node"] = {"use": "workflow:unavailable", "in": {"new": {}}}
            if in_selector:
                definition["node"]["in"] = {"ref": "reviewer"}
            else:
                definition["node"]["sessions"] = {"peer": {"ref": "reviewer"}}
            with (
                self.subTest(selector=in_selector),
                tempfile.TemporaryDirectory() as directory,
            ):
                output = Path(directory, "prompt.md")
                completed = self.invoke(definition, "--output", str(output))
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn("unbound session reference: reviewer", completed.stderr)
                self.assertFalse(output.exists())

    def test_outer_use_calls_are_rejected_with_an_actionable_error(self):
        for selector in ({"new": {}}, {"ref": {"id": "session-carrier"}}):
            call = {
                "use": single_step_workflow(),
                "in": selector,
                "sessions": {"peer": "current"},
            }
            with self.subTest(selector=selector):
                completed = self.invoke(call, "--sessions", '{"peer":"session-peer"}')
                self.assertEqual(completed.returncode, 2)
                self.assertEqual(completed.stdout, "")
                self.assertIn(
                    "pass the use call's use value and resolved imports",
                    completed.stderr,
                )

    def test_workflow_references_cannot_use_paths_outside_the_library(self):
        with installed_workflow(single_step_workflow()) as (installed, resource):
            outside = resource.parent.parent / "outside.yaml"
            outside.write_text(resource.read_text())
            for reference in (
                "workflow:../outside",
                f"workflow:{outside.with_suffix('')}",
            ):
                with self.subTest(reference=reference):
                    completed = subprocess.run(
                        [sys.executable, installed.__file__, reference],
                        cwd=tempfile.gettempdir(),
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 2)
                    self.assertEqual(completed.stdout, "")
                    self.assertIn("invalid workflow: reference", completed.stderr)

    def test_rejected_anonymous_output_name_has_exit_two_and_empty_stdout(self):
        definition = workflow()
        definition["graph"]["edges"] = ["start.task -> act", "act.done -> end.done"]
        completed = self.invoke(definition)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("anonymous output", completed.stderr)


if __name__ == "__main__":
    unittest.main()
