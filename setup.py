from setuptools import setup

setup(name='historicdutchweather',
        version='1.0',
        description='Download the hourly historic weather from the dutch weather agency KNMI and localize the data to a particular lon/lat',
        url='https://github.com/stephanpcpeters/HourlyHistoricWeather',
        project_urls={
            "Bug Tracker": "https://github.com/stephanpcpeters/HourlyHistoricWeather/issues",
        },
        author='Stephan Peters',
        author_email='s.p.c.peters@gmail.com',
        license='MIT',
        packages=['historicdutchweather'],
        install_requires=[
            'pandas',
            'numpy',
            'tqdm',
            'scipy'
        ],
        classifiers=[
            "Programming Language :: Python :: 3",
            "License :: OSI Approved :: MIT License",
            "Operating System :: OS Independent",
        ],
        python_requires=">=3.6",
        zip_safe=False)