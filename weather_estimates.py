# imports
import datetime
import warnings
import sys
import numpy as np
import pandas as pd
import scipy.optimize

# workaround for importing classes
sys.path.append('./weather_predictions/')
import knmi  # noqa


class WeatherEstimates:
    """
    Class that is used to estimate weather given coordinates and a timeslot.
    """

    def __init__(self, start_date: datetime, end_date: datetime = None):
        """
        Initialize class and get data from KNMI api
        """
        if end_date is None:
            end_date = start_date + datetime.timedelta(days=1)
        if start_date > end_date:
            raise Exception("Start date is later than end date")
        self.start_date = start_date
        self.end_date = end_date
        self.knmi = knmi.Knmi(start_date, end_date)
        self.data = self.knmi.get_data()
 
    def _get_value(self, lon: float, lat: float, identifier: str) -> pd.DataFrame:
        """Function that estimates a weather attribute given an identifier in a given location within a given timeslot using KNMI data and the lon, lat, start_time and end_time of the class.
        Returns a dataframe of the given identifier (temperature, wind speed or horizontal irradiation) within the given timespan."""
        # List used to store dates and temps
        lst = list()
        warnings.filterwarnings('ignore')

        def f_linear(x_var, a_var, b_var, c_var):
            return a_var * x_var[:, 0] + b_var * x_var[:, 1] + c_var

        start_date = self.start_date
        end_date = self.end_date

        nearest_stations = self.knmi.get_closest_stations(lon, lat)

        # Calculate an estimate temperature for every hour
        while start_date <= end_date:
            hour = None
            used_date = None

            # Parse date to compareable values
            if start_date.hour == 0:
                used_date = start_date - datetime.timedelta(hours=1)
                hour = 24
            else:
                used_date = start_date
                hour = used_date.hour

            date_string = f'{used_date.year}{used_date.month:02d}{used_date.day:02d}'
            # Select data that will be used to calculate temperature
            df_datehour = self.data[((self.data['HH'] == hour)) & (
                self.data['YYYYMMDD'] == int(date_string))].set_index('STN')
            df_for_fit = nearest_stations.join(df_datehour, how='inner')
            # Get values that are needed in order to calculate temperature
            x_val = df_for_fit[['LON(east)', 'LAT(north)']].values
            y_val = df_for_fit[identifier].values

            if y_val.size == 0:
                raise Exception(
                    f"No values are available for date: {used_date}")

            # Fit curve and calculate temperature
            popt, pcov = scipy.optimize.curve_fit(f_linear, x_val, y_val)

            # Add time and temperature to dictionary
            value = f_linear(
                np.array([[lon, lat]]), popt[0], popt[1], popt[2])[0]

            # if value is lower than 0, set it to 0
            if value < 0:
                value = 0

            lst.append([value, start_date])

            start_date = start_date + datetime.timedelta(hours=1)

        # Convert list to dataframe and add timestamp
        dataframe = pd.DataFrame(lst, columns=['value', 'datetime'])

        dataframe["timestamp"] = dataframe['datetime'].apply(lambda t: t.timestamp())

        dataframe["index"] = dataframe.index

        dataframe = dataframe[["index", "value", "datetime", "timestamp"]]

        return dataframe

    def get_temperature(self, lon: float, lat: float) -> pd.DataFrame:
        """
        Function that returns an estimate temperature in the given coordinates °C.
        """

        return self._get_value(lon, lat, 'T')

    def get_wind_speed(self, lon: float, lat: float) -> pd.DataFrame:
        """
        Function that returns an estimate wind speed in the given coordinates in m/s.
        """
        return self._get_value(lon, lat, 'FF')

    def get_horizontal_irradiation(self, lon: float, lat: float) -> pd.DataFrame:
        """
        Function that returns an estimated irradiation in the given coordinates.
        """
        dataframe = self._get_value(lon, lat, 'Q')
        dataframe['value'] = round(dataframe['value'], 5)
        return dataframe
