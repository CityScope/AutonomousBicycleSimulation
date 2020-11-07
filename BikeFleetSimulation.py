#MAIN
# This is the beginning of the code

#LIBRARIES
import simpy #For sequential coding
import random 
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from Router import Network
import time

#PARAMETERS/CONFIGURATION
mode=2 # 0 for StationBased / 1 for Dockless / 2 for Autonomous
n_bikes= 300

WALK_RADIUS = 3500 #Just to try the dockless mode !
MAX_AUTONOMOUS_RADIUS= 3000
WALKING_SPEED= 5/3.6 #m/s
RIDING_SPEED = 15/3.6 #m/s
AUT_DRIVING_SPEED = 10/3.6 #m/s
BATTERY_CONSUMPTION_METER= 0.1 #Just a random number for now
MIN_BATTERY_LEVEL= 25
CHARGING_SPEED= 100/(0.0005*3600) #%/second  (This is 5h for 100% charge)
#map

network=Network()

# station information
stations_data=pd.read_excel('bluebikes_stations.xlsx', index_col=None)
stations_data.drop([83],inplace=True) #This station has 0 docks
stations_data.reset_index(drop=True, inplace=True) #reset index

#charging station info -> For the moment, same than docking stations
charging_stations_data=pd.read_excel('bluebikes_stations.xlsx', index_col=None)
charging_stations_data.drop([83],inplace=True) #This station has 0 docks
charging_stations_data.reset_index(drop=True, inplace=True) #reset index
#bike information
bikes_data = [] 

if mode==1 or mode==2:
    #For dockless and autonomous the initial location is the lat,lon of a random station (placeholder)
    i=0
    while i<n_bikes: 
        rand_station=random.randint(0,len(stations_data)-1)
        lat=stations_data.iloc[rand_station]['Latitude']
        lon=stations_data.iloc[rand_station]['Longitude']
        bike=[i,lat,lon] 
        bikes_data.append(bike) 
        i+=1
elif mode==0:
    #For station based the initial location is defined by the id of a random station (placeholder)
    i=0
    while i<n_bikes:
        #We can only set to len(stations_data)-1 because length is 340 but the last station is the 339 (First row + deleted station)
        bike_station_id=random.randint(0,len(stations_data)-1)  #Warning! This does not check if the station is full     
        bike=[i,bike_station_id]    
        bikes_data.append(bike)
        i+=1

#Loads info from ODmatrix
OD_df=pd.read_excel('output_sample.xlsx')


#DEFINITION OF CLASSES

