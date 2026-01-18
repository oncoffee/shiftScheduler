import numpy as np
import pandas as pd
from datetime import time, timedelta, datetime
from dateutil import parser
from data_import import stores, schedule


def create_time_periods_df(start_time: time, end_time: time) -> pd.DataFrame:
    interval = timedelta(minutes=30)
    start_dt = datetime.combine(datetime.today(), start_time)
    end_dt = datetime.combine(datetime.today(), end_time)

    periods = []
    current = start_dt
    period = 0
    while current < end_dt:
        periods.append({'Time': current.time(), 'Period': period})
        current += interval
        period += 1

    return pd.DataFrame(periods)


def putting_store_time_in_df(dow: str, start: time, end: time) -> pd.DataFrame:
    df = create_time_periods_df(start, end)
    df['day_of_week'] = dow
    return df


def creating_employee_df(employee_name: str, dow: str, start: str, end: str) -> pd.DataFrame:
    start_time = parser.parse(start).time()
    end_time = parser.parse(end).time()
    df = create_time_periods_df(start_time, end_time)
    df[employee_name] = 1
    df['day_of_week'] = dow
    return df[['day_of_week', 'Time', employee_name]].copy()

if __name__ == '__main__':

    for s in stores:
        week_no = s.week_no
        store_name = s.store_name
        day_of_week = s.day_of_week
        store_start_time = parser.parse(s.start_time).time()
        store_end_time = parser.parse(s.end_time).time()

        store_df = putting_store_time_in_df(s.day_of_week, store_start_time,
                                            store_end_time)

        for sch in schedule:
            if sch.day_of_week == s.day_of_week:
                df_name = f'df_{sch.employee_name.lower()}'
                df = creating_employee_df(sch.employee_name, sch.day_of_week,
                                          sch.availability.split(" - ")[0],
                                          sch.availability.split(" - ")[1])
                locals()[df_name] = df
                store_df = store_df.merge(
                    df,
                    on=['day_of_week', 'Time'],
                    how='left'
                )
            store_df = store_df.replace(np.NaN, 0)
        print(store_df)