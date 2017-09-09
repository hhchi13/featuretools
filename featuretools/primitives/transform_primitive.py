from .primitive_base import PrimitiveBase
from featuretools.variable_types import (Discrete, Numeric, Categorical, Boolean,
                                         Ordinal, Text, Datetime, Timedelta, Variable,
                                         TimeIndex, DatetimeTimeIndex, Id)

import datetime
import os
import pandas as pd
import numpy as np
current_path = os.path.dirname(os.path.realpath(__file__))
FEATURE_DATASETS = os.path.join(os.path.join(current_path, '..'), 'feature_datasets')


class TransformPrimitive(PrimitiveBase):
    """Feature for entity that is a based off one or more other features
        in that entity"""
    rolling_function = False

    def __init__(self, *base_features):
        self.base_features = [self._check_feature(f) for f in base_features]
        if any(bf.expanding for bf in self.base_features):
            self.expanding = True
        assert len(set([f.entity for f in self.base_features])) == 1, \
            "More than one entity for base features"
        super(TransformPrimitive, self).__init__(self.base_features[0].entity,
                                                 self.base_features)

    def _get_name(self):
        name = u"{}(".format(self.name.upper())
        name += u", ".join(f.get_name() for f in self.base_features)
        name += u")"
        return name

    @property
    def default_value(self):
        return self.base_features[0].default_value


class IsNull(TransformPrimitive):
    """For each value of base feature, return true if value is null"""
    name = "is_null"
    input_types = [Variable]
    return_type = Boolean

    def get_function(self):
        return lambda array: pd.isnull(pd.Series(array))


class Absolute(TransformPrimitive):
    """Absolute value of base feature"""
    name = "absolute"
    input_types = [Numeric]
    return_type = Numeric

    def get_function(self):
        return lambda array: np.absolute(array)


class TimeSincePrevious(TransformPrimitive):
    """ Compute the time since the previous instance for each instance in a time indexed entity"""
    name = "time_since_previous"
    input_types = [DatetimeTimeIndex, Id]
    return_type = Numeric

    def __init__(self, time_index, group_feature):
        """Summary

        Args:
            base_feature (:class:`PrimitiveBase`): base feature
            group_feature (None, optional): variable or feature to group
                rows by before calculating diff

        """
        group_feature = self._check_feature(group_feature)
        assert issubclass(group_feature.variable_type, Discrete), \
            "group_feature must have a discrete variable_type"
        self.group_feature = group_feature
        super(TimeSincePrevious, self).__init__(time_index, group_feature)

    def _get_name(self):
        return u"time_since_previous_by_%s" % self.group_feature.get_name()

    def get_function(self):
        def pd_diff(base_array, group_array):
            bf_name = 'base_feature'
            groupby = 'groupby'
            grouped_df = pd.DataFrame.from_dict({bf_name: base_array, groupby: group_array}).groupby(groupby).diff()
            return grouped_df[bf_name].apply(lambda x:
                                             x.total_seconds())
        return pd_diff


class DatetimeUnitBasePrimitive(TransformPrimitive):
    """Transform Datetime feature into time or calendar units (second/day/week/etc)"""
    name = None
    input_types = [Datetime]
    return_type = Ordinal

    def get_function(self):
        return lambda array: pd_time_unit(self.name)(pd.DatetimeIndex(array))


class TimedeltaUnitBasePrimitive(TransformPrimitive):
    """Transform Timedelta features into number of time units (seconds/days/etc) they encompass"""
    name = None
    input_types = [Timedelta]
    return_type = Numeric

    def get_function(self):
        return lambda array: pd_time_unit(self.name)(pd.TimedeltaIndex(array))


class Day(DatetimeUnitBasePrimitive):
    name = "day"


class Days(TimedeltaUnitBasePrimitive):
    name = "days"


class Hour(DatetimeUnitBasePrimitive):
    name = "hour"


class Hours(TimedeltaUnitBasePrimitive):
    name = "hours"

    def get_function(self):
        return lambda array: pd_time_unit("seconds")(pd.TimedeltaIndex(array)) / 3600.


class Second(DatetimeUnitBasePrimitive):
    name = "second"


class Seconds(TimedeltaUnitBasePrimitive):
    name = "seconds"


class Minute(DatetimeUnitBasePrimitive):
    name = "minute"


class Minutes(TimedeltaUnitBasePrimitive):
    name = "minutes"

    def get_function(self):
        return lambda array: pd_time_unit("seconds")(pd.TimedeltaIndex(array)) / 60.


class Week(DatetimeUnitBasePrimitive):
    name = "week"


class Weeks(TimedeltaUnitBasePrimitive):
    name = "weeks"

    def get_function(self):
        return lambda array: pd_time_unit("days")(pd.TimedeltaIndex(array)) / 7.


class Month(DatetimeUnitBasePrimitive):
    name = "month"


