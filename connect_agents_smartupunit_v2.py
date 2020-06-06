from MET4FOFDataReceiver import DataReceiver, genericPlotter
import time
import numpy as np
from agentMET4FOF.agentMET4FOF.agents import AgentMET4FOF, AgentNetwork, MonitorAgent
from agentMET4FOF.agentMET4FOF.streams import SineGenerator
import matplotlib.pyplot as plt
import copy
import matplotlib
matplotlib.use('Agg')

#updated some functions in generic plotter
def empty_buffer(self):
    self.Buffer = [None] * self.BufferLength
    self.Datasetpushed = 0

def update_plot(self):
    # flush the axis
    for ax in self.ax:
        ax.clear()
    # set titles and Y labels
    for i in range(len(self.titles)):
        self.ax[i].set_title(self.titles[i])
        self.ax[i].set_ylabel(self.__getShortunitStr(self.unitstr[i]))
    # actual draw
    i = 0
    for unit in self.units:
        for channel in self.units[unit]:
            self.ax[i].plot(self.x, self.Y[channel - 1])
        i = i + 1

def update_Y(self, message):
    # Pushing data in to the numpy array for convinience
    i = self.Datasetpushed
    self.Buffer[i] = message
    self.Y[0, i] = self.Buffer[i].Data_01
    self.Y[1, i] = self.Buffer[i].Data_02
    self.Y[2, i] = self.Buffer[i].Data_03
    self.Y[3, i] = self.Buffer[i].Data_04
    self.Y[4, i] = self.Buffer[i].Data_05
    self.Y[5, i] = self.Buffer[i].Data_06
    self.Y[6, i] = self.Buffer[i].Data_07
    self.Y[7, i] = self.Buffer[i].Data_08
    self.Y[8, i] = self.Buffer[i].Data_09
    self.Y[9, i] = self.Buffer[i].Data_10
    self.Y[10, i] = self.Buffer[i].Data_11
    self.Y[11, i] = self.Buffer[i].Data_12
    self.Y[12, i] = self.Buffer[i].Data_13
    self.Y[13, i] = self.Buffer[i].Data_14
    self.Y[14, i] = self.Buffer[i].Data_15
    self.Y[15, i] = self.Buffer[i].Data_16

def getShortunitStr(self, unitstr): #Not sure why it is not detecting this function, perhaps due to underscores in name?
    """
    converts the log DSI compatible unit sting to shorter ones for matplotlib plotting.
    e.g. '\\metre\\second\\tothe{-2}'--> "m/s^2".

    Parameters
    ----------
    unitstr : string
        DSi compatible string.

    Returns
    -------
    result : string
        Short string for matplotlib plotting.

    """
    convDict = {
        "\\degreecelsius": "°C",
        "\\micro\\tesla": "µT",
        "\\radian\\second\\tothe{-1}": "rad/s",
        "\\metre\\second\\tothe{-2}": "m/s^2",
    }
    try:
        result = convDict[unitstr]
    except KeyError:
        result = unitstr
    return result

genericPlotter.empty_buffer = empty_buffer
genericPlotter.update_plot = update_plot
genericPlotter.update_Y = update_Y
genericPlotter.__getShortunitStr =getShortunitStr

class WP1_SensorAgent(AgentMET4FOF):
    def init_parameters(self, buffer_length=100, plot_mode="plotly", ip_address="192.168.1.100"):
        DR = DataReceiver(ip_address, 7654)
        time.sleep(5)
        firstSensorId = list(DR.AllSensors.keys())[0]
        self.log_info(
            "First sensor is"
            + str(DR.AllSensors[firstSensorId])
            + " binding generic plotter"
        )
        self.GP = genericPlotter(buffer_length)
        DR.AllSensors[firstSensorId].SetCallback(self.sensor_callback)
        self.plot_mode = plot_mode

    def plot_random(self):
        fig = plt.figure()
        plt.plot(np.random.sample(100))
        return fig

    def plot_random(self):
        fig, (ax1,ax2) = plt.subplots(2,1)
        ax1.plot(np.random.sample(100))
        ax2.plot(np.random.sample(100))
        return fig

    def sensor_callback(self, message, Description):
        if self.current_state == "Running":
            if self.GP.Datasetpushed == 0:
                self.GP.Description = copy.deepcopy(Description)

            if self.GP.Datasetpushed < self.GP.BufferLength:
                self.GP.update_Y(message)
                self.GP.Datasetpushed = self.GP.Datasetpushed + 1
            else:
                self.GP.fig, self.GP.ax = self.GP.setUpFig()
                self.GP.update_plot()
                self.GP.empty_buffer()
                self.send_plot(fig=self.GP.fig, mode=self.plot_mode)

if __name__ == "__main__":
    #start agent network server
    agentNetwork = AgentNetwork()

    #init agents by adding into the agent network
    gen_agent = agentNetwork.add_agent(agentType= WP1_SensorAgent, log_mode=False)
    # gen_agent.init_parameters(buffer_length=100,ip_address="192.168.1.100")

    monitor_agent = agentNetwork.add_agent(agentType= MonitorAgent, log_mode=False)

    #connect agents
    agentNetwork.bind_agents(gen_agent, monitor_agent)

    # set all agents states to "Running"
    agentNetwork.set_running_state()
