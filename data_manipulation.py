import numpy as np
import pandas as pd
from datetime import timedelta, datetime
from data_import import *

def putting_store_time_in_df(dow, start, end):
    df = pd.DataFrame(columns=['Time', 'Period'])

    start_time = start
    end_time = end
    interval = timedelta(minutes=30)

    start_datetime = datetime.combine(datetime.today(), start_time)
    end_datetime = datetime.combine(datetime.today(), end_time)

    period = 0

    current_datetime = start_datetime
    while current_datetime < end_datetime:
        new_row = pd.DataFrame({'Time': current_datetime.time(), 'Period': period}, index=[0])
        df = pd.concat([df, new_row], ignore_index=True)
        current_datetime += interval
        period += 1
    df['day_of_week'] = dow
    return df

def creating_employee_df(employee_name, dow, start, end):
    df = pd.DataFrame(columns=['Time', 'Period'])

    start_time = parser.parse(start).time()
    end_time = parser.parse(end).time()
    interval = timedelta(minutes=30)

    start_datetime = datetime.combine(datetime.today(), start_time)
    end_datetime = datetime.combine(datetime.today(), end_time)

    period = 0

    current_datetime = start_datetime
    while current_datetime < end_datetime:
        new_row = pd.DataFrame({'Time': current_datetime.time(), 'Period': period}, index=[0])
        df = pd.concat([df, new_row], ignore_index=True)
        current_datetime += interval
        period += 1
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