#! /usr/bin/env python

import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import askdirectory

from collections import namedtuple, OrderedDict
from subprocess import check_output, SubprocessError
from textwrap import indent
from itertools import count
from getpass import getuser

# TODO: remote host validation, and feedback by colouring the background of the entry field
#from socket import gethostbyname

_rf = namedtuple("_RsyncFlag", ["variable", "flag", "dirty"])

# dirty, pun intended, closure 'magic'
# Can't use weakrefs because bools are immutable.
def _dirty_factory():
    _dirty = False
    def callback(_set=None):
        nonlocal _dirty
        if _set is None:
            return _dirty
        else:
            _dirty = _set
    return callback

def _set_factory(target, next_callback=None):
    def callback(target=target, next_callback=next_callback):
        target(True)
        if next_callback is not None:
            next_callback()
    return callback

class RsyncTkGUI(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        rows = count()

        # TODO: Cache previous 'preferences'

        # TODO: Refuse, or heavily discourage, unencrypted sync

        # --- Source and destination handling --- #
        row = next(rows)
        ttk.Label(self, text="Local…").grid(row=row, column=0, columnspan=2,
                                            sticky=(tk.W, tk.E))

        row = next(rows)
        self.localpath = tk.StringVar()
        ttk.Label(self, text="directory:").grid(row=row, column=0,
                                                      sticky=tk.W)
        f = ttk.Frame(self)
        f.grid(row=row, column=1)
        ttk.Entry(f, textvariable=self.localpath).grid(row=0, column=0,
                                                       sticky=(tk.W, tk.E))
        # FIXME: Use desktop metaphore terms (i.e., here, 'folder'), or older
        #        terms (i.e., here, 'directory')?
        ttk.Button(f, command=lambda lp=self.localpath: lp.set(askdirectory()),
                   text="Select directory…").grid(row=0, column=1)

        row = next(rows)
        ttk.Label(self, text="Remote…").grid(row=row, column=0, columnspan=2,
                                             sticky=(tk.W, tk.E))

        row = next(rows)
        self.remoteuser = tk.StringVar(value=getuser())
        ttk.Label(self, text="user:").grid(row=row, column=0, sticky=tk.W)
        ttk.Entry(self, textvariable=self.remoteuser).grid(row=row, column=1,
                                                           sticky=(tk.W, tk.E))

        row = next(rows)
        self.remotehost = tk.StringVar()
        # TODO: notebook and option of local directory or remote host; local directory 
        # TODO: Determine if the file sync use case is really necessary
        ttk.Label(self, text="host:").grid(row=row, column=0, sticky=tk.W)
        ttk.Entry(self, textvariable=self.remotehost).grid(row=row, column=1,
                                                           sticky=(tk.W, tk.E))

        row = next(rows)
        self.remotedirectory = tk.StringVar()
        ttk.Label(self, text="directory:").grid(row=row, column=0,
                                                sticky=tk.W)
        entry = ttk.Entry(self, textvariable=self.remotedirectory)
        entry.grid(row=row, column=1, sticky=(tk.W, tk.E))

        row = next(rows)
        self.syncmode = tk.StringVar()
        ttk.Label(self, text="Sync mode:").grid(row=row, column=0, sticky=tk.W)
        f = ttk.Frame(self)
        f.grid(row=row, column=1)
        def callback():
            if self.syncmode == "both":
                self.flags["update"].variable.set(True)
        for column, mode in enumerate(["send", "receive", "both"]):
            rb = ttk.Radiobutton(f, text=mode, value=mode,
                                 variable=self.syncmode,
                                 command=callback)
            rb.grid(row=0, column=column, sticky=tk.E)
        rb.invoke()  # mode "both"

        # --- Copy options --- #
        row = next(rows)
        nb = ttk.Notebook(self)
        nb.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E))
        self.flags = {}

        # --- --- advanced options --- --- #
        advanced = ttk.Frame(nb)
        subrows = count()
        for subrow, (groupname, group) in \
            zip(subrows,
                [("Attributes to preserve",
                  [("Permissions",                    "--perms",      "perms"),
                   ("Modification times",             "--times",      "mtimes"),
                   # -O, --omit-dir-times        omit directories from --times
                   # -J, --omit-link-times       omit symlinks from --times
                   ("Owning user",                    "--owner",      "owner"),
                   ("Owning group",                   "--group",      "group"),
                   ("Extended ACLs",                  "--acls",       "xacls"),
                   ("Extended attributes",            "--xattrs",     "xattrs")]),

                 # -L, --copy-links            transform symlink into referent file/dir
                 #     --copy-unsafe-links     only "unsafe" symlinks are transformed
                 #     --safe-links            ignore symlinks that point outside the tree
                 #     --munge-links           munge symlinks to make them safer
                 # -k, --copy-dirlinks         transform symlink to dir into referent dir
                 # -K, --keep-dirlinks         treat symlinked dir on receiver as dir
                 # -H, --hard-links            preserve hard links
                 #("Link handling",
                 # []),

                 #     --inplace               update destination files in-place
                 #     --append                append data onto shorter files
                 #     --append-verify         --append w/old data in file checksum
                 #("Update mode",
                 # []),

                 # -S, --sparse                handle sparse files efficiently
                 #     --preallocate           allocate dest files before writing
                 # -W, --whole-file            copy files whole (w/o delta-xfer algorithm)
                 # -B, --block-size=SIZE       force a fixed checksum block-size
                 # -z, --compress              compress file data during the transfer
                 # TODO: Use [ttk.Scale widget](http://www.tkdocs.com/tutorial/morewidgets.html#scale) here.
                 #     --compress-level=NUM    explicitly set compression level
                 #     --skip-compress=LIST    skip compressing files with suffix in LIST
                 #("Performance",
                 # []),

                 # Required for syncmode == "both"
                 # -u, --update                skip files that are newer on the receiver

                 # -c, --checksum              skip based on checksum, not mod-time & size
                 # -y, --fuzzy                 find similar file for basis if no dest file
                 # -I, --ignore-times          don't skip files that match size and time
                 #     --modify-window=NUM     compare mod-times with reduced accuracy
                 #     --size-only             skip files that match in size
                 #     --existing              skip creating new files on receiver
                 #     --ignore-existing       skip updating files that exist on receiver
                 #     --remove-source-files   sender removes synchronized files (non-dir)
                 #     --force                 force deletion of dirs even if not empty
                 # -m, --prune-empty-dirs      prune empty directory chains from file-list
                 #("Difference detection and resolution",
                 # []),

                 #     --numeric-ids           don't map uid/gid values by user/group name
                 #     --usermap=STRING        custom username mapping
                 #     --groupmap=STRING       custom groupname mapping
                 #     --chown=USER:GROUP      simple username/groupname mapping
                 #("Remote end file ownership",
                 # []),

                 #     --partial               keep partially transferred files
                 #     --partial-dir=DIR       put a partially transferred file into DIR

                 #     --timeout=SECONDS       set I/O timeout in seconds
                 #     --contimeout=SECONDS    set daemon connection timeout in seconds
                 #     --port=PORT             specify double-colon alternate port number
                 # -4, --ipv4                  prefer IPv4
                 # -6, --ipv6                  prefer IPv6
                 #("Network",
                 # []),

                 #     --link-dest=DIR         hardlink to files in DIR when unchanged
                 # -b, --backup                make backups (see --suffix & --backup-dir)
                 #     --backup-dir=DIR        make backups into hierarchy based in DIR
                 #     --suffix=SUFFIX         backup suffix (default ~ w/o --backup-dir)
                 #     --delay-updates         put all updated files into place at end
                 #("'Backup'",
                 # []),

                 #     --stats                 give some file-transfer stats
                 # -8, --8-bit-output          leave high-bit chars unescaped in output
                 # -h, --human-readable        output numbers in a human-readable format
                 # -i, --itemize-changes       output a change-summary for all updates
                 #     --log-file=FILE         log what we're doing to the specified FILE
                 # TODO: Show [indeterminate # progress](http://www.tkdocs.com/tutorial/morewidgets.html#progressbar)
                 #       if this is unset. Else, this'll show up in the redirected
                 #       standard output.
                 #     --progress              show progress during transfer
                 #("Reporting",
                 # []),

                 # -x, --one-file-system       don't cross filesystem boundaries
                 #     --max-delete=NUM        don't delete more than NUM files
                 #     --max-size=SIZE         don't transfer any file larger than SIZE
                 #     --min-size=SIZE         don't transfer any file smaller than SIZE

                 # -C, --cvs-exclude           auto-ignore files in the same way CVS does
                 # -f, --filter=RULE           add a file-filtering RULE
                 #     --exclude=PATTERN       exclude files matching PATTERN
                 #     --exclude-from=FILE     read exclude patterns from FILE
                 #     --include=PATTERN       don't exclude files matching PATTERN
                 #     --include-from=FILE     read include patterns from FILE
                 #     --files-from=FILE       read list of source-file names from FILE

                 #     --bwlimit=RATE          limit socket I/O bandwidth
                 #("Throttling and filtering",
                 # []),

                 # Assorted:
                 #     --ignore-errors         delete even if there are I/O errors
                 # -n, --dry-run               perform a trial run with no changes made
                 #     --list-only             list the files instead of copying them
                 # -T, --temp-dir=DIR          create temporary files in directory DIR
                 #     --compare-dest=DIR      also compare received files relative to DIR
                 #     --copy-dest=DIR         ... and include copies of unchanged files

                 ("Additional file types to preserve",
                  [("Directories",                    "--dirs",       "directories"),
                   ("Symbolic links",                 "--links",      "slinks"),
                   ("Hard links",                     "--hard-links", "hlinks"),
                   ("Special files",                  "--specials",   "specials"),
                   ("Device files (super-user only)", "--devices",    "devices")])]):
            subframe = ttk.Labelframe(advanced, text=groupname)
            subframe.grid(row=subrow, column=0, columnspan=2,
                          sticky=tk.W)
            for subsubrow, (description, flag, key) in enumerate(group):
                variable = tk.BooleanVar()
                rf = _rf(variable, flag, _dirty_factory())
                self.flags[key] = rf
                checkbutton = ttk.Checkbutton(subframe,
                                              text=description,
                                              variable=variable,
                                              onvalue=True, offvalue=False,
                                              command=_set_factory(rf.dirty))
                checkbutton.grid(row=subsubrow, column=0, columnspan=2,
                                 sticky=(tk.W, tk.E))

        subframe = ttk.Labelframe(advanced, text="Deletion")
        subsubrows = count()
        # --delete-* should only be available if --delete is set
        choice = tk.StringVar()
        variable = tk.BooleanVar()
        widgets = []
        def callback(widgets=widgets, variable=variable):
            statespec = (tk.NORMAL if variable.get() else tk.DISABLED,)
            for widget in widgets:
                widget["state"] = statespec
        checkbutton = ttk.Checkbutton(subframe, variable=variable,
                                      onvalue=True, offvalue=False,
                                      text="Delete extraneous files from"
                                           " destination directories",
                                      command=callback)
        checkbutton.grid(row=next(subsubrows), column=0, columnspan=2,
                         sticky=(tk.W, tk.E))
        for subsubrow, (description, flag) in \
            zip(subsubrows,
                [("Before transfer", "--delete-before"),
                 # Too complex for some users?
                 #("During transfer", "--delete-during"),
                 #("Find deletions during, delete after", "--delete-delay")
                 ("After transfer",  "--delete-after")]):
            label = ttk.Label(subframe,
                              text=description,
                              # FIXME: unavoidable duplication of work?
                              state=(tk.DISABLED,))
            label.grid(row=subsubrow, column=0, sticky=tk.W)
            widgets.append(label)
            button = ttk.Radiobutton(subframe, variable=variable, value=flag,
                                     # FIXME: unavoidable duplication of work?
                                     state=(tk.DISABLED,))
            button.grid(row=subsubrow, column=1, sticky=(tk.W, tk.E))
            widgets.append(button)
        subframe.grid(row=next(subrows), column=0, columnspan=2,
                      sticky=(tk.W, tk.E))

        # --- --- simple options --- --- #
        simple = ttk.Frame(nb)
        subrows = count()

        archive_mode = tk.BooleanVar()
        def callback():
            mode = archive_mode.get()
            for flag in map(self.flags.__getitem__,
                            [# As per rsync '-a' flag, minus recursion. Not
                             # exactly the semantics of the original rsync,
                             # but sensible to someone who hasn't used it.
                             # Would they care, they'd use rsync directly
                             # anyhow.
                             "slinks", "perms", "mtimes",
                             "group", "owner", "devices", "specials",
                             # what users really should also care about,
                             # despite not being included in '-a' set
                             "xattrs", "xacls", "hlinks",
                             # We separate the notion of 'archiving' from
                             # recursing, but still copy directories themselves
                             # (not their contents).
                             "directories"]):
                flag.variable.set(mode)
        checkbutton = ttk.Checkbutton(simple,
                                      onvalue=True, offvalue=False,
                                      text="Full archival mode"
                                           " (all metadata and file types)",
                                      variable=archive_mode,
                                      # no need to track dirtying
                                      command=callback)
        checkbutton.grid(row=next(subrows), column=0, columnspan=2)

        variable = tk.BooleanVar()
        rf = _rf(variable, "--recursive", _dirty_factory())
        self.flags["recursive"] = rf
        def callback():
            # FIXME: closure name clash (clobbering) issues?
            mode = variable.get()
            if mode or not self.flags["directories"].dirty():
                self.flags["directories"].variable.set(mode)
        checkbutton = ttk.Checkbutton(simple,
                                      onvalue=True, offvalue=False,
                                      text="Recurse into directories",
                                      variable=variable,
                                      # no need to track dirtying
                                      command=callback)
        checkbutton.grid(row=next(subrows), column=0, columnspan=2,
                         sticky=tk.W)

        nb.add(simple, text="Simple")
        nb.add(advanced, text="Advanced")

        # TODO: Display command at bottom, as being built

        row = next(rows)
        ttk.Button(self, text="Sync", command=self.sync).grid(row=row, column=1,
                                                              sticky=tk.E)

        row = next(rows)
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=row, column=0,
                                                       columnspan=2,
                                                       sticky=(tk.W, tk.E))


    def showversion(self):
        try:
            message = check_output(["rsync", "--version"])
        except SubprocessError as e:
            message = "Couldn't invoke rsync. Is it installed properly?\n\n" \
                      + indent(str(e), prefix="\t")
            dialog = messagebox.showerror
        else:
            dialog = messagebox.showinfo
        finally:
            # FIXME: Pass parent widget if possible?
            dialog(message)

    def sync(self):
        raise NotImplementedError()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("rsync GUI wrapper")
    RsyncTkGUI(root).pack()

    root.mainloop()
