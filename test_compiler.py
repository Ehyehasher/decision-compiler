import unittest
from compiler import run_demo, compile_package, Criterion, Constraint, Assumption, BiasCheck, Evidence, Option


class CompilerTest(unittest.TestCase):
    def test_refresh_flips_selection(self):
        demo = run_demo()
        self.assertEqual(demo["episode_1"]["selected"], "ICE")
        self.assertEqual(demo["episode_2"]["selected"], "HYB")
        self.assertTrue(demo["flipped"])
        self.assertTrue(demo["episode_1"]["signer_ready"])
        self.assertEqual(demo["episode_2"]["refresh_of"], demo["episode_1"]["hash"])

    def test_failed_bias_check_blocks_signoff(self):
        pkg = compile_package(
            "blocked",
            "question",
            [Criterion("only", "cost", 1.0, False)],
            [],
            [Assumption("a", "stated", "holds")],
            [BiasCheck("b", False, "failed on purpose")],
            [Evidence("e", "claim", "src", 1.0)],
            [Option("A", "a", {"cost": 1}, ["e"], ["a"]), Option("B", "b", {"cost": 2}, ["e"], ["a"])],
        )
        self.assertFalse(pkg.signer_ready)
        self.assertIn("b failed", pkg.blocking)


if __name__ == "__main__":
    unittest.main()
