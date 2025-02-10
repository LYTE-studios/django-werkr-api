import pandas as pd


class ExportUtil:

    @staticmethod
    def alter_column(data_frame: pd.DataFrame, column_name: str, function):
        column = data_frame[column_name]

        new_column = column.apply(function)

        data_frame[column_name] = new_column

        return data_frame

    @staticmethod
    def format_ssn(ssn: str):
        if ssn is None:
            return ""

        return ssn.zfill(10)