class Months(TimedeltaUnitBasePrimitive):
    name = "months"

    def get_function(self):
        return lambda array: pd_time_unit("days")(pd.TimedeltaIndex(array)) * (12. / 365)


class Year(DatetimeUnitBasePrimitive):
    name = "year"


class Years(TimedeltaUnitBasePrimitive):
    name = "years"

    def get_function(self):
        return lambda array: pd_time_unit("days")(pd.TimedeltaIndex(array)) / 365


class Weekend(TransformPrimitive):
    """Transform Datetime feature into the boolean of Weekend"""
    name = "is_weekend"
    input_types = [Datetime]
    return_type = Boolean

    def get_function(self):
        return lambda df: pd_time_unit("weekday")(pd.DatetimeIndex(df)) > 4


class Weekday(DatetimeUnitBasePrimitive):
    name = "weekday"


# class Like(TransformPrimitive):
#     """Equivalent to SQL LIKE(%text%)
#        Returns true if text is contained with the string base_feature
#     """
#     name = "like"
#     input_types =  [(Text,), (Categorical,)]
#     return_type = Boolean

#     def __init__(self, base_feature, like_statement, case_sensitive=False):
#         self.like_statement = like_statement
#         self.case_sensitive = case_sensitive
#         super(Like, self).__init__(base_feature)

#     def get_function(self):
#         def pd_like(df, f):
#             return df[df.columns[0]].str.contains(f.like_statement,
#                                                   case=f.case_sensitive)
#         return pd_like


class TimeSince(TransformPrimitive):
    """
    For each value of the base feature, compute the timedelta between it and a datetime
    """
    name = "time_since"
    input_types = [[DatetimeTimeIndex], [Datetime]]
    return_type = Timedelta
    uses_calc_time = True

    def get_function(self):
        def pd_time_since(array, time):
            if time is None:
                time = datetime.now()
            return (time - pd.DatetimeIndex(array)).values
        return pd_time_since


class DaysSince(TransformPrimitive):
    """
    For each value of the base feature, compute the number of days between it and a datetime
    """
    name = "days_since"
    input_types = [DatetimeTimeIndex]
    return_type = Numeric
    uses_calc_time = True

    def get_function(self):
        def pd_days_since(array, time):
            if time is None:
                time = datetime.now()
            return pd_time_unit('days')(time - pd.DatetimeIndex(array))
        return pd_days_since


class IsIn(TransformPrimitive):
    """
    For each value of the base feature, checks whether it is in a list that is provided.
    """
    name = "isin"
    input_types =  [Variable]
    return_type = Boolean

    def __init__(self, base_feature, list_of_outputs=None):
        self.list_of_outputs = list_of_outputs
        super(IsIn, self).__init__(base_feature)

    def get_function(self):
        def pd_is_in(array, list_of_outputs=self.list_of_outputs):
            if list_of_outputs is None:
                list_of_outputs = []
            return pd.Series(array).isin(list_of_outputs)
        return pd_is_in

    def _get_name(self):
        return u"%s.isin(%s)" % (self.base_features[0].get_name(),
                                str(self.list_of_outputs))


class Diff(TransformPrimitive):
    """
    For each value of the base feature, compute the difference between it and the previous value.

    If it is a Datetime feature, compute the difference in seconds
    """
    name = "diff"
    input_types =  [Numeric, Id]
    return_type = Numeric

    def __init__(self, base_feature, group_feature):
        """Summary

        Args:
            base_feature (:class:`PrimitiveBase`): base feature
            group_feature (:class:`PrimitiveBase`): variable or feature to group
                rows by before calculating diff

        """
        self.group_feature = self._check_feature(group_feature)
        super(Diff, self).__init__(base_feature, group_feature)

    def _get_name(self):
        base_features_str = self.base_features[0].get_name() + u" by " + self.group_feature.get_name()
        return u"%s(%s)" % (self.name.upper(), base_features_str)

    def get_function(self):
        def pd_diff(base_array, group_array):
            bf_name = 'base_feature'
            groupby = 'groupby'
            grouped_df = pd.DataFrame.from_dict({bf_name: base_array, groupby: group_array}).groupby(groupby).diff()
            return grouped_df[bf_name]
        return pd_diff


class Not(TransformPrimitive):
    name = "not"
    input_types =  [Boolean]
    return_type = Boolean

    def _get_name(self):
        return u"NOT({})".format(self.base_features[0].get_name())

    def _get_op(self):
        return "__not__"

    def get_function(self):
        return lambda array: np.logical_not(array)


class Percentile(TransformPrimitive):
    name = 'percentile'
    input_types = [Numeric]
    return_type = Numeric

    def get_function(self):
        return lambda array: pd.Series(array).rank(pct=True)


def pd_time_unit(time_unit):
    def inner(pd_index):
        return getattr(pd_index, time_unit).values
    return inner