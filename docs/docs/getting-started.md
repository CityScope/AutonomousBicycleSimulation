---
sidebar_position: 2
---

# Getting Started

Before you start, you will need to download the code from our **[GitHub repo](https://github.com/CityScope/AutonomousMicroMobility)**. If you are new to GitHub, **[here's](http://rogerdudler.github.io/git-guide/)** a simple guide to get you started. To get our code run:

```shell
git clone https://github.com/NaroaCS/AutonomousBicycleSimulation.git
```

Make sure you have Python 3.6 or higher. To check your python version:

```shell
python3 --version
```

If you do not have Python 3, you can donwload it from  **[Python.org](https://www.python.org/downloads/)**. 

Finally, you will need some packages:

* simpy
* pandas
* numpy
* matplotlib
* networkx
* scipy==1.6.0
* geopandas
* scikit-learn
* pyproj
* tqdm
* tensorflow==1.15
* *git+git://github.com/imartinezl/pandana.git@master*

To install the packages you can use pip3, which comes already ingtegated with Python3. Eg:

```shell
pip3 install numpy
```

Alternatively, you can also use **[Anaconda](https://www.anaconda.com/)**, which can help you to handle packages and libraries. In that case, you would use conda to install the packages. Eg: 

```shell
conda install numpy
```

# The fast-track

1. Clone the git repository
2. You can then customize the inputs as desired:
    * To change the city you will need to obtain a shapefile containing the **[buildings](https://osmbuildings.org/)** and a graph containing the **[road network](https://overpass-turbo.eu/)**. 
    * You can customize the parameters in the configuration file *config.json*

3. Run the script:
* To run a single file, adapt ‘config.json’ to the desired parameters for each experiment and run ‘main.py’
* To run multiple experiments in a batch simulation, Specify the MODE (0=Station-based, 1=Dockless, 2= Autonomous) in Line 21 in ‘run.py’ and run it.

4. The run times will be printed at the end of the simulation and the results will be saved in the ‘results’ folder in a subfolder with the filename being the timestamp of the simulation launch time. This folder will contain the configuration file that was used to launch it and the two main output files: ‘user_trips.csv’ and ‘bike_trips.csv’.