class SimulationEngine: #Initialization and loading of data

    def __init__(self, env, stations_data, OD_data, bikes_data, charging_stations_data, datainterface, demandmanager): 
            self.env = env 
            self.stations_data=stations_data
            self.charging_stations_data=charging_stations_data
            self.od_data=OD_data
            self.bikes_data=bikes_data

            self.stations = [] 
            self.charging_stations =[]
            self.bikes = []
            self.users = []

            self.datainterface=datainterface 
            self.demandmanager=demandmanager
            #self.chargemanager=chargemanager

            self.start() 

    def start(self): 
            self.init_stations()
            self.init_charging_stations()
            self.init_bikes()
            self.init_users()
            self.init_managers()

    def init_stations(self):
        #Generate and configure stations
            for station_id, station_data in self.stations_data.iterrows(): 
                station = Station(self.env, station_id)  
                station.set_capacity(station_data['Total docks']) 
                station.set_location(station_data['Latitude'], station_data['Longitude'])
                self.stations.append(station) 

    def init_charging_stations(self):
        #Generate and configure stations
            for station_id, station_data in self.charging_stations_data.iterrows(): 
                charging_station = ChargingStation(self.env, station_id)  
                charging_station.set_capacity(station_data['Total docks']) 
                charging_station.set_location(station_data['Latitude'], station_data['Longitude'])
                self.charging_stations.append(charging_station)

    def init_bikes(self):
            #Generate and configure bikes
            for bike_id, bike_data in enumerate(self.bikes_data): 
                if mode == 0: #Station Based
                    bike = StationBike(self.env, bike_id) 
                    station_id = bike_data[1] #station id
                    self.stations[station_id].attach_bike(bike_id) #saves the bike in the station
                    bike.attach_station(station_id)  #saves the station in the bike
                    bike.set_location(self.stations[station_id].location[0],self.stations[station_id].location[1])  
                elif mode == 1: #Dockless
                    bike = DocklessBike(self.env, bike_id) 
                    bike.set_location(bike_data[1], bike_data[2])  #lat, lon
                elif mode == 2: #Autonomous
                    bike = AutonomousBike(self.env, bike_id,datainterface) 
                    bike.set_location(bike_data[1], bike_data[2]) #lat, lon
                self.bikes.append(bike) 

    def init_users(self):
            #Generate and configure users
            for index,row in self.od_data.iterrows(): 
                origin=[]
                destination=[]
                origin.append(row['start station latitude']) #origin lat
                origin.append(row['start station longitude']) #origin lon
                origin_np=np.array(origin)
                destination.append(row['end station latitude']) #destination lat
                destination.append(row['end station longitude']) #destination lon
                destination_np=np.array(destination)
                departure_time=row['elapsed time'] #departure time
                if mode == 0:
                    user = StationBasedUser(self.env, index, origin_np, destination_np, departure_time, datainterface)
                elif mode == 1:
                    user = DocklessUser(self.env, index, origin_np, destination_np, departure_time, datainterface)
                elif mode == 2:
                    user = AutonomousUser(self.env, index, origin_np, destination_np, departure_time, datainterface, demandmanager)
                user.start()   
                self.users.append(user) 
    def init_managers(self):
        self.datainterface.set_data(self.stations,self.charging_stations, self.bikes)
        self.demandmanager.set_data(self.bikes)
        #self.chargemanager.set_data(self.bikes)
        #self.chargemanager.start()
        

class Bike:
    def __init__(self,env, bike_id):
        self.env=env
        self.bike_id=bike_id
        self.location=None
        self.user=None
        self.busy=False #reserved, driving autonomously, in use...

    def set_location(self, lat, lon):
        self.location = np.array([lat,lon])
    
    def update_user(self,user_id):
        self.user = user_id

    def delete_user(self):
        self.user = None

    def vacant(self):
        if (self.user is None):
            return True

    def ride(self,destination):
        distance = self.dist(self.location, destination)
        time=distance/RIDING_SPEED
        yield self.env.timeout(time)
        self.location = destination

    def dist(self, a, b):
        route=network.get_route(a[1], a[0], b[1], b[0])
        d=route['cum_distances'][-1]
        return d
             
class StationBike(Bike):
    def __init__(self,env,bike_id):
        super().__init__(env, bike_id)  
        self.station_id = None

    def attach_station(self, station_id):
        self.station_id = station_id

    def detach_station(self):
        self.station_id = None

    def register_unlock(self, user_id):
        self.update_user(user_id)
        self.detach_station()
        self.busy=True

    def register_lock(self, station_id):
        self.delete_user()
        self.attach_station(station_id)
        self.busy=False
    
    def docked(self):
        return self.station_id is not None

class DocklessBike(Bike):
    def __init__(self, env, bike_id):
        super().__init__(env, bike_id)        

    def unlock(self, user_id):
        self.update_user(user_id)
        self.busy=True

    def lock(self):
        self.delete_user()
        self.busy=False

