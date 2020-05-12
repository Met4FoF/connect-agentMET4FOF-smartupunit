# Connect AgentME4TFOF and SmartupUnit

- Developed within context of MET4FOF project (https://www.ptb.de/empir2018/met4fof/information-communication/blog/)
- How can we connect the smartup unit developed in WP1 to the agent framework in WP2?
- two repos are included as submodules : agentMET4FOF (https://github.com/bangxiangyong/agentMET4FOF) and datareceiver (https://github.com/Met4FoF/datareceiver)

## connect_agents_smartupunit_v1.py
- Connect sensor agent without generic plotter provided by `datareceiver` submodule
- `WP1_SensorAgent` sends the sensor numerical data to the `MonitorAgent` instance.

## connect_agents_smartupunit_v2.py
- Connect sensor agent with generic plotter, where matplotlib figures are generated within and sent from `WP1_SensorAgent`. The sensor agent does not send the raw sensor data to the monitor agent in this case. 
- I repackaged some functions in generic plotter to be more modular, perhaps a pull request can be made to incorporate into the main repo due to its genericity.
- Strangely, the `__getShortunitStr` could not be detected and had to be reimported, I guess this is due to the double underscores? I resolved it by removing the underscores:
`genericPlotter.__getShortunitStr = getShortunitStr`

## Screenshot
![alt text](https://github.com/bangxiangyong/connect-agentMET4FOF-smartupunit/blob/master/wp1_agents.PNG)
