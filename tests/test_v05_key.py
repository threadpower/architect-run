"""v0.5 gate 2: a parked Anthropic key. One word out, no key, no hash, no network, no builder."""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_v01 import Base, HERE, read, write  # noqa: E402

AMP = "sk-ant-AMPKEY-not-real-000000000000"
NEW = "sk-ant-BUILDERKEY-not-real-00000000"
XAI = "xai-TESTKEY-not-real-0000000000"
PROVE = os.path.join("setup", "7-prove-anthropic-key.sh")
PLACE = os.path.join("setup", "7a-place-anthropic-key.sh")


class ParkedKey(Base):
    def setUp(self):
        super().setUp()
        self.secrets = os.path.join(self.tmp, "secrets.env")
        write(self.secrets, 'XAI_API_KEY=xai-shared\nANTHROPIC_API_KEY="%s"\nOTHER=1\n' % AMP)
        self.edit(PROVE, "SECRETS=/forge/secrets.env", "SECRETS=" + self.secrets)
        os.makedirs(os.path.join(self.root, "keys"), mode=0o700)
        self.key("xai", XAI)
        self.key("anthropic", NEW)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        # architect can read r2_child.py and nothing under keys/, unless a test says otherwise
        self.shim("sudo", 'for a; do last="$a"; done\n'
                          'case "$last" in */r2_child.py) exit ${SHIM_CONTROL:-0};; *) exit ${SHIM_READS:-1};; esac')

    def key(self, name, value, mode=0o600):
        p = os.path.join(self.root, "keys", name)
        write(p, value + "\n")
        os.chmod(p, mode)

    def prove(self, **env):
        e = dict(os.environ, PATH=self.shims + os.pathsep + os.environ["PATH"])
        e.update(env)
        return subprocess.run(["bash", os.path.join(self.root, PROVE)], cwd=self.root, env=e,
                              capture_output=True, text=True, timeout=60)

    def clean(self, r):
        for secret in (AMP, NEW, XAI, "AMPKEY", "BUILDERKEY", "TESTKEY"):
            self.assertNotIn(secret, r.stdout + r.stderr)
        self.assertNotRegex(r.stdout + r.stderr, r"[0-9a-f]{32}")       # no hash either

    def test_differ_is_one_word_and_exit_0(self):
        r = self.prove()
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "DIFFER\n", ""))

    def test_a_copy_of_amps_key_or_of_the_xai_key_is_match(self):
        self.key("anthropic", ' "%s" ' % AMP)                # quotes and spaces do not hide a copy
        r = self.prove()
        self.assertEqual((r.returncode, r.stdout), (1, "MATCH\n"))
        self.clean(r)
        self.key("anthropic", XAI)
        r = self.prove()
        self.assertEqual((r.returncode, r.stdout), (1, "MATCH\n"))
        self.clean(r)

    def test_exit_2_and_silence_when_it_cannot_tell(self):
        write(self.secrets, "XAI_API_KEY=x\n")                                  # no Amp line
        self.assertEqual((self.prove().returncode, self.prove().stdout), (2, ""))
        write(self.secrets, "ANTHROPIC_API_KEY=%s\nANTHROPIC_API_KEY=%s\n" % (AMP, AMP))   # two Amp lines
        self.assertEqual((self.prove().returncode, self.prove().stdout), (2, ""))
        write(self.secrets, "ANTHROPIC_API_KEY=%s\n" % AMP)
        self.assertEqual(self.prove(SHIM_CONTROL="1").returncode, 2)             # cannot test architect at all
        os.remove(os.path.join(self.root, "keys", "anthropic"))
        self.assertEqual((self.prove().returncode, self.prove().stdout), (2, ""))

    def test_each_broken_item_is_fail_and_names_itself_without_a_secret(self):
        cases = (
            (lambda: os.chmod(os.path.join(self.root, "keys", "anthropic"), 0o640), "not mode 600"),
            (lambda: self.edit(".gitignore", "keys/\n", ""), "not ignored by git"),
            (lambda: self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_IS_REAL=yes", "CONSOLE_CAP_ANTHROPIC_IS_REAL=no"), "IS_REAL"),
            (lambda: self.edit("limits.env", "CONSOLE_CAP_ANTHROPIC_USD=40", "CONSOLE_CAP_ANTHROPIC_USD=400"), "ANTHROPIC_USD"),
            (lambda: self.edit("limits.env", "ANTHROPIC_MONTH_USD=0", "ANTHROPIC_MONTH_USD=2"), "ANTHROPIC_MONTH_USD"),
            (lambda: self.edit("limits.env", "CONSOLE_CAP_XAI_IS_REAL=no", "CONSOLE_CAP_XAI_IS_REAL=yes"), "XAI_IS_REAL"),
            (lambda: self.edit("limits.env", "XAI_MONTH_USD=15", "XAI_MONTH_USD=40"), "XAI_MONTH_USD"),
            (lambda: self.edit("r2.py", "REVIEWER_MODEL", 'KEYFILE = "keys/anthropic"\nREVIEWER_MODEL'), "r2.py mentions"),
        )
        for break_it, needle in cases:
            self.tearDown()
            self.setUp()
            break_it()
            r = self.prove()
            self.assertEqual((r.returncode, r.stdout), (1, "FAIL\n"), needle + r.stderr)
            self.assertIn(needle, r.stderr)
            self.clean(r)

    def test_fail_when_architect_can_read_the_key_or_it_is_tracked(self):
        r = self.prove(SHIM_READS="0")
        self.assertEqual((r.returncode, r.stdout), (1, "FAIL\n"))
        self.assertIn("architect can read keys/anthropic", r.stderr)
        subprocess.run(["git", "-C", self.root, "add", "-f", "keys/anthropic"], check=True)
        r = self.prove()
        self.assertEqual((r.returncode, r.stdout), (1, "FAIL\n"))
        self.assertIn("tracked by git", r.stderr)

    def test_neither_script_touches_the_network_or_reads_secrets_wrongly(self):
        prove, place = read(os.path.join(HERE, PROVE)), read(os.path.join(HERE, PLACE))
        for text in (prove, place):
            for word in ("curl", "wget", "http", "api.anthropic", "python", "docker", "nc ", "echo \"$k\"", "echo $A", "echo \"$A\""):
                self.assertNotIn(word, text, word)
        self.assertNotIn("secrets.env", place.replace("Never copy the key from secrets.env", "").replace("reads no secrets file", ""))
        self.assertIn("read -rs", place)

    def test_place_script_saves_600_prints_nothing_secret_and_never_overwrites(self):
        os.remove(os.path.join(self.root, "keys", "anthropic"))
        run = lambda text: subprocess.run(["bash", os.path.join(self.root, PLACE)], input=text, cwd=self.root,
                                          capture_output=True, text=True, timeout=60)
        self.assertEqual(run("short\n").returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(self.root, "keys", "anthropic")))
        r = run(NEW + "\n")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.clean(r)
        kf = os.path.join(self.root, "keys", "anthropic")
        self.assertEqual((read(kf), os.stat(kf).st_mode & 0o777), (NEW + "\n", 0o600))
        r = run(AMP + "\n")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(read(kf), NEW + "\n")

    def test_r2_files_never_mention_the_anthropic_key(self):
        for name in ("r2.py", "r2_child.py", "r2.sh"):
            self.assertNotIn("anthropic", read(os.path.join(HERE, name)).lower(), name)


if __name__ == "__main__":
    import unittest
    unittest.main()
