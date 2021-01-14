# imports
import io
import datetime as dt
from functools import lru_cache
from math import sin, cos, sqrt, atan2, radians
import requests
import pandas as pd

class Knmi :
    '''
    Class that gets the data from the knmi and .
    '''
    def __init__(self, start_date: dt, end_date: dt):
        self._stations = None
        self._data = None
        self.start_date = start_date
        self.end_date = end_date
        self._url = r'http://projects.knmi.nl/klimatologie/uurgegevens/getdata_uur.cgi'
        self._set_knmi_data(start_date, end_date)
        self.path_to_stations = './data/weather_data_knmi/stations.txt'
        self._set_stationinfo()
        self._remove_nan_values()


    @lru_cache(maxsize=32)
    def _get_raw_knmi_data(self, begin_date: dt.datetime, end_date: dt.datetime) -> str:
        """Function to download the raw KNMI data out of the API"""

        # Create the post package
        data = {
            'byear': begin_date.year,
            'bmonth': begin_date.month,
            'bday': begin_date.day,
            'eyear': end_date.year,
            'emonth': end_date.month,
            'eday': end_date.day,
            'WIND': 'FF',
            'TEMP': 'T',
            'SUNR': 'Q'
        }

        # Do the actual post
        res = requests.post(self._url, data=data)

        # Raise for errors
        res.raise_for_status()

        # Get rid of whitespaces, confuses Pandas
        text = res.text.replace(' ', '')

        return text

    def _set_knmi_data(self, begin_date: dt.datetime, end_date: dt.datetime) -> pd.DataFrame:
        """
        Function that downloads the KNMI data and converts it to a Pandas dataframe
        """
        starttime = begin_date.hour
        endtime = end_date.hour
        if starttime == 0:
            begin_date = begin_date - dt.timedelta(hours=1)
            starttime = 24
        if endtime == 0:
            end_date = end_date - dt.timedelta(hours=1)
            endtime = 24

        text = self._get_raw_knmi_data(begin_date, end_date)

        headers = "STN,YYYYMMDD,   HH,   DD,   FH,   FF,   FX,    T, T10N,   TD,   SQ,    Q,   DR,   RH,    P,   VV,    N,    U,   WW,   IX,    M,    R,    S,    O,    Y"
        headerline = [i.strip() for i in headers.split(',')]

        dataframe = pd.read_csv(io.StringIO(text), comment="#", names=headerline)

        # Only select what is needed
        start_date_int = int(f'{begin_date.year}{begin_date.month:02d}{begin_date.day:02d}')
        end_date_int = int(f'{end_date.year}{end_date.month:02d}{end_date.day:02d}')
        dataframe = dataframe.loc[((dataframe['YYYYMMDD'] > start_date_int) & (dataframe['YYYYMMDD'] < end_date_int)) | ((dataframe['YYYYMMDD'] == start_date_int)
                                                                                         & (dataframe['HH'] >= starttime)) | ((dataframe['YYYYMMDD'] == end_date_int) & (dataframe['HH'] <= endtime))]

        # Convert to usable values
        dataframe['T'] = dataframe['T'] / 10
        dataframe['FF'] = dataframe['FF'] / 10
        dataframe['Q'] = round(dataframe['Q'] * (25 / 9), 5)
        self._data = dataframe

    def _set_stationinfo(self) -> pd.DataFrame:
        headerline = [i.strip() for i in "STN, LON(east), LAT(north), ALT(m), NAME".split(',')]
        try :
            with open(self.path_to_stations, 'r') as file:
                txt = file.read()
        except BaseException:
            self.path_to_stations = '../data/weather_data_knmi/stations.txt'
            with open(self.path_to_stations, 'r') as file:
                txt = file.read()

        txt = txt.replace(' ', '')
        dataframe = pd.read_csv(io.StringIO(txt), comment="#", names=headerline).set_index('STN')
        self._stations = dataframe

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        # Approximate radius of earth in km
        radius = 6373.0

        lat1 = radians(lat1)
        lon1 = radians(lon1)
        lat2 = radians(lat2)
        lon2 = radians(lon2)

        difference_lon = lon2 - lon1
        difference_lat = lat2 - lat1

        # Haversine formula
        arcsin = sin(difference_lat / 2)**2 + cos(lat1) * cos(lat2) * sin(difference_lon / 2)**2
        haversine = 2 * atan2(sqrt(arcsin), sqrt(1 - arcsin))

        return radius * haversine

    def _remove_nan_values(self):
         # Remove stations when they have a NaN value
        for stn, row in self._stations.iterrows():
            temp = self._data.loc[self._data['STN'] == stn][['T', 'FF', 'Q']]
            if temp.isnull().values.any():
                self._stations.drop(stn, inplace=True)
                data = self._data.loc[self._data['STN'] == stn].index
                self._data.drop(data, inplace=True)

    def get_closest_stations(self, lon: float, lat: float, N: int = 3) -> pd.DataFrame:
        """
        Function that gets N nearest stations given a longitude (lon) and latitude (lat)
        """
        dataframe = self._stations

        # Convert LAT(north) and LON(east) to float.
        dataframe['LAT(north)'] = pd.to_numeric(dataframe['LAT(north)'], downcast='float')
        dataframe['LON(east)'] = pd.to_numeric(dataframe['LON(east)'], downcast='float')

        # Calculate distance to stations from given coordinates.
        dataframe['distance'] = dataframe.apply(lambda row: self._calculate_distance(lat, lon, row['LAT(north)'], row['LON(east)']), axis=1)
        dataframe.sort_values('distance', inplace=True)

        return dataframe.head(N)

    def get_data(self):
        '''
        Function that gets the data from KNMI which is loaded in the constructor.
        '''
        return self._data
