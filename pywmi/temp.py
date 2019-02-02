import os
import tempfile


class TemporaryFile(object):
    def __init__(self, prefix=None, suffix=None, directory=None, callback=None):
        self.prefix = prefix
        self.suffix = suffix
        self.directory = directory
        self.callback = callback
        self.filename = None

    def __enter__(self):
        tmp_file = tempfile.mkstemp(prefix=self.prefix, suffix=self.suffix, dir=self.directory)
        self.tmp_filename = tmp_file[1]
        if self.callback:
            self.callback(self.tmp_filename)
        return self.tmp_filename

    def __exit__(self, t, value, traceback):
        if os.path.exists(self.tmp_filename):
            os.remove(self.tmp_filename)
