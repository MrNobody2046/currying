# encoding: utf-8

import datetime
import difflib
import json
import math
import re
import types
from urlparse import urlparse

BASIC_TYPE = '#basic'
HIGH_ORDER_TYPE = '#high_order'
UNPACKER_TYPE = '#unpacker'
LAZY_TYPE = '#lazy'
RAISE_ERROR = 'raise_error'


class UnpackError(Exception):
    pass


class Result(object):
    """
    wrapper for bool expression result, save value and statements of exp
    """

    def __init__(self, bol, stmt=None, original=None):
        """
        :param bol: True or False
        :param stmt: (str) expression be called
        :param original: (obj) expression/function/callable, original definition
        :return:
        """
        if bol not in (True, False):
            raise TypeError('should be True or False, get %s' % bol)
        self._bol = bol
        self._stmt = stmt
        self._original = original

    def __nonzero__(self):
        return self._bol

    def __str__(self):
        return '%s => %s' % (self._stmt, self._bol)

    @property
    def bool(self):
        return self._bol

    @property
    def stmt(self):
        return self._stmt

    @property
    def type(self):
        if isinstance(self._original, types.FunctionType):
            return self._original.func_name
        else:
            return self._original


def wrap_basic():
    """
    Make a partial function generator by hoisting some args & kwargs.

     - divided original call into two steps, first call generate the
       expression with known args(hoisting_args) & kwargs, and get
       real value in second call.
     - evaluate lazy expression in parameters
     - handle exception when calls function be wrapped
     - !! packing return value in Result type, always return Result

    Example:
        @wrap_basic()
        def calculate(a, b, c):
            return a + b * c

        # generate a new function by hoisting a and b
        calculate_with_c = calculate(1,2)

        # get finally result
        calculate_with_c(3) -> 7
    :return: decorator
    """

    def _decorator(func):
        def partial_generator(*hoisting_args, **hoisting_kwargs):
            def _evaluator(*args, **kwargs):
                processed_hoisting_args = ()
                for arg in hoisting_args:
                    if hasattr(arg, 'type') and arg.type == LAZY_TYPE:
                        arg = arg()
                    processed_hoisting_args += (arg,)
                args = processed_hoisting_args + args
                kwargs.update(hoisting_kwargs)
                raise_error = kwargs.pop(RAISE_ERROR, False)
                msg = '%s%s' % (func.func_name, args)
                try:
                    return Result(func(*args, **kwargs), stmt=msg, original=func)
                except Exception, e:
                    if raise_error:
                        raise
                    return Result(False, stmt=msg + ', %s' % e, original=func)

            _evaluator.type = BASIC_TYPE
            _evaluator.func_name = func.func_name
            return _evaluator

        partial_generator.name = func.func_name
        return partial_generator

    return _decorator


def wrap_high_order(default_unpacker=None):
    """
    wrap_high_order is a special wrapper looks like basic_wrapper but only act on
    specific functions which use basic functions as only args. the first call
    of high_order function also generate the expression. such as:

        each(ge(0),le(100)) -> generate the function like lambda val:0 <= val <= 100

        between_0_100 = each(ge(0), le(100))  # -> lambda x: 0 <= x <= 100
        between_0_100(90) -> True

        ! noticed that callable items should be basic function according to current
        high order function design (these functions always return Result type)

    :param default_unpacker:
    :return:
    """

    def _decorator(high_order_func):
        def partial_generator(*func_list):
            def _evaluator(*args, **kwargs):
                def _apply_func_list_(func, func_li, _args, _kwargs, _msg, _raise):
                    try:
                        real_args = []
                        for _func in func_li:
                            _arg = lambda _a=_args, _k=_kwargs, _f=_func: _f(*_a, **_k)
                            _arg.func_name = '%s%s' % (_func.func_name, _args)
                            real_args.append(_arg)
                        return func(*real_args)
                    except Exception, e:
                        if _raise:
                            raise
                        return Result(False, stmt=_msg + ', %s' % e, original=func)

                msg = '%s%s' % (high_order_func.func_name, func_list)
                raise_error = kwargs.pop(RAISE_ERROR, False)
                r_func_list = list(func_list)
                unpacker = r_func_list.pop(0) if r_func_list[0].type == UNPACKER_TYPE else default_unpacker
                if unpacker:
                    for val in unpacker(*args, **kwargs):
                        _res = _apply_func_list_(high_order_func, r_func_list, (val,), {}, msg, raise_error)
                        if not _res:
                            return _res
                    return Result(True, stmt=msg, original=high_order_func)
                else:
                    return _apply_func_list_(high_order_func, r_func_list, args, kwargs, msg, raise_error)

            _evaluator.type = HIGH_ORDER_TYPE
            _evaluator.func_name = high_order_func.func_name
            return _evaluator

        partial_generator.name = high_order_func.func_name
        return partial_generator

    return _decorator


