# Import packages
import pandas as pd
import requests
import geopandas
from tqdm import tqdm

# Import Geocoder
from geopy.geocoders import ArcGIS
geolocator = ArcGIS()

# Read address information
a_df = pd.read_csv("./data/prepped/geospatial.csv").fillna("")

#Create lists to store response
lat = []
lon = []

#Create loop to cycle through addresses
for i in tqdm(range(len(a_df))):
    street = str(a_df.street[i])
    city = str(a_df.city[i])
    state = str(a_df.state[i])
    zipcode = str(a_df["zip"][i])
    address = street + ', ' + city + ', ' + state + ', ' + zipcode + ', USA'
    location = geolocator.geocode(address)
    lat.append(location.latitude)
    lon.append(location.longitude)

#Create new df of latitude and longitude
df2 = pd.DataFrame({'longitude_x' : lon, 'latitude_y' : lat})

#Concatenate dataframes
df_total = pd.concat([a_df, df2], axis = 1)
print(df_total.head())
df_total.to_csv("./geocoded.csv", index=False)

#Convert to geodata frame
df_total = geopandas.GeoDataFrame(
    df_total, 
    geometry=geopandas.points_from_xy(df_total.longitude_x, df_total.latitude_y), 
    crs="EPSG:4326",
)

#Read shape file
gdf = geopandas.read_file('./data/source/Cuyahoga_Land_Use_2014.shp')

#Ensure both dataframes are using the same reference
df_total.crs = gdf.crs

#Join data frames
j_df = df_total.sjoin(gdf, how = 'left')

#Determine if use class is residential or apartment
j_df['Is_RESIDENTIAL_or_APARTMENT'] = (j_df.USE_CLASS_ == 'RESIDENTIAL') |  (j_df.USE_CLASS_ == 'APARTMENT')

#Output only desired data
final_df = j_df[['ccmeo_case', 'Is_RESIDENTIAL_or_APARTMENT']]
print(final_df.head())

final_df.to_csv("./data/processed/residential.csv", index=False)