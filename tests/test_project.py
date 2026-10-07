"""Тесты структуры проекта: скиллы, установщик, манифесты плагина, README."""
import importlib.util
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())

spec = importlib.util.spec_from_file_location("validate", ROOT / "scripts" / "validate.py")
validate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validate)


def write_skill(base, folder, text):
    skill = Path(base) / folder
    skill.mkdir()
    (skill / "SKILL.md").write_text(text, encoding="utf-8")
    return skill


class SkillsTest(unittest.TestCase):
    def test_every_skill_passes_validation(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                self.assertEqual(validate.check_skill(skill), [])

    def test_every_skill_has_core_sections(self):
        for skill in SKILLS:
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill.name):
                self.assertIn("## Правила", text)
                self.assertRegex(text, r"## (Формат результата|Процесс|Режимы)")

    def test_every_skill_forbids_inventing_data(self):
        pattern = re.compile(r"не выдумывай|не придумывай", re.IGNORECASE)
        for skill in SKILLS:
            text = (skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill.name):
                self.assertRegex(text, pattern)


CUSTOMER_FACING = ["review-replies", "buyer-questions", "returns-claims",
                   "content-plan", "lead-triage", "commercial-offer"]


class BrandVoiceTest(unittest.TestCase):
    def test_customer_facing_skills_require_brand_voice_first(self):
        for name in CUSTOMER_FACING:
            text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=name):
                self.assertIn("## Шаг 0. Стиль общения", text)
                self.assertIn("brand-voice.md", text)
                self.assertIn("Файла нет — не пиши ответы", text)
                # Шаг 0 стоит раньше, чем входные данные и процесс.
                self.assertLess(text.index("## Шаг 0"), text.index("## Процесс") if "## Процесс" in text else len(text))

    def test_template_covers_key_questions(self):
        template = (ROOT / "skills" / "brand-voice" / "template.md").read_text(encoding="utf-8")
        for section in ["## Как обращаемся", "## Тон", "## Слова", "## Сложные ситуации",
                        "## Примеры ответов"]:
            with self.subTest(section=section):
                self.assertIn(section, template)

    def test_brand_voice_skill_links_template(self):
        text = (ROOT / "skills" / "brand-voice" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("](template.md)", text)


class ValidatorTest(unittest.TestCase):
    def test_rejects_name_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = write_skill(tmp, "good-name", "---\nname: other\ndescription: Делает. Используй, когда нужно.\n---\n")
            self.assertTrue(any("не совпадает" in e for e in validate.check_skill(skill)))

    def test_rejects_missing_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = write_skill(tmp, "x", "# Без frontmatter\n")
            self.assertTrue(any("frontmatter" in e for e in validate.check_skill(skill)))

    def test_rejects_description_without_trigger(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = write_skill(tmp, "x", "---\nname: x\ndescription: Просто описание.\n---\n")
            self.assertTrue(any("Используй" in e for e in validate.check_skill(skill)))

    def test_rejects_missing_skill_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "empty"
            skill.mkdir()
            self.assertTrue(any("SKILL.md" in e for e in validate.check_skill(skill)))

    def test_accepts_template_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = (ROOT / "docs" / "skill-template" / "SKILL.md").read_text(encoding="utf-8")
            skill = write_skill(tmp, "my-skill", text)
            self.assertEqual(validate.check_skill(skill), [])


class InstallTest(unittest.TestCase):
    def test_installs_every_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["sh", str(ROOT / "install.sh"), tmp], check=True, capture_output=True)
            installed = sorted(p.name for p in Path(tmp).iterdir())
            self.assertEqual(installed, [s.name for s in SKILLS])
            self.assertTrue((Path(tmp) / "unit-economics" / "calc.py").is_file())

    def test_reinstall_replaces_old_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "review-replies" / "stale.txt"
            stale.parent.mkdir()
            stale.write_text("old")
            subprocess.run(["sh", str(ROOT / "install.sh"), tmp], check=True, capture_output=True)
            self.assertFalse(stale.exists())


class ManifestTest(unittest.TestCase):
    def setUp(self):
        self.plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))

    def test_names_are_consistent(self):
        self.assertEqual(self.plugin["name"], self.market["plugins"][0]["name"])
        self.assertEqual(self.market["plugins"][0]["source"], "./")

    def test_version_is_semver(self):
        self.assertRegex(self.plugin["version"], r"^\d+\.\d+\.\d+$")

    def test_readme_install_command_matches_manifest(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        name = self.plugin["name"]
        self.assertIn(f"/plugin install {name}@{self.market['name']}", readme)


class ReadmeTest(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_every_skill_is_listed(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                self.assertIn(f"skills/{skill.name}/SKILL.md", self.readme)

    def test_local_links_exist(self):
        for link in re.findall(r"\]\(((?!https?://|\.\./|#)[^)]+)\)", self.readme):
            with self.subTest(link=link):
                self.assertTrue((ROOT / link).exists(), link)


if __name__ == "__main__":
    unittest.main()