class AutonomousBike(Bike):
    def __init__(self,env, bike_id,datainterface):
        super().__init__(env, bike_id)
        self.datainterface=datainterface
        self.battery= 26 #We will assume that all the bikes start with a full charge
        self.charging_station_id = None
        self.visited_stations=[]

    def go_towards(self, destination_location): #This is for the demand prediction -> maybe it's enugh with autonomous_drive()  
        distance = self.dist(self.location, destination_location) 
        time=distance/AUT_DRIVING_SPEED
        yield self.env.timeout(time)
        self.location = destination_location

    def autonomous_drive(self, user_location):
        print('[%.2f] Bike %d driving autonomously from [%.4f, %.4f] to location [%.4f, %.4f]' % (self.env.now, self.bike_id, self.location[0], self.location[1], user_location[0], user_location[1]))
        distance = self.dist(self.location, user_location)
        time=distance/AUT_DRIVING_SPEED
        yield self.env.timeout(time)
        self.location =user_location
        self.battery= self.battery-distance*BATTERY_CONSUMPTION_METER
        print('[%.2f] Battery level of bike %d: %.2f' % (self.env.now, self.bike_id,self.battery))
        print('[%.2f] Bike %d drove autonomously from [%.4f, %.4f] to location [%.4f, %.4f]' % (self.env.now, self.bike_id, self.location[0], self.location[1], user_location[0], user_location[1]))

    def drop(self):
        self.delete_user()
        self.busy=False

    def unlock(self, user_id):
        self.update_user(user_id)
        self.busy=True
        
    def autonomous_charge(self): #Triggered when battery is below a certain SOC
        print('autonomous_charge')
        self.env.process(self.process())   

    def process(self):

        print('[%.2f] Bike %d needs to recharge. Battery level:  %.2f' % (self.env.now, self.bike_id,self.battery))
        #Set bike as busy
        self.busy=True
        self.event_interact_chargingstation = self.env.event()

        while not self.event_interact_chargingstation.triggered:
            #Select charging station
            [station,station_location,visited_stations]=self.select_charging_station(self.location,self.visited_stations)
            self.charging_station_id=station

            if self.charging_station_id is None:
                continue #Will try again

            print('[%.2f] Bike %d going to station %d for recharge' % (self.env.now, self.bike_id, self.charging_station_id))

            #Drive autonomously to station
            yield self.env.process(self.autonomous_drive(station_location))

            #Lock in station
            yield self.env.process(self.interact_charging_station(action='lock'))

            charging_start_time=self.env.now
        print('[%.2f] Bike %d started recharging' % (self.env.now, self.bike_id))
        self.event_interact_chargingstation=self.env.event()

        #wait until it charges
        yield self.env.process(self.charging())  

        #Leave station (unlock and not busy)
        yield self.env.process(self.interact_charging_station(action='unlock'))

        #Bike is free for use again
        self.busy=False
        print('[%.2f] Bike %d is charged and available again' % (self.env.now, self.bike_id))

    def select_charging_station(self, location, visited_stations):
        selected_station_info=self.datainterface.select_charging_station(location,visited_stations) 
        return selected_station_info

    def interact_charging_station(self,action):
        charging_station_id=self.charging_station_id
        if action=='lock':
            #check if there are available bikes
            valid = self.datainterface.charging_station_has_space(charging_station_id)
            if valid:
                self.datainterface.charging_station_attach_bike(charging_station_id,self.bike_id)
                self.event_interact_chargingstation.succeed()
            else:
                print('[%.2f] Charging station %d had zero spaces available at arrival' %
                (self.env.now, self.station_id))
        else: #unlock
            self.datainterface.charging_station_detach_bike(charging_station_id,self.bike_id)
            self.event_interact_chargingstation.succeed()
        
        yield self.env.timeout(1)

    def charging(self):
        charging_time=(100-self.battery)/CHARGING_SPEED
        yield self.env.timeout(charging_time)
        self.battery=100

class Station:
    def __init__(self,env,station_id):
        self.env=env
        self.station_id=station_id
        self.location = None
        self.capacity = 0
        self.n_bikes= 0

        self.bikes = []

    def set_location(self, lat, lon):
        self.location = np.array([lat,lon])

    def set_capacity(self, capacity):
        self.capacity = capacity
   
    def has_bikes(self):
        return self.n_bikes > 0

    def has_docks(self):
        return self.capacity - self.n_bikes > 0

    def empty(self):
        return self.n_bikes == 0

    def full(self):
        return self.n_bikes == self.capacity
    
    def choose_bike(self):  # Selects any bike 
        return random.choice(self.bikes)

    def attach_bike(self, bike_id): #What hapens if no docks?
        if self.has_docks(): 
            self.n_bikes+=1 
            self.bikes.append(bike_id) 
        else:
            print('[%.2f] Station %d has no docks available' %
              (self.env.now, self.station_id))

    def detach_bike(self): #What hapens if no bikes?
        if self.has_bikes(): 
            self.n_bikes-=1 
            bike_id=random.choice(self.bikes) 
            self.bikes.remove(bike_id) 
        else:
            print('[%.2f] Station %d has no bikes available' %
              (self.env.now, self.station_id))
