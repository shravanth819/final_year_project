# ESP8266 wiring

- RS485 transceiver `RO/DI` connects to hardware serial pins `GPIO3/GPIO1`.
- Tie RS485 `DE` and `RE` to the selected direction-control GPIO.
- Connect the DHT11 data line to a digital GPIO with a 10k pull-up.
- Power the NodeMCU and sensors from a regulated 5V supply; use a common ground.
- Wire `GPIO16` to `RST` for the 15-minute deep-sleep wake cycle.
- Provide `AGRI_WIFI_SSID`, `AGRI_WIFI_PASSWORD`, `AGRI_API_URL`, and `AGRI_SENSOR_TOKEN` as private build flags; never place them in this file or source control.
