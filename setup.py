from setuptools import setup

setup(name='historicdutchweather',
      version='0.1',
      description='Download the hourly historic weather from the dutch weather agency KNMI and localize the data to a particular lon/lat',
      url='https://github.com/stephanpcpeters/HourlyHistoricWeather',
      author='Stephan Peters',
      author_email='s.p.c.peters@gmail.com',
      license='MIT',
      packages=['historicdutchweather'],
      zip_safe=False)