class ChargingStation:
    def __init__(self,env,station_id):
        self.env=env
        self.station_id=station_id
        self.location = None
        self.capacity = 0
        self.n_bikes= 0

        self.bikes = []

    def set_location(self, lat, lon):
        self.location = np.array([lat,lon])

    def set_capacity(self, capacity):
        self.capacity = capacity

    def has_space(self):
        return self.capacity - self.n_bikes > 0

    def attach_bike(self, bike_id): #What hapens if no docks?
        if self.has_space(): 
            self.n_bikes+=1 
            self.bikes.append(bike_id) 
        else:
            print('[%.2f] Charging station %d has no spaces available' %
              (self.env.now, self.station_id))

    def detach_bike(self, bike_id): 
        self.n_bikes-=1 
        self.bikes.remove(bike_id) 

class User:
    def __init__(self,env,user_id, origin, destination, departure_time):
        self.env=env
        self.user_id=user_id
        self.location= None
        self.state=None #None, walking,waiting,biking ..> Not used for now
        self.event_setup_task = self.env.event() # ?¿ Here or in a start() function
        self.bike_id=None

        self.origin=origin
        self.destination=destination
        self.departure_time=departure_time
    
    def process(self):

        # 1-Init on origin
        yield self.env.process(self.init_user())

    def init_user(self):
        #waits until its the hour to initialize user
        yield self.env.timeout(self.departure_time) 
        self.location = self.origin
        print('[%.2f] User %d initialized at location [%.4f, %.4f]' % (self.env.now, self.user_id, self.location[0], self.location[1]))
                  
    def walk_to(self, location):
        distance = self.dist(self.location, location)
        time=distance/WALKING_SPEED
        yield self.env.timeout(time)
        print('[%.2f] User %d walked from [%.4f, %.4f] to location [%.4f, %.4f]' % (self.env.now, self.user_id, self.location[0], self.location[1], location[0], location[1]))
        self.location = location

    def ride_bike_to(self, location):
        bike_id=self.bike_id
        print('[%.2f] User %d biking from [%.4f, %.4f] to location [%.4f, %.4f]' % (self.env.now, self.user_id, self.location[0], self.location[1], location[0], location[1]))
        yield self.env.process(self.datainterface.bike_ride(bike_id, location)) 
        self.location = location
        
    
    def dist(self, a, b):
        route=network.get_route(a[1], a[0], b[1], b[0]) #Warning! In routing is lon,lat instead of lat,lon
        d=route['cum_distances'][-1] #The cumulative distance is saved in thsi colum so we only need the last item
        return d

