from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent_resume.models import Job
from agent_resume.runner_exec import run_job
from agent_resume.storage import Storage


class RunnerResumeTests(unittest.TestCase):
    def test_usage_limit_marks_partial_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = Storage(td)
            storage.ensure_dirs()
            agent_script = Path(td) / "mock_agent.py"
            agent_script.write_text(
                "\n".join(
                    [
                        "import sys",
                        "p = sys.argv[1]",
                        "print('quota exceeded' if p == 'second' else 'ok')",
                    ]
                ),
                encoding="utf-8",
            )
            job = Job(
                job_id="job_test",
                type="once",
                project_dir=td,
                session_id="s1",
                prompt_queue=["first", "second"],
                log_file_path=str(storage.log_path("job_test")),
                runner_script_path=str(storage.runners_dir / "job_test.sh"),
                queue_mode="resume",
            )
            storage.upsert_job(job)

            cfg_path = Path(td) / "cfg.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        f"storage_dir: {td}",
                        "default_agent_type: claude",
                        f"default_agent_bin: {agent_script}",
                        "claude:",
                        "  command_template: \"python {agent_bin} {prompt}\"",
                        "  usage_limit_patterns:",
                        "    - quota exceeded",
                    ]
                ),
                encoding="utf-8",
            )

            code = run_job("job_test", str(cfg_path))
            self.assertNotEqual(code, 0)
            updated = storage.get_job("job_test")
            self.assertEqual(updated.current_prompt_index, 1)
            self.assertEqual(updated.queue_status, "partially_completed")

            agent_script.write_text("print('ok')\n", encoding="utf-8")
            cfg_path.write_text(
                "\n".join(
                    [
                        f"storage_dir: {td}",
                        "default_agent_type: claude",
                        f"default_agent_bin: {agent_script}",
                        "claude:",
                        "  command_template: \"python {agent_bin} {prompt}\"",
                    ]
                ),
                encoding="utf-8",
            )
            code2 = run_job("job_test", str(cfg_path))
            self.assertEqual(code2, 0)
            final = storage.get_job("job_test")
            self.assertEqual(final.current_prompt_index, 2)
            self.assertEqual(final.queue_status, "completed")

    def test_extra_flags_injected_into_command(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = Storage(td)
            storage.ensure_dirs()
            agent_script = Path(td) / "mock_agent.py"
            # Print all args so we can verify --dangerously-skip-permissions is present
            agent_script.write_text(
                "\n".join(
                    [
                        "import sys",
                        "print(' '.join(sys.argv[1:]))",
                    ]
                ),
                encoding="utf-8",
            )
            log_path = storage.log_path("job_flags", 1)
            job = Job(
                job_id="job_flags",
                type="once",
                project_dir=td,
                session_id="s2",
                prompt_queue=["hello"],
                log_file_path=str(storage.log_path("job_flags")),
                runner_script_path=str(storage.runners_dir / "job_flags.sh"),
                queue_mode="resume",
            )
            storage.upsert_job(job)

            cfg_path = Path(td) / "cfg.yaml"
            cfg_path.write_text(
                "\n".join(
                    [
                        f"storage_dir: {td}",
                        "default_agent_type: claude",
                        f"default_agent_bin: {agent_script}",
                        "claude:",
                        "  command_template: \"python {agent_bin} {extra_flags} {prompt}\"",
                        "  extra_flags: \"--dangerously-skip-permissions\"",
                    ]
                ),
                encoding="utf-8",
            )

            code = run_job("job_flags", str(cfg_path))
            self.assertEqual(code, 0)
            output = log_path.read_text(encoding="utf-8")
            self.assertIn("--dangerously-skip-permissions", output)

    def test_extra_flags_empty_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            storage = Storage(td)
            storage.ensure_dirs()
            agent_script = Path(td) / "mock_agent.py"
            agent_script.write_text(
                "\n".join(
                    [
                        "import sys",
                        "print(' '.join(sys.argv[1:]))",
                    ]
                ),
                encoding="utf-8",
            )
            log_path = storage.log_path("job_noflags", 1)
            job = Job(
                job_id="job_noflags",
                type="once",
                project_dir=td,
                session_id="s3",
                prompt_queue=["hello"],
                log_file_path=str(storage.log_path("job_noflags")),
                runner_script_path=str(storage.runners_dir / "job_noflags.sh"),
                queue_mode="resume",
            )
            storage.upsert_job(job)

            cfg_path = Path(td) / "cfg.yaml"
            # Explicitly clear extra_flags — should produce no extra flags
            cfg_path.write_text(
                "\n".join(
                    [
                        f"storage_dir: {td}",
                        "default_agent_type: claude",
                        f"default_agent_bin: {agent_script}",
                        "claude:",
                        "  command_template: \"python {agent_bin} {extra_flags} {prompt}\"",
                        "  extra_flags: \"\"",
                    ]
                ),
                encoding="utf-8",
            )

            code = run_job("job_noflags", str(cfg_path))
            self.assertEqual(code, 0)
            output = log_path.read_text(encoding="utf-8")
            self.assertNotIn("--dangerously-skip-permissions", output)


if __name__ == "__main__":
    unittest.main()
