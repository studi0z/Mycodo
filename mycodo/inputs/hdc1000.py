# coding=utf-8
#
# Created in part from github.com/switchdoclabs/SDL_Pi_HDC1000
#
import array
import fcntl
import io
import logging
import time

from .base_input import AbstractInput
from .sensorutils import convert_units
from .sensorutils import dewpoint

# I2C Address
HDC1000_ADDRESS = 0x40  # 1000000

# Registers
HDC1000_TEMPERATURE_REGISTER = 0x00
HDC1000_HUMIDITY_REGISTER = 0x01
HDC1000_CONFIGURATION_REGISTER = 0x02
HDC1000_MANUFACTURERID_REGISTER = 0xFE
HDC1000_DEVICEID_REGISTER = 0xFF
HDC1000_SERIALIDHIGH_REGISTER = 0xFB
HDC1000_SERIALIDMID_REGISTER = 0xFC
HDC1000_SERIALIDBOTTOM_REGISTER = 0xFD

# Configuration Register Bits
HDC1000_CONFIG_RESET_BIT = 0x8000
HDC1000_CONFIG_HEATER_ENABLE = 0x2000
HDC1000_CONFIG_ACQUISITION_MODE = 0x1000
HDC1000_CONFIG_BATTERY_STATUS = 0x0800
HDC1000_CONFIG_TEMPERATURE_RESOLUTION = 0x0400
HDC1000_CONFIG_HUMIDITY_RESOLUTION_HBIT = 0x0200
HDC1000_CONFIG_HUMIDITY_RESOLUTION_LBIT = 0x0100

HDC1000_CONFIG_TEMPERATURE_RESOLUTION_14BIT = 0x0000
HDC1000_CONFIG_TEMPERATURE_RESOLUTION_11BIT = 0x0400

HDC1000_CONFIG_HUMIDITY_RESOLUTION_14BIT = 0x0000
HDC1000_CONFIG_HUMIDITY_RESOLUTION_11BIT = 0x0100
HDC1000_CONFIG_HUMIDITY_RESOLUTION_8BIT = 0x0200

I2C_SLAVE = 0x0703