class StationBasedUser(User):
    def __init__(self, env, user_id, origin, destination, departure_time, datainterface):
        super().__init__(env, user_id, origin, destination, departure_time)
        self.datainterface=datainterface

    def start(self):   
        self.station_id = None
        self.event_select_station = self.env.event()
        self.event_interact_bike = self.env.event()
        self.visited_stations = []

        self.env.process(self.process())

    def process(self):
        # 0-Setup
        # 1-Init on origin

        yield self.env.process(super().process())
        
        self.event_interact_bike = self.env.event() 
        while not self.event_interact_bike.triggered:

            # 2-Select origin station
            [station, station_location, visited_stations]=self.select_start_station(self.location,self.visited_stations)
            self.station_id=station

            if self.station_id is None:
                print('[%.2f] User %d  will not make the trip' % (self.env.now, self.user_id))
                return

            print('[%.2f] User %d selected start station [%.4f, %.4f]' % (self.env.now, self.user_id, station_location[0],station_location[1]))


            # 3-Walk to origin station
            yield self.env.process(self.walk_to(station_location))

            # 4-unlock bike
            yield self.env.process(self.interact_bike(action='unlock'))
            
        self.event_interact_bike = self.env.event()
        visited_stations.clear() #here we should zero it because one might do a round trip
        
        while not self.event_interact_bike.triggered:
            # 5-Select destination station
            [station, station_location, visited_stations]=self.select_end_station(self.destination,self.visited_stations)

            print('[%.2f] User %d selected end station %d' % (self.env.now, self.user_id, self.station_id))

            # 6-Ride bike
            yield self.env.process(self.ride_bike_to(station_location))

            # 7-lock bike
            yield self.env.process(self.interact_bike(action='lock'))

        # 8-Walk to destination
        yield self.env.process(self.walk_to(self.destination))
    
        # 9-Save state
        # self.save_state()

        # # 10-Finish
        yield self.env.timeout(10)
        print('[%.2f] User %d arrived to final destination' % (self.env.now, self.user_id))
    
    def select_start_station(self,location,visited_stations):
        selected_station_info=self.datainterface.select_start_station(location,visited_stations)
        return selected_station_info

    def select_end_station(self,destination,visited_stations):
        selected_station_info=self.datainterface.select_end_station(destination,visited_stations)
        return selected_station_info


    def interact_bike(self, action):
        station_id=self.station_id
        
        #Check if there are still bikes(unlock)/docks(lock) at arrival
        if action=='unlock':
            valid=self.datainterface.station_has_bikes(station_id)
        else: #lock
            valid=self.datainterface.station_has_docks(station_id)
    
        if valid:
            if action == 'unlock':
                self.bike_id = self.datainterface.station_choose_bike(station_id)
                bike_id=self.bike_id
                self.datainterface.bike_register_unlock(bike_id, self.user_id)
                self.datainterface.station_detach_bike(station_id)
            else: #lock
                bike_id=self.bike_id
                self.datainterface.bike_register_lock(bike_id, self.user_id)
                self.datainterface.station_attach_bike(station_id, self.bike_id)

            self.event_interact_bike.succeed()

            yield self.env.timeout(1)

        else: 
            print('[%.2f] Station %d had zero %s available at arrival' %
                       (self.env.now, self.station_id, 'bikes' if action == 'unlock' else 'docks'))
             
class DocklessUser(User):
    def __init__(self, env, user_id, origin, destination, departure_time, datainterface):
        super().__init__(env, user_id, origin, destination, departure_time)
        self.datainterface=datainterface
    def start(self):
        self.event_select_dockless_bike = self.env.event()
        self.event_unlock_bike = self.env.event()

        self.env.process(self.process())

    def process(self):
        # 0-Setup
        # 1-Init on origin
        yield self.env.process(super().process())

        while not self.event_unlock_bike.triggered:

            # 2-Select dockless bike
            [dockless_bike_id,dockless_bike_location]=self.select_dockless_bike(self.location)
            self.bike_id=dockless_bike_id

            if dockless_bike_id is None:
                print('[%.2f] User %d  will not make the trip' % (self.env.now, self.user_id))
                return

            print('[%.2f] User %d selected dockless bike %d' % (self.env.now, self.user_id, dockless_bike_id))

            # 3-Walk to dockless bike
            yield self.env.process(self.walk_to(dockless_bike_location))

            # 4-Unlock bike
            yield self.env.process(self.unlock_bike())

        # 5-Ride bike
        yield self.env.process(self.ride_bike_to(self.destination))

        # 6-Drop bike
        self.lock_bike()

        # 7-Save state
        #self.save_state()

        # # 8-Finish
        yield self.env.timeout(10)
        print('[%.2f] User %d arrived to final destination' % (self.env.now, self.user_id))
           
    def select_dockless_bike(self,location):

        selected_bike_info=self.datainterface.select_dockless_bike(location)
        return selected_bike_info

    def unlock_bike(self):
        dockless_bike_id=self.bike_id
        if not self.datainterface.dockless_bike_busy(dockless_bike_id):
            #yield self.env.timeout(1)
            self.bike_id = dockless_bike_id
            self.datainterface.dockless_bike_unlock(dockless_bike_id, self.user_id)
            self.event_unlock_bike.succeed()
        else:
            #yield self.env.timeout(3)
            print('[%.2f] User %d -> Bike %d has already been rented. Looking for another one.' % (self.env.now, self.user_id,dockless_bike_id))

    def lock_bike(self):
        dockless_bike_id=self.bike_id
        self.datainterface.dockless_bike_lock(dockless_bike_id)

