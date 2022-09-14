import pandas as pd
import math
from datetime import datetime
import numpy as np
import scipy.optimize
import tqdm
from io import StringIO
from .measuringstations import measuringstations
import pytz

import warnings
from scipy.optimize import OptimizeWarning
warnings.simplefilter("ignore", OptimizeWarning)

__headerline = ['STN', 'YYYYMMDD', 'HH', 'DD', 'FH', 'FF', 'FX', 'T', 'T10N', 'TD',
       'SQ', 'Q', 'DR', 'RH', 'P', 'VV', 'N', 'U', 'WW', 'IX', 'M', 'R', 'S',
       'O', 'Y']

__baseurl = 'https://cdn.knmi.nl/knmi/map/page/klimatologie/gegevens/uurgegevens/uurgeg_{0}_{1}-{2}.zip'


column_descriptions = {
    'T':'Temperatuur',
    'FH': 'Uurgemiddelde windsnelheid',
    'DD': 'Windrichting',
    'Q': 'Globale straling',
    'DR': "Duur van de neerslag",
    "RH": "Uursom van de neerslag",
    "N": "Bewolking",
    "U": "Relatieve vochtigheid (in procenten)"
}



def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    # Based on https://stackoverflow.com/a/4913653/2235667

    radius = 6372.8 #km
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    difference_lon = lon2 - lon1
    difference_lat = lat2 - lat1
    arcsin = math.sin(difference_lat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(difference_lon / 2)**2
    haversine = 2 * math.atan2(math.sqrt(arcsin), math.sqrt(1 - arcsin))

    return radius * haversine

def _get_stationinfo() -> None:
    """Get the station positional data"""
    return pd.read_csv(StringIO(measuringstations))

def _get_closest_stations(lon:float, lat:float, N:int=3) -> pd.DataFrame:
    """Calculate the closest N stations to a given coordinate set"""

    df = _get_stationinfo()
    df['distance'] = df.apply(lambda row: _calculate_distance(lat, lon, row['LAT'], row['LON']), axis=1)
    df.sort_values('distance', inplace=True)

    return df.head(N)

def _get_station_year_weather(stn:int, lower_year:int, upper_year:int, metrics:list) -> pd.DataFrame:
    """Download the data for a particular timeframe"""

    url = __baseurl.format(stn, lower_year, upper_year)
    
    df = pd.read_csv(url, comment="#", skiprows=30, skip_blank_lines=True, names=__headerline, low_memory=False)
    
    for metric in metrics:
        df[metric] = pd.to_numeric(df[metric], errors='coerce')


    df['T'] = pd.to_numeric(df['T'], errors='coerce')
    df['FH'] = pd.to_numeric(df['FH'], errors='coerce')
    df['DR'] = pd.to_numeric(df['DR'], errors='coerce')
    df['DD'] = pd.to_numeric(df['DD'], errors='coerce')
    df['RH'] = pd.to_numeric(df['RH'], errors='coerce')

    df['T'] = df['T'] / 10 # Temperature in decimal
    df['FH'] = df['FH'] / 10 # Wind speed in decimal
    df['DR'] = df['DR'] / 10 # Duration of rain
    
    # Filter not relevant wind directions
    df.loc[df['DD'] < 0.01, 'DD'] = np.nan
    df.loc[df['DD'] > 360, 'DD'] = np.nan
    
    df.loc[df['RH'] < 0, 'RH'] = 0
   
    return df

def _get_station_weather(stn:int, metrics:list) -> pd.DataFrame:
    """Download multiple timeperiods for one station"""
    
    df_2010s = _get_station_year_weather(stn, 2011, 2020, metrics)
    df_2020s = _get_station_year_weather(stn, 2021, 2030, metrics)
    
    return pd.concat([df_2010s, df_2020s])

def _get_all_station_weather(df_stations:pd.DataFrame, metrics) -> pd.DataFrame:
    """Download multiple timeperiods for multiple stations"""
    
    df = pd.DataFrame()
    # print("Model 2")

    
    for stn in df_stations['STN'].unique():

        df_station = _get_station_weather(stn, metrics)
        df = pd.concat([df, df_station])
        
    return df

def _fit_metric(df_for_fit:pd.DataFrame, lon:float, lat:float, metric:str) -> float:
    """Localize a metric for a single timestamp. 
    Requires a set of station in df_for_fit and a target location (lon, lat)"""
    
    # Model for a linear plane
    def f(X, a, b, c):
        return a*X[:,0] + b*X[:, 1] + c

    # Select the X & Y for the temperature
    x = df_for_fit[['LON', 'LAT']].values
    y = df_for_fit[metric].values

    # Do the actual fit
    popt, _ = scipy.optimize.curve_fit(f, x, y)

    # Temperature in Zwolle
    return f(np.array([[lon, lat]]), popt[0], popt[1], popt[2])

def _calculate_locate_weather(df:pd.DataFrame, df_closest_stations:pd.DataFrame, lon:float, lat:float, metrics:list, N:int) -> pd.DataFrame:
    
    # Establish what each unique combination is
    datetime_combinations = df[['YYYYMMDD', 'HH']].drop_duplicates()
    datetime_combinations.index = range(datetime_combinations.shape[0])

    # Run over each timestamp seperately
    df_result = pd.DataFrame()
    for datetime_index in tqdm.tqdm(datetime_combinations.index):

        # Grab the timestamp
        datetime_item = datetime_combinations.loc[datetime_index]

        # Grab the relevant data and combine that with the lat/lon of the stations
        m = (df['YYYYMMDD'] == datetime_item['YYYYMMDD']) & (df['HH'] == datetime_item['HH'])
        df_subset = pd.merge(df.loc[m], df_closest_stations, on='STN')

        # Create a results row
        df_result_row = pd.DataFrame({'YYYYMMDD':[datetime_item['YYYYMMDD']], 
                                      'HH':[datetime_item['HH']],
                                      'datetime': datetime(int(str(datetime_item['YYYYMMDD'])[:4]), 
                                                              int(str(datetime_item['YYYYMMDD'])[4:6]), 
                                                              int(str(datetime_item['YYYYMMDD'])[6:8]),
                                                              datetime_item['HH']-1,
                                                              0,
                                                              0
                                      )}
                                    )
        
        # Do a 2D linear regression for each metric we are interested in
        for metric in metrics:        
            if df_subset[metric].dropna().shape[0] > (N-1):
                df_result_row[metric] = _fit_metric(df_subset.loc[~df_subset[metric].isna()].head(N), lon, lat, metric)
     
        df_result = pd.concat([df_result, df_result_row])

    # Final fixes
    if 'N' in df_result.columns:
        df_result.loc[df_result['N'] < 0, 'N'] = 0        
        df_result.loc[df_result['N'] > 9, 'N'] = 9      
    return df_result

def get_local_weather(starttime:datetime, endtime:datetime, lat:float, lon:float, 
                      N_stations:int=3, metrics:list = ['T', 'FH', 'DD', 'Q', 'DR', 'RH', 'U', 'N']) -> pd.DataFrame:
    """Get the localized hourly weather from the dutch KNMI website for a particular timeframe.
       
       Currently supports times starting as of 2010

       Timestamp represents the start of a particular hour. E.g. 14:00 represents 14:00-15:00

       Parameters
       ----------
       starttime : datetime object which represents the starting time
       endtime : datetime object which represents the ending time (inclusive)
       lat : target latitude
       lon : target longitude
       N_stations : number of stations to extrapolate the weather from, defaults to 3
       metrics : list of metrics to extrapolate"""

    # Get the nearest stations in the dataset
    df_closest_stations = _get_closest_stations(lon, lat, N=(N_stations*2))
    
    # Download the historic data for those stations
    df_combined = _get_all_station_weather(df_closest_stations, metrics)
    
    # Filter the dataset based on the supplied ranges
    df_combined = df_combined.loc[(df_combined['YYYYMMDD'] >= int(starttime.astimezone(pytz.timezone('UTC')).strftime('%Y%m%d'))) & \
                                    (df_combined['YYYYMMDD'] <= int(endtime.astimezone(pytz.timezone('UTC')).strftime('%Y%m%d')))]
    
    # Required to ensure all columns exist (when no data is available, these would drop)
    df_template = pd.DataFrame(columns=metrics) 

    # Localize the data
    df_local_weather = _calculate_locate_weather(df_combined, df_closest_stations, lon, lat, metrics=metrics, N=N_stations).set_index('datetime')
    df_result = pd.concat([df_template, df_local_weather])[metrics].tz_localize('UTC').tz_convert('Europe/Amsterdam')

    # return as timezone aware dataframe
    return df_result[starttime:endtime]