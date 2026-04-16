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


if __name__ == "__main__":
    unittest.main()
