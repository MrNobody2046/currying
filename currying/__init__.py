class PartialObject(object):
    def __init__(self, callee):
        self._callee = callee
        self._args = ()
        self._kwargs = {}

    def __call__(self, *args, **kwargs):
        pass

    def apply(self):
        pass

    def __str__(self):
        pass

    def __repr__(self):
        pass


