"""Exercise implementation snapshots against real Git indexes and worktrees.

Run with ``python3 -m unittest discover -s tests -v``. No services or third-party
packages are needed; each test owns a temporary Git repository.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills/impl-snapshot/scripts/snapshot-tree.sh"
)
REF = "refs/baselines/impl/test/round-1-after"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def index_path(repo: Path) -> Path:
    return Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index"))


def working_files(repo: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(repo)): path.read_bytes()
        for path in repo.rglob("*")
        if path.is_file() and ".git" not in path.relative_to(repo).parts
    }


def repository_state(repo: Path) -> tuple[str, bytes, dict[str, bytes]]:
    return (
        git(repo, "rev-parse", "HEAD"),
        index_path(repo).read_bytes(),
        working_files(repo),
    )


def snapshot(repo: Path, ref: str = REF) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["sh", str(SCRIPT), ref], cwd=repo, capture_output=True, text=True
    )


class SnapshotTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="abyss snapshot ")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet", "--initial-branch=main")
        git(self.repo, "config", "user.name", "Snapshot Test")
        git(self.repo, "config", "user.email", "snapshot@example.invalid")
        (self.repo / ".gitignore").write_text("*.log\n")
        for name in ("tracked.txt", "deleted.txt", "staged.txt", "tracked.log"):
            (self.repo / name).write_text("original\n")
        git(self.repo, "add", "--force", "--", ".")
        git(
            self.repo,
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "--quiet",
            "-m",
            "Initial fixture",
        )

    def test_captures_working_tree_without_changing_real_staging(self) -> None:
        (self.repo / "staged.txt").write_text("staged version\n")
        git(self.repo, "add", "staged.txt")
        (self.repo / "staged.txt").write_text("working version\n")
        (self.repo / "tracked.txt").write_text("modified\n")
        (self.repo / "tracked.log").write_text("tracked despite ignore rule\n")
        (self.repo / "deleted.txt").unlink()
        (self.repo / "new.txt").write_text("untracked\n")
        (self.repo / "ignored.log").write_text("ignored\n")
        before = repository_state(self.repo)

        result = snapshot(self.repo)

        self.assertEqual(result.returncode, 0, result.stderr)
        tree = result.stdout.strip()
        self.assertEqual(git(self.repo, "cat-file", "-t", tree), "tree")
        self.assertEqual(git(self.repo, "rev-parse", REF), tree)
        self.assertEqual(repository_state(self.repo), before)
        expected = {
            ".gitignore": "*.log",
            "staged.txt": "working version",
            "tracked.txt": "modified",
            "tracked.log": "tracked despite ignore rule",
            "new.txt": "untracked",
        }
        self.assertEqual(
            set(git(self.repo, "ls-tree", "-r", "--name-only", tree).splitlines()),
            set(expected),
        )
        for name, contents in expected.items():
            self.assertEqual(git(self.repo, "show", f"{tree}:{name}"), contents)
        self.assertIn(
            "new.txt",
            git(self.repo, "diff", "HEAD", tree, "--name-only").splitlines(),
        )

    def test_ref_cannot_be_overwritten(self) -> None:
        first = snapshot(self.repo)
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.repo / "tracked.txt").write_text("later change\n")
        before = repository_state(self.repo)

        duplicate = snapshot(self.repo)

        self.assertNotEqual(duplicate.returncode, 0)
        self.assertEqual(duplicate.stdout, "")
        self.assertEqual(git(self.repo, "rev-parse", REF), first.stdout.strip())
        self.assertEqual(repository_state(self.repo), before)

    def test_linked_worktree_with_split_index_from_nested_directory(self) -> None:
        linked = Path(self.temp.name) / "linked"
        git(self.repo, "worktree", "add", "--quiet", "-b", "linked", str(linked))
        git(linked, "update-index", "--split-index")
        (linked / "staged.txt").write_text("staged\n")
        git(linked, "add", "staged.txt")
        (linked / "staged.txt").write_text("working\n")
        nested = linked / "nested"
        nested.mkdir()
        (nested / "new.txt").write_text("new file\n")
        before = repository_state(linked)

        result = snapshot(nested)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(repository_state(linked), before)
        tree = result.stdout.strip()
        self.assertEqual(git(linked, "show", f"{tree}:staged.txt"), "working")
        self.assertEqual(git(linked, "show", f"{tree}:nested/new.txt"), "new file")

    def test_unborn_repository_keeps_head_and_missing_index(self) -> None:
        unborn = Path(self.temp.name) / "unborn"
        unborn.mkdir()
        git(unborn, "init", "--quiet", "--initial-branch=main")
        (unborn / "new.txt").write_text("first file\n")
        head = (unborn / ".git/HEAD").read_bytes()
        files = working_files(unborn)

        result = snapshot(unborn)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            git(unborn, "show", f"{result.stdout.strip()}:new.txt"), "first file"
        )
        self.assertEqual((unborn / ".git/HEAD").read_bytes(), head)
        self.assertEqual(working_files(unborn), files)
        self.assertFalse(index_path(unborn).exists(), "snapshot must not create a real index")


if __name__ == "__main__":
    unittest.main()
