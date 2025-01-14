'''Used to do a diff out of WebNetworkdum files'''

import os, shutil 
from pyats_genie_command_parse import GenieCommandParse
import json
from genie.utils.diff import Diff

INPUTFOLDER="./input_files"
DIFFFOLDER="./diff"
WORKDIRS=[]
DEVICES=[]
WORKFILES=[]
parsed1={}
parsed2={}

def readfiles():
    global devices, WORKDIRS
    try:
        files = os.listdir(INPUTFOLDER)
        if len(files) != 2:
            print("There must exctly 2 input files")
            return
    except Exception as e:
        print(f"Error during fileoperation: \n{e}")
    for file in files:
        dirname=file.replace(" ","") # cleanup filenames
        # delete folder if allready exist 
        if os.path.exists(f"{dirname}"):
            shutil.rmtree(f"{dirname}", ignore_errors=False, onerror=None)
        #create empty Working_Dir directorys
        path = os.path.join("./",f"{dirname}")
        os.mkdir(path) 
        WORKDIRS.append(path)
        #Unzip content
        try:
            shutil.unpack_archive(f"{INPUTFOLDER}/{file}", path)
        except Exception as E:
            print (f"Something went wrong with unzipping: \n{e}")
            return

def create_devices():
    global WORKDIRS,DEVICES
    devices=[]
    for dir in WORKDIRS:
        files = os.listdir(dir)
        for file in files:           
            if file[-12:]=="_command.txt":
                WORKFILES.append(f"{dir}/{file}")
                device=(file[:-12])
                devices.append(device)
    for device in devices:
        if devices.count(device)==2:
            if device in DEVICES:
                continue
            DEVICES.append(device)

def parse(nos,command,raw_text): #parses with CiscoPyatsGenie the rawtext and returns dict with parsed data
    parse_obj= GenieCommandParse(nos=nos)
    data = parse_obj.parse_string(show_command=command,show_output_data=raw_text)
    return(data)

def read_dates(device):
    pass

def netmiko_to_genie(nos):
    if nos=="cisco_ios":
        nos="iosxe"
    elif nos=="cisco_asa":
        nos="asa"
    elif nos=="cisco_nxos":
        nos="nxos"
    return (nos)


def getnos(device):
    try:
        with open (f"{WORKDIRS[0]}/device_file.csv") as file:
            dev_file1=file.read()
        with open (f"{WORKDIRS[1]}/device_file.csv") as file:
            dev_file2=file.read()
        for line in dev_file1.split('\n'):
            if line.split(',')[0]==device:
                nos1=line.split(',')[1]
                continue
        for line in dev_file2.split('\n'):
            if line.split(',')[0]==device:
                nos2=line.split(',')[1]
                continue
    except Exception as e:
        print(f"Error finding NOS: using ios\n{e}")
        nos1="cisco_ios"
        nos2="cisco_ios"
    nos1 = netmiko_to_genie(nos1)
    nos2 = netmiko_to_genie(nos2)
    return([nos1,nos2])


def parse_devices():
    for device in DEVICES:
        parsed1[device]={}
        parsed2[device]={}
        print(f"Parsing Device {device} ...")
        ### Open device-files of both Dumps
        with open (f"{WORKDIRS[0]}/{device}_command.txt") as file:
            devicefile1=file.read()
        with open (f"{WORKDIRS[1]}/{device}_command.txt") as file:
            devicefile2=file.read()
        commands1=devicefile1.split('****************************************')
        commands2=devicefile2.split('****************************************')
        clock1=(commands1[1].split('**----------------------------------------**')[1])
        clock2=(commands2[1].split('**----------------------------------------**')[1])
        nos1 = getnos(device)[0]
        nos2 = getnos(device)[1]
        parse_obj1=GenieCommandParse(nos=nos1)
        parse_obj2=GenieCommandParse(nos=nos2)
        # Create Directory Structure
        parsed_clock1=parse_obj1.parse_string(show_command="show clock",show_output_data=clock1)
        parsed_clock2=parse_obj2.parse_string(show_command="show clock",show_output_data=clock2)
        dir1=f"{device}_{parsed_clock1['year']}_{parsed_clock1['day']}_{parsed_clock1['month']}_{parsed_clock1['time']}"
        dir2=f"{device}_{parsed_clock2['year']}_{parsed_clock2['day']}_{parsed_clock2['month']}_{parsed_clock2['time']}"
        dirname=f"{DIFFFOLDER}/{device}"
        # delete folder if allready exist 
        if os.path.exists(f"{dirname}"):
            shutil.rmtree(f"{dirname}", ignore_errors=False, onerror=None)
        #create empty Working_Dir directorys
        path = os.path.join("./",f"{dirname}")
        os.mkdir(path)
        path1 = os.path.join("./",f"{dirname}/{dir1}")
        os.mkdir(path1)
        path2 = os.path.join("./",f"{dirname}/{dir2}")
        os.mkdir(path2)
        for command in commands1:  # Parse first file
            send_command=command.split('**----------------------------------------**')[0]
            send_command=send_command.strip()
            try:
                return_string=command.split('**----------------------------------------**')[1]
            except IndexError:
                continue
            try:
                data=parse_obj1.parse_string(show_command=send_command,show_output_data=return_string)
            except Exception as e:
                print(f"Somthing went wrong on parsing command:{send_command}\n{e}")
            parsed1[device][send_command]=data
        with open (f'{path1}/parsed_data.json', 'w') as file: # write json file
            file.write(json.dumps(parsed1, indent=4))
        print(f"JsonDumpfile1 of for device {device} was written")
        
        for command in commands2: # Parse 2nd file
            send_command=command.split('**----------------------------------------**')[0]
            send_command=send_command.strip()
            try:
                return_string=command.split('**----------------------------------------**')[1]
            except IndexError:
                continue
            try:
                data=parse_obj2.parse_string(show_command=send_command,show_output_data=return_string)
            except Exception as e:
                #print(f"Somthing went wrong on parsing command:{send_command}\n{e}")
                pass
            parsed2[device][send_command]=data
        with open (f'{path2}/parsed_data.json', 'w') as file: # write json file
            file.write(json.dumps(parsed2, indent=4))
        print(f"JsonDumpfile2 of for device {device} was written")
    
    #### Do diff #####
        for key in parsed1[device]:
            data1=parsed1[device][key]
            data2=parsed2[device].get(key)
            dd=Diff(data1, data2)
            dd.findDiff()
            if dd.diffs == []:
                continue
            with open(f"{DIFFFOLDER}/{device}/diff.txt", "a") as file:
                file.write(f"{key} : \n-------------------\n{dd}\n------------------------------------------------------------------------\n")
        print(f"Diff for device {device} was written")

if __name__ == "__main__":
    ### Used to run as single App and do a diff for Files in Input Folder
    readfiles()
    create_devices()
    parse_devices()

    

