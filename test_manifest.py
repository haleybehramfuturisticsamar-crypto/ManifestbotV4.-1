"""Dependency-free static regression tests for the Manifest V11.5 source package."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "main.py").read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


class ManifestRegressionTests(unittest.TestCase):
    def test_source_compiles(self):
        compile(SOURCE, "main.py", "exec")

    def test_version_is_115(self):
        self.assertIn('VERSION = "11.5"', SOURCE)

    def test_creator_identity_uses_configured_maker_id(self):
        self.assertIn("OWNER_USER_ID = MAKER_USER_ID", SOURCE)
        self.assertIn("return user.id == OWNER_USER_ID", SOURCE)

    def test_health_payload_does_not_expose_developer_ids(self):
        health = SOURCE[SOURCE.index("async def health("):SOURCE.index("async def start_web_server(")]
        self.assertNotIn('"developer_team"', health)
        self.assertNotIn('"maker_id"', health)
        self.assertNotIn('"music_last_error"', health)
        self.assertNotIn('disconnected_for', health)

    def test_ai_channel_restriction_has_real_channel_id_check(self):
        self.assertIn('ai_channel_id = int(await setting(guild.id, "ai_channel_id", 0) or 0)', SOURCE)
        self.assertIn("message.channel.id == ai_channel_id", SOURCE)
        self.assertIn('name="ai_channel"', SOURCE)

    def test_level_role_rewards_are_persisted_and_configurable(self):
        self.assertIn("CREATE TABLE IF NOT EXISTS level_rewards", SOURCE)
        self.assertIn('name="reward_set"', SOURCE)
        self.assertIn('name="reward_remove"', SOURCE)
        self.assertIn('name="rewards"', SOURCE)
        self.assertIn("reached level {new_level}", SOURCE)

    def test_server_owners_can_configure_server_local_autopilot(self):
        self.assertIn('name="autopilot"', SOURCE)
        self.assertIn('@server_manager_or_maker()', SOURCE)
        self.assertIn('name="antinuke"', SOURCE)

    def test_history_is_scoped_by_guild_user_and_channel(self):
        self.assertIn('async def persistent_history(guild_id: int, user_id: int, channel_id: int)', SOURCE)
        self.assertIn('AND channel_id=? ORDER BY id DESC LIMIT 10', SOURCE)

    def test_commands_and_existing_features_remain(self):
        for feature in ('async def play(', 'async def ticket_panel(', 'async def create_channel(',
                        'async def leaderboard(', 'async def handle_natural_action(',
                        'async def ask_ai(', 'async def health('):
            self.assertIn(feature, SOURCE)

    def test_no_duplicate_top_level_definitions(self):
        names = [n.name for n in TREE.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