def wrap_unpacker():
    """
    This wrapper looks like wrap_basic, but it will not handle error, process
    parameters, or wraps return value.
    :return:
    """

    def _decorator(unpacker):
        def partial_generator(*hoisting_args, **hoisting_kwargs):
            def _evaluator(*args, **kwargs):
                kwargs.update(hoisting_kwargs)
                return unpacker(*(hoisting_args + args), **kwargs)

            _evaluator.type = UNPACKER_TYPE
            return _evaluator

        partial_generator.name = unpacker.func_name
        return partial_generator

    return _decorator


def wrap_lazy(func):
    def _evaluator():
        return func()

    _evaluator.type = LAZY_TYPE
    return _evaluator


@wrap_basic()
def eq(expected, val):
    return expected == val


@wrap_basic()
def ge(expected, val):
    return val >= expected


@wrap_basic()
def gt(expected, val):
    return val > expected


@wrap_basic()
def le(expected, val):
    return val <= expected


@wrap_basic()
def lt(expected, val):
    return val < expected


@wrap_basic()
def is_in(container, val):
    return val in container


@wrap_basic()
def is_type(expected, val):
    return type(val) == expected


@wrap_basic()
def is_instance(expected, val):
    return isinstance(val, expected)


@wrap_basic()
def is_json(val):
    return every(load_json())(val).bool


@wrap_basic()
def is_url(val):
    return every(parse_url(),
                 every(extract_attribute(specified_key='scheme'),
                       is_instance(basestring), is_in({'http', 'https'})),
                 every(extract_attribute(specified_key='netloc'),
                       non_empty_string_without_whitespace()))(val).bool


@wrap_basic()
def matches(regex, val):
    return bool(re.compile(regex).match(val))


@wrap_basic()
def contains(expected, container):
    return expected in container


@wrap_basic()
def string_diff_below(threshold, new_value, old_value):
    """
    :param threshold: float between 0.0-1.0, diff ratio
    :param new_value: new_value
    :param old_value: old_value if this value is invalid, return True
    :return: bool
    """
    if not old_value:
        return True
    ratio = difflib.SequenceMatcher(isjunk=None, a=new_value, b=old_value).ratio()
    return 1 - ratio < threshold


@wrap_basic()
def string_length_between(min_length, max_length, val, unit='bytes'):
    if not isinstance(val, basestring):
        return False
    if isinstance(val, unicode):
        val = val.encode('utf-8')
    if unit == 'bits':
        return min_length <= len(val) * 8 <= max_length
    else:
        return min_length <= len(val) <= max_length


@wrap_basic()
def number_change_below(threshold, new_value, old_value):
    delta = abs(old_value - new_value)
    return delta / (min((new_value, old_value)) + .0000000001) < threshold


@wrap_basic()
def float_precision_magnitude_le(expected_precision, expected_magnitude, val):
    """
    float's magnitude and precision should less then expected number

        float_precision_magnitude_le(2,2)(2.1) -> True

        the magnitude, precision of 2.1 is 1, 1, all less then 2, so get True

    :param expected_precision: int
    :param expected_magnitude: int
    :param val:
    :return:
    """
    if not isinstance(val, float):
        raise TypeError('should be float, get %s, %s' % (val, str(type(val)).strip('<>')))
    magnitude, precision = get_magnitude_and_precision(val)
    if magnitude <= expected_magnitude and precision <= expected_precision:
        return True
    return False


