#!/usr/bin/env python3

# Please: DO NOT USE THIS AS AN EXAMPLE.
#
# This file is NOT for demonstration of how to use git-filter-repo as a
# libary; it exists to test corner cases or otherwise unusual inputs, and
# to verify some invariants that git-filter-repo currently aims to maintain
# (these invariants might be different in future versions of
# git-filter-repo).  As such, it reaches deep into the internals and does
# weird things that you should probably avoid in your usage of
# git-filter-repo.  Any code in this testcase is much more likely to have
# API breaks than other files in t9391.

import collections
import os
import random
import io
import sys
import textwrap

import git_filter_repo as fr

def handle_progress(progress):
  print("Decipher this: "+''.join(reversed(progress.message)))

def handle_checkpoint(checkpoint_object):
  # Flip a coin; see if we want to pass the checkpoint through.
  if random.randint(0,1) == 0:
    checkpoint_object.dump(filter._output)

total_objects = {'common': 0, 'uncommon': 0}
def track_everything(obj):
  if type(obj) == fr.Blob or type(obj) == fr.Commit:
    total_objects['common'] += 1
  else:
    total_objects['uncommon'] += 1
  if type(obj) == fr.Reset:
    def assert_not_reached(x): raise SystemExit("should have been skipped!")
    obj.dump = assert_not_reached
    obj.skip()
  if hasattr(obj, 'id'):
    # The creation of myblob should cause objects in stream to get their ids
    # increased by 1; this shouldn't be depended upon as API by external
    # projects, I'm just verifying an invariant of the current code.
    assert fr._IDS._reverse_translation[obj.id] == [obj.id - 1]

mystr = 'This is the contents of the blob'
compare = "Blob:\n  blob\n  mark :1\n  data {}\n  {}".format(len(mystr), mystr)
# Next line's only purpose is testing code coverage of something that helps
# debugging git-filter-repo; it is NOT something external folks should depend
# upon.
myblob = fr.Blob(mystr)
assert str(myblob) == compare
# Everyone should be using RepoFilter objects, not FastExportFilter.  But for
# testing purposes...
filter = fr.FastExportFilter('.',
                             progress_callback = handle_progress,
                             checkpoint_callback = handle_checkpoint,
                             everything_callback = track_everything)

filter.run(input = sys.stdin.detach(),
           output = open(os.devnull, 'bw'),
           fast_import_pipes = None,
           quiet = True)
# DO NOT depend upon or use _IDS directly you external script writers.  I'm
# only testing here for code coverage; the capacity exists to help debug
# git-filter-repo itself, not for external folks to use.
assert str(fr._IDS).startswith("Current count: 4")
assert filter.num_commits_parsed() == 1
print("Found {} blobs/commits and {} other objects"
      .format(total_objects['common'], total_objects['uncommon']))


stream = io.StringIO(textwrap.dedent('''
  blob
  mark :1
  data 5
  hello

  commit refs/heads/A
  mark :2
  author Just Me <just@here.org> 1234567890 -0200
  committer Just Me <just@here.org> 1234567890 -0200
  data 2
  A

  commit refs/heads/B
  mark :3
  author Just Me <just@here.org> 1234567890 -0200
  committer Just Me <just@here.org> 1234567890 -0200
  data 2
  B
  from :2
  M 100644 :1 greeting

  commit refs/heads/C
  mark :4
  author Just Me <just@here.org> 1234567890 -0200
  committer Just Me <just@here.org> 1234567890 -0200
  data 2
  C
  from :3
  M 100644 :1 salutation

  '''[1:]))

counts = collections.Counter()
def look_for_reset(obj):
  print("Processing {}".format(obj))
  counts[type(obj)] += 1
  if type(obj) == fr.Reset:
    assert obj.ref == 'refs/heads/B'

# Use all kinds of internals that external scripts should NOT use and which
# are likely to break in the future, just to verify a few invariants...
args = fr.FilteringOptions.parse_args(['--stdin', '--dry-run',
                                       '--path', 'salutation'])
filter = fr.RepoFilter(args, everything_callback = look_for_reset)
filter._input = stream
filter._setup_output()
filter._sanity_checks_handled = True
filter.run()
assert counts == collections.Counter({fr.Blob: 1, fr.Commit: 3, fr.Reset: 1})
