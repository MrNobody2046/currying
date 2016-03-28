import inspect


class PartialObject(object):
    def __init__(self, callee):
        self._callee = callee
        self._args = ()
        self._kwargs = {}
        self._args_spec = list(inspect.getargspec(callee).args)
        print self._args_spec

    @property
    def original(self):
        return self._callee

    @property
    def args(self):
        return self._args

    @property
    def kwargs(self):
        return self._kwargs

    def add_args(self, *args):
        for arg in args:
            self._args_spec.pop(0)
        self._args += args

    def add_kwargs(self, **kwargs):
        self._kwargs.update(kwargs)

    def __call__(self, *args, **kwargs):
        self.add_args(args)
        self.add_kwargs()
        pass

    def apply(self):
        pass

    def __str__(self):
        pass

    def __repr__(self):
        pass


def currying(function):
    return PartialObject(function)


@currying
def print_number(x, y, f,z, *aa, **kwargs):
    print "(%d,%d)" % (x, y)


if __name__ == '__main__':
    print_number(1, 2, 3, s=1, x=1, y=2, f=3)
