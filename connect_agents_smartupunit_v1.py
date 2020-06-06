from datareceiver.MET4FOFDataReceiver import DataReceiver
import time
import numpy as np
from agentMET4FOF.agentMET4FOF.agents import AgentMET4FOF, AgentNetwork, MonitorAgent
from agentMET4FOF.agentMET4FOF.streams import SineGenerator


def unpack_sensor_data(message):
    data_np = np.zeros(16)
    data_np[0] = message.Data_01
    data_np[1] = message.Data_02
    data_np[2] = message.Data_03
    data_np[3] = message.Data_04
    data_np[4] = message.Data_05
    data_np[5] = message.Data_06
    data_np[6] = message.Data_07
    data_np[7] = message.Data_08
    data_np[8] = message.Data_09
    data_np[9] = message.Data_10
    data_np[10] = message.Data_11
    data_np[11] = message.Data_12
    data_np[12] = message.Data_13
    data_np[13] = message.Data_14
    data_np[14] = message.Data_15
    data_np[15] = message.Data_16
    return data_np

class WP1_SensorAgent(AgentMET4FOF):
    def init_parameters(self):
        DR = DataReceiver("192.168.0.200", 7654)
        time.sleep(5) #wait for sensor Description to be sent
        firstSensorId = list(DR.AllSensors.keys())[0]
        self.log_info(
            "First sensor is"
            + str(DR.AllSensors[firstSensorId])
            + " binding generic plotter"
        )
        DR.AllSensors[firstSensorId].SetCallback(self.sensor_callback)

    def sensor_callback(self, message, description):
        if self.current_state == "Running":
            current_sensor_data = unpack_sensor_data(message)
            current_sensor_data = {"Data_"+str(i):current_sensor_data[i] for i in range(len(current_sensor_data))}
            self.send_output(current_sensor_data)


def readData(message, Description):
    time.sleep(5)
    print("MSG:"+str(message))
    print(type(message))
    print("DATA1:"+str(message.Data_01))
    current_sensor_data = unpack_sensor_data(message)
    print(current_sensor_data)
    print("DESCRIPT:"+str(Description))


if __name__ == "__main__":
    #start agent network server
    agentNetwork = AgentNetwork()

    #init agents by adding into the agent network
    gen_agent = agentNetwork.add_agent(agentType= WP1_SensorAgent, log_mode=False)
    monitor_agent = agentNetwork.add_agent(agentType= MonitorAgent, log_mode=False)

    #connect agents
    agentNetwork.bind_agents(gen_agent, monitor_agent)

    # set all agents states to "Running"
    agentNetwork.set_running_state()

