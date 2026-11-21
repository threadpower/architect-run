"""v0.4 cage proof: the host-side script must fail closed. Uses a fake docker; starts nothing."""
import os
import re
import stat
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCKER = r'''#!/bin/bash
src() { sed -n 's/.*source=\([^,]*\),target.*/\1/p' "$SHIM_LOG"; }
case "$1" in
 version) exit 0;;
 image) [ "$2" = ls ] && [ -z "${SHIM_NOIMG:-}" ] && { echo "python:3.11-slim"; echo "python:3.12-slim"; echo "forge-ads:latest"; }; exit 0;;
 ps) if [ "$2" = "-a" ]; then [ -n "${SHIM_STAY:-}" ] && echo abc; exit 0; fi; echo "warp|0.0.0.0:8097->8000/tcp"; exit 0;;
 network) echo '[]'; exit 0;;
 pull) echo pulled >> "$SHIM_LOG.pull"; exit 0;;
 create) echo "$@" > "$SHIM_LOG"; echo cid; exit 0;;
 inspect) cat <<J
[{"HostConfig":{"AutoRemove":true,"Privileged":${SHIM_PRIV:-false},"NetworkMode":"${SHIM_NET:-none}","PidMode":"","UTSMode":"","UsernsMode":"","IpcMode":"none","CgroupnsMode":"private","CapAdd":null,"CapDrop":["ALL"],"SecurityOpt":["no-new-privileges"],"Mounts":[{"Type":"bind","Source":"$(src)","Target":"/work"}],"Binds":${SHIM_BINDS:-null}},
"Config":{"User":"65534:65534","Env":["PATH=/usr/bin","GPG_KEY=abc"${SHIM_ENV:-}],"Volumes":null},
"Mounts":[{"Destination":"/work"}],"NetworkSettings":{"Networks":{"${SHIM_NET:-none}":{}}}}]
J
 exit 0;;
 start) [ -z "${SHIM_NOWRITE:-}" ] && echo run1 > "$(src)/from-run1.txt"; echo "PROBE-COMPLETE mode=run1 checks=40 fails=${SHIM_F1:-0}"; exit ${SHIM_F1:-0};;
 run) echo "$@" >> "$SHIM_LOG.run"; [ -n "${SHIM_SILENT2:-}" ] && exit 0; echo "PROBE-COMPLETE mode=run2 checks=40 fails=0"; exit 0;;
esac
'''
ID = r'''#!/bin/bash
case "$*" in "-u") echo "${SHIM_UID:-1000}";; "-un") echo jb;; "architect") echo "uid=999(architect)";; "-Gn architect") echo "${SHIM_AG:-architect}";; *) echo jb;; esac
'''


class CageProof(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cage-test-")
        self.bin = os.path.join(self.tmp, "bin")
        os.mkdir(self.bin)
        for name, body in (("docker", DOCKER), ("id", ID), ("sudo", '#!/bin/bash\nexit ${SHIM_SUDO:-1}\n'),
                           ("stat", '#!/bin/bash\necho ${SHIM_OWNER:-65534}\n')):
            path = os.path.join(self.bin, name)
            with open(path, "w") as fh:
                fh.write(body)
            os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def prove(self, **env):
        e = dict(os.environ, PATH=self.bin + ":" + os.environ["PATH"], SHIM_LOG=os.path.join(self.tmp, "log"))
        e.update(env)
        return subprocess.run(["bash", os.path.join(HERE, "cage", "prove.sh")], env=e, capture_output=True, text=True)

    def test_passes_only_when_everything_holds(self):
        r = self.prove()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("=== PASS", r.stdout)
        self.assertIn("does not authorize a builder", r.stdout)
        self.assertNotIn("FAIL", r.stdout)

    def test_any_single_break_fails_the_script(self):
        for env in ({"SHIM_PRIV": "true"}, {"SHIM_NET": "forge-net"},
                    {"SHIM_BINDS": '["/var/run/docker.sock:/var/run/docker.sock"]'},
                    {"SHIM_ENV": ',"XAI_API_KEY=x"'}, {"SHIM_STAY": "1"}, {"SHIM_F1": "1"}, {"SHIM_SILENT2": "1"},
                    {"SHIM_NOWRITE": "1"}, {"SHIM_OWNER": "0"}, {"SHIM_SUDO": "0"}, {"SHIM_AG": "architect docker"}):
            r = self.prove(**env)
            self.assertEqual(r.returncode, 1, "%s\n%s" % (env, r.stdout))
            self.assertIn("=== FAIL", r.stdout, env)

    def test_refuses_root_and_never_pulls_an_image(self):
        self.assertEqual(self.prove(SHIM_UID="0").returncode, 2)
        r = self.prove(SHIM_NOIMG="1")
        self.assertEqual(r.returncode, 2)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "log.pull")))

    def test_work_folder_is_removed_and_stays_under_work(self):
        r = self.prove()
        m = re.search(r"^work:\s+(\S+)$", r.stdout, re.M)
        self.assertTrue(m.group(1).startswith(os.path.join(HERE, "work", "cage-proof-")))
        self.assertFalse(os.path.exists(m.group(1)))

    def test_cage_flags_are_the_ones_grok_named(self):
        flags = open(os.path.join(HERE, "cage", "cage.sh")).read()
        for word in ("--rm", "--network none", "--cap-drop ALL", "no-new-privileges", "--user 65534:65534",
                     "type=bind,source=$work,target=/work"):
            self.assertIn(word, flags)
        for word in ("--privileged", "docker.sock", "forge-net", "--pid ", "--pid=", "--network host", "-v ", "--volume",
                     "--env-file", "secrets.env", "docker pull"):
            self.assertNotIn(word, flags)
        self.prove()
        ran = open(os.path.join(self.tmp, "log.run")).read()
        self.assertIn("--network none", ran)
        self.assertIn("-i PATH=/usr/local/bin:/usr/bin:/bin HOME=/work python3 /work/probe.py run2", ran)

    def test_cage_files_read_no_secret_and_call_no_model(self):
        for name in os.listdir(os.path.join(HERE, "cage")):
            if not name.endswith((".sh", ".py")):
                continue
            text = open(os.path.join(HERE, "cage", name)).read()
            for word in ("curl", "wget", "docker pull", "ANTHROPIC_API_KEY", "XAI_API_KEY", "urllib", "requests", "https://"):
                self.assertNotIn(word, text, "%s in %s" % (word, name))
            if name != "probe.py":      # the probe names the secret paths only to prove it cannot read them
                self.assertNotIn("secrets.env", text, name)


if __name__ == "__main__":
    unittest.main()
