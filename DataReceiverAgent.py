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
    def init_parameters(self, ip_adress="", port=7654, agent_network_ip="127.0.0.1", agent_network_port=3333):
        self.agentNetwork = AgentNetwork(ip_addr=agent_network_ip, port= agent_network_port, connect=True, dashboard_modules=False)

        self.loop_wait=0.0 #socket.recvfrom() is blocking so no delay needed
        self.flags = {"Networtinited": False}
        self.params = {"IP": ip_adress, "Port": port, "PacketrateUpdateCount": 10000}
        self.socket = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM  # Internet
        )  # UDP

        # Try to open the UDP connection
        try:
            self.socket.bind((ip_adress, port))
        except OSError as err:
            print("OS error: {0}".format(err))
            if err.errno == 99:
                print(
                    "most likely no network card of the system has the ip address"
                    + str(ip_adress)
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
                    message = {"ProtMsg": msg_buf, "Type": "Data"}
                    BytesProcessed += msg_len
                except:
                    pass  # ? no exception for wrong data type !!
                if not (wasValidData or wasValidDescription):
                    print("INVALID PROTODATA")
                    pass  # invalid data leave parsing routine

                if SensorID in self.AllSensors:
                    try:
                        self.AllSensors[SensorID].send_output(message)
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
                    self.AllSensors[SensorID]=self.agentNetwork.add_agent(agentType= SensorAgent, log_mode=False, ID=SensorID)
                    self.agentNetwork.add_coalition("Sensor_Group_1", [self]+list(self.AllSensors.values()))
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
                    message = {"ProtMsg": msg_buf, "Type": "Description"}
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
                    self.AllSensors[SensorID]=self.agentNetwork.add_agent(agentType= SensorAgent, log_mode=False, ID=SensorID)
                    self.agentNetwork.add_coalition("Sensor_Group_1", [self]+list(self.AllSensors.values()))
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

### classes to proces sensor descriptions
class AliasDict(dict):
    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.aliases = {}

    def __getitem__(self, key):
        return dict.__getitem__(self, self.aliases.get(key, key))

    def __setitem__(self, key, value):
        return dict.__setitem__(self, self.aliases.get(key, key), value)

    def add_alias(self, key, alias):
        self.aliases[alias] = key


class ChannelDescription:
    def __init__(self, CHID):
        """


        Parameters
        ----------
        CHID : intger
            ID of the channel startig with 1.

        Returns
        -------
        None.

        """
        self.Description = {
            "CHID": CHID,
            "PHYSICAL_QUANTITY": False,
            "UNIT": False,
            "RESOLUTION": False,
            "MIN_SCALE": False,
            "MAX_SCALE": False,
        }
        self._complete = False

    def __getitem__(self, key):
        # if key='SpecialKey':
        # self.Description['SpecialKey']
        return self.Description[key]

    def __repr__(self):
        """
        Prints the quantity and unit of the channel.
        """
        return (
            "Channel: "
            + str(self.Description["CHID"])
            + " ==>"
            + str(self.Description["PHYSICAL_QUANTITY"])
            + " in "
            + str(self.Description["UNIT"])
        )

    # todo override set methode
    def setDescription(self, key, value):
        """
        Sets an spefic key of an channel description.

        Parameters
        ----------
        key : string
            PHYSICAL_QUANTITY",UNIT,RESOLUTION,MIN_SCALE or MAX_SCALE.
        value : string or intger
            valuie coresponding to the key.
        Returns
        -------
        None.

        """
        self.Description[key] = value
        if (
            self.Description["PHYSICAL_QUANTITY"] != False
            and self.Description["UNIT"] != False
            and self.Description["RESOLUTION"] != False
            and self.Description["MIN_SCALE"] != False
            and self.Description["MAX_SCALE"] != False
        ):
            self._complete = True


class SensorDescription:
    """
    this class is holding the Sensor description.
    It's subscriptable by :
    1. inter number of the channel   eg.g. SensorDescription[1]
    2. Name of The physical quantity SensorDescription["Temperature"]
    3. Name of the data field SensorDescription["Data_01"]
    """

    def __init__(self, ID=0x00000000, SensorName="undefined", fromDict=None):
        """


        Parameters
        ----------
        ID : uint32
            ID of the Sensor.The default is 0x00000000
        SensorName : sting
            Name of the sensor.The default is "undefined".
        fromDict : dict
            If an Description dict is passed the Channel params will be set accordingly.
        Returns
        -------
        None.

        """
        self.ID = ID
        self.SensorName = SensorName
        self._complete = False
        self.Channels = AliasDict([])
        self.ChannelCount = 0
        self._ChannelsComplte = 0
        if type(fromDict) is dict:
            try:
                self.ID = fromDict["ID"]
            except KeyError:
                warnings.warn("ID not in Dict", RuntimeWarning)
            try:
                self.SensorName = fromDict["Name"]
            except KeyError:
                warnings.warn("Name not in Dict", RuntimeWarning)
            for i in range(16):
                try:
                    channelDict = fromDict[i]
                    for key in channelDict.keys():
                        if key == "CHID":
                            pass
                        else:
                            self.setChannelParam(
                                channelDict["CHID"], key, channelDict[key]
                            )
                    print("Channel " + str(i) + " read from dict")
                except KeyError:
                    #ok maybe the channels are coded as string
                    try:
                        channelDict = fromDict[str(i)]
                        for key in channelDict.keys():
                            if key == "CHID":
                                pass
                            else:
                                self.setChannelParam(
                                    channelDict["CHID"], key, channelDict[key]
                                )
                        print("Channel " + str(i) + " read from dict")
                    except KeyError:
                        pass

    def setChannelParam(self, CHID, key, value):
        """
        Set parametes for an specific channel.

        Parameters
        ----------
        CHID : intger
            ID of the channel startig with 1.
        key : string
            PHYSICAL_QUANTITY",UNIT,RESOLUTION,MIN_SCALE or MAX_SCALE.
        value : string or intger
            valuie coresponding to the key.

        Returns
        -------
        None.

        """
        wasComplete = False
        if CHID in self.Channels:
            wasComplete = self.Channels[
                CHID
            ]._complete  # read if channel was completed before
            self.Channels[CHID].setDescription(key, value)
            if key == "PHYSICAL_QUANTITY":
                self.Channels.add_alias(
                    CHID, value
                )  # make channels callable by their Quantity
        else:
            if key == "PHYSICAL_QUANTITY":
                self.Channels.add_alias(
                    CHID, value
                )  # make channels callable by their Quantity
            self.Channels[CHID] = ChannelDescription(CHID)
            self.Channels[CHID].setDescription(key, value)
            self.Channels.add_alias(
                CHID, "Data_" + "{:02d}".format(CHID)
            )  # make channels callable by ther Data_xx name
            self.ChannelCount = self.ChannelCount + 1
        if wasComplete == False and self.Channels[CHID]._complete:
            self._ChannelsComplte = self._ChannelsComplte + 1
            if self._ChannelsComplte == self.ChannelCount:
                self._complete = True
                print("Description completed")

    def __getitem__(self, key):
        """
        Reutrns the description for an channel callable by Channel ID eg 1, Channel name eg. Data_01 or Physical PHYSICAL_QUANTITY eg. Acceleration_x.

        Parameters
        ----------
        key : sting or int
            Channel ID eg 1, Channel name eg. "Data_01" or Physical PHYSICAL_QUANTITY eg. "X Acceleration".

        Returns
        -------
        ChannelDescription
            The description of the channel.

        """
        # if key='SpecialKey':
        # self.Description['SpecialKey']
        return self.Channels[key]

    def __repr__(self):
        return "Descripton of" + self.SensorName + hex(self.ID)

    def asDict(self):
        """
        ChannelDescription as dict.

        Returns
        -------
        ReturnDict : dict
            ChannelDescription as dict.

        """
        ReturnDict = {"Name": self.SensorName, "ID": self.ID}
        for key in self.Channels:
            print(self.Channels[key].Description)
            ReturnDict.update(
                {self.Channels[key]["CHID"]: self.Channels[key].Description}
            )
        return ReturnDict

    def getUnits(self):
        units = {}
        for Channel in self.Channels:
            if self.Channels[Channel]["UNIT"] in units:
                units[self.Channels[Channel]["UNIT"]].append(Channel)
            else:
                units[self.Channels[Channel]["UNIT"]] = [Channel]
        return units


class SensorAgent(AgentMET4FOF):
    """Class for Processing the Data from Datareceiver class. All instances of this class will be swaned in Datareceiver.AllSensors

    .. image:: ../doc/Sensor_loop.png

    """

    StrFieldNames = [
        "str_Data_01",
        "str_Data_02",
        "str_Data_03",
        "str_Data_04",
        "str_Data_05",
        "str_Data_06",
        "str_Data_07",
        "str_Data_08",
        "str_Data_09",
        "str_Data_10",
        "str_Data_11",
        "str_Data_12",
        "str_Data_13",
        "str_Data_14",
        "str_Data_15",
        "str_Data_16",
    ]
    FFieldNames = [
        "f_Data_01",
        "f_Data_02",
        "f_Data_03",
        "f_Data_04",
        "f_Data_05",
        "f_Data_06",
        "f_Data_07",
        "f_Data_08",
        "f_Data_09",
        "f_Data_10",
        "f_Data_11",
        "f_Data_12",
        "f_Data_13",
        "f_Data_14",
        "f_Data_15",
        "f_Data_16",
    ]
    DescriptionTypNames = {
        0: "PHYSICAL_QUANTITY",
        1: "UNIT",
        2: "UNCERTAINTY_TYPE",
        3: "RESOLUTION",
        4: "MIN_SCALE",
        5: "MAX_SCALE",
    }
    def doNothingCB(self):
        pass

    def init_parameters(self, ID, BufferSize=25e5):
        """
        Constructor for the Sensor class

        Parameters
        ----------
        ID : uint32
            ID of the Sensor.
        BufferSize : integer, optional
            Size of the Data Queue. The default is 25e5.

        Returns
        -------
        None.

        """
        self.Description = SensorDescription(ID, "Name not Set")
        self.buffersize = BufferSize
        self.flags = {
            "DumpToFile": False,
            "DumpToFileProto":False,
            "DumpToFileASCII": False,
            "PrintProcessedCounts": True,
            "callbackSet": False,
        }
        self.params = {"ID": ID, "BufferSize": BufferSize, "DumpFileName": ""}
        self.DescriptionsProcessed = AliasDict(
            {
                "PHYSICAL_QUANTITY": False,
                "UNIT": False,
                "UNCERTAINTY_TYPE": False,
                "RESOLUTION": False,
                "MIN_SCALE": False,
                "MAX_SCALE": False,
            }
        )
        for i in range(6):
            self.DescriptionsProcessed.add_alias(self.DescriptionTypNames[i], i)
        self.ProcessedPacekts = 0
        self.datarate = 0
        self.timeoutOccured=False
        self.timeSinceLastPacket = 0

    def __repr__(self):
        """
        prints the Id and sensor name.

        Returns
        -------
        None.

        """
        return hex(self.Description.ID) + " " + self.Description.SensorName

    def StartDumpingToFileASCII(self, filename=""):
        """
        Activate dumping Messages in a file ASCII encoded ; seperated.

        Parameters
        ----------
        filename : path
            path to the dumpfile.

        Returns
        -------
        None.

        """
        # check if the path is valid
        # if(os.path.exists(os.path.dirname(os.path.abspath('data/dump.csv')))):
        if filename == "":
            now = datetime.now()
            filename = (
                "data/"
                + now.strftime("%Y%m%d%H%M%S")
                + "_"
                + str(self.Description.SensorName).replace(" ", "_")
                + "_"
                + hex(self.Description.ID)
                + ".dump"
            )
        self.DumpfileASCII = open(filename, "a")
        json.dump(self.Description.asDict(), self.DumpfileASCII)
        self.DumpfileASCII.write("\n")
        self.DumpfileASCII.write(
            "id;sample_number;unix_time;unix_time_nsecs;time_uncertainty;Data_01;Data_02;Data_03;Data_04;Data_05;Data_06;Data_07;Data_08;Data_09;Data_10;Data_11;Data_12;Data_13;Data_14;Data_15;Data_16\n"
        )
        self.params["DumpFileNameASCII"] = filename
        self.flags["DumpToFileASCII"] = True

    def StopDumpingToFileASCII(self):
        """
        Stops dumping to file ASCII encoded.

        Returns
        -------
        None.

        """
        self.flags["DumpToFileASCII"] = False
        self.params["DumpFileNameASCII"] = ""
        self.DumpfileASCII.close()

    def StartDumpingToFileProto(self, filename=""):
        """
        Activate dumping Messages in a file ProtBuff encoded \\n seperated.

        Parameters
        ----------
        filename : path
            path to the dumpfile.


        Returns
        -------
        None.

        """
        # check if the path is valid
        # if(os.path.exists(os.path.dirname(os.path.abspath('data/dump.csv')))):
        if filename == "":
            now = datetime.now()
            filename = (
                "data/"
                + now.strftime("%Y%m%d%H%M%S")
                + "_"
                + str(self.Description.SensorName).replace(" ", "_")
                + "_"
                + hex(self.Description.ID)
                + ".protodump"
            )
        self.DumpfileProto = open(filename, "a")
        json.dump(self.Description.asDict(), self.DumpfileProto)
        self.DumpfileProto.write("\n")
        self.DumpfileProto = open(filename, "ab")
        self.params["DumpFileNameProto"] = filename
        self.flags["DumpToFileProto"] = True

    def StopDumpingToFileProto(self):
        """
        Stops dumping to file Protobuff encoded.

        Returns
        -------
        None.

        """
        self.flags["DumpToFileProto"] = False
        self.params["DumpFileNameProto"] = ""
        self.DumpfileProto.close()

    def on_received_message(self, message):
        self.timeoutOccured = False
        self.ProcessedPacekts = self.ProcessedPacekts + 1
        if self.flags["PrintProcessedCounts"]:
            if self.ProcessedPacekts % 10000 == 0:
                print(
                    "processed 10000 packets in receiver for Sensor ID:"
                    + hex(self.params["ID"])
                    + " Packets in Que "
                    + str(self.buffer.qsize())
                    + " -->"
                    + str((self.buffer.qsize() / self.buffersize) * 100)
                    + "%"
                )
        if message["Type"] == "Description":
            ProtoDescription = messages_pb2.DescriptionMessage()
            Description = ProtoDescription.ParseFromString(message["ProtMsg"])
            try:
                if (
                    not any(self.DescriptionsProcessed.values())
                    and Description.IsInitialized()
                ):
                    # run only if no description packed has been procesed ever
                    # self.Description.SensorName=message.Sensor_name
                    print(
                        "Found new description "
                        + Description.Sensor_name
                        + " sensor with ID:"
                        + str(self.params["ID"])
                    )
                    # print(str(Description.Description_Type))
                if (
                    self.DescriptionsProcessed[Description.Description_Type]
                    == False
                ):

                    if self.Description.SensorName == "Name not Set":
                        self.Description.SensorName = Description.Sensor_name
                    # we havent processed thiss message before now do that
                    if Description.Description_Type in [
                        0,
                        1,
                        2,
                    ]:  # ["PHYSICAL_QUANTITY","UNIT","UNCERTAINTY_TYPE"]
                        # print(Description)
                        # string Processing

                        FieldNumber = 1
                        for StrField in self.StrFieldNames:
                            if Description.HasField(StrField):
                                self.Description.setChannelParam(
                                    FieldNumber,
                                    self.DescriptionTypNames[
                                        Description.Description_Type
                                    ],
                                    Description.__getattribute__(StrField),
                                )
                                # print(str(FieldNumber)+' '+Description.__getattribute__(StrField))
                            FieldNumber = FieldNumber + 1

                        self.DescriptionsProcessed[
                            Description.Description_Type
                        ] = True
                        # print(self.DescriptionsProcessed)
                    if Description.Description_Type in [
                        3,
                        4,
                        5,
                    ]:  # ["RESOLUTION","MIN_SCALE","MAX_SCALE"]
                        self.DescriptionsProcessed[
                            Description.Description_Type
                        ] = True
                        FieldNumber = 1
                        for FloatField in self.FFieldNames:
                            if Description.HasField(FloatField):
                                self.Description.setChannelParam(
                                    FieldNumber,
                                    self.DescriptionTypNames[
                                        Description.Description_Type
                                    ],
                                    Description.__getattribute__(FloatField),
                                )
                                # print(str(FieldNumber)+' '+str(Description.__getattribute__(FloatField)))
                            FieldNumber = FieldNumber + 1
                        # print(self.DescriptionsProcessed)
                        # string Processing
            except Exception:
                print(
                    " Sensor id:"
                    + hex(self.params["ID"])
                    + "Exception in user Description parsing:"
                )
                print("-" * 60)
                traceback.print_exc(file=sys.stdout)
                print("-" * 60)
        if message["Type"] == "Data":
            ProtoData = messages_pb2.DataMessage()
            Data = ProtoData.ParseFromString(message["ProtMsg"])
        if self.flags["callbackSet"]:
            if message["Type"] == "Data":
                try:
                    self.callback(Data, self.Description)
                except Exception:
                    print(
                        " Sensor id:"
                        + hex(self.params["ID"])
                        + "Exception in user callback:"
                    )
                    print("-" * 60)
                    traceback.print_exc(file=sys.stdout)
                    print("-" * 60)
                    pass

        if self.flags["DumpToFileProto"]:
            if message["Type"] == "Data":
                try:
                    self.__dumpMsgToFileProto(Data)
                except Exception:
                    print(
                        " Sensor id:"
                        + hex(self.params["ID"])
                        + "Exception in user datadump:"
                    )
                    print("-" * 60)
                    traceback.print_exc(file=sys.stdout)
                    print("-" * 60)
                    pass
        if self.flags["DumpToFileASCII"]:
            if message["Type"] == "Data":
                try:
                    self.__dumpMsgToFileASCII(Data)
                except Exception:
                    print(
                        " Sensor id:"
                        + hex(self.params["ID"])
                        + "Exception in user datadump:"
                    )
                    print("-" * 60)
                    traceback.print_exc(file=sys.stdout)
                    print("-" * 60)
                    pass

    def SetCallback(self, callback):
        """
        Sets an callback function signature musste be: callback(message["ProtMsg"], self.Description)

        Parameters
        ----------
        callback : function
            callback function signature musste be: callback(message["ProtMsg"], self.Description).

        Returns
        -------
        None.

        """
        self.flags["callbackSet"] = True
        self.callback = callback

    def UnSetCallback(self,):
        """
        deactivates the callback.

        Returns
        -------
        None.

        """
        self.flags["callbackSet"] = False
        self.callback = self.doNothingCB


    def __dumpMsgToFileASCII(self, message):
        """
        private function to dump MSG as ASCII line \n for new line.

        Parameters
        ----------
        message : protobuff message
            Data to be dumped.

        Returns
        -------
        None.

        """
        self.DumpfileASCII.write(
            str(message.id)
            + ";"
            + str(message.sample_number)
            + ";"
            + str(message.unix_time)
            + ";"
            + str(message.unix_time_nsecs)
            + ";"
            + str(message.time_uncertainty)
            + ";"
            + str(message.Data_01)
            + ";"
            + str(message.Data_02)
            + ";"
            + str(message.Data_03)
            + ";"
            + str(message.Data_04)
            + ";"
            + str(message.Data_05)
            + ";"
            + str(message.Data_06)
            + ";"
            + str(message.Data_07)
            + ";"
            + str(message.Data_08)
            + ";"
            + str(message.Data_09)
            + ";"
            + str(message.Data_10)
            + ";"
            + str(message.Data_11)
            + ";"
            + str(message.Data_12)
            + ";"
            + str(message.Data_13)
            + ";"
            + str(message.Data_14)
            + ";"
            + str(message.Data_15)
            + ";"
            + str(message.Data_16)
            + "\n"
        )

    def __dumpMsgToFileProto(self, message):
        """
        private function to dump MSG as binaryblob \n for new data packet.

        Parameters
        ----------
        message : protobuff message
            Data to be dumped.

        Returns
        -------
        None.

        """
        size = message.ByteSize()
        self.DumpfileProto.write(_VarintBytes(size))
        self.DumpfileProto.write(message.SerializeToString())

if __name__ == "__main__":
    #start agent network server
    agentNetwork = AgentNetwork()

    #init agents by adding into the agent network
    gen_agent = agentNetwork.add_agent(agentType=Met4FOFSSUDataReceiverAgent, log_mode=False)

    monitor_agent = agentNetwork.add_agent(agentType= MonitorAgent, log_mode=False)

    #connect agents
    agentNetwork.bind_agents(gen_agent, monitor_agent)

    # set all agents states to "Running"
    agentNetwork.set_running_state()
