#!/usr/bin/env python3
"""architect-run: copy one reviewed slice to the landing place. No model, no network, $0.

  python3 land.py <slice id>

The landing place is OUT_ROOT/<project>/<slice id>/. It is not a live app, it is not on
forge-net, and no model is ever given the path. Jeremy creates OUT_ROOT/<project>/ by hand,
and Jeremy runs this. A slice is copied only when all of these hold:

  1. it is named in landing.txt with its project;
  2. the frozen test still matches the slice task's expect_sha256 line;
  3. there is exactly one live review of it in rulings/ with nothing blocking, and that review
     names the same test hash;
  4. every built file under work/<id>/ still has the hash that review read.

The files under work/ are read and never changed. The destination is never overwritten.
Exit codes: 0 copied, 2 refused, 4 a hash does not match.
"""
import hashlib
import os
import re
import stat
import sys

ROOT = os.path.dirname(os.path.realpath(__file__))
OUT_ROOT = "/forge/architect-out"
INBOX = os.path.join(ROOT, "inbox")
WORK = os.path.join(ROOT, "work")
RULINGS = os.path.join(ROOT, "rulings")
OK, REFUSED, FAIL = 0, 2, 4
MAX_FILE_BYTES = 64 * 1024
NAME = r"[a-z0-9][a-z0-9-]{0,40}"


def finish(code, text):
    print("result: %s" % text)
    sys.exit(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def yaml_lines(path):
    out = {}
    for raw in read_bytes(path).decode("utf-8").splitlines():
        if raw.strip() and not raw.lstrip().startswith("#") and ":" in raw:
            k, v = raw.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


if len(sys.argv) != 2 or not re.fullmatch(NAME, sys.argv[1]):
    finish(REFUSED, "REFUSED usage: land.py <slice id>, for example hopper-intake")
ident = sys.argv[1]

# 1. named
named = {}
for raw in read_bytes(os.path.join(ROOT, "landing.txt")).decode("utf-8").splitlines():
    parts = raw.split()
    if parts and not parts[0].startswith("#"):
        if len(parts) != 2 or not re.fullmatch(NAME, parts[0]) or not re.fullmatch(NAME, parts[1]):
            finish(REFUSED, "REFUSED landing.txt has a line that is not '<slice id> <project>'. Nothing copied.")
        named[parts[0]] = parts[1]
if ident not in named:
    finish(REFUSED, "REFUSED %s is not named in landing.txt. Nothing copied." % ident)
project = named[ident]
print("named: %s, project %s" % (ident, project))

# 2. the frozen test
slice_file = os.path.join(INBOX, "%s.yaml" % ident)
if not os.path.isfile(slice_file) or os.path.islink(slice_file):
    finish(REFUSED, "REFUSED inbox/%s.yaml is not there. Nothing copied." % ident)
piece = yaml_lines(slice_file)
names = piece.get("impl", "").split()
test_rel = piece.get("test", "")
if (piece.get("kind") != "r3" or piece.get("id") != ident or len(names) not in (1, 3)
        or not all(re.fullmatch(r"[a-z_][a-z0-9_]{0,40}\.py", n) for n in names)
        or not re.fullmatch(r"inbox/[a-z_][a-z0-9_]{0,40}\.py", test_rel)):
    finish(REFUSED, "REFUSED inbox/%s.yaml is not an R3 task with this id, impl and test. Nothing copied." % ident)
test_path = os.path.join(ROOT, test_rel)
if not os.path.isfile(test_path) or os.path.islink(test_path):
    finish(REFUSED, "REFUSED %s is not there. Nothing copied." % test_rel)
test_sha = sha(read_bytes(test_path))
if test_sha != piece.get("expect_sha256", "").lower():
    finish(FAIL, "FAIL the test file no longer matches the slice's expect_sha256 line. Nothing copied.")
print("test: %s  sha256 %s  (unchanged)" % (test_rel, test_sha))

# 3. one live review, nothing blocking, same test
reviews = sorted(f for f in (os.listdir(RULINGS) if os.path.isdir(RULINGS) else [])
                 if re.fullmatch(r"\d{4}-\d\d-\d\d-%s-review(-\d+)?\.md" % re.escape(ident), f))
if len(reviews) != 1:
    finish(REFUSED, "REFUSED rulings/ needs exactly one live review of %s and has %d. Nothing copied."
           % (ident, len(reviews)))
review = read_bytes(os.path.join(RULINGS, reviews[0])).decode("utf-8")
if "one call, live" not in review or "FIXTURE" in review or "\n## Blocking\n\n- none\n" not in review:
    finish(REFUSED, "REFUSED rulings/%s is not a live review with nothing blocking. Nothing copied." % reviews[0])
if "- Frozen test: `%s` sha256 `%s`" % (test_rel, test_sha) not in review:
    finish(FAIL, "FAIL rulings/%s was written against a different test. Nothing copied." % reviews[0])
print("review: rulings/%s  live, nothing blocking, same test" % reviews[0])

# 4. the built files are the ones the review read
built_dir = os.path.join(WORK, ident)
if os.path.islink(WORK) or os.path.islink(built_dir) or not os.path.isdir(built_dir):
    finish(REFUSED, "REFUSED work/%s/ is not there. Nothing copied." % ident)
built = {}
for name in names:
    path = os.path.join(built_dir, name)
    try:
        st = os.lstat(path)
    except OSError:
        finish(REFUSED, "REFUSED work/%s/%s is missing. Nothing copied." % (ident, name))
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
        finish(REFUSED, "REFUSED work/%s/%s is not a plain file of a sane size. Nothing copied." % (ident, name))
    built[name] = read_bytes(path)
    line = "- Read, not changed: `work/%s/%s` sha256 `%s`" % (ident, name, sha(built[name]))
    if line not in review:
        finish(FAIL, "FAIL work/%s/%s is not the file the review read. Nothing copied." % (ident, name))
    print("built: work/%s/%s  sha256 %s  (the file the review read)" % (ident, name, sha(built[name])))

# the landing place
project_dir = os.path.join(OUT_ROOT, project)
real = os.path.realpath(project_dir)
if (real != project_dir or not os.path.isdir(project_dir)
        or os.path.commonpath([real, ROOT]) == ROOT or os.path.commonpath([real, os.path.realpath(ROOT)]) == real):
    finish(REFUSED, "REFUSED %s must already exist as a real directory outside this repository. "
                    "Jeremy creates it by hand. Nothing copied." % project_dir)
dest = os.path.join(project_dir, ident)
if os.path.lexists(dest):
    finish(REFUSED, "REFUSED %s already exists. It is never overwritten. Nothing copied." % dest)
os.mkdir(dest, 0o755)
manifest = ["slice: %s" % ident, "project: %s" % project, "review: rulings/%s" % reviews[0],
            "test: %s sha256 %s" % (test_rel, test_sha)]
for name in names:
    target = os.path.join(dest, name)
    with open(target, "xb") as fh:
        fh.write(built[name])
    if sha(read_bytes(target)) != sha(built[name]):
        finish(FAIL, "FAIL %s does not read back the same. Look at %s by hand." % (name, dest))
    manifest.append("file: %s sha256 %s" % (name, sha(built[name])))
    print("copied: %s" % target)
with open(os.path.join(dest, "LANDED.txt"), "x") as fh:
    fh.write("\n".join(manifest) + "\n")
finish(OK, "OK %s landed in %s. Nothing was run, and nothing under work/ changed." % (ident, dest))
