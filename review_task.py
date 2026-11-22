#!/usr/bin/env python3
"""architect-run: write the R4 review task for a slice that has been built. No model, no network, $0.

  python3 review_task.py inbox/<slice>.yaml inbox/<spec>.md

It reads the slice task, the frozen test, the built files under work/<id>/, the excerpt
inbox/<id>.spec.txt and the spec. It writes exactly one file, inbox/<id>-review.yaml, and never
overwrites one. It changes nothing else, calls nothing, and does not run the review: it prints
the command, and a person runs it. Exit codes: 0 written, 2 refused, 4 a hash does not match.
"""
import hashlib
import os
import re
import stat
import sys

ROOT = os.path.dirname(os.path.realpath(__file__))
INBOX = os.path.join(ROOT, "inbox")
WORK = os.path.join(ROOT, "work")
OK, REFUSED, FAIL = 0, 2, 4
MAX_FILE_BYTES = 64 * 1024


def finish(code, text):
    print("result: %s" % text)
    sys.exit(code)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def yaml_lines(path):
    out = {}
    with open(path) as fh:
        for raw in fh:
            raw = raw.rstrip("\n")
            if raw.strip() and not raw.lstrip().startswith("#") and ":" in raw:
                k, v = raw.split(":", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def plain(text):            # the same rule r4.py uses
    return " ".join(re.sub(r"[*`\\_]", "", text).split())


def in_inbox(path, what):
    full = os.path.realpath(os.path.join(ROOT, path))
    if os.path.dirname(full) != os.path.realpath(INBOX) or not os.path.isfile(full) or os.path.islink(
            os.path.join(ROOT, path)):
        finish(REFUSED, "REFUSED %s must be a plain file directly inside inbox/: %s" % (what, path))
    return full


if len(sys.argv) != 3:
    finish(REFUSED, "REFUSED usage: review_task.py inbox/<slice>.yaml inbox/<spec>.md")
slice_file = in_inbox(sys.argv[1], "the slice task")
spec_file = in_inbox(sys.argv[2], "the spec")
piece = yaml_lines(slice_file)
names = piece.get("impl", "").split()
if (piece.get("kind") != "r3" or not re.fullmatch(r"[A-Za-z0-9._-]{1,60}", piece.get("id", ""))
        or len(names) not in (1, 3) or not all(re.fullmatch(r"[a-z_][a-z0-9_]{0,40}\.py", n) for n in names)
        or not piece.get("test")):
    finish(REFUSED, "REFUSED the first file must be an R3 task with id, impl and test")
ident = piece["id"]
print("slice: %s  files %s" % (ident, ", ".join(names)))

out_rel = os.path.join("inbox", "%s-review.yaml" % ident)
out_path = os.path.join(ROOT, out_rel)
if os.path.lexists(out_path):
    finish(REFUSED, "REFUSED %s already exists. It is never overwritten." % out_rel)

with open(in_inbox(piece["test"], "the test file"), "rb") as fh:
    if sha(fh.read()) != piece.get("expect_sha256", "").lower():
        finish(FAIL, "FAIL the test file does not match the slice's expect_sha256 line. Nothing written.")

built_dir = os.path.join(WORK, ident)
if os.path.islink(WORK) or os.path.islink(built_dir) or not os.path.isdir(built_dir):
    finish(REFUSED, "REFUSED work/%s/ is not there. The slice has not been built, so there is nothing to review."
           % ident)
hashes = []
for name in names:
    path = os.path.join(built_dir, name)
    try:
        st = os.lstat(path)
    except OSError:
        finish(REFUSED, "REFUSED work/%s/%s is missing. Nothing written." % (ident, name))
    if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_FILE_BYTES:
        finish(REFUSED, "REFUSED work/%s/%s is not a plain file of a sane size. Nothing written." % (ident, name))
    with open(path, "rb") as fh:
        hashes.append(sha(fh.read()))
    print("built: work/%s/%s  sha256 %s" % (ident, name, hashes[-1]))

excerpt_rel = os.path.join("inbox", "%s.spec.txt" % ident)
excerpt_file = in_inbox(excerpt_rel, "the excerpt")
with open(excerpt_file, "rb") as fh:
    excerpt_bytes = fh.read()
try:
    with open(spec_file, "rb") as fh:
        spec_plain = plain(fh.read().decode("utf-8"))
    paragraphs = [ln.strip() for ln in excerpt_bytes.decode("utf-8").splitlines()
                  if ln.strip() and not ln.lstrip().startswith("#")]
except UnicodeDecodeError:
    finish(REFUSED, "REFUSED the spec or the excerpt is not UTF-8 text. Nothing written.")
if not paragraphs:
    finish(REFUSED, "REFUSED the excerpt has no paragraphs. Nothing written.")
for n, para in enumerate(paragraphs, 1):
    if plain(para) not in spec_plain:
        finish(REFUSED, "REFUSED excerpt paragraph %d is not in %s word for word: \"%s...\". Nothing written."
               % (n, sys.argv[2], para[:50]))
print("excerpt: %s  %d paragraphs, each found word for word in %s" % (excerpt_rel, len(paragraphs), sys.argv[2]))

text = ("# Review task for the built slice %s. Written by review_task.py from the files on disk.\n"
        "# No model wrote or chose anything here. The hashes pin exactly what the reviewer is sent.\n"
        "id: %s-review\nkind: r4\nslice: %s\nspec: %s\nexcerpt: %s\nexpect_excerpt_sha256: %s\nfiles_sha256: %s\n"
        % (ident, ident, os.path.relpath(slice_file, ROOT), os.path.relpath(spec_file, ROOT), excerpt_rel,
           sha(excerpt_bytes), " ".join(hashes)))
with open(out_path, "x") as fh:
    fh.write(text)
print("wrote: %s" % out_rel)
print("next, by hand, and only when a review call is authorized:")
print("  ARCHITECT_LIVE=1 bash r4.sh %s" % out_rel)
finish(OK, "OK %s is ready. Nothing was run." % out_rel)