class AutonomousUser(User):
    def __init__(self, env, user_id, origin, destination, departure_time, datainterface, demandmanager):
        super().__init__(env, user_id, origin, destination, departure_time)
        self.demandmanager=demandmanager
        self.datainterface=datainterface

    def start(self):
        self.event_call_autonomous_bike = self.env.event()
        self.env.process(self.process())

    def process(self):
        # 0-Setup
        # 1-Init on origin
        yield self.env.process(super().process())

        # 2-Call autonomous bike
        [autonomous_bike_id,autonomous_bike_location]=self.call_autonomous_bike(self.location)
        self.bike_id=autonomous_bike_id

        if self.bike_id is None:
            print('[%.2f] User %d  will not make the trip' % (self.env.now, self.user_id))
            return

        print('[%.2f] User %d was assigned the autonomous bike %d' % (self.env.now, self.user_id, autonomous_bike_id))
       

        # 3-Wait for autonomous bike
        yield self.env.process(self.drive_autonomously())
        self.datainterface.unlock_autonomous_bike(self.bike_id,self.user_id)

        # 4-Ride bike
        yield self.env.process(self.ride_bike_to(self.destination))

        # 5-Drop bike
        self.drop_bike()
        print('[%.2f] User %d dropped the autonomous bike %d at the destination [%.4f, %.4f]' % (self.env.now, self.user_id, autonomous_bike_id, self.location[0],self.location[1]))

        # 6-Save state
        #self.save_state()

        # 7-Finish
        yield self.env.timeout(10)
        print('[%.2f] User %d arrived to final destination' % (self.env.now, self.user_id))

    def drive_autonomously(self):
        yield self.env.process(self.datainterface.autonomous_bike_drive(self.bike_id, self.location))

    def call_autonomous_bike(self, location):  
        assigned_bike_info=self.demandmanager.assign_autonomous_bike(location)
        return assigned_bike_info

    def drop_bike(self):
        #bike = self.bikes[self.bike_id]
        bike_id=self.bike_id
        self.datainterface.bike_drop(bike_id)

class Assets: #Put inside of City
    #location of bikes, situaition of stations
    #it is updated by user trips and the FleetManager
    def __init__(self,env):
        self.env=env

