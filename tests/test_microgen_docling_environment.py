import tempfile
import unittest
from pathlib import Path
from unittest import mock
import microgen_batch
import microgen_docling_environment as de


class ExistingDoclingTests(unittest.TestCase):
    def test_explicit_interpreter_has_top_priority(self):
        with mock.patch.object(de,"supports_docling") as check:
            result=de.resolve_docling_python(
                "D:/ExistingDocling/python.exe",
                main_python="C:/Default/python.exe",
                env={"MICROGEN_DOCLING_PY":"C:/Configured/python.exe"})
        self.assertEqual(result,str(Path("D:/ExistingDocling/python.exe")))
        check.assert_not_called()

    def test_machine_config_interpreter_has_priority_without_reinstall(self):
        with mock.patch.object(de,"supports_docling") as check:
            path=de.resolve_docling_python(
                main_python="C:/Default/python.exe",
                env={"MICROGEN_DOCLING_PY":"C:/Users/User/miniconda3/envs/docling_3/python.exe"})
        self.assertIn("docling_3",path)
        check.assert_not_called()

    def test_reuses_first_valid_local_conda_environment(self):
        with mock.patch.object(de,"supports_docling",side_effect=[False,False,True]) as probe,\
             mock.patch.object(de,"docling_candidates",
                               return_value=[Path("C:/docling_win/python.exe"),
                                             Path("C:/docling_3/python.exe")]):
            got=de.resolve_docling_python(main_python="C:/main/python.exe",env={})
        self.assertEqual(got,str(Path("C:/docling_3/python.exe")))
        self.assertEqual(probe.call_count,3)

    def test_main_python_is_used_when_docling_installed_there(self):
        with mock.patch.object(de,"supports_docling",return_value=True):
            got=de.resolve_docling_python(main_python="C:/ready/python.exe",env={})
        self.assertEqual(got,"C:/ready/python.exe")

    def test_unavailable_docling_does_not_trigger_pip(self):
        with mock.patch.object(de,"supports_docling",return_value=False),\
             mock.patch.object(de,"docling_candidates",return_value=[]):
            got=de.resolve_docling_python(main_python="C:/main/python.exe",env={})
        self.assertEqual(got,"C:/main/python.exe")

    def test_batch_parser_accepts_existing_environment_default(self):
        args=microgen_batch.build_parser().parse_args([
            "--source-root","D:/Data","--work-root","D:/Scratch","--targets","1.1"])
        self.assertIsNone(args.docling_py)
        self.assertEqual(args.main_py,microgen_batch.sys.executable)

    def test_reads_persisted_user_setting_if_agent_process_env_is_stale(self):
        path="C:/Users/User/AppData/Local/miniconda3/envs/docling_win/python.exe"
        with mock.patch.dict(de.os.environ, {"MICROGEN_DOCLING_PY": ""}), \
             mock.patch.object(de, "persisted_windows_docling_python", return_value=path) as user_setting, \
             mock.patch.object(de, "supports_docling") as check:
            got=de.resolve_docling_python(main_python="C:/main/python.exe")
        self.assertEqual(got, str(Path(path)))
        user_setting.assert_called_once()
        check.assert_not_called()

    def test_process_setting_overrides_stored_setting(self):
        with mock.patch.dict(de.os.environ, {"MICROGEN_DOCLING_PY": "C:/process/python.exe"}), \
             mock.patch.object(de, "persisted_windows_docling_python") as user_setting, \
             mock.patch.object(de, "supports_docling") as check:
            got=de.resolve_docling_python(main_python="C:/main/python.exe")
        self.assertEqual(got, str(Path("C:/process/python.exe")))
        user_setting.assert_not_called()
        check.assert_not_called()

    def test_explicit_env_never_leaks_windows_user_registry(self):
        with mock.patch.object(de, "persisted_windows_docling_python") as user_setting, \
             mock.patch.object(de, "supports_docling", return_value=True):
            got=de.resolve_docling_python(main_python="C:/main/python.exe", env={})
        self.assertEqual(got, "C:/main/python.exe")
        user_setting.assert_not_called()

    def test_cold_docling_probe_uses_bounded_extended_timeout(self):
        from types import SimpleNamespace
        with mock.patch.object(de.Path, "is_file", return_value=True), \
             mock.patch.object(de.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            self.assertTrue(de.supports_docling("C:/conda/python.exe"))
        self.assertGreaterEqual(run.call_args.kwargs["timeout"], 90)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 120)

    def test_docling_import_timeout_fails_closed(self):
        from subprocess import TimeoutExpired
        with mock.patch.object(de.Path, "is_file", return_value=True), \
             mock.patch.object(de.subprocess, "run", side_effect=TimeoutExpired("python", 90)):
            self.assertFalse(de.supports_docling("C:/conda/python.exe"))


if __name__=="__main__":
    unittest.main()
