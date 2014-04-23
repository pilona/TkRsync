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

_rf = namedtuple("_RsyncFlag", ["variable", "widget", "flag", "dirty"])

class RsyncTkGUI(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)

        rows = count()

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
        ttk.Label(self, text="user:").grid(row=row, column=0,
                                                  sticky=tk.W)
        ttk.Entry(self, textvariable=self.remoteuser).grid(row=row, column=1,
                                                           sticky=(tk.W, tk.E))

        row = next(rows)
        self.remotehost = tk.StringVar()
        # TODO: notebook and option of local directory or remote host; local directory 
        # TODO: Determine if the file sync use case is really necessary
        ttk.Label(self, text="host:").grid(row=row, column=0,
                                                  sticky=tk.W)
        ttk.Entry(self, textvariable=self.remotehost).grid(row=row, column=1,
                                                           sticky=(tk.W, tk.E))

        row = next(rows)
        self.remotedirectory = tk.StringVar()
        ttk.Label(self, text="directory:").grid(row=row, column=0,
                                                       sticky=tk.W)
        ttk.Entry(self, textvariable=self.remotedirectory).grid(row=row, column=1,
                                                                sticky=(tk.W, tk.E))

        row = next(rows)
        self.syncmode = tk.StringVar()
        ttk.Label(self, text="Sync mode:").grid(row=row, column=0)
        f = ttk.Frame(self)
        f.grid(row=row, column=1)
        def callback():
            if self.syncmode == "both" and not self.flags["update"].dirty:
                self.flags["update"].variable.set(True)
        for column, mode in enumerate(["send", "receive", "both"]):
            rb = ttk.Radiobutton(f, text=mode, value=mode,
                                 variable=self.syncmode,
                                 command=callback)
            rb.grid(row=0, column=column)
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

                 ("Directory handling",
                  [("Recurse into directories",       "--recursive",  "recursive")]),

                 ("Additional file types to preserve",
                  [("Symbolic links",                 "--links",      "slinks"),
                   ("Hard links",                     "--hard-links", "hlinks"),
                   ("Special files",                  "--specials",   "specials"),
                   ("Device files (super-user only)", "--devices",    "devices")])]):
            subframe = ttk.Labelframe(advanced, text=groupname)
            subframe.grid(row=subrow, column=0, columnspan=2,
                          sticky=tk.W)
            for subsubrow, (description, flag, key) in enumerate(group):
                variable = tk.BooleanVar()
                checkbutton = ttk.Checkbutton(subframe,
                                              text=description,
                                              variable=variable,
                                              onvalue=True, offvalue=False)
                checkbutton.grid(row=subsubrow, column=0, columnspan=2,
                                 sticky=(tk.W, tk.E))
                self.flags[key] = _rf(variable, checkbutton, flag, dirty=False)

        subframe = ttk.Labelframe(advanced, text="Deletion")
        # --delete-* should only be available if --delete is set
        choice = tk.StringVar()
        variable = tk.BooleanVar()
        buttons = []
        def callback():
            state = "normal" if variable.get() else "disabled"
            for button in buttons:
                button.state(state)
        checkbutton = ttk.Checkbutton(subframe, variable=variable,
                                      onvalue=True, offvalue=False,
                                      text="Delete extraneous files from"
                                           " destination directories")
        checkbutton.grid(row=next(subrows), column=0, columnspan=2,
                         sticky=(tk.W, tk.E))
        for subrow, (description, flag) in \
            zip(subrows,
                [("Before transfer", "--delete-before"),
                 ("After transfer",  "--delete-after")]):
            ttk.Label(subframe, text=description).grid(row=subrow, column=0,
                                                       sticky=tk.W)
            button = ttk.Radiobutton(subframe, textvariable=variable, value=flag)
            button.grid(row=subrow, column=1,
                        sticky=(tk.W, tk.E))
            buttons.append(button)

        # --- --- simple options --- --- #
        simple = ttk.Frame(nb)
        subrows = count()

        archive_mode = tk.BooleanVar()
        def callback():
            mode = archive_mode.get()
            for flag in map(self.flags.__getitem__,
                            ["recursive", "slinks", "perms", "mtimes",
                             "group", "owner", "devices", "specials"]):
                if not flag.dirty and bool(flag.variable.get()) != mode:
                    flag.widget.invoke()
        checkbutton = ttk.Checkbutton(simple,
                                      onvalue=True, offvalue=False,
                                      text="Full archival mode"
                                           " (all metadata and file types)",
                                      variable=archive_mode, command=callback)
        checkbutton.grid(row=next(subrows), column=0, columnspan=2)

        nb.add(simple, text="Simple")
        nb.add(advanced, text="advanced")

        # TODO: Display command at bottom, as being built

        # TODO: Implement
        #self.dirty = False  # i.e., user made changes to sync options

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