class DataInterface:

    def __init__(self,env):
        self.env=env

    def set_data(self, stations, charging_stations, bikes):
        self.stations = stations
        self.bikes = bikes
        self.charging_stations= charging_stations

    def dist(self, a, b):
        route=network.get_route(a[1], a[0], b[1], b[0])
        d=route['cum_distances'][-1]
        return d
      
    def select_start_station(self,location,visited_stations):
        values = []
        for station in self.stations:
            station_id = station.station_id
            has_bikes = station.has_bikes()
            visited = station_id in visited_stations
            distance = self.dist(location, station.location) 
            walkable = distance < WALK_RADIUS
            lat=station.location[0]
            lon=station.location[1]
            values.append((station_id, has_bikes,
                           visited, distance, walkable, lat, lon))
        labels = ['station_id', 'has_bikes',
                  'visited', 'distance', 'walkable', 'lat','lon']
        types = [int, int,
                 int, float, int, float, float]
        dtype = list(zip(labels, types))
        station_info = np.array(values, dtype=dtype)

        select_succeeded = 0

        for e in np.sort(station_info, order='distance'):
            valid = e['has_bikes'] and not e['visited'] and e['walkable']
            if valid:
                station_id = e['station_id']
                lat=e['lat']
                lon=e['lon']
                visited_stations.append(station_id)
                select_succeeded = 1  
                station_location=np.array([lat,lon]) 
                break         
  
        if select_succeeded == 0: 
            print('[%.2f] No bikes fount in a walkable distance' %
              (self.env.now))
            station_id=None
            station_location=None

        return [station_id, station_location, visited_stations] 

    def select_end_station(self,destination,visited_stations):
        values = []
        for station in self.stations:
            station_id = station.station_id
            has_docks = station.has_docks()
            visited = station_id in visited_stations
            distance = self.dist(destination, station.location) 
            walkable = distance < WALK_RADIUS # ---> Once that ou're in the bike you have to leav eit even if it's very far
            lat=station.location[0]
            lon=station.location[1]
            values.append((station_id, has_docks,
                           visited, distance, lat, lon))
        labels = ['station_id', 'has_docks',
                  'visited', 'distance', 'walkable','lat','lon']
        types = [int, int, 
                 int, float,int, float, float]
        dtype = list(zip(labels, types))
        station_info = np.array(values, dtype=dtype)

        select_succeeded = 0

        for e in np.sort(station_info, order='distance'):
            valid = e['has_docks'] and not e['visited'] 
            if valid:
                station_id = e['station_id']
                lat=e['lat']
                lon=e['lon']
                visited_stations.append(station_id)
                select_succeeded = 1
                if not e['walkable']:
                    print('[%.2f] (Note) The station slected is located ot of a walkable distance from the destination' %
                    (self.env.now))
                break        
                
        station_location=np.array([lat,lon])
        return [station_id,station_location,visited_stations]

    def select_dockless_bike(self,location):

        values = []

        for bike in self.bikes:
            if isinstance(bike, DocklessBike):
                bike_id = bike.bike_id
                busy = bike.busy
                distance = self.dist(location, bike.location)
                walkable = distance < WALK_RADIUS
                lat=bike.location[0]
                lon=bike.location[1]
                values.append((bike_id, busy, distance, walkable,lat,lon))
        labels = ['bike_id', 'busy', 'distance', 'walkable','lat','lon']
        types = [int, int, float, int,float,float]
        dtype = list(zip(labels, types))
        bike_info = np.array(values, dtype=dtype)

        select_dockless_bike_succeeded = 0

        for e in np.sort(bike_info, order='distance'):
            valid = not e['busy'] and e['walkable']
            if valid:
                dockless_bike_id = e['bike_id']
                lat=e['lat']
                lon=e['lon']
                select_dockless_bike_succeeded = 1
                bike_location=np.array([lat,lon])
                break

        if select_dockless_bike_succeeded == 0:
            print('[%.2f] No bikes in walkable distance' %
              (self.env.now))
            dockless_bike_id=None
            bike_location=None

        return [dockless_bike_id,bike_location]

    def select_charging_station(self,location,visited_stations):
        values = []
        for station in self.charging_stations:
            station_id = station.station_id
            has_space = station.has_space()
            visited = station_id in visited_stations
            distance = self.dist(location, station.location) 
            lat=station.location[0]
            lon=station.location[1]
            values.append((station_id, has_space,
                           visited, distance,  lat, lon))
        labels = ['station_id', 'has_space',
                  'visited', 'distance', 'lat','lon'] 
        types = [int, int,
                 int, float, float, float] 
        dtype = list(zip(labels, types))
        station_info = np.array(values, dtype=dtype)

        select_succeeded = 0

        for e in np.sort(station_info, order='distance'):
            valid = e['has_space'] and not e['visited']  
            if valid:
                station_id = e['station_id']
                lat=e['lat']
                lon=e['lon']
                visited_stations.append(station_id)
                select_succeeded = 1  
                station_location=np.array([lat,lon]) 
                break         
  
        if select_succeeded == 0: 
            print('[%.2f] No charging stations with available space that have not been visited yet' %
              (self.env.now))
            station_id=None
            station_location=None

        return [station_id, station_location, visited_stations]

    def bike_ride(self, bike_id, location):
        bike=self.bikes[bike_id]
        yield self.env.process(bike.ride(location))
    def autonomous_bike_drive(self, bike_id, location):
        bike=self.bikes[bike_id]
        yield self.env.process(bike.autonomous_drive(location))

    def station_has_bikes(self, station_id):
        station=self.stations[station_id]
        valid=station.has_bikes()
        return valid  
    def station_has_docks(self, station_id):
        station=self.stations[station_id]
        valid=station.has_docks()
        return valid  
    
    def charging_station_has_space(self,station_id):
        station=self.charging_stations[station_id]
        valid=station.has_space()
        return valid
    def station_choose_bike(self, station_id):
        station=self.stations[station_id]
        bike_id=station.choose_bike()
        return bike_id
    
    def station_attach_bike(self, station_id, bike_id):
        station=self.stations[station_id]
        station.attach_bike(bike_id)
    def station_detach_bike(self, station_id):
        station=self.stations[station_id]
        station.detach_bike()
    
    def charging_station_attach_bike(self,charging_station_id,bike_id):
        station=self.charging_stations[charging_station_id]
        station.attach_bike(bike_id)

    def charging_station_detach_bike(self,charging_station_id,bike_id):
        station=self.charging_stations[charging_station_id]
        station.detach_bike(bike_id)
    
    def bike_register_unlock(self, bike_id, user_id):
        bike=self.bikes[bike_id]
        bike.register_unlock(user_id)
    def bike_register_lock(self, bike_id, user_id):
        bike=self.bikes[bike_id]
        bike.register_lock(user_id)

    def dockless_bike_busy(self,dockless_bike_id):
        bike=self.bikes[dockless_bike_id]
        busy=bike.busy
        return busy
    def dockless_bike_unlock(self, dockless_bike_id, user_id):
        bike=self.bikes[dockless_bike_id]
        bike.unlock(user_id)
    def dockless_bike_lock(self,dockless_bike_id):
        bike=self.bikes[dockless_bike_id]
        bike.lock()

    def unlock_autonomous_bike(self, bike_id,user_id):
        bike=self.bikes[bike_id]
        bike.unlock(user_id)
    def bike_drop(self,bike_id):
        bike=self.bikes[bike_id]
        bike.drop()
