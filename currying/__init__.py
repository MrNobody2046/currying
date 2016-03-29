import inspect


class _PlaceHolder(object):
    def __init__(self, arg_name):
        self.arg_name = arg_name

    def __str__(self):
        return 'Not Specified Arg %s' % self.arg_name


class Args(dict):
    def __missing__(self, v):
        return _PlaceHolder(v)


class PartialObject(object):
    APPLY_KEY = '_ap_now_'

    def __init__(self, callee, transmit_default=True):
        self._callee = callee
        self._args = Args()
        self.magic_args = ()
        self.magic_kwargs = {}
        args_spec = inspect.getargspec(callee)
        self._args_spec = tuple(args_spec.args)
        self._args_spec_list = list(self._args_spec)
        self._support_star_args = bool(args_spec.varargs)
        self._support_star_kwargs = bool(args_spec.keywords)
        self._defaults = args_spec.defaults
        if self._defaults:
            self._default_args = dict(zip(args_spec.args[-len(self._defaults):], self._defaults))
        else:
            self._default_args = {}
        if transmit_default:
            self._args.update(self._default_args)
            for k in self._default_args:
                self._args_spec_list.remove(k)
        print self.__dict__
        print args_spec

    @property
    def name(self):
        return self.original.func_name

    @property
    def original(self):
        return self._callee

    @property
    def args(self):
        return [self._args.get(arg) for arg in self._args_spec]

    def add_args(self, args):
        for arg in args:
            try:
                arg_name = self._args_spec_list.pop(0)
                self._args[arg_name] = arg
            except IndexError:
                raise TypeError("%s() got multiple values for argument '%s'" % (self.name, arg_name))

    def add_kwargs(self, kwargs):
        for k, v in kwargs.items():
            if k in self._args_spec_list:
                self._args_spec_list.remove(k)
                self._args[k] = v
            else:
                self.magic_kwargs[k] = v

    def __call__(self, *args, **kwargs):
        apply_now = kwargs.pop(self.APPLY_KEY, False)
        self.add_args(args)
        self.add_kwargs(kwargs)
        if apply_now or self.ready():
            return self.apply()
        return self

    def apply(self):
        return self.original(**self._args)

    def ready(self):
        if self._support_star_args or self._support_star_kwargs or len(self._args_spec_list) > 0:
            return False
        return True

    def __str__(self):
        return str(self.original)

    def __repr__(self):
        return ''


def currying(function):
    return PartialObject(function)


if __name__ == '__main__':
    # @currying
    # def print_number(x, y, f, z=1, *aa, **kwargs):
    #     print aa
    #     print kwargs
    #     print "(%d,%d)" % (x, y)


    @currying
    def pr(a, b=3):
        print 'execute pr'
        return a + b


    print pr(1)
    #
    # print print_number
    # print [print_number]
    # print print_number(1, 2, 3, s=1, x=1, y=2, f=3)
    # print print_number(1, 2, 3, s=1, x=1, y=2, f=3).args
    # print_number.original(1, 2, 3, s=1, x=1, y=2, f=3)
