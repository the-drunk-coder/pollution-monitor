#!/usr/bin/env python3

import time
import colorsys
import sys
import ST7735
try:
    # Transitional fix for breaking change in LTR559
    from ltr559 import LTR559
    ltr559 = LTR559()
except ImportError:
    import ltr559

from bme280 import BME280
from pms5003 import PMS5003, ReadTimeoutError as pmsReadTimeoutError
from enviroplus import gas
from subprocess import PIPE, Popen
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from fonts.ttf import RobotoMedium as UserFont
import logging

logging.basicConfig(
    format='%(asctime)s.%(msecs)03d %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

logging.info("""all-in-one.py - Displays readings from all of Enviro plus' sensors

Press Ctrl+C to exit!

""")

# local database connection
import sqlite3
conn = sqlite3.connect("pollution_monitor.db")
c = conn.cursor()

# BME280 temperature/pressure/humidity sensor
bme280 = BME280()

# PMS5003 particulate sensor
pms5003 = PMS5003()

# Create ST7735 LCD display class
st7735 = ST7735.ST7735(
    port=0,
    cs=1,
    dc=9,
    backlight=12,
    rotation=270,
    spi_speed_hz=10000000
)

# Initialize display
st7735.begin()

WIDTH = st7735.width
HEIGHT = st7735.height

# Set up canvas and font
img = Image.new('RGB', (WIDTH, HEIGHT), color=(0, 0, 0))
draw = ImageDraw.Draw(img)
font_size = 20
font = ImageFont.truetype(UserFont, font_size)

message = ""

# The position of the top bar
top_pos = 25

# Displays data and text on the 0.96" LCD
def display_text(variable, data, unit):
    # Maintain length of list
    values[variable] = values[variable][1:] + [data]
    # Scale the values for the variable between 0 and 1
    vmin = min(values[variable])
    vmax = max(values[variable])
    colours = [(v - vmin + 1) / (vmax - vmin + 1) for v in values[variable]]
    # Format the variable name and value
    message = "{}: {:.1f} {}".format(variable[:4], data, unit)
    #logging.info(message)
    draw.rectangle((0, 0, WIDTH, HEIGHT), (255, 255, 255))
    for i in range(len(colours)):
        # Convert the values to colours from red to blue
        colour = (1.0 - colours[i]) * 0.6
        r, g, b = [int(x * 255.0) for x in colorsys.hsv_to_rgb(colour, 1.0, 1.0)]
        # Draw a 1-pixel wide rectangle of colour
        draw.rectangle((i, top_pos, i + 1, HEIGHT), (r, g, b))
        # Draw a line graph in black
        line_y = HEIGHT - (top_pos + (colours[i] * (HEIGHT - top_pos))) + top_pos
        draw.rectangle((i, line_y, i + 1, line_y + 1), (0, 0, 0))
    # Write the text at the top in black
    draw.text((0, 0), message, font=font, fill=(0, 0, 0))
    st7735.display(img)


# Get the temperature of the CPU for compensation
def get_cpu_temperature():
    process = Popen(['vcgencmd', 'measure_temp'], stdout=PIPE, universal_newlines=True)
    output, _error = process.communicate()
    return float(output[output.index('=') + 1:output.rindex("'")])


# Tuning factor for compensation. Decrease this number to adjust the
# temperature down, and increase to adjust up
factor = 2.25

cpu_temps = [get_cpu_temperature()] * 5

delay = 0.5  # Debounce the proximity tap
mode = 8     # The starting mode
last_page = 0
light = 1

# Create a values dict to store the data
variables = ["temperature",
             "pressure",
             "humidity",
             "light",
             "oxidised",
             "reduced",
             "nh3",
             "pm1",
             "pm25",
             "pm10"]

# this is mostly for the displayed history ...
values = {}

for v in variables:
    values[v] = [1] * WIDTH

# The main loop
try:
    while True:
        proximity = ltr559.get_proximity()
        #logging.info(proximity)
        # If the proximity crosses the threshold, toggle the mode
        if proximity > 100 and time.time() - last_page > delay:
            mode += 1
            mode %= len(variables)
            last_page = time.time()

        # get all available data

        #cpu temperature
        cpu_temp = get_cpu_temperature()
        # Smooth out with some averaging to decrease jitter
        cpu_temps = cpu_temps[1:] + [cpu_temp]
        avg_cpu_temp = sum(cpu_temps) / float(len(cpu_temps))
        raw_temp = bme280.get_temperature()

        temp_comp = raw_temp - ((avg_cpu_temp - raw_temp) / factor)
        pressure = bme280.get_pressure()
        humidity =  bme280.get_humidity()

        if proximity < 10:
            light = ltr559.get_lux()
        else:
            light = 1

        gas_all = gas.read_all()
        gas_ox = gas_all.oxidising / 1000
        gas_red = gas_all.reducing / 1000
        gas_nh3 = gas_all.nh3 / 1000

        try:
            data = pms5003.read()
        except pmsReadTimeoutError:
            logging.warning("Failed to read PMS5003")
        else:
            pm_1 = float(data.pm_ug_per_m3(1.0))
            pm_2p5 = float(data.pm_ug_per_m3(2.5))
            pm_10 = float(data.pm_ug_per_m3(10))

        c.execute("INSERT INTO environmental_data (temp,pressure,humidity,light,gas_ox,gas_red,gas_nh3,pm_1,pm_2p5,pm_10) VALUES (?,?,?,?,?,?,?,?,?,?)",
                  (temp_comp, pressure, humidity, light, gas_ox, gas_red, gas_nh3, pm_1, pm_2p5, pm_10))

        conn.commit()
            
        # Display modes - one mode for each variable
        if mode == 0: # temperature            
            unit = "C"    
            display_text(variables[mode], temp_comp, unit)

        if mode == 1: # pressure
            unit = "hPa"
            display_text(variables[mode], pressure, unit)

        if mode == 2: # humidity            
            unit = "%"            
            display_text(variables[mode], humidity, unit)

        if mode == 3: # light
            unit = "Lux"
            display_text(variables[mode], light, unit)

        if mode == 4: # gas ox
            unit = "kO"
            display_text(variables[mode], gas_ox, unit)

        if mode == 5: # gas red
            unit = "kO"            
            display_text(variables[mode], gas_red, unit)

        if mode == 6: # gas nh3
            unit = "kO"
            display_text(variables[mode], gas_nh3, unit)

        if mode == 7: # pm1            
            unit = "ug/m3"
            display_text(variables[mode], pm_1, unit)

        if mode == 8: # pm 2.5
            unit = "ug/m3"
            display_text(variables[mode], pm_2p5, unit)

        if mode == 9: # pm 10
            unit = "ug/m3"            
            display_text(variables[mode], pm_10, unit)

# Exit cleanly
except KeyboardInterrupt:
    sys.exit(0)