@wrap_basic()
def non_empty_string(val):
    return False if (not isinstance(val, basestring) or len(val) == 0) else True


@wrap_basic()
def as_url_contains_email(url, email_regex=re.compile(r"[^@]+@[^@]+\.[^@]+")):
    parts = urlparse(url)
    return False if parts.scheme == '' or not email_regex.match(url) else True


@wrap_basic()
def non_empty_string_without_whitespace(val):
    return False if not isinstance(val, basestring) or any(s.isspace() for s in val) else True


@wrap_unpacker()
def extract_elements(container):
    if isinstance(container, dict):
        for _ in container.values():
            yield _
    else:
        try:
            for _ in container:
                yield _
        except Exception:
            raise UnpackError("can't extra elements from type(%s), val %s" % (type(container), container))


@wrap_unpacker()
def parse_url(url):
    parts = urlparse(url)
    yield {k: getattr(parts, k) for k in ('scheme', 'netloc', 'path', 'params', 'query', 'fragment')}


@wrap_unpacker()
def load_json(json_str):
    try:
        yield json.loads(json_str)
    except ValueError:
        raise UnpackError("can't load json from type(%s), val '%s'" % (type(json_str), json_str))


@wrap_high_order()
def either(*fx_list):
    for fx in fx_list:
        res = fx()
        if res:
            return res
    fx_str = str(tuple([fx.func_name for fx in fx_list])).replace("'", '')
    return Result(False, stmt="either%s" % fx_str, original="either")


@wrap_high_order()
def every(*fx_list):
    for fx in fx_list:
        res = fx()
        if not res:
            return res
    return Result(True, stmt="every%s" % str(tuple([fx.func_name for fx in fx_list])), original="every")


@wrap_high_order()
def neg(fx):
    res = fx()
    return Result(not res.bool, str(res))


@wrap_high_order(default_unpacker=extract_elements())
def each(*fx_list):
    for fx in fx_list:
        res = fx()
        if not res:
            return res
    return Result(True, stmt="every%s" % str(tuple([fx.func_name for fx in fx_list])), original="each")


@wrap_basic()
def value(*args):
    return every(extract_attribute(specified_key=args[0]), *args[1:-1])(args[-1]).bool


@wrap_unpacker()
def extract_attribute(container, specified_key=None):
    try:
        if isinstance(container, dict):
            yield container.get(specified_key)
        else:
            yield getattr(container, specified_key)
    except (AttributeError, KeyError):
        raise UnpackError('Container->type(%s) not have %s' % (type(container), specified_key))


@wrap_lazy
def tomorrow():
    return datetime.datetime.now().date() + datetime.timedelta(days=1)


def get_magnitude_and_precision(number):
    """
    Get length of each part of float number
            12.001
            ↑↑ ↑↑↑
    magnitude -> 2 , scale -> 3
    example:
        precision_and_scale(1.3) -> (1,1)
        precision_and_scale(12345.3) -> (5,1)
        precision_and_scale(12345.123) -> (5,3)
    :param number:
    :return:
    """
    max_digits = 14
    int_part = int(abs(number))
    magnitude = 1 if int_part == 0 else int(math.log10(int_part)) + 1
    if magnitude >= max_digits:
        return magnitude, 0
    frac_part = abs(number) - int_part
    multiplier = 10 ** (max_digits - magnitude)
    frac_digits = multiplier + int(multiplier * frac_part + 0.5)
    while frac_digits % 10 == 0:
        frac_digits /= 10
    precision = int(math.log10(frac_digits))
    return magnitude, precision


@wrap_basic()
def price_float_in(threshold, old_price, new_price):
    """
    :param threshold: percentage 100 means 100% int/float
    :param old_price: old value price int/float
    :param new_price: new value price int/float
    :return:bool
    """
    if 0 in (old_price, new_price):
        return True
    delta = abs(new_price - old_price)
    return (delta / old_price) < (threshold / 100.0)