class RebalancingManager:
    #makes rebalancing decisions for SB and dockless
    def __init__(self,env):
        self.env=env
class DemandPredictionManager:
    #predictive rebalancing for autonomous
    def __init__(self,env):
        self.env=env
# class ChargeManager:
#     #makes recharging decisions
#     def __init__(self,env):
#         self.env=env

#     def set_data(self, bikes):
#         self.bikes = bikes
#     def start(self):
#         print('stating charge manager')
#         self.env.process(self.battery_checking())
        
#     def battery_checking(self):
#         print('started checking batteries')
#         while True:
#             for bike in self.bikes:
#                 if bike.battery < MIN_BATTERY_LEVEL:
#                     bike.autonomous_charge()
            
class DemandManager:
    #receives orders from users and decides which bike goes
    def __init__(self,env):
        self.env=env
    
    def set_data(self, bikes):
        self.bikes = bikes

    def dist(self, a, b):
        route=network.get_route(a[1], a[0], b[1], b[0])
        d=route['cum_distances'][-1]
        return d
      

    def assign_autonomous_bike(self, location):
        values = []

        for bike in self.bikes:
            if isinstance(bike, AutonomousBike):
                bike_id = bike.bike_id
                busy = bike.busy
                distance = self.dist(location, bike.location)
                reachable = distance < MAX_AUTONOMOUS_RADIUS
                battery= bike.battery > MIN_BATTERY_LEVEL
                if battery == False and busy == False: #Otherwise it could be already on the way to chagring
                    bike.autonomous_charge()
                lat=bike.location[0]
                lon=bike.location[1]
                values.append((bike_id, busy, distance, reachable,battery, lat,lon))
        labels = ['bike_id', 'busy', 'distance', 'reachable', 'battery','lat','lon']
        types = [int, int, float, int, int, float,float]
        dtype = list(zip(labels, types))
        bike_info = np.array(values, dtype=dtype)

        select_autonomous_bike_succeeded = 0

        for e in np.sort(bike_info, order='distance'):
            valid = not e['busy'] and e['reachable'] and e[battery]
            if valid:
                autonomous_bike_id = e['bike_id']
                lat=e['lat']
                lon=e['lon']
                select_autonomous_bike_succeeded = 1
                bike_location=np.array([lat,lon])
                break

        if select_autonomous_bike_succeeded == 0:
            print("No autonomous bikes in "+ str(MAX_AUTONOMOUS_RADIUS) +" distance")
            autonomous_bike_id=None
            bike_location=None

        return [autonomous_bike_id,bike_location]

class FleetManager:
    #sends the decisions to the bikes
    #updates SystemStateData
    def __init__(self,env):
        self.env=env

#MAIN BODY - SIMULATION AND HISTORY GENERATION
env = simpy.Environment()
datainterface=DataInterface(env)
demandmanager=DemandManager(env)
#chargemanager=ChargeManager(env)
city = SimulationEngine(env, stations_data, OD_df, bikes_data, charging_stations_data, datainterface, demandmanager)
env.run(until=1000)