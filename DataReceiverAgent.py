import time
import numpy as np
import sys
import traceback
import os
import socket

import warnings
from datetime import datetime
import time
import copy
import json

# for live plotting
import matplotlib.pyplot as plt
import matplotlib.animation
import numpy as np

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)
# proptobuff message encoding
import messages_pb2
import google.protobuf as pb
from google.protobuf.internal.encoder import _VarintBytes
from google.protobuf.internal.decoder import _DecodeVarint32
from agentMET4FOF.agentMET4FOF.agents import AgentMET4FOF, AgentNetwork, MonitorAgent

class Met4FOFSSUDataReceiverAgent(AgentMET4FOF):
    def init_parameters(self, ip_adress="", port=7654):
        self.loop_wait=0.0#socket.recvfrom is blocking so no delay needed
        self.flags = {"Networtinited": False}
        self.params = {"IP": id_adress, "Port": port, "PacketrateUpdateCount": 10000}
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM  # Internet
        )  # UDP

        # Try to open the UDP connection
        try:
            self.socket.bind((id_adress, port))
        except OSError as err:
            print("OS error: {0}".format(err))
            if err.errno == 99:
                print(
                    "most likely no network card of the system has the ip address"
                    + str(id_adress)
                    + " check this with >>> ifconfig on linux or with >>> ipconfig on Windows"
                )
            if err.errno == 98:
                print(
                    "an other task is blocking the connection on linux use >>> sudo netstat -ltnp | grep -w ':"
                    + str(port)
                    + "' on windows use in PowerShell >>> Get-Process -Id (Get-NetTCPConnection -LocalPort "
                    + str(port)
                    + ").OwningProcess"
                )
            raise (err)
            # we need to raise an exception to prevent __init__ from returning
            # otherwise a broken class instance will be created
        except:
            print("Unexpected error:", sys.exc_info()[0])
            raise ("Unexpected error:", sys.exc_info()[0])
        self.flags["Networtinited"] = True
        self.packestlosforsensor = {}
        self.AllSensors = {}
        self.msgcount = 0
        self.lastTimestamp = 0
        self.Datarate = 0
        print("Data receiver now running wating for Packates")

    def agent_loop(self):
        data, addr = self.socket.recvfrom(1500)  # buffer size is 1024 bytes
        wasValidData = False
        wasValidDescription = False
        ProtoData = messages_pb2.DataMessage()
        ProtoDescription = messages_pb2.DescriptionMessage()
        SensorID = 0
        BytesProcessed = 4  # we need an offset of 4 sice
        if data[:4] == b"DATA":
            while BytesProcessed < len(data):
                msg_len, new_pos = _DecodeVarint32(data, BytesProcessed)
                BytesProcessed = new_pos

                try:
                    msg_buf = data[new_pos: new_pos + msg_len]
                    ProtoData.ParseFromString(msg_buf)
                    wasValidData = True
                    SensorID = ProtoData.id
                    message = {"ProtMsg": copy.deepcopy(ProtoData), "Type": "Data"}
                    BytesProcessed += msg_len
                except:
                    pass  # ? no exception for wrong data type !!
                if not (wasValidData or wasValidDescription):
                    print("INVALID PROTODATA")
                    pass  # invalid data leave parsing routine

                if SensorID in self.AllSensors:
                    try:
                        self.AllSensors[SensorID].buffer.put_nowait(message)
                    except:
                        tmp = self.packestlosforsensor[SensorID] = (
                                self.packestlosforsensor[SensorID] + 1
                        )
                        if tmp == 1:
                            print("!!!! FATAL PERFORMANCE PROBLEMS !!!!")
                            print(
                                "FIRSTTIME packet lost for sensor ID:"
                                + str(SensorID)
                            )
                            print(
                                "DROP MESSAGES ARE ONLY PRINTETD EVERY 1000 DROPS FROM NOW ON !!!!!!!! "
                            )
                        if tmp % 1000 == 0:
                            print("oh no lost an other  thousand packets :(")
                else:
                    self.AllSensors[SensorID] = Sensor(SensorID)
                    print(
                        "FOUND NEW SENSOR WITH ID=hex"
                        + hex(SensorID)
                        + "==>dec:"
                        + str(SensorID)
                    )
                    self.packestlosforsensor[
                        SensorID
                    ] = 0  # initing lost packet counter
                self.msgcount = self.msgcount + 1

                if self.msgcount % self.params["PacketrateUpdateCount"] == 0:
                    print(
                        "received "
                        + str(self.params["PacketrateUpdateCount"])
                        + " packets"
                    )
                    if self.lastTimestamp != 0:
                        timeDIFF = datetime.now() - self.lastTimestamp
                        timeDIFF = timeDIFF.seconds + timeDIFF.microseconds * 1e-6
                        self.Datarate = (
                                self.params["PacketrateUpdateCount"] / timeDIFF
                        )
                        print("Update rate is " + str(self.Datarate) + " Hz")
                        self.lastTimestamp = datetime.now()
                    else:
                        self.lastTimestamp = datetime.now()
        elif data[:4] == b"DSCP":
            while BytesProcessed < len(data):
                msg_len, new_pos = _DecodeVarint32(data, BytesProcessed)
                BytesProcessed = new_pos
                try:
                    msg_buf = data[new_pos: new_pos + msg_len]
                    ProtoDescription.ParseFromString(msg_buf)
                    # print(msg_buf)
                    wasValidData = True
                    SensorID = ProtoDescription.id
                    message = {"ProtMsg": ProtoDescription, "Type": "Description"}
                    BytesProcessed += msg_len
                except:
                    pass  # ? no exception for wrong data type !!
                if not (wasValidData or wasValidDescription):
                    print("INVALID PROTODATA")
                    pass  # invalid data leave parsing routine

                if SensorID in self.AllSensors:
                    try:
                        self.AllSensors[SensorID].buffer.put_nowait(message)
                    except:
                        print("packet lost for sensor ID:" + hex(SensorID))
                else:
                    self.AllSensors[SensorID] = Sensor(SensorID)
                    print(
                        "FOUND NEW SENSOR WITH ID=hex"
                        + hex(SensorID)
                        + " dec==>:"
                        + str(SensorID)
                    )
                self.msgcount = self.msgcount + 1

                if self.msgcount % self.params["PacketrateUpdateCount"] == 0:
                    print(
                        "received "
                        + str(self.params["PacketrateUpdateCount"])
                        + " packets"
                    )
                    if self.lastTimestamp != 0:
                        timeDIFF = datetime.now() - self.lastTimestamp
                        timeDIFF = timeDIFF.seconds + timeDIFF.microseconds * 1e-6
                        self.Datarate = (
                                self.params["PacketrateUpdateCount"] / timeDIFF
                        )
                        print("Update rate is " + str(self.Datarate) + " Hz")
                        self.lastTimestamp = datetime.now()
                    else:
                        self.lastTimestamp = datetime.now()
        else:
            print("unrecognized packed preamble" + str(data[:5]))

    def __repr__(self):
        """
        Prints IP and Port as well as list of all sensors (self.AllSensors).

        Returns
        -------
        None.

        """
        return (
            "Datareceiver liestening at ip "
            + str(self.params["IP"])
            + " Port "
            + str(self.params["Port"])
            + "\n Active Snesors are:"
            + str(self.AllSensors)
        )



if __name__ == "__main__":
    #start agent network server
    agentNetwork = AgentNetwork()

    #init agents by adding into the agent network
    gen_agent = agentNetwork.add_agent(agentType= Met4FOFSSUDataReceiverAgent, log_mode=False)
    # gen_agent.init_parameters(buffer_length=100,ip_address="192.168.1.100")

    monitor_agent = agentNetwork.add_agent(agentType= MonitorAgent, log_mode=False)

    #connect agents
    agentNetwork.bind_agents(gen_agent, monitor_agent)

    # set all agents states to "Running"
    agentNetwork.set_running_state()
