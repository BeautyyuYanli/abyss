"""Public prompt/validation contracts for local actions and bound workflows."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "abyss.py"
SPEC = importlib.util.spec_from_file_location("abyss_cli", SCRIPT)
abyss = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(abyss)


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
        for selected in (
            definition,
            {"use": definition, "in": {"ref": "worker"}},
            {"use": definition, "in": {"new": {}}},
        ):
            with self.subTest(selected=selected):
                result = abyss.prepare_invocation(selected, {"value": "Update work."})
                self.assertEqual(result["workflow"], original)
                self.assertEqual(
                    result["input"], {"type": "revision", "value": "Update work."}
                )
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
            "in": {"ref": "worker"},
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
            with (
                self.subTest(selector=selector),
                self.assertRaises(abyss.InvocationError),
            ):
                abyss.prepare_invocation(call, {"type": "task"})

    def test_use_handoff_preserves_callee_and_explicit_imports_only(self):
        definition = workflow()
        context = {"sessions": [{"ref": "peer", "value": "session-123"}]}
        for selector in ({"ref": "worker"}, {"new": {"as": "worker"}}):
            call = {
                "use": definition,
                "in": selector,
                "sessions": {"peer": "current"},
            }
            original = copy.deepcopy(call)
            result = abyss.prepare_invocation(call, context=context)
            self.assertEqual(result["workflow"], definition)
            self.assertEqual(result["context"]["sessions"], context["sessions"])
            self.assertEqual(call, original)

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
            with (
                self.subTest(definition=definition),
                self.assertRaises(abyss.InvocationError),
            ):
                abyss.prepare_invocation({"use": definition, "in": {"new": {}}})

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
                context = {
                    "parent": {"instructions": ["Keep this within the parent."]},
                    "sessions": [{"ref": "peer", "value": "session-123"}],
                }
                original_definition = copy.deepcopy(definition)
                original_context = copy.deepcopy(context)
                with self.subTest(definition=definition):
                    result = abyss.prepare_invocation(definition, context=context)
                    self.assertEqual(result["workflow"], original_definition)
                    self.assertEqual(
                        result["context"],
                        {
                            "resources": {"skills": "skills", "workflows": "workflows"},
                            "sessions": original_context["sessions"],
                        },
                    )
                    self.assertEqual(definition, original_definition)
                    self.assertEqual(context, original_context)

    def test_whole_field_instruction_inheritance_is_resolved_before_handoff(self):
        for definition in (workflow(), single_step_workflow()):
            definition["instructions"] = "^"
            context = {
                "parent": {"instructions": ["skill:persona-mei", "Stay in scope."]}
            }
            original_definition = copy.deepcopy(definition)
            original_context = copy.deepcopy(context)
            expected = {**definition, "instructions": context["parent"]["instructions"]}
            for selected in (
                definition,
                {"use": definition, "in": {"ref": "worker"}},
                {"use": definition, "in": {"new": {}}},
            ):
                with self.subTest(selected=selected):
                    result = abyss.prepare_invocation(selected, context=context)
                    self.assertEqual(result["workflow"], expected)
                    self.assertEqual(set(result["context"]), {"resources", "sessions"})
                    self.assertEqual(definition, original_definition)
                    self.assertEqual(context, original_context)

    def test_instruction_list_splices_parent_at_each_marker_in_order(self):
        parent = ["skill:persona-mei", "Keep the task in scope."]
        for instructions, expected in (
            (["Before.", "^", "After."], ["Before.", *parent, "After."]),
            (["^", "Local.", "^"], [*parent, "Local.", *parent]),
            (["^", "skill:persona-mei"], [*parent, "skill:persona-mei"]),
        ):
            definition = single_step_workflow()
            definition["instructions"] = instructions
            context = {"parent": {"instructions": parent}}
            original_definition = copy.deepcopy(definition)
            original_context = copy.deepcopy(context)
            with self.subTest(instructions=instructions):
                result = abyss.prepare_invocation(definition, context=context)
                self.assertEqual(result["workflow"]["instructions"], expected)
                self.assertEqual(set(result["context"]), {"resources", "sessions"})
                self.assertEqual(definition, original_definition)
                self.assertEqual(context, original_context)

    def test_instruction_markers_expand_an_empty_parent_by_default(self):
        for context in (None, {}, {"parent": {}}, {"parent": {"instructions": []}}):
            for instructions, expected in (
                ("^", []),
                (["Before.", "^", "After."], ["Before.", "After."]),
            ):
                definition = single_step_workflow()
                definition["instructions"] = instructions
                with self.subTest(context=context, instructions=instructions):
                    result = abyss.prepare_invocation(definition, context=context)
                    self.assertEqual(result["workflow"]["instructions"], expected)
                    self.assertEqual(set(result["context"]), {"resources", "sessions"})

    def test_nested_inheritance_is_resolved_at_each_workflows_own_activation(self):
        grandchild = single_step_workflow()
        grandchild["instructions"] = ["^", "Grandchild instruction."]
        child = workflow()
        child["instructions"] = ["^", "Child instruction."]
        child["graph"]["nodes"]["act"] = {"use": grandchild, "in": {"new": {}}}
        child["graph"]["edges"] = ["start.task -> act.task", "act.done -> end.done"]
        original = copy.deepcopy(child)

        result = abyss.prepare_invocation(
            child, context={"parent": {"instructions": ["Parent instruction."]}}
        )
        self.assertEqual(
            result["workflow"]["instructions"],
            ["Parent instruction.", "Child instruction."],
        )
        call = result["workflow"]["graph"]["nodes"]["act"]
        self.assertEqual(call["use"]["instructions"], ["^", "Grandchild instruction."])
        nested = abyss.prepare_invocation(
            call,
            context={"parent": {"instructions": result["workflow"]["instructions"]}},
        )
        self.assertEqual(
            nested["workflow"]["instructions"],
            ["Parent instruction.", "Child instruction.", "Grandchild instruction."],
        )
        self.assertEqual(child, original)

    def test_parent_instructions_must_already_be_resolved(self):
        for instructions in ("^", ["^"], ["Local instruction.", "^"]):
            definition = single_step_workflow()
            definition["instructions"] = "^"
            with (
                self.subTest(instructions=instructions),
                self.assertRaisesRegex(
                    abyss.InvocationError, "context.parent.instructions"
                ),
            ):
                abyss.prepare_invocation(
                    definition, context={"parent": {"instructions": instructions}}
                )

    def test_legacy_role_fields_are_rejected_in_workflows_and_parent_context(self):
        for definition in (workflow(), single_step_workflow()):
            for role in ("skill:persona-mei", "^"):
                with self.subTest(definition=definition, role=role):
                    with self.assertRaisesRegex(
                        abyss.InvocationError, "workflow fields"
                    ):
                        abyss.prepare_invocation({**definition, "role": role})
                    with self.assertRaisesRegex(
                        abyss.InvocationError, "context.parent fields"
                    ):
                        abyss.prepare_invocation(
                            definition, context={"parent": {"role": role}}
                        )

    def test_reference_lookup_uses_resource_override_and_input_declaration_order(self):
        for definition in (workflow(), single_step_workflow()):
            with (
                self.subTest(definition=definition),
                tempfile.TemporaryDirectory() as directory,
            ):
                definition["input_type"] = {
                    "revision": "Existing work.",
                    "task": "New work.",
                }
                if "graph" in definition:
                    definition["graph"]["edges"].insert(0, "start.revision -> act")
                Path(directory, "example.yaml").write_text(json.dumps(definition))
                result = abyss.prepare_invocation(
                    "workflow:example",
                    context={"resources": {"workflows": directory}},
                )
                self.assertEqual(result["workflow"], "workflow:example")
                self.assertEqual(result["input"], {"type": "revision", "value": ""})

    def test_noninheriting_reference_stays_unexpanded_with_explicit_input(self):
        definition = workflow()
        definition["instructions"] = ["Local instruction."]
        definition["graph"]["nodes"]["act"] = {
            "use": "workflow:unavailable",
            "in": {"ref": "worker"},
        }
        definition["graph"]["edges"] = ["start.task -> act", "act.done -> end.done"]
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "example.yaml").write_text(json.dumps(definition))
            result = abyss.prepare_invocation(
                {"use": "workflow:example", "in": {"ref": "worker"}},
                {"type": "task", "value": None},
                context={
                    "resources": {"workflows": directory},
                    "parent": {"instructions": ["Parent instruction."]},
                },
            )
            self.assertEqual(result["workflow"], "workflow:example")
            self.assertEqual(result["input"], {"type": "task", "value": "null"})
            self.assertEqual(set(result["context"]), {"resources", "sessions"})

    def test_inheriting_reference_is_materialized_even_with_explicit_input(self):
        for instructions in ("^", ["Before.", "^", "After."]):
            definition = single_step_workflow()
            definition["instructions"] = instructions
            for message in (None, {"type": "task", "value": "Review the work."}):
                with (
                    self.subTest(instructions=instructions, message=message),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    path = Path(directory, "example.yaml")
                    resource = json.dumps(definition)
                    path.write_text(resource)
                    context = {
                        "resources": {"workflows": directory},
                        "parent": {"instructions": ["Parent instruction."]},
                    }
                    result = abyss.prepare_invocation(
                        "workflow:example", message, context
                    )
                    expected = (
                        ["Parent instruction."]
                        if instructions == "^"
                        else ["Before.", "Parent instruction.", "After."]
                    )
                    self.assertEqual(
                        result["workflow"], {**definition, "instructions": expected}
                    )
                    self.assertEqual(set(result["context"]), {"resources", "sessions"})
                    self.assertEqual(path.read_text(), resource)

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
            "in": {"ref": "worker"},
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
    def invoke(self, declaration):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "prompt", "-"],
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

    def test_instruction_inheritance_is_expanded_and_parent_removed_from_prompt(self):
        context = {
            "parent": {"instructions": ["Parent instruction."]},
            "sessions": [{"ref": "peer", "value": "session-123"}],
        }
        with tempfile.TemporaryDirectory() as directory:
            context_path = Path(directory, "context.json")
            context_path.write_text(json.dumps(context))
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
                with self.subTest(instructions=instructions):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(SCRIPT),
                            "prompt",
                            "-",
                            "--context",
                            str(context_path),
                        ],
                        input=json.dumps(definition),
                        cwd=directory,
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    payload = json.loads(
                        completed.stdout.split("```json\n", 1)[1].split("\n```", 1)[0]
                    )
                    self.assertEqual(
                        payload["workflow"], {**definition, "instructions": expected}
                    )
                    self.assertEqual(
                        payload["context"],
                        {
                            "resources": {"skills": "skills", "workflows": "workflows"},
                            "sessions": context["sessions"],
                        },
                    )

    def test_rejected_current_selector_has_exit_two_and_empty_stdout(self):
        completed = self.invoke({"use": workflow(), "in": "current"})
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("use call.in", completed.stderr)

    def test_rejected_anonymous_output_name_has_exit_two_and_empty_stdout(self):
        definition = workflow()
        definition["graph"]["edges"] = ["start.task -> act", "act.done -> end.done"]
        completed = self.invoke(definition)
        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("anonymous output", completed.stderr)


if __name__ == "__main__":
    unittest.main()
