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
        "role": "skill:persona-mei",
        "input_type": {"task": "Work to perform."},
        "output_type": {"done": "Completed work."},
        "graph": {
            "nodes": {"act": {"run": "skill:example"}},
            "edges": ["start.task -> act", "act -> end.done"],
        },
    }


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

    def test_action_cannot_override_role_or_select_a_session(self):
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

    def test_use_selects_a_workflow_graph_not_a_skill_action(self):
        for definition in (
            {"run": "skill:example"},
            {**workflow(), "run": "skill:example"},
        ):
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

    def test_inherited_workflow_role_requires_resolved_parent_context(self):
        definition = {**workflow(), "role": "^"}
        with self.assertRaises(abyss.InvocationError):
            abyss.prepare_invocation(definition)
        context = {"parent": {"role": "skill:persona-mei"}}
        self.assertEqual(
            abyss.prepare_invocation(definition, context=context)["workflow"],
            definition,
        )

    def test_reference_lookup_uses_resource_override_and_input_declaration_order(self):
        with tempfile.TemporaryDirectory() as directory:
            definition = workflow()
            definition["input_type"] = {
                "revision": "Existing work.",
                "task": "New work.",
            }
            definition["graph"]["edges"].insert(0, "start.revision -> act")
            Path(directory, "example.yaml").write_text(json.dumps(definition))
            result = abyss.prepare_invocation(
                "workflow:example",
                context={"resources": {"workflows": directory}},
            )
        self.assertEqual(result["workflow"], "workflow:example")
        self.assertEqual(result["input"], {"type": "revision", "value": ""})

    def test_explicit_input_keeps_referenced_resources_opaque(self):
        result = abyss.prepare_invocation(
            {"use": "workflow:unavailable", "in": {"ref": "worker"}},
            {"type": "task", "value": None},
        )
        self.assertEqual(result["workflow"], "workflow:unavailable")
        self.assertEqual(result["input"], {"type": "task", "value": "null"})

    def test_builtin_workflows_render_with_migrated_inline_graphs(self):
        for path in (ROOT / "workflows").glob("*.yaml"):
            with self.subTest(workflow=path.stem):
                result = abyss.prepare_invocation(f"workflow:{path.stem}")
                self.assertEqual(result["input"], {"type": "task", "value": ""})


class GraphTests(unittest.TestCase):
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
        completed = self.invoke({"run": "skill:example"})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(
            completed.stdout.split("```json\n", 1)[1].split("\n```", 1)[0]
        )
        self.assertEqual(payload["input"], {"value": ""})
        self.assertEqual(payload["workflow"], {"run": "skill:example"})

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