class HDC1000Sensor(AbstractInput):
    """
    A sensor support class that measures the HDC1000's humidity and temperature
    and calculates the dew point

    """
    def __init__(self, input_dev, testing=False):
        super(HDC1000Sensor, self).__init__()
        self.logger = logging.getLogger("mycodo.inputs.hdc1000")
        self._dew_point = None
        self._humidity = None
        self._temperature = None

        self.resolution_temperature = input_dev.resolution
        self.resolution_humidity = input_dev.resolution_2

        if not testing:
            self.logger = logging.getLogger(
                "mycodo.inputs.hdc1000_{id}".format(id=input_dev.id))
            self.i2c_bus = input_dev.i2c_bus
            self.i2c_address = 0x40  # HDC1000-F Address
            self.convert_to_unit = input_dev.convert_to_unit

            self.HDC1000_fr = io.open("/dev/i2c-" + str(self.i2c_bus), "rb", buffering=0)
            self.HDC1000_fw = io.open("/dev/i2c-" + str(self.i2c_bus), "wb", buffering=0)

            # set device address
            fcntl.ioctl(self.HDC1000_fr, I2C_SLAVE, self.i2c_address)
            fcntl.ioctl(self.HDC1000_fw, I2C_SLAVE, self.i2c_address)
            time.sleep(0.015)  # 15ms startup time

            config = HDC1000_CONFIG_ACQUISITION_MODE

            s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
            s2 = bytearray(s)
            self.HDC1000_fw.write(s2)  # sending config register bytes
            time.sleep(0.015)  # From the data sheet

            # Set resolutions
            if self.resolution_temperature == 11:
                self.set_temperature_resolution(HDC1000_CONFIG_TEMPERATURE_RESOLUTION_11BIT)
            elif self.resolution_temperature == 14:
                self.set_temperature_resolution(HDC1000_CONFIG_TEMPERATURE_RESOLUTION_14BIT)

            if self.resolution_humidity == 8:
                self.set_humidity_resolution(HDC1000_CONFIG_HUMIDITY_RESOLUTION_8BIT)
            elif self.resolution_humidity == 11:
                self.set_humidity_resolution(HDC1000_CONFIG_HUMIDITY_RESOLUTION_11BIT)
            elif self.resolution_humidity == 14:
                self.set_humidity_resolution(HDC1000_CONFIG_HUMIDITY_RESOLUTION_14BIT)

    def __repr__(self):
        """  Representation of object """
        return "<{cls}(dewpoint={dpt})(humidity={hum})(temperature={temp})>".format(
            cls=type(self).__name__,
            dpt="{0:.2f}".format(self._dew_point),
            hum="{0:.2f}".format(self._humidity),
            temp="{0:.2f}".format(self._temperature))

    def __str__(self):
        """ Return measurement information """
        return "Dew Point: {dpt}, Humidity: {hum}, Temperature: {temp}".format(
            dpt="{0:.2f}".format(self._dew_point),
            hum="{0:.2f}".format(self._humidity),
            temp="{0:.2f}".format(self._temperature))

    def __iter__(self):  # must return an iterator
        """ HDC1000Sensor iterates through live measurement readings """
        return self

    def next(self):
        """ Get next measurement reading """
        if self.read():  # raised an error
            raise StopIteration  # required
        return dict(dewpoint=float('{0:.2f}'.format(self._dew_point)),
                    humidity=float('{0:.2f}'.format(self._humidity)),
                    temperature=float('{0:.2f}'.format(self._temperature)))

    @property
    def dew_point(self):
        """ HDC1000 dew point in Celsius """
        if self._dew_point is None:  # update if needed
            self.read()
        return self._dew_point

    @property
    def humidity(self):
        """ HDC1000 relative humidity in percent """
        if self._humidity is None:  # update if needed
            self.read()
        return self._humidity

    @property
    def temperature(self):
        """ HDC1000 temperature in Celsius """
        if self._temperature is None:  # update if needed
            self.read()
        return self._temperature

    def get_measurement(self):
        """ Gets the humidity and temperature """
        self._dew_point = None
        self._humidity = None
        self._temperature = None

        temperature = self.read_temperature()
        humidity = self.read_humidity()
        dew_pt = dewpoint(temperature, humidity)

        # Check for conversions
        dew_pt = convert_units(
            'dewpoint', 'celsius', self.convert_to_unit, dew_pt)
        temperature = convert_units(
            'temperature', 'celsius', self.convert_to_unit, temperature)

        return dew_pt, humidity, temperature

    def read(self):
        """
        Takes a reading from the HDC1000 and updates the self._humidity and
        self._temperature values

        :returns: None on success or 1 on error
        """
        try:
            (self._dew_point,
             self._humidity,
             self._temperature) = self.get_measurement()
            if self._dew_point is not None:
                return  # success - no errors
        except Exception as e:
            self.logger.exception(
                "{cls} raised an exception when taking a reading: "
                "{err}".format(cls=type(self).__name__, err=e))
        return 1

    def read_temperature(self):
        s = [HDC1000_TEMPERATURE_REGISTER]  # temp
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet

        data = self.HDC1000_fr.read(2)  # read 2 byte temperature data
        buf = array.array('B', data)
        # print ( "Temp: %f 0x%X %X" % (  ((((buf[0]<<8) + (buf[1]))/65536.0)*165.0 ) - 40.0   ,buf[0],buf[1] )  )

        # Convert the data
        temp = (buf[0] * 256) + buf[1]
        temp_c = (temp / 65536.0) * 165.0 - 40
        return temp_c

    def read_humidity(self):
        # Send humidity measurement command, 0x01(01)
        time.sleep(0.015)  # From the data sheet

        s = [HDC1000_HUMIDITY_REGISTER]  # hum
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet

        data = self.HDC1000_fr.read(2)  # read 2 byte humidity data
        buf = array.array('B', data)
        # print ( "Humidity: %f 0x%X %X " % (  ((((buf[0]<<8) + (buf[1]))/65536.0)*100.0 ),  buf[0], buf[1] ) )
        humidity = (buf[0] * 256) + buf[1]
        humidity = (humidity / 65536.0) * 100.0
        return humidity

    def read_config_register(self):
        # Read config register
        s = [HDC1000_CONFIGURATION_REGISTER]  # temp
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet
        data = self.HDC1000_fr.read(2)  # read 2 byte config data
        buf = array.array('B', data)
        # print "register=%X %X"% (buf[0], buf[1])
        return buf[0] * 256 + buf[1]

    def turn_heater_on(self):
        # Read config register
        config = self.read_config_register()
        config = config | HDC1000_CONFIG_HEATER_ENABLE
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)  # sending config register bytes
        time.sleep(0.015)  # From the data sheet
        return

    def turn_heater_off(self):
        # Read config register
        config = self.read_config_register()
        config = config & ~HDC1000_CONFIG_HEATER_ENABLE
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)  # sending config register bytes
        time.sleep(0.015)  # From the data sheet
        return

    def set_humidity_resolution(self, resolution):
        # Read config register
        config = self.read_config_register()
        config = (config & ~0x0300) | resolution
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)  # sending config register bytes
        time.sleep(0.015)  # From the data sheet
        return

    def set_temperature_resolution(self, resolution):
        # Read config register
        config = self.read_config_register()
        config = (config & ~0x0400) | resolution
        s = [HDC1000_CONFIGURATION_REGISTER, config >> 8, 0x00]
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)  # sending config register bytes
        time.sleep(0.015)  # From the data sheet
        return

    def read_battery_status(self):
        # Read config register
        config = self.read_config_register()
        config = config & ~ HDC1000_CONFIG_HEATER_ENABLE
        if config == 0:
            return True
        else:
            return False

    def read_manufacturer_id(self):
        s = [HDC1000_MANUFACTURERID_REGISTER]  # temp
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet
        data = self.HDC1000_fr.read(2)  # read 2 byte config data
        buf = array.array('B', data)
        return buf[0] * 256 + buf[1]

    def read_device_id(self):
        s = [HDC1000_DEVICEID_REGISTER]  # temp
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet
        data = self.HDC1000_fr.read(2)  # read 2 byte config data
        buf = array.array('B', data)
        return buf[0] * 256 + buf[1]

    def read_serial_number(self):
        s = [HDC1000_SERIALIDHIGH_REGISTER]  # temp
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet
        data = self.HDC1000_fr.read(2)  # read 2 byte config data
        buf = array.array('B', data)
        serial_number = buf[0] * 256 + buf[1]

        s = [HDC1000_SERIALIDMID_REGISTER]  # temp
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet
        data = self.HDC1000_fr.read(2)  # read 2 byte config data
        buf = array.array('B', data)
        serial_number *= 256 + buf[0] * 256 + buf[1]

        s = [HDC1000_SERIALIDBOTTOM_REGISTER]  # temp
        s2 = bytearray(s)
        self.HDC1000_fw.write(s2)
        time.sleep(0.0625)  # From the data sheet
        data = self.HDC1000_fr.read(2)  # read 2 byte config data
        buf = array.array('B', data)
        serial_number *= 256 + buf[0] * 256 + buf[1]
        return serial_number